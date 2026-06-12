import pytest

from pathlib import Path

from cq3d.ast_nodes import (
    BoxCommand,
    ChamferCommand,
    CombineCommand,
    ConeCommand,
    CopyCommand,
    CylinderCommand,
    ExportCommand,
    FilletCommand,
    MoveCommand,
    RoundedBoxCommand,
    RoundedBarCommand,
    RotateCommand,
    SlotCommand,
    VariableAssignment,
)
from cq3d.errors import ParseError
from cq3d.parser import parse_document


def test_parses_mvp_document():
    source = """
model display_steps
unit mm

width = 165
depth = 160

box lower
  size width depth 75
  at 0 0 0
end

combine body
  union lower lower
end

fillet body
  radius 2
end

export stl "display_steps.stl"
"""
    document = parse_document(source)
    assert document.name == "display_steps"
    assert document.unit == "mm"
    assert isinstance(document.commands[0], VariableAssignment)
    assert isinstance(document.commands[2], BoxCommand)
    assert isinstance(document.commands[3], CombineCommand)
    assert isinstance(document.commands[4], FilletCommand)
    assert document.exports == [ExportCommand(format="stl", path="display_steps.stl", line=21)]


def test_splits_multi_token_expressions():
    source = """
model sample
unit mm
depth = 160

box upper
  size 165 depth / 2 75
  at 0 depth / 2 75
end
"""
    document = parse_document(source)
    box = document.commands[1]
    assert isinstance(box, BoxCommand)
    assert box.size[1].text == "depth / 2"
    assert box.at[1].text == "depth / 2"


def test_reports_missing_end():
    with pytest.raises(ParseError, match="missing 'end'"):
        parse_document(
            """
model broken
unit mm
box body
  size 1 2 3
"""
        )


def test_parses_all_mvp_block_types_and_source_path():
    source = """
model fixture
unit mm
offset = 5

box base
  size 10 20 30
  center true
end

cylinder peg
  diameter 8
  height 12
  at offset 0 0
  axis x
end

combine body
  union base peg
  cut body peg
end

move body
  by 1 2 3
end

rotate body
  around y
  angle 45
  origin 1 2 3
end

fillet body
  radius 2
  safe false
  edges all
end

export stl
export step "fixture.step"
"""
    document = parse_document(source, source_path="examples/fixture.cq3d")
    assert document.source_path == Path("examples/fixture.cq3d")
    assert isinstance(document.commands[1], BoxCommand)
    assert document.commands[1].center is True
    assert isinstance(document.commands[2], CylinderCommand)
    assert document.commands[2].diameter.text == "8"
    assert document.commands[2].axis == "x"
    assert isinstance(document.commands[4], MoveCommand)
    assert isinstance(document.commands[5], RotateCommand)
    rotate = document.commands[5]
    assert rotate.axis == "y"
    assert rotate.origin[2].text == "3"
    assert isinstance(document.commands[6], FilletCommand)
    assert document.commands[6].safe is False
    assert document.exports[0].format == "stl"
    assert document.exports[0].path is None
    assert document.exports[1] == ExportCommand(format="step", path="fixture.step", line=40)


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ("model one\nmodel two\n", "model is already declared"),
        ("unit mm\nunit mm\n", "unit is already declared"),
        ("unit cm\n", "only 'mm' units are supported"),
        ("oops 1 2 3\n", "unknown command"),
        ("end = 1\n", "reserved keyword"),
        ("width =\n", "missing an expression"),
        ('export stl "unterminated\n', "invalid export command"),
        ("export obj\n", "unsupported export format"),
        ("box\nend\n", "block syntax"),
        ("box body\n  size 1 2 3\n  box inner\nend\n", "nested blocks are not supported"),
        ("box body\n  center maybe\nend\n", "center must be true or false"),
        ("box body\n  radius 3\nend\n", "unknown field 'radius' in box block"),
        ("box body\nend\n", "box block requires a size field"),
        ("cylinder peg\n  height 5\n  axis q\nend\n", "axis must be x, y, or z"),
        ("cylinder peg\n  size 1 2 3\nend\n", "unknown field 'size' in cylinder block"),
        ("cylinder peg\n  radius 2\nend\n", "cylinder block requires a height field"),
        ("combine body\n  intersect a b\nend\n", "unknown combine operation"),
        ("combine body\n  union\nend\n", "union requires object references"),
        ("combine body\n  union a bad-id\nend\n", "invalid object reference"),
        ("combine body\nend\n", "combine block requires at least one operation"),
        ("move body\n  at 1 2 3\nend\n", "move block requires a 'by' field"),
        ("move body\n  by 1 2 3\n  by 4 5 6\nend\n", "move block requires a single 'by' field"),
        ("rotate body\n  around q\n  angle 30\nend\n", "rotate axis must be x, y, or z"),
        ("rotate body\n  by 30\nend\n", "unknown field 'by' in rotate block"),
        ("rotate body\n  around z\nend\n", "rotate block requires 'around' and 'angle' fields"),
        ("fillet body\n  safe maybe\n  radius 2\nend\n", "safe must be true or false"),
        ("fillet body\n  edges top\n  radius 2\nend\n", "only 'edges all' is supported"),
        ("fillet body\n  size 1\nend\n", "unknown field 'size' in fillet block"),
        ("fillet body\n  safe true\nend\n", "fillet block requires a radius field"),
        ("box body\n  size 1 2\nend\n", "size requires 3 values"),
        ("move body\n  by 1 2 +\nend\n", "could not parse 3 expressions for by"),
    ],
)
def test_parser_reports_targeted_errors(source, message):
    with pytest.raises(ParseError, match=message):
        parse_document(source)


def test_parses_rounded_box_cone_chamfer_and_export_block():
    source = """
model spindle_bits
unit mm

rounded_box arm
  size 40 12 8
  radius 2
  at 0 0 0
end

cone tip
  diameter1 10
  diameter2 4
  height 20
  at 0 0 8
end

chamfer arm
  distance 1
  safe false
  edges all
end

export stl "arm.stl"
  object arm
end
"""
    document = parse_document(source)
    assert isinstance(document.commands[0], RoundedBoxCommand)
    assert isinstance(document.commands[1], ConeCommand)
    assert isinstance(document.commands[2], ChamferCommand)
    assert document.exports[0].format == "stl"
    assert document.exports[0].path == "arm.stl"
    assert document.exports[0].object_ids == ["arm"]


def test_parses_copy_slot_and_rounded_bar():
    source = """
model spindle
unit mm

rounded_bar arm_a
  length 140
  width 22
  height 10
  radius 4
  axis x
  at -70 -11 20
end

copy arm_b from arm_a
  rotate around z angle 90 origin 0 0 0
end

slot arm_slot
  size 24 12 8
  clearance 0.3
  at -12 -6 4
end
"""
    document = parse_document(source)
    assert isinstance(document.commands[0], RoundedBarCommand)
    assert isinstance(document.commands[1], CopyCommand)
    assert document.commands[1].source_id == "arm_a"
    assert isinstance(document.commands[2], SlotCommand)
