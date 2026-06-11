from __future__ import annotations

from pathlib import Path

import cadquery as cq

from cq3d.ast_nodes import ExportCommand, ModelDocument
from cq3d.errors import BackendError


def export_document(
    document: ModelDocument,
    final_object: cq.Workplane | None,
    *,
    out_dir: str | Path | None = None,
) -> list[Path]:
    if final_object is None:
        raise BackendError("no final object is available to export")

    exports = document.exports or _default_exports(document)
    source_dir = document.source_path.parent if document.source_path else Path.cwd()
    override_dir = Path(out_dir) if out_dir else None
    written: list[Path] = []

    for export in exports:
        target = _resolve_export_path(export, document, source_dir, override_dir)
        target.parent.mkdir(parents=True, exist_ok=True)
        cq.exporters.export(final_object, str(target))
        written.append(target)

    return written


def _default_exports(document: ModelDocument) -> list[ExportCommand]:
    model_name = document.name or "model"
    return [ExportCommand(format="stl", path=f"{model_name}.stl", line=1)]


def _resolve_export_path(
    export: ExportCommand,
    document: ModelDocument,
    source_dir: Path,
    override_dir: Path | None,
) -> Path:
    default_name = document.name or "model"
    raw_path = export.path or f"{default_name}.{export.format}"
    target = Path(raw_path)
    if not target.is_absolute():
        base_dir = override_dir if override_dir is not None else source_dir
        target = base_dir / target
    return target
