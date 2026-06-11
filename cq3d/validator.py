from __future__ import annotations

from dataclasses import dataclass

from cq3d.ast_nodes import (
    BoxCommand,
    CombineCommand,
    CylinderCommand,
    Expression,
    FilletCommand,
    ModelDocument,
    MoveCommand,
    RotateCommand,
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

        if isinstance(command, FilletCommand):
            _require_object(command.id, known_objects, command.line)
            _validate_positive(command.radius, variables)
            continue

    for export in document.exports:
        if export.format not in {"stl", "step"}:
            raise ValidationError(f"unsupported export format {export.format!r}", export.line)

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


def _validate_positive(expression: Expression, variables: dict[str, float]) -> None:
    value = evaluate_expression(expression.text, variables, line=expression.line)
    if value <= 0:
        raise ValidationError("value must be greater than zero", expression.line)


def _validate_triplet(
    expressions: tuple[Expression, Expression, Expression],
    variables: dict[str, float],
    line: int,
    *,
    positive: bool = False,
) -> None:
    for expression in expressions:
        value = evaluate_expression(expression.text, variables, line=expression.line)
        if positive and value <= 0:
            raise ValidationError("dimensions must be greater than zero", line)
