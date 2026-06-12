from pathlib import Path

import pytest

from cq3d.cadquery_backend import build_document, get_bounding_box
from cq3d.compiler import build_file
from cq3d.errors import ValidationError
from cq3d.parser import parse_document
from cq3d.validator import validate_document


@pytest.mark.parametrize(
    ("source", "expected_bbox"),
    [
        (
            """
model simple_box
unit mm

box body
  size 30 20 10
  at 0 0 0
end
""",
            {"xlen": 30.0, "ylen": 20.0, "zlen": 10.0},
        ),
        (
            """
model simple_cylinder
unit mm

cylinder body
  radius 5
  height 25
  at 10 10 0
end
""",
            {"xlen": 10.0, "ylen": 10.0, "zlen": 25.0},
        ),
        (
            """
model cut_case
unit mm

box base
  size 20 20 10
  at 0 0 0
end

cylinder cutter
  radius 3
  height 12
  at 10 10 -1
end

combine body
  cut base cutter
end
""",
            {"xlen": 20.0, "ylen": 20.0, "zlen": 10.0},
        ),
        (
            """
model fillet_case
unit mm

box body
  size 20 20 10
  at 0 0 0
end

fillet body
  radius 1
end
""",
            {"xlen": 20.0, "ylen": 20.0, "zlen": 10.0},
        ),
    ],
)
def test_existing_core_models_remain_buildable(source, expected_bbox):
    document = parse_document(source)
    validate_document(document)
    result = build_document(document)
    bbox = get_bounding_box(result.final_object)
    for key, value in expected_bbox.items():
        assert bbox[key] == pytest.approx(value)


def test_old_and_new_export_syntax_both_build(tmp_path):
    old_style = tmp_path / "old_style.cq3d"
    old_style.write_text(
        """
model old_style
unit mm

box body
  size 10 20 30
end

export stl "old_style.stl"
export step "old_style.step"
""".strip()
        + "\n"
    )

    new_style = tmp_path / "new_style.cq3d"
    new_style.write_text(
        """
model new_style
unit mm

box body
  size 10 20 30
end

box cap
  size 10 20 5
  at 0 0 30
end

export stl "body.stl"
  object body
end

export step "assembly.step"
  objects body cap
end
""".strip()
        + "\n"
    )

    old_result = build_file(old_style)
    new_result = build_file(new_style)

    assert {path.name for path in old_result.exports} == {"old_style.stl", "old_style.step"}
    assert {path.name for path in new_result.exports} == {"body.stl", "assembly.step"}


def test_rejects_duplicate_object_ids():
    document = parse_document(
        """
model duplicate_ids
unit mm

box body
  size 10 10 10
end

cylinder body
  radius 5
  height 10
end
"""
    )
    with pytest.raises(ValidationError, match="already defined"):
        validate_document(document)


def test_rejects_invalid_object_identifier():
    with pytest.raises(ValidationError, match="invalid identifier"):
        parse_document(
            """
model bad_id
unit mm

box arm-slot
  size 10 10 10
end
"""
        )


def test_builds_advanced_spindle_example_and_exports_parts(tmp_path):
    source_path = Path("examples/turkish_spindle_advanced.cq3d")
    result = build_file(source_path, out_dir=tmp_path)

    assert {path.name for path in result.exports} == {
        "shaft.stl",
        "arm_a.stl",
        "arm_b.stl",
        "turkish_spindle_assembly.step",
    }
    for path in result.exports:
        assert path.exists()

    assert result.build.final_object_id == "body"
    assert set(result.build.objects) >= {"shaft", "arm_a", "arm_b", "body"}

    body_bbox = get_bounding_box(result.build.objects["body"])
    shaft_bbox = get_bounding_box(result.build.objects["shaft"])
    arm_a_bbox = get_bounding_box(result.build.objects["arm_a"])
    arm_b_bbox = get_bounding_box(result.build.objects["arm_b"])

    assert body_bbox["xlen"] == pytest.approx(140.0, abs=0.02)
    assert body_bbox["ylen"] == pytest.approx(140.0, abs=0.02)
    assert body_bbox["zlen"] == pytest.approx(174.0, abs=0.02)
    assert shaft_bbox["zlen"] == pytest.approx(174.0, abs=0.02)
    assert arm_a_bbox["xlen"] == pytest.approx(140.0, abs=0.02)
    assert arm_a_bbox["zlen"] == pytest.approx(8.0, abs=0.02)
    assert arm_b_bbox["ylen"] == pytest.approx(140.0, abs=0.02)
