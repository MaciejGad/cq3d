from pathlib import Path

import pytest

cq = pytest.importorskip("cadquery")

from cq3d.cadquery_backend import build_document
from cq3d.exporters import export_document
from cq3d.parser import parse_document


def _bbox(workplane: cq.Workplane):
    bbox = workplane.val().BoundingBox()
    return bbox.xlen, bbox.ylen, bbox.zlen


def test_builds_display_steps_example_with_expected_bounds():
    source = Path("examples/display_steps.cq3d").read_text()
    document = parse_document(source, source_path="examples/display_steps.cq3d")
    result = build_document(document)
    assert result.final_object_id == "body"
    assert _bbox(result.final_object) == pytest.approx((165.0, 160.0, 150.0))


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
