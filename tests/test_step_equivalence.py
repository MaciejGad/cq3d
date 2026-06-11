from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

cq = pytest.importorskip("cadquery")

from cq3d.cadquery_backend import build_document
from cq3d.exporters import export_document
from cq3d.parser import parse_document


@dataclass(frozen=True)
class ShapeMetrics:
    volume: float
    area: float
    bbox: tuple[float, float, float]
    bbox_min: tuple[float, float, float]
    bbox_max: tuple[float, float, float]
    solids: int
    faces: int
    edges: int


def _lower_corner_box(size: tuple[float, float, float], at: tuple[float, float, float] = (0, 0, 0)):
    x, y, z = size
    ax, ay, az = at
    return cq.Workplane("XY").box(x, y, z).translate((x / 2 + ax, y / 2 + ay, z / 2 + az))


def _cylinder(
    radius: float,
    height: float,
    at: tuple[float, float, float] = (0, 0, 0),
    axis: str = "z",
):
    obj = cq.Workplane("XY").circle(radius).extrude(height)
    if axis == "x":
        obj = obj.rotate((0, 0, 0), (0, 1, 0), 90)
    elif axis == "y":
        obj = obj.rotate((0, 0, 0), (1, 0, 0), -90)
    return obj.translate(at)


def _metrics(step_path: Path) -> ShapeMetrics:
    imported = cq.importers.importStep(str(step_path))
    shape = imported.val()
    bbox = shape.BoundingBox()
    return ShapeMetrics(
        volume=shape.Volume(),
        area=shape.Area(),
        bbox=(bbox.xlen, bbox.ylen, bbox.zlen),
        bbox_min=(bbox.xmin, bbox.ymin, bbox.zmin),
        bbox_max=(bbox.xmax, bbox.ymax, bbox.zmax),
        solids=len(imported.solids().vals()),
        faces=len(shape.Faces()),
        edges=len(shape.Edges()),
    )


def _symmetric_difference_volumes(left_step: Path, right_step: Path) -> tuple[float, float]:
    left = cq.importers.importStep(str(left_step))
    right = cq.importers.importStep(str(right_step))
    return left.cut(right).val().Volume(), right.cut(left).val().Volume()


def _export_cq3d(source: str, out_dir: Path) -> Path:
    document = parse_document(source, source_path=out_dir / "model.cq3d")
    build = build_document(document)
    written = export_document(document, build.final_object)
    assert len(written) == 1
    return written[0]


def _export_python(model: cq.Workplane, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    cq.exporters.export(model, str(path))
    return path


@pytest.mark.parametrize(
    ("name", "source", "builder"),
    [
        pytest.param(
            "box",
            """
model box_case
unit mm

box body
  size 10 20 30
  at 0 0 0
end

export step "box_case.step"
""",
            lambda: _lower_corner_box((10, 20, 30)),
            marks=pytest.mark.xfail(
                strict=True,
                reason="Known placement mismatch: cq3d box output is offset from the origin compared to the reference model.",
            ),
        ),
        pytest.param(
            "cylinder",
            """
model cylinder_case
unit mm

cylinder body
  radius 5
  height 12
  at 0 0 0
end

export step "cylinder_case.step"
""",
            lambda: _cylinder(5, 12),
        ),
        pytest.param(
            "union_boxes",
            """
model union_boxes_case
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

export step "union_boxes_case.step"
""",
            lambda: _lower_corner_box((10, 20, 30)).union(_lower_corner_box((10, 20, 10), (0, 0, 30))),
            marks=pytest.mark.xfail(
                strict=True,
                reason="Known box placement bug collapses the union case by shifting the second box into the first one.",
            ),
        ),
    ],
)
def test_cq3d_step_matches_reference_python_step(tmp_path, name, source, builder):
    cq3d_step = _export_cq3d(source, tmp_path / "cq3d")
    python_step = _export_python(builder(), tmp_path / "python" / f"{name}.step")

    cq3d_metrics = _metrics(cq3d_step)
    python_metrics = _metrics(python_step)

    assert cq3d_metrics.volume == pytest.approx(python_metrics.volume, abs=1e-6)
    assert cq3d_metrics.area == pytest.approx(python_metrics.area, abs=1e-6)
    assert cq3d_metrics.bbox == pytest.approx(python_metrics.bbox, abs=1e-6)
    assert cq3d_metrics.bbox_min == pytest.approx(python_metrics.bbox_min, abs=1e-6)
    assert cq3d_metrics.bbox_max == pytest.approx(python_metrics.bbox_max, abs=1e-6)
    assert cq3d_metrics.solids == python_metrics.solids
    assert cq3d_metrics.faces == python_metrics.faces
    assert cq3d_metrics.edges == python_metrics.edges

    left_only, right_only = _symmetric_difference_volumes(cq3d_step, python_step)
    assert left_only == pytest.approx(0.0, abs=1e-6)
    assert right_only == pytest.approx(0.0, abs=1e-6)
