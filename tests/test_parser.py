import pytest

from cq3d.ast_nodes import BoxCommand, CombineCommand, ExportCommand, FilletCommand, VariableAssignment
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
