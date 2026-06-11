from __future__ import annotations

import shlex
from dataclasses import dataclass
from pathlib import Path

from cq3d.ast_nodes import (
    BoxCommand,
    CombineCommand,
    CombineOperation,
    CylinderCommand,
    ExportCommand,
    Expression,
    FilletCommand,
    ModelDocument,
    MoveCommand,
    RotateCommand,
    VariableAssignment,
)
from cq3d.errors import ParseError
from cq3d.expressions import VALID_NAME_RE, validate_identifier

BLOCK_KEYWORDS = {"box", "cylinder", "combine", "move", "rotate", "fillet"}
RESERVED_WORDS = BLOCK_KEYWORDS | {
    "model",
    "unit",
    "end",
    "export",
    "union",
    "cut",
    "size",
    "at",
    "radius",
    "diameter",
    "height",
    "axis",
    "by",
    "around",
    "angle",
    "origin",
    "safe",
    "center",
}


@dataclass(slots=True)
class SourceLine:
    number: int
    text: str


def parse_document(text: str, source_path: str | Path | None = None) -> ModelDocument:
    lines = _prepare_lines(text)
    doc = ModelDocument(name=None, unit=None, source_path=Path(source_path) if source_path else None)
    index = 0

    while index < len(lines):
        line = lines[index]
        stripped = line.text

        if stripped.startswith("model "):
            if doc.name is not None:
                raise ParseError("model is already declared", line.number)
            name = stripped[6:].strip()
            if not name:
                raise ParseError("model name is required", line.number)
            validate_identifier(name, line=line.number)
            doc.name = name
            index += 1
            continue

        if stripped.startswith("unit "):
            if doc.unit is not None:
                raise ParseError("unit is already declared", line.number)
            unit = stripped[5:].strip()
            if unit != "mm":
                raise ParseError("only 'mm' units are supported", line.number)
            doc.unit = unit
            index += 1
            continue

        if stripped.startswith("export "):
            doc.exports.append(_parse_export(line))
            index += 1
            continue

        if "=" in stripped:
            doc.commands.append(_parse_assignment(line))
            index += 1
            continue

        keyword = stripped.split()[0]
        if keyword not in BLOCK_KEYWORDS:
            raise ParseError(f"unknown command {keyword!r}", line.number)

        command, index = _parse_block(lines, index)
        doc.commands.append(command)

    return doc


def _prepare_lines(text: str) -> list[SourceLine]:
    prepared: list[SourceLine] = []
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        prepared.append(SourceLine(number=line_number, text=stripped))
    return prepared


def _parse_assignment(line: SourceLine) -> VariableAssignment:
    name, expression = line.text.split("=", 1)
    identifier = name.strip()
    expression_text = expression.strip()
    validate_identifier(identifier, line=line.number)
    if identifier in RESERVED_WORDS:
        raise ParseError(f"{identifier!r} is a reserved keyword", line.number)
    if not expression_text:
        raise ParseError("variable assignment is missing an expression", line.number)
    return VariableAssignment(
        name=identifier,
        expression=Expression(expression_text, line.number),
        line=line.number,
    )


def _parse_export(line: SourceLine) -> ExportCommand:
    try:
        parts = shlex.split(line.text)
    except ValueError as exc:
        raise ParseError("invalid export command", line.number) from exc

    if len(parts) not in {2, 3}:
        raise ParseError("export syntax is 'export <stl|step> [path]'", line.number)
    _, export_format, *path_parts = parts
    if export_format not in {"stl", "step"}:
        raise ParseError(f"unsupported export format {export_format!r}", line.number)
    return ExportCommand(export_format, path_parts[0] if path_parts else None, line.number)


def _parse_block(lines: list[SourceLine], start_index: int):
    header = lines[start_index]
    header_parts = header.text.split()
    if len(header_parts) != 2:
        raise ParseError("block syntax is '<command> <id>'", header.number)
    keyword, object_id = header_parts
    validate_identifier(object_id, line=header.number)

    body: list[SourceLine] = []
    index = start_index + 1
    while index < len(lines):
        line = lines[index]
        if line.text == "end":
            break
        if line.text.split()[0] in BLOCK_KEYWORDS:
            raise ParseError("nested blocks are not supported", line.number)
        body.append(line)
        index += 1
    else:
        raise ParseError(f"missing 'end' for {keyword!r} block", header.number)

    if keyword == "box":
        command = _parse_box(header, object_id, body)
    elif keyword == "cylinder":
        command = _parse_cylinder(header, object_id, body)
    elif keyword == "combine":
        command = _parse_combine(header, object_id, body)
    elif keyword == "move":
        command = _parse_move(header, object_id, body)
    elif keyword == "rotate":
        command = _parse_rotate(header, object_id, body)
    else:
        command = _parse_fillet(header, object_id, body)

    return command, index + 1


def _parse_box(header: SourceLine, object_id: str, body: list[SourceLine]) -> BoxCommand:
    size = None
    at = None
    center = False

    for line in body:
        key, _, rest = line.text.partition(" ")
        if key == "size":
            size = _parse_expression_tuple(rest, 3, line.number, key)
        elif key == "at":
            at = _parse_expression_tuple(rest, 3, line.number, key)
        elif key == "center":
            value = rest.strip()
            if value not in {"true", "false"}:
                raise ParseError("center must be true or false", line.number)
            center = value == "true"
        else:
            raise ParseError(f"unknown field {key!r} in box block", line.number)

    if size is None:
        raise ParseError("box block requires a size field", header.number)

    return BoxCommand(id=object_id, size=size, at=at, center=center, line=header.number)


