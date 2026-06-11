from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cq3d.parser import parse_document
from cq3d.validator import ValidationResult, validate_document


@dataclass(slots=True)
class FileBuildResult:
    build: object
    exports: list[Path]


def parse_file(path: str | Path):
    source_path = Path(path)
    return parse_document(source_path.read_text(), source_path=source_path)


def validate_file(path: str | Path) -> ValidationResult:
    document = parse_file(path)
    return validate_document(document)


def build_file(path: str | Path, *, out_dir: str | Path | None = None) -> FileBuildResult:
    from cq3d.cadquery_backend import build_document
    from cq3d.exporters import export_document

    document = parse_file(path)
    build = build_document(document)
    exports = export_document(document, build.final_object, out_dir=out_dir)
    return FileBuildResult(build=build, exports=exports)
