from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


@dataclass(slots=True)
class Expression:
    text: str
    line: int


@dataclass(slots=True)
class VariableAssignment:
    name: str
    expression: Expression
    line: int


@dataclass(slots=True)
class BoxCommand:
    id: str
    size: tuple[Expression, Expression, Expression]
    at: tuple[Expression, Expression, Expression] | None
    center: bool
    line: int


@dataclass(slots=True)
class RoundedBoxCommand:
    id: str
    size: tuple[Expression, Expression, Expression]
    radius: Expression
    at: tuple[Expression, Expression, Expression] | None
    center: bool
    line: int


@dataclass(slots=True)
class CylinderCommand:
    id: str
    radius: Expression | None
    diameter: Expression | None
    height: Expression
    at: tuple[Expression, Expression, Expression] | None
    axis: Literal["x", "y", "z"]
    line: int


@dataclass(slots=True)
class ConeCommand:
    id: str
    radius1: Expression | None
    radius2: Expression | None
    diameter1: Expression | None
    diameter2: Expression | None
    height: Expression
    at: tuple[Expression, Expression, Expression] | None
    axis: Literal["x", "y", "z"]
    line: int


@dataclass(slots=True)
class SlotCommand:
    id: str
    size: tuple[Expression, Expression, Expression]
    clearance: Expression | None
    at: tuple[Expression, Expression, Expression] | None
    center: bool
    line: int


@dataclass(slots=True)
class CombineOperation:
    kind: Literal["union", "cut"]
    object_ids: list[str]
    line: int


@dataclass(slots=True)
class CombineCommand:
    id: str
    operations: list[CombineOperation]
    line: int


@dataclass(slots=True)
class MoveCommand:
    id: str
    by: tuple[Expression, Expression, Expression]
    line: int


@dataclass(slots=True)
class RotateCommand:
    id: str
    axis: Literal["x", "y", "z"]
    angle: Expression
    origin: tuple[Expression, Expression, Expression]
    line: int


@dataclass(slots=True)
class CopyByOperation:
    by: tuple[Expression, Expression, Expression]
    line: int


@dataclass(slots=True)
class CopyRotateOperation:
    axis: Literal["x", "y", "z"]
    angle: Expression
    origin: tuple[Expression, Expression, Expression]
    line: int


CopyOperation = CopyByOperation | CopyRotateOperation


@dataclass(slots=True)
class CopyCommand:
    id: str
    source_id: str
    operations: list[CopyOperation]
    line: int


@dataclass(slots=True)
class FilletCommand:
    id: str
    radius: Expression
    safe: bool
    line: int


@dataclass(slots=True)
class ChamferCommand:
    id: str
    distance: Expression
    safe: bool
    line: int


@dataclass(slots=True)
class RoundedBarCommand:
    id: str
    length: Expression
    width: Expression
    height: Expression
    radius: Expression
    at: tuple[Expression, Expression, Expression] | None
    axis: Literal["x", "y", "z"]
    line: int


@dataclass(slots=True)
class ExportCommand:
    format: Literal["stl", "step"]
    path: str | None
    line: int
    object_ids: list[str] | None = None


Command = (
    VariableAssignment
    | BoxCommand
    | RoundedBoxCommand
    | CylinderCommand
    | ConeCommand
    | SlotCommand
    | CombineCommand
    | MoveCommand
    | RotateCommand
    | CopyCommand
    | FilletCommand
    | ChamferCommand
    | RoundedBarCommand
)


@dataclass(slots=True)
class ModelDocument:
    name: str | None
    unit: str | None
    commands: list[Command] = field(default_factory=list)
    exports: list[ExportCommand] = field(default_factory=list)
    source_path: Path | None = None
