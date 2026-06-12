from __future__ import annotations

import shlex
from dataclasses import dataclass
from pathlib import Path

from cq3d.ast_nodes import (
    BoxCommand,
    ChamferCommand,
    CombineCommand,
    CombineOperation,
    ConeCommand,
    CopyByOperation,
    CopyCommand,
    CopyRotateOperation,
    CylinderCommand,
    ExportCommand,
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
from cq3d.errors import ParseError
from cq3d.expressions import VALID_NAME_RE, validate_identifier

BLOCK_KEYWORDS = {"box", "rounded_box", "rounded_bar", "cylinder", "cone", "slot", "combine", "move", "rotate", "copy", "fillet", "chamfer"}
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
    "radius1",
    "radius2",
    "diameter",
    "diameter1",
    "diameter2",
    "height",
    "axis",
    "by",
    "around",
    "angle",
    "origin",
    "safe",
    "center",
    "distance",
    "clearance",
    "from",
    "object",
    "objects",
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
            export_command, index = _parse_export(lines, index)
            doc.exports.append(export_command)
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


def _parse_export(lines: list[SourceLine], start_index: int):
    line = lines[start_index]
    try:
        parts = shlex.split(line.text)
    except ValueError as exc:
        raise ParseError("invalid export command", line.number) from exc

    if len(parts) not in {2, 3}:
        raise ParseError("export syntax is 'export <stl|step> [path]'", line.number)
    _, export_format, *path_parts = parts
    if export_format not in {"stl", "step"}:
        raise ParseError(f"unsupported export format {export_format!r}", line.number)

    if start_index + 1 >= len(lines) or lines[start_index + 1].text.split()[0] not in {"object", "objects"}:
        return ExportCommand(export_format, path_parts[0] if path_parts else None, line.number), start_index + 1

    index = start_index + 1
    object_ids: list[str] | None = None
    while index < len(lines):
        current = lines[index]
        if current.text == "end":
            if object_ids is None:
                raise ParseError("export block requires an object or objects field", line.number)
            return ExportCommand(export_format, path_parts[0] if path_parts else None, line.number, object_ids), index + 1

        key, _, rest = current.text.partition(" ")
        refs = rest.split()
        if key == "object":
            if len(refs) != 1:
                raise ParseError("object requires exactly one object id", current.number)
            object_ids = refs
        elif key == "objects":
            if not refs:
                raise ParseError("objects requires at least one object id", current.number)
            object_ids = refs
        else:
            raise ParseError(f"unknown field {key!r} in export block", current.number)
        index += 1

    raise ParseError("missing 'end' for 'export' block", line.number)


def _parse_block(lines: list[SourceLine], start_index: int):
    header = lines[start_index]
    header_parts = header.text.split()
    keyword = header_parts[0]
    if keyword == "copy":
        if len(header_parts) != 4 or header_parts[2] != "from":
            raise ParseError("copy syntax is 'copy <new_id> from <source_id>'", header.number)
        _, object_id, _, source_id = header_parts
        validate_identifier(object_id, line=header.number)
        validate_identifier(source_id, line=header.number)
    else:
        if len(header_parts) != 2:
            raise ParseError("block syntax is '<command> <id>'", header.number)
        _, object_id = header_parts
        validate_identifier(object_id, line=header.number)

    body: list[SourceLine] = []
    index = start_index + 1
    while index < len(lines):
        line = lines[index]
        if line.text == "end":
            break
        if line.text.split()[0] in BLOCK_KEYWORDS and not line.text.startswith("rotate around "):
            raise ParseError("nested blocks are not supported", line.number)
        body.append(line)
        index += 1
    else:
        raise ParseError(f"missing 'end' for {keyword!r} block", header.number)

    if keyword == "box":
        command = _parse_box(header, object_id, body)
    elif keyword == "rounded_box":
        command = _parse_rounded_box(header, object_id, body)
    elif keyword == "rounded_bar":
        command = _parse_rounded_bar(header, object_id, body)
    elif keyword == "cylinder":
        command = _parse_cylinder(header, object_id, body)
    elif keyword == "cone":
        command = _parse_cone(header, object_id, body)
    elif keyword == "slot":
        command = _parse_slot(header, object_id, body)
    elif keyword == "combine":
        command = _parse_combine(header, object_id, body)
    elif keyword == "move":
        command = _parse_move(header, object_id, body)
    elif keyword == "rotate":
        command = _parse_rotate(header, object_id, body)
    elif keyword == "copy":
        command = _parse_copy(header, object_id, source_id, body)
    elif keyword == "chamfer":
        command = _parse_chamfer(header, object_id, body)
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


def _parse_rounded_box(header: SourceLine, object_id: str, body: list[SourceLine]) -> RoundedBoxCommand:
    size = None
    radius = None
    at = None
    center = False

    for line in body:
        key, _, rest = line.text.partition(" ")
        if key == "size":
            size = _parse_expression_tuple(rest, 3, line.number, key)
        elif key == "radius":
            radius = _parse_expression_tuple(rest, 1, line.number, key)[0]
        elif key == "at":
            at = _parse_expression_tuple(rest, 3, line.number, key)
        elif key == "center":
            value = rest.strip()
            if value not in {"true", "false"}:
                raise ParseError("center must be true or false", line.number)
            center = value == "true"
        else:
            raise ParseError(f"unknown field {key!r} in rounded_box block", line.number)

    if size is None:
        raise ParseError("rounded_box block requires a size field", header.number)
    if radius is None:
        raise ParseError("rounded_box block requires a radius field", header.number)

    return RoundedBoxCommand(id=object_id, size=size, radius=radius, at=at, center=center, line=header.number)


def _parse_rounded_bar(header: SourceLine, object_id: str, body: list[SourceLine]) -> RoundedBarCommand:
    length = None
    width = None
    height = None
    radius = None
    at = None
    axis = "x"

    for line in body:
        key, _, rest = line.text.partition(" ")
        if key == "length":
            length = _parse_expression_tuple(rest, 1, line.number, key)[0]
        elif key == "width":
            width = _parse_expression_tuple(rest, 1, line.number, key)[0]
        elif key == "height":
            height = _parse_expression_tuple(rest, 1, line.number, key)[0]
        elif key == "radius":
            radius = _parse_expression_tuple(rest, 1, line.number, key)[0]
        elif key == "at":
            at = _parse_expression_tuple(rest, 3, line.number, key)
        elif key == "axis":
            axis = rest.strip()
            if axis not in {"x", "y", "z"}:
                raise ParseError("axis must be x, y, or z", line.number)
        else:
            raise ParseError(f"unknown field {key!r} in rounded_bar block", line.number)

    missing = [name for name, value in {"length": length, "width": width, "height": height, "radius": radius}.items() if value is None]
    if missing:
        raise ParseError(f"rounded_bar block requires {', '.join(missing)}", header.number)

    return RoundedBarCommand(
        id=object_id,
        length=length,
        width=width,
        height=height,
        radius=radius,
        at=at,
        axis=axis,
        line=header.number,
    )


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


def _parse_cone(header: SourceLine, object_id: str, body: list[SourceLine]) -> ConeCommand:
    radius1 = None
    radius2 = None
    diameter1 = None
    diameter2 = None
    height = None
    at = None
    axis = "z"

    for line in body:
        key, _, rest = line.text.partition(" ")
        if key == "radius1":
            radius1 = _parse_expression_tuple(rest, 1, line.number, key)[0]
        elif key == "radius2":
            radius2 = _parse_expression_tuple(rest, 1, line.number, key)[0]
        elif key == "diameter1":
            diameter1 = _parse_expression_tuple(rest, 1, line.number, key)[0]
        elif key == "diameter2":
            diameter2 = _parse_expression_tuple(rest, 1, line.number, key)[0]
        elif key == "height":
            height = _parse_expression_tuple(rest, 1, line.number, key)[0]
        elif key == "at":
            at = _parse_expression_tuple(rest, 3, line.number, key)
        elif key == "axis":
            axis = rest.strip()
            if axis not in {"x", "y", "z"}:
                raise ParseError("axis must be x, y, or z", line.number)
        else:
            raise ParseError(f"unknown field {key!r} in cone block", line.number)

    if height is None:
        raise ParseError("cone block requires a height field", header.number)

    return ConeCommand(
        id=object_id,
        radius1=radius1,
        radius2=radius2,
        diameter1=diameter1,
        diameter2=diameter2,
        height=height,
        at=at,
        axis=axis,
        line=header.number,
    )


def _parse_slot(header: SourceLine, object_id: str, body: list[SourceLine]) -> SlotCommand:
    size = None
    clearance = None
    at = None
    center = False

    for line in body:
        key, _, rest = line.text.partition(" ")
        if key == "size":
            size = _parse_expression_tuple(rest, 3, line.number, key)
        elif key == "clearance":
            clearance = _parse_expression_tuple(rest, 1, line.number, key)[0]
        elif key == "at":
            at = _parse_expression_tuple(rest, 3, line.number, key)
        elif key == "center":
            value = rest.strip()
            if value not in {"true", "false"}:
                raise ParseError("center must be true or false", line.number)
            center = value == "true"
        else:
            raise ParseError(f"unknown field {key!r} in slot block", line.number)

    if size is None:
        raise ParseError("slot block requires a size field", header.number)

    return SlotCommand(id=object_id, size=size, clearance=clearance, at=at, center=center, line=header.number)


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


def _parse_copy(header: SourceLine, object_id: str, source_id: str, body: list[SourceLine]) -> CopyCommand:
    operations = []
    for line in body:
        key, _, rest = line.text.partition(" ")
        if key == "by":
            operations.append(CopyByOperation(by=_parse_expression_tuple(rest, 3, line.number, key), line=line.number))
        elif key == "rotate":
            parts = rest.split()
            if len(parts) < 4 or parts[0] != "around" or parts[2] != "angle":
                raise ParseError("copy rotate syntax is 'rotate around <axis> angle <degrees> [origin x y z]'", line.number)
            axis = parts[1]
            if axis not in {"x", "y", "z"}:
                raise ParseError("rotate axis must be x, y, or z", line.number)
            if "origin" in parts:
                origin_index = parts.index("origin")
                angle_text = " ".join(parts[3:origin_index])
                origin = _parse_expression_tuple(" ".join(parts[origin_index + 1:]), 3, line.number, "origin")
            else:
                angle_text = " ".join(parts[3:])
                origin = (
                    Expression("0", line.number),
                    Expression("0", line.number),
                    Expression("0", line.number),
                )
            operations.append(
                CopyRotateOperation(
                    axis=axis,
                    angle=Expression(angle_text, line.number),
                    origin=origin,
                    line=line.number,
                )
            )
        else:
            raise ParseError(f"unknown field {key!r} in copy block", line.number)

    if not operations:
        raise ParseError("copy block requires at least one operation", header.number)

    return CopyCommand(id=object_id, source_id=source_id, operations=operations, line=header.number)


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


def _parse_chamfer(header: SourceLine, object_id: str, body: list[SourceLine]) -> ChamferCommand:
    distance = None
    safe = True

    for line in body:
        key, _, rest = line.text.partition(" ")
        if key == "distance":
            distance = _parse_expression_tuple(rest, 1, line.number, key)[0]
        elif key == "safe":
            value = rest.strip()
            if value not in {"true", "false"}:
                raise ParseError("safe must be true or false", line.number)
            safe = value == "true"
        elif key == "edges":
            if rest.strip() != "all":
                raise ParseError("only 'edges all' is supported in the MVP", line.number)
        else:
            raise ParseError(f"unknown field {key!r} in chamfer block", line.number)

    if distance is None:
        raise ParseError("chamfer block requires a distance field", header.number)
    return ChamferCommand(id=object_id, distance=distance, safe=safe, line=header.number)


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
