from __future__ import annotations

from dataclasses import dataclass, field

import cadquery as cq

from cq3d.ast_nodes import (
    BoxCommand,
    ChamferCommand,
    CombineCommand,
    ConeCommand,
    CopyByOperation,
    CopyCommand,
    CopyRotateOperation,
    CylinderCommand,
    Expression,
    FilletCommand,
    ModelDocument,
    MoveCommand,
    RoundedBoxCommand,
    RoundedBarCommand,
    RotateCommand,
    SlotCommand,
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
        elif isinstance(command, RoundedBoxCommand):
            context.objects[command.id] = _build_rounded_box(command, context.variables)
            context.last_object_id = command.id
        elif isinstance(command, CylinderCommand):
            context.objects[command.id] = _build_cylinder(command, context.variables)
            context.last_object_id = command.id
        elif isinstance(command, ConeCommand):
            context.objects[command.id] = _build_cone(command, context.variables)
            context.last_object_id = command.id
        elif isinstance(command, SlotCommand):
            context.objects[command.id] = _build_slot(command, context.variables)
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
        elif isinstance(command, CopyCommand):
            context.objects[command.id] = _build_copy(command, context.objects, context.variables)
            context.last_object_id = command.id
        elif isinstance(command, FilletCommand):
            context.objects[command.id] = _apply_fillet(
                command,
                context.objects[command.id],
                context.variables,
            )
            context.last_object_id = command.id
        elif isinstance(command, ChamferCommand):
            context.objects[command.id] = _apply_chamfer(
                command,
                context.objects[command.id],
                context.variables,
            )
            context.last_object_id = command.id
        elif isinstance(command, RoundedBarCommand):
            context.objects[command.id] = _build_rounded_bar(command, context.variables)
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


def _build_rounded_box(command: RoundedBoxCommand, variables: dict[str, float]) -> cq.Workplane:
    size = [_eval(expr.text, variables, command.line) for expr in command.size]
    radius = _eval(command.radius.text, variables, command.radius.line)
    obj = cq.Workplane("XY").box(*size, centered=(command.center, command.center, command.center))
    if command.at is not None:
        at = [_eval(expr.text, variables, expr.line) for expr in command.at]
        obj = obj.translate(tuple(at))
    try:
        return obj.edges().fillet(radius)
    except Exception as exc:  # pragma: no cover
        raise BackendError(
            f"rounded_box failed for object {command.id!r}; try a smaller radius",
            command.line,
        ) from exc


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


def _build_cone(command: ConeCommand, variables: dict[str, float]) -> cq.Workplane:
    if command.radius1 is not None:
        radius1 = _eval(command.radius1.text, variables, command.radius1.line)
        radius2 = _eval(command.radius2.text, variables, command.radius2.line)
    else:
        radius1 = _eval(command.diameter1.text, variables, command.diameter1.line) / 2
        radius2 = _eval(command.diameter2.text, variables, command.diameter2.line) / 2
    height = _eval(command.height.text, variables, command.height.line)
    direction = {
        "x": (1.0, 0.0, 0.0),
        "y": (0.0, 1.0, 0.0),
        "z": (0.0, 0.0, 1.0),
    }[command.axis]
    anchor = (0.0, 0.0, 0.0)
    if command.at is not None:
        anchor = tuple(_eval(expr.text, variables, expr.line) for expr in command.at)
    solid = cq.Solid.makeCone(radius1, radius2, height, pnt=anchor, dir=direction)
    return cq.Workplane("XY").newObject([solid])


def _build_slot(command: SlotCommand, variables: dict[str, float]) -> cq.Workplane:
    size = [_eval(expr.text, variables, command.line) for expr in command.size]
    clearance = _eval(command.clearance.text, variables, command.clearance.line) if command.clearance is not None else 0.0
    enlarged = [dimension + (clearance * 2) for dimension in size]
    obj = cq.Workplane("XY").box(*enlarged, centered=(command.center, command.center, command.center))
    if command.at is not None:
        at = [_eval(expr.text, variables, expr.line) for expr in command.at]
        obj = obj.translate(tuple(at))
    return obj


def _build_combine(command: CombineCommand, objects: dict[str, cq.Workplane]) -> cq.Workplane:
    result = None

    def resolve_object(object_id: str) -> cq.Workplane:
        if object_id == command.id and result is not None:
            return result
        return objects[object_id]

    for operation in command.operations:
        if operation.kind == "union":
            operation_result = resolve_object(operation.object_ids[0])
            for object_id in operation.object_ids[1:]:
                operation_result = operation_result.union(resolve_object(object_id))
        else:
            operation_result = resolve_object(operation.object_ids[0])
            for object_id in operation.object_ids[1:]:
                operation_result = operation_result.cut(resolve_object(object_id))

        if result is None:
            result = operation_result
        elif command.id in operation.object_ids:
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


def _build_copy(command: CopyCommand, objects: dict[str, cq.Workplane], variables: dict[str, float]) -> cq.Workplane:
    base = cq.Workplane("XY").newObject(objects[command.source_id].vals())
    for operation in command.operations:
        if isinstance(operation, CopyByOperation):
            by = [_eval(expr.text, variables, expr.line) for expr in operation.by]
            base = base.translate(tuple(by))
        elif isinstance(operation, CopyRotateOperation):
            origin = tuple(_eval(expr.text, variables, expr.line) for expr in operation.origin)
            axis_map = {
                "x": (1.0, 0.0, 0.0),
                "y": (0.0, 1.0, 0.0),
                "z": (0.0, 0.0, 1.0),
            }
            axis_vector = axis_map[operation.axis]
            end = tuple(origin[i] + axis_vector[i] for i in range(3))
            angle = _eval(operation.angle.text, variables, operation.angle.line)
            base = base.rotate(origin, end, angle)
    return base


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


def _apply_chamfer(command: ChamferCommand, obj: cq.Workplane, variables: dict[str, float]) -> cq.Workplane:
    distance = _eval(command.distance.text, variables, command.distance.line)
    try:
        return obj.edges().chamfer(distance)
    except Exception as exc:  # pragma: no cover
        if command.safe:
            return obj
        raise BackendError(
            f"chamfer failed on object {command.id!r}; try a smaller distance",
            command.line,
        ) from exc


def _build_rounded_bar(command: RoundedBarCommand, variables: dict[str, float]) -> cq.Workplane:
    length = _eval(command.length.text, variables, command.length.line)
    width = _eval(command.width.text, variables, command.width.line)
    height = _eval(command.height.text, variables, command.height.line)
    radius = _eval(command.radius.text, variables, command.radius.line)
    if command.axis == "x":
        size = (
            Expression(str(length), command.line),
            Expression(str(width), command.line),
            Expression(str(height), command.line),
        )
    elif command.axis == "y":
        size = (
            Expression(str(width), command.line),
            Expression(str(length), command.line),
            Expression(str(height), command.line),
        )
    else:
        size = (
            Expression(str(width), command.line),
            Expression(str(height), command.line),
            Expression(str(length), command.line),
        )
    rounded = RoundedBoxCommand(
        id=command.id,
        size=size,
        radius=Expression(str(radius), command.line),
        at=command.at,
        center=False,
        line=command.line,
    )
    return _build_rounded_box(rounded, variables)


def _select_final_object_id(context: BuildContext) -> str | None:
    if "body" in context.objects:
        return "body"
    return context.last_object_id


def _eval(text: str, variables: dict[str, float], line: int) -> float:
    return evaluate_expression(text, variables, line=line)
