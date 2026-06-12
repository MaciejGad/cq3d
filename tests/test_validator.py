import pytest

from cq3d.errors import ParseError, ValidationError
from cq3d.parser import parse_document
from cq3d.validator import validate_document


def test_rejects_variable_reassignment():
    document = parse_document(
        """
model demo
unit mm
width = 10
width = 20
"""
    )
    with pytest.raises(ValidationError, match="cannot be reassigned"):
        validate_document(document)


def test_rejects_unknown_object_reference():
    document = parse_document(
        """
model demo
unit mm

box base
  size 10 10 10
end

combine body
  union base missing
end
"""
    )
    with pytest.raises(ValidationError, match="unknown object 'missing'"):
        validate_document(document)


def test_requires_positive_dimensions():
    document = parse_document(
        """
model demo
unit mm

box base
  size 10 0 10
end
"""
    )
    with pytest.raises(ValidationError, match="dimensions must be greater than zero"):
        validate_document(document)


@pytest.mark.parametrize(
    ("source", "message"),
    [
        (
            """
model demo
unit mm

rounded_box body
  size 10 10 10
  radius 6
end
""",
            "radius",
        ),
        (
            """
model demo
unit mm

cone body
  radius1 4
  diameter2 6
  height 10
end
""",
            "do not allow mixing",
        ),
        (
            """
model demo
unit mm

box body
  size 10 10 10
end

chamfer body
  distance 0
end
""",
            "greater than zero",
        ),
        (
            """
model demo
unit mm

box body
  size 10 10 10
end

export stl "body.stl"
  object missing
end
""",
            "unknown object 'missing'",
        ),
    ],
)
def test_rejects_invalid_extended_geometry_input(source, message):
    document = parse_document(source)
    with pytest.raises(ValidationError, match=message):
        validate_document(document)


@pytest.mark.parametrize(
    ("source", "message"),
    [
        (
            """
model demo
unit mm

copy arm_b from arm_a
  by 0 10 0
end
""",
            "unknown object 'arm_a'",
        ),
        (
            """
model demo
unit mm

box arm
  size 10 10 10
end

copy arm_b from arm
end
""",
            "at least one operation",
        ),
        (
            """
model demo
unit mm

slot cutter
  size 10 10 10
  clearance -0.1
end
""",
            "clearance must be greater than or equal to zero",
        ),
        (
            """
model demo
unit mm

rounded_bar arm
  length 100
  width 20
  height 8
  radius 6
end
""",
            "radius",
        ),
    ],
)
def test_rejects_invalid_copy_slot_and_rounded_bar(source, message):
    if "copy arm_b from arm\nend" in source:
        with pytest.raises(ParseError, match=message):
            parse_document(source)
        return
    document = parse_document(source)
    with pytest.raises(ValidationError, match=message):
        validate_document(document)
