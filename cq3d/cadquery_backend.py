from __future__ import annotations

from dataclasses import dataclass, field

import cadquery as cq

from cq3d.ast_nodes import (
    BoxCommand,
    CombineCommand,
    CylinderCommand,
    FilletCommand,
    ModelDocument,
    MoveCommand,
    RotateCommand,
    VariableAssignment,
)
from cq3d.errors import BackendError
from cq3d.expressions import evaluate_expression
from cq3d.validator import validate_document


@dataclass(slots=True)
class BuildContext:
    document: ModelDocument
    variables: dict[str, float]
    objects: dict[str, cq.Workplane] = field(default_factory=dict)
    last_object_id: str | None = None


@dataclass(slots=True)
class BuildResult:
    document: ModelDocument
    variables: dict[str, float]
    objects: dict[str, cq.Workplane]
    final_object_id: str | None
    final_object: cq.Workplane | None


def get_bounding_box(obj: cq.Workplane) -> dict[str, float]:
    bbox = obj.val().BoundingBox()
    return {
        "xmin": bbox.xmin,
        "xmax": bbox.xmax,
        "xlen": bbox.xlen,
        "ymin": bbox.ymin,
        "ymax": bbox.ymax,
        "ylen": bbox.ylen,
        "zmin": bbox.zmin,
        "zmax": bbox.zmax,
        "zlen": bbox.zlen,
    }


def build_document(document: ModelDocument) -> BuildResult:
    validation = validate_document(document)
    context = BuildContext(document=document, variables=dict(validation.variables))

    for command in document.commands:
        if isinstance(command, VariableAssignment):
            continue
        if isinstance(command, BoxCommand):
            context.objects[command.id] = _build_box(command, context.variables)
            context.last_object_id = command.id
        elif isinstance(command, CylinderCommand):
            context.objects[command.id] = _build_cylinder(command, context.variables)
            context.last_object_id = command.id
        elif isinstance(command, CombineCommand):
            context.objects[command.id] = _build_combine(command, context.objects)
            context.last_object_id = command.id
        elif isinstance(command, MoveCommand):
            context.objects[command.id] = _apply_move(command, context.objects[command.id], context.variables)
            context.last_object_id = command.id
        elif isinstance(command, RotateCommand):
            context.objects[command.id] = _apply_rotate(
                command,
                context.objects[command.id],
                context.variables,
            )
            context.last_object_id = command.id
        elif isinstance(command, FilletCommand):
            context.objects[command.id] = _apply_fillet(
                command,
                context.objects[command.id],
                context.variables,
            )
            context.last_object_id = command.id

    final_object_id = _select_final_object_id(context)
    final_object = context.objects.get(final_object_id) if final_object_id else None
    return BuildResult(
        document=document,
        variables=context.variables,
        objects=context.objects,
        final_object_id=final_object_id,
        final_object=final_object,
    )


def _build_box(command: BoxCommand, variables: dict[str, float]) -> cq.Workplane:
    size = [_eval(expr.text, variables, command.line) for expr in command.size]
    obj = cq.Workplane("XY").box(*size, centered=(command.center, command.center, command.center))

    if command.at is not None:
        at = [_eval(expr.text, variables, expr.line) for expr in command.at]
        obj = obj.translate(tuple(at))
    return obj


def _build_cylinder(command: CylinderCommand, variables: dict[str, float]) -> cq.Workplane:
    radius = (
        _eval(command.radius.text, variables, command.radius.line)
        if command.radius is not None
        else _eval(command.diameter.text, variables, command.diameter.line) / 2
    )
    height = _eval(command.height.text, variables, command.height.line)
    obj = cq.Workplane("XY").circle(radius).extrude(height)

    if command.axis == "x":
        obj = obj.rotate((0, 0, 0), (0, 1, 0), 90)
    elif command.axis == "y":
        obj = obj.rotate((0, 0, 0), (1, 0, 0), -90)

    if command.at is not None:
        at = [_eval(expr.text, variables, expr.line) for expr in command.at]
        obj = obj.translate(tuple(at))
    return obj


def _build_combine(command: CombineCommand, objects: dict[str, cq.Workplane]) -> cq.Workplane:
    result = None

    for operation in command.operations:
        if operation.kind == "union":
            operation_result = objects[operation.object_ids[0]]
            for object_id in operation.object_ids[1:]:
                operation_result = operation_result.union(objects[object_id])
        else:
            operation_result = objects[operation.object_ids[0]]
            for object_id in operation.object_ids[1:]:
                operation_result = operation_result.cut(objects[object_id])

        if result is None:
            result = operation_result
        else:
            if operation.kind == "union":
                result = result.union(operation_result)
            else:
                result = result.cut(operation_result)

    if result is None:
        raise BackendError("combine block did not produce a result", command.line)
    return result


def _apply_move(command: MoveCommand, obj: cq.Workplane, variables: dict[str, float]) -> cq.Workplane:
    by = [_eval(expr.text, variables, expr.line) for expr in command.by]
    return obj.translate(tuple(by))


def _apply_rotate(command: RotateCommand, obj: cq.Workplane, variables: dict[str, float]) -> cq.Workplane:
    origin = tuple(_eval(expr.text, variables, expr.line) for expr in command.origin)
    axis_map = {
        "x": (1.0, 0.0, 0.0),
        "y": (0.0, 1.0, 0.0),
        "z": (0.0, 0.0, 1.0),
    }
    axis_vector = axis_map[command.axis]
    end = tuple(origin[i] + axis_vector[i] for i in range(3))
    angle = _eval(command.angle.text, variables, command.angle.line)
    return obj.rotate(origin, end, angle)


def _apply_fillet(command: FilletCommand, obj: cq.Workplane, variables: dict[str, float]) -> cq.Workplane:
    radius = _eval(command.radius.text, variables, command.radius.line)
    try:
        return obj.edges().fillet(radius)
    except Exception as exc:  # pragma: no cover - exact exception depends on CadQuery/OCP
        if command.safe:
            return obj
        raise BackendError(
            f"fillet failed on object {command.id!r}; try a smaller radius",
            command.line,
        ) from exc


def _select_final_object_id(context: BuildContext) -> str | None:
    if "body" in context.objects:
        return "body"
    return context.last_object_id


def _eval(text: str, variables: dict[str, float], line: int) -> float:
    return evaluate_expression(text, variables, line=line)