def _parse_cylinder(header: SourceLine, object_id: str, body: list[SourceLine]) -> CylinderCommand:
    radius = None
    diameter = None
    height = None
    at = None
    axis = "z"

    for line in body:
        key, _, rest = line.text.partition(" ")
        if key == "radius":
            radius = _parse_expression_tuple(rest, 1, line.number, key)[0]
        elif key == "diameter":
            diameter = _parse_expression_tuple(rest, 1, line.number, key)[0]
        elif key == "height":
            height = _parse_expression_tuple(rest, 1, line.number, key)[0]
        elif key == "at":
            at = _parse_expression_tuple(rest, 3, line.number, key)
        elif key == "axis":
            axis = rest.strip()
            if axis not in {"x", "y", "z"}:
                raise ParseError("axis must be x, y, or z", line.number)
        else:
            raise ParseError(f"unknown field {key!r} in cylinder block", line.number)

    if height is None:
        raise ParseError("cylinder block requires a height field", header.number)

    return CylinderCommand(
        id=object_id,
        radius=radius,
        diameter=diameter,
        height=height,
        at=at,
        axis=axis,
        line=header.number,
    )


def _parse_combine(header: SourceLine, object_id: str, body: list[SourceLine]) -> CombineCommand:
    operations: list[CombineOperation] = []
    for line in body:
        parts = line.text.split()
        if not parts:
            continue
        op = parts[0]
        if op not in {"union", "cut"}:
            raise ParseError(f"unknown combine operation {op!r}", line.number)
        refs = parts[1:]
        if not refs:
            raise ParseError(f"{op} requires object references", line.number)
        for ref in refs:
            if not VALID_NAME_RE.match(ref):
                raise ParseError(f"invalid object reference {ref!r}", line.number)
        operations.append(CombineOperation(kind=op, object_ids=refs, line=line.number))

    if not operations:
        raise ParseError("combine block requires at least one operation", header.number)
    return CombineCommand(id=object_id, operations=operations, line=header.number)


def _parse_move(header: SourceLine, object_id: str, body: list[SourceLine]) -> MoveCommand:
    if len(body) != 1:
        raise ParseError("move block requires a single 'by' field", header.number)
    line = body[0]
    key, _, rest = line.text.partition(" ")
    if key != "by":
        raise ParseError("move block requires a 'by' field", line.number)
    by = _parse_expression_tuple(rest, 3, line.number, key)
    return MoveCommand(id=object_id, by=by, line=header.number)


def _parse_rotate(header: SourceLine, object_id: str, body: list[SourceLine]) -> RotateCommand:
    axis = None
    angle = None
    origin = (
        Expression("0", header.number),
        Expression("0", header.number),
        Expression("0", header.number),
    )

    for line in body:
        key, _, rest = line.text.partition(" ")
        if key == "around":
            axis = rest.strip()
            if axis not in {"x", "y", "z"}:
                raise ParseError("rotate axis must be x, y, or z", line.number)
        elif key == "angle":
            angle = _parse_expression_tuple(rest, 1, line.number, key)[0]
        elif key == "origin":
            origin = _parse_expression_tuple(rest, 3, line.number, key)
        else:
            raise ParseError(f"unknown field {key!r} in rotate block", line.number)

    if axis is None or angle is None:
        raise ParseError("rotate block requires 'around' and 'angle' fields", header.number)
    return RotateCommand(id=object_id, axis=axis, angle=angle, origin=origin, line=header.number)


def _parse_fillet(header: SourceLine, object_id: str, body: list[SourceLine]) -> FilletCommand:
    radius = None
    safe = True

    for line in body:
        key, _, rest = line.text.partition(" ")
        if key == "radius":
            radius = _parse_expression_tuple(rest, 1, line.number, key)[0]
        elif key == "safe":
            value = rest.strip()
            if value not in {"true", "false"}:
                raise ParseError("safe must be true or false", line.number)
            safe = value == "true"
        elif key == "edges":
            if rest.strip() != "all":
                raise ParseError("only 'edges all' is supported in the MVP", line.number)
        else:
            raise ParseError(f"unknown field {key!r} in fillet block", line.number)

    if radius is None:
        raise ParseError("fillet block requires a radius field", header.number)
    return FilletCommand(id=object_id, radius=radius, safe=safe, line=header.number)


def _parse_expression_tuple(
    text: str,
    count: int,
    line: int,
    field_name: str,
) -> tuple[Expression, ...]:
    expressions = _split_expressions(text.strip(), count, line=line, field_name=field_name)
    return tuple(Expression(value, line) for value in expressions)


def _split_expressions(text: str, count: int, *, line: int, field_name: str) -> list[str]:
    tokens = text.split()
    if len(tokens) < count:
        raise ParseError(f"{field_name} requires {count} values", line)

    cache: dict[tuple[int, int], list[str] | None] = {}

    def search(index: int, remaining: int) -> list[str] | None:
        key = (index, remaining)
        if key in cache:
            return cache[key]
        if remaining == 0:
            return [] if index == len(tokens) else None

        limit = len(tokens) - remaining + 1
        for end in range(index + 1, limit + 1):
            candidate = " ".join(tokens[index:end])
            if not _looks_like_expression(candidate):
                continue
            tail = search(end, remaining - 1)
            if tail is not None:
                cache[key] = [candidate, *tail]
                return cache[key]

        cache[key] = None
        return None

    result = search(0, count)
    if result is None:
        raise ParseError(f"could not parse {count} expressions for {field_name}", line)
    return result


def _looks_like_expression(text: str) -> bool:
    from ast import parse

    try:
        parse(text, mode="eval")
    except SyntaxError:
        return False
    return True
