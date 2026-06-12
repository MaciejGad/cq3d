from __future__ import annotations

from dataclasses import dataclass

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
from cq3d.errors import ValidationError
from cq3d.expressions import evaluate_expression


@dataclass(slots=True)
class ValidationResult:
    variables: dict[str, float]


def validate_document(document: ModelDocument) -> ValidationResult:
    if document.unit is None:
        raise ValidationError("unit declaration is required")
    if document.unit != "mm":
        raise ValidationError("only 'mm' units are supported")

    variables: dict[str, float] = {}
    known_objects: set[str] = set()

    for command in document.commands:
        if isinstance(command, VariableAssignment):
            if command.name in variables:
                raise ValidationError(f"variable {command.name!r} cannot be reassigned", command.line)
            variables[command.name] = evaluate_expression(
                command.expression.text,
                variables,
                line=command.expression.line,
            )
            continue

        if isinstance(command, BoxCommand):
            _ensure_unique_object(command.id, known_objects, command.line)
            _validate_triplet(command.size, variables, command.line, positive=True)
            if command.at is not None:
                _validate_triplet(command.at, variables, command.line)
            continue

        if isinstance(command, RoundedBoxCommand):
            _ensure_unique_object(command.id, known_objects, command.line)
            size_values = _validate_triplet(command.size, variables, command.line, positive=True)
            radius_value = _validate_positive(command.radius, variables)
            if radius_value > min(size_values) / 2:
                raise ValidationError("radius must not be larger than half of the smallest dimension", command.line)
            if command.at is not None:
                _validate_triplet(command.at, variables, command.line)
            continue

        if isinstance(command, CylinderCommand):
            _ensure_unique_object(command.id, known_objects, command.line)
            if (command.radius is None) == (command.diameter is None):
                raise ValidationError(
                    "cylinder requires exactly one of radius or diameter",
                    command.line,
                )
            if command.radius is not None:
                _validate_positive(command.radius, variables)
            if command.diameter is not None:
                _validate_positive(command.diameter, variables)
            _validate_positive(command.height, variables)
            if command.at is not None:
                _validate_triplet(command.at, variables, command.line)
            continue

        if isinstance(command, ConeCommand):
            _ensure_unique_object(command.id, known_objects, command.line)
            uses_radius = command.radius1 is not None or command.radius2 is not None
            uses_diameter = command.diameter1 is not None or command.diameter2 is not None
            if uses_radius and uses_diameter:
                raise ValidationError("do not allow mixing radius and diameter in the same cone", command.line)
            if not uses_radius and not uses_diameter:
                raise ValidationError("cone requires either radius1/radius2 or diameter1/diameter2", command.line)
            if uses_radius:
                if command.radius1 is None or command.radius2 is None:
                    raise ValidationError("cone requires both radius1 and radius2", command.line)
                _validate_positive(command.radius1, variables)
                _validate_positive(command.radius2, variables)
            if uses_diameter:
                if command.diameter1 is None or command.diameter2 is None:
                    raise ValidationError("cone requires both diameter1 and diameter2", command.line)
                _validate_positive(command.diameter1, variables)
                _validate_positive(command.diameter2, variables)
            _validate_positive(command.height, variables)
            if command.at is not None:
                _validate_triplet(command.at, variables, command.line)
            continue

        if isinstance(command, SlotCommand):
            _ensure_unique_object(command.id, known_objects, command.line)
            _validate_triplet(command.size, variables, command.line, positive=True)
            if command.clearance is not None:
                clearance = evaluate_expression(command.clearance.text, variables, line=command.clearance.line)
                if clearance < 0:
                    raise ValidationError("clearance must be greater than or equal to zero", command.clearance.line)
            if command.at is not None:
                _validate_triplet(command.at, variables, command.line)
            continue

        if isinstance(command, CombineCommand):
            _ensure_unique_object(command.id, known_objects, command.line)
            _validate_combine(command, known_objects)
            continue

        if isinstance(command, MoveCommand):
            _require_object(command.id, known_objects, command.line)
            _validate_triplet(command.by, variables, command.line)
            continue

        if isinstance(command, RotateCommand):
            _require_object(command.id, known_objects, command.line)
            evaluate_expression(command.angle.text, variables, line=command.angle.line)
            _validate_triplet(command.origin, variables, command.line)
            continue

        if isinstance(command, CopyCommand):
            _ensure_unique_object(command.id, known_objects, command.line)
            _require_object(command.source_id, known_objects, command.line)
            if not command.operations:
                raise ValidationError("copy block requires at least one operation", command.line)
            for operation in command.operations:
                if isinstance(operation, CopyByOperation):
                    _validate_triplet(operation.by, variables, operation.line)
                elif isinstance(operation, CopyRotateOperation):
                    evaluate_expression(operation.angle.text, variables, line=operation.angle.line)
                    _validate_triplet(operation.origin, variables, operation.line)
            continue

        if isinstance(command, FilletCommand):
            _require_object(command.id, known_objects, command.line)
            _validate_positive(command.radius, variables)
            continue

        if isinstance(command, ChamferCommand):
            _require_object(command.id, known_objects, command.line)
            _validate_positive(command.distance, variables)
            continue

        if isinstance(command, RoundedBarCommand):
            _ensure_unique_object(command.id, known_objects, command.line)
            length = _validate_positive(command.length, variables)
            width = _validate_positive(command.width, variables)
            height = _validate_positive(command.height, variables)
            radius = _validate_positive(command.radius, variables)
            if radius > min(width, height) / 2:
                raise ValidationError("radius must not be larger than half of the width or height", command.line)
            if command.at is not None:
                _validate_triplet(command.at, variables, command.line)
            continue

    for export in document.exports:
        if export.format not in {"stl", "step"}:
            raise ValidationError(f"unsupported export format {export.format!r}", export.line)
        if export.object_ids is not None:
            for object_id in export.object_ids:
                if object_id not in known_objects:
                    raise ValidationError(f"unknown object {object_id!r}", export.line)

    return ValidationResult(variables=variables)


def _ensure_unique_object(object_id: str, known_objects: set[str], line: int) -> None:
    if object_id in known_objects:
        raise ValidationError(f"object {object_id!r} is already defined", line)
    known_objects.add(object_id)


def _require_object(object_id: str, known_objects: set[str], line: int) -> None:
    if object_id not in known_objects:
        raise ValidationError(f"unknown object {object_id!r}", line)


def _validate_combine(command: CombineCommand, known_objects: set[str]) -> None:
    for operation in command.operations:
        if operation.kind == "union" and len(operation.object_ids) < 2:
            raise ValidationError("union requires at least two objects", operation.line)
        if operation.kind == "cut" and len(operation.object_ids) < 2:
            raise ValidationError("cut requires a base object and at least one cutter", operation.line)
        for object_id in operation.object_ids:
            if object_id not in known_objects:
                raise ValidationError(f"unknown object {object_id!r}", operation.line)


def _validate_positive(expression: Expression, variables: dict[str, float]) -> float:
    value = evaluate_expression(expression.text, variables, line=expression.line)
    if value <= 0:
        raise ValidationError("value must be greater than zero", expression.line)
    return value


def _validate_triplet(
    expressions: tuple[Expression, Expression, Expression],
    variables: dict[str, float],
    line: int,
    *,
    positive: bool = False,
) -> tuple[float, float, float]:
    values: list[float] = []
    for expression in expressions:
        value = evaluate_expression(expression.text, variables, line=expression.line)
        values.append(value)
        if positive and value <= 0:
            raise ValidationError("dimensions must be greater than zero", line)
    return values[0], values[1], values[2]
