from pathlib import Path

import pytest

cq = pytest.importorskip("cadquery")

from cq3d.cadquery_backend import build_document, get_bounding_box
from cq3d.exporters import export_document
from cq3d.parser import parse_document


def _bbox(workplane: cq.Workplane):
    bbox = workplane.val().BoundingBox()
    return bbox.xlen, bbox.ylen, bbox.zlen


def _bbox_min_max(workplane: cq.Workplane):
    bbox = workplane.val().BoundingBox()
    return (bbox.xmin, bbox.ymin, bbox.zmin), (bbox.xmax, bbox.ymax, bbox.zmax)


def test_bounding_box_helper_reports_expected_fields():
    source = """
model demo
unit mm

box body
  size 10 20 30
  at 5 6 7
end
"""
    result = build_document(parse_document(source))
    bbox = get_bounding_box(result.final_object)
    assert bbox == pytest.approx(
        {
            "xmin": 5.0,
            "xmax": 15.0,
            "xlen": 10.0,
            "ymin": 6.0,
            "ymax": 26.0,
            "ylen": 20.0,
            "zmin": 7.0,
            "zmax": 37.0,
            "zlen": 30.0,
        }
    )


def test_builds_display_steps_example_with_expected_bounds():
    source = Path("examples/display_steps.cq3d").read_text()
    document = parse_document(source, source_path="examples/display_steps.cq3d")
    result = build_document(document)
    assert result.final_object_id == "body"
    assert _bbox(result.final_object) == pytest.approx((165.0, 160.0, 150.0))
    assert get_bounding_box(result.final_object) == pytest.approx(
        {
            "xmin": 0.0,
            "xmax": 165.0,
            "xlen": 165.0,
            "ymin": 0.0,
            "ymax": 160.0,
            "ylen": 160.0,
            "zmin": 0.0,
            "zmax": 150.0,
            "zlen": 150.0,
        }
    )


def test_move_rotate_and_cut_pipeline():
    source = """
model demo
unit mm

box base
  size 40 20 10
  at 0 0 0
end

cylinder hole
  radius 3
  height 20
  at 20 10 -5
end

combine cut_body
  cut base hole
end

move cut_body
  by 5 0 0
end

rotate cut_body
  around z
  angle 90
  origin 0 0 0
end
    """
    document = parse_document(source)
    result = build_document(document)
    assert result.final_object_id == "cut_body"
    assert _bbox(result.final_object) == pytest.approx((20.0, 40.0, 10.0))


def test_safe_fillet_does_not_crash():
    source = """
model demo
unit mm

box body
  size 10 10 10
end

fillet body
  radius 100
  safe true
end
"""
    result = build_document(parse_document(source))
    assert _bbox(result.final_object) == pytest.approx((10.0, 10.0, 10.0))


def test_box_at_uses_lower_corner_coordinates():
    source = """
model demo
unit mm

box body
  size 10 20 30
  at 0 0 0
end
"""
    result = build_document(parse_document(source))
    bbox_min, bbox_max = _bbox_min_max(result.final_object)
    assert bbox_min == pytest.approx((0.0, 0.0, 0.0))
    assert bbox_max == pytest.approx((10.0, 20.0, 30.0))


def test_box_at_offset_uses_lower_front_left_bottom_anchor():
    source = """
model demo
unit mm

box body
  size 100 50 20
  at 10 20 0
end
"""
    result = build_document(parse_document(source))
    assert get_bounding_box(result.final_object) == pytest.approx(
        {
            "xmin": 10.0,
            "xmax": 110.0,
            "xlen": 100.0,
            "ymin": 20.0,
            "ymax": 70.0,
            "ylen": 50.0,
            "zmin": 0.0,
            "zmax": 20.0,
            "zlen": 20.0,
        }
    )


@pytest.mark.parametrize(
    ("axis", "expected"),
    [
        (
            "z",
            {
                "xmin": 5.0,
                "xmax": 15.0,
                "xlen": 10.0,
                "ymin": 10.0,
                "ymax": 20.0,
                "ylen": 10.0,
                "zmin": 0.0,
                "zmax": 20.0,
                "zlen": 20.0,
            },
        ),
        (
            "x",
            {
                "xmin": 10.0,
                "xmax": 30.0,
                "xlen": 20.0,
                "ymin": 10.0,
                "ymax": 20.0,
                "ylen": 10.0,
                "zmin": -5.0,
                "zmax": 5.0,
                "zlen": 10.0,
            },
        ),
        (
            "y",
            {
                "xmin": 5.0,
                "xmax": 15.0,
                "xlen": 10.0,
                "ymin": 15.0,
                "ymax": 35.0,
                "ylen": 20.0,
                "zmin": -5.0,
                "zmax": 5.0,
                "zlen": 10.0,
            },
        ),
    ],
)
def test_cylinder_anchor_and_axis_bounding_boxes(axis, expected):
    source = f"""
model demo
unit mm

cylinder body
  radius 5
  height 20
  at 10 15 0
  axis {axis}
end
"""
    result = build_document(parse_document(source))
    assert get_bounding_box(result.final_object) == pytest.approx(expected, abs=1e-6)


def test_cylinder_defaults_to_vertical_z_axis():
    source = """
model demo
unit mm

cylinder body
  radius 5
  height 20
  at 10 15 0
end
"""
    result = build_document(parse_document(source))
    assert get_bounding_box(result.final_object) == pytest.approx(
        {
            "xmin": 5.0,
            "xmax": 15.0,
            "xlen": 10.0,
            "ymin": 10.0,
            "ymax": 20.0,
            "ylen": 10.0,
            "zmin": 0.0,
            "zmax": 20.0,
            "zlen": 20.0,
        },
        abs=1e-6,
    )


def test_move_applies_relative_translation_after_creation():
    source = """
model demo
unit mm

box body
  size 10 20 30
  at 1 2 3
end

move body
  by 4 5 6
end
"""
    result = build_document(parse_document(source))
    assert get_bounding_box(result.final_object) == pytest.approx(
        {
            "xmin": 5.0,
            "xmax": 15.0,
            "xlen": 10.0,
            "ymin": 7.0,
            "ymax": 27.0,
            "ylen": 20.0,
            "zmin": 9.0,
            "zmax": 39.0,
            "zlen": 30.0,
        }
    )


def test_union_preserves_world_coordinates():
    source = """
model demo
unit mm

box lower
  size 10 20 30
  at 0 0 0
end

box upper
  size 10 20 10
  at 0 0 30
end

combine body
  union lower upper
end
"""
    result = build_document(parse_document(source))
    assert get_bounding_box(result.final_object) == pytest.approx(
        {
            "xmin": 0.0,
            "xmax": 10.0,
            "xlen": 10.0,
            "ymin": 0.0,
            "ymax": 20.0,
            "ylen": 20.0,
            "zmin": 0.0,
            "zmax": 40.0,
            "zlen": 40.0,
        }
    )


def test_exports_stl_and_step(tmp_path):
    source = """
model demo
unit mm

box body
  size 10 20 30
end

export stl "nested/demo.stl"
export step "nested/demo.step"
"""
    document = parse_document(source, source_path=tmp_path / "demo.cq3d")
    result = build_document(document)
    written = export_document(document, result.final_object)
    assert {path.suffix for path in written} == {".stl", ".step"}
    for path in written:
        assert path.exists()
        assert path.stat().st_size > 0


def test_builds_rounded_box_and_cone(tmp_path):
    source = """
model demo
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
  at 5 6 8
end

combine body
  union arm tip
end

export step "demo.step"
"""
    document = parse_document(source, source_path=tmp_path / "demo.cq3d")
    result = build_document(document)
    written = export_document(document, result.final_object)
    assert result.final_object_id == "body"
    assert any(path.suffix == ".step" for path in written)


def test_chamfer_safe_failure_keeps_object():
    source = """
model demo
unit mm

box body
  size 10 10 10
end

chamfer body
  distance 100
  safe true
end
"""
    result = build_document(parse_document(source))
    assert _bbox(result.final_object) == pytest.approx((10.0, 10.0, 10.0))


def test_object_specific_export_writes_selected_objects(tmp_path):
    source = """
model demo
unit mm

box arm
  size 20 10 5
end

box shaft
  size 5 5 30
  at 30 0 0
end

export stl "arm.stl"
  object arm
end

export step "assembly.step"
  objects arm shaft
end
    """
    document = parse_document(source, source_path=tmp_path / "demo.cq3d")
    result = build_document(document)
    written = export_document(document, result.final_object, objects=result.objects)
    assert {path.name for path in written} == {"arm.stl", "assembly.step"}
    for path in written:
        assert path.exists()
        assert path.stat().st_size > 0


def test_builds_copy_slot_and_rounded_bar():
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
  at -12 -6 21
end

combine body
  union arm_a arm_b
  cut body arm_slot
end
"""
    result = build_document(parse_document(source))
    assert result.final_object_id == "body"
    assert "arm_a" in result.objects
    assert "arm_b" in result.objects
    assert "arm_slot" in result.objects


def test_copy_does_not_mutate_source_object():
    source = """
model demo
unit mm

box arm_a
  size 20 10 5
  at 0 0 0
end

copy arm_b from arm_a
  by 30 0 0
end
"""
    result = build_document(parse_document(source))
    assert get_bounding_box(result.objects["arm_a"]) == pytest.approx(
        {
            "xmin": 0.0,
            "xmax": 20.0,
            "xlen": 20.0,
            "ymin": 0.0,
            "ymax": 10.0,
            "ylen": 10.0,
            "zmin": 0.0,
            "zmax": 5.0,
            "zlen": 5.0,
        }
    )
    assert get_bounding_box(result.objects["arm_b"]) == pytest.approx(
        {
            "xmin": 30.0,
            "xmax": 50.0,
            "xlen": 20.0,
            "ymin": 0.0,
            "ymax": 10.0,
            "ylen": 10.0,
            "zmin": 0.0,
            "zmax": 5.0,
            "zlen": 5.0,
        }
    )


def test_combine_supports_sequential_self_referencing_cuts():
    source = """
model demo
unit mm

box arm_blank
  size 40 12 8
  at -20 -6 0
end

slot top_slot
  size 10 4 4
  at -5 -2 4
end

cylinder center_hole
  radius 3
  height 10
  at 0 0 -1
end

combine arm
  cut arm_blank top_slot
  cut arm center_hole
end
"""
    result = build_document(parse_document(source))
    assert get_bounding_box(result.objects["arm"]) == pytest.approx(
        {
            "xmin": -20.0,
            "xmax": 20.0,
            "xlen": 40.0,
            "ymin": -6.0,
            "ymax": 6.0,
            "ylen": 12.0,
            "zmin": 0.0,
            "zmax": 8.0,
            "zlen": 8.0,
        },
        abs=1e-6,
    )
