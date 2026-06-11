#!/usr/bin/env python3
"""
cq3d_server - web-based editor and STL preview for .cq3d files.

Provides a split-pane UI: CodeMirror editor on the left, Three.js STL preview
on the right. The browser sends raw .cq3d source to the server; the server
compiles it to CadQuery geometry, exports STL, and the frontend renders that STL.
"""

from __future__ import annotations

import argparse
import io
import re
import tempfile
from collections import OrderedDict
from pathlib import Path
from uuid import uuid4

import cadquery as cq
from flask import Flask, Response, jsonify, request, send_file, send_from_directory

from cq3d.cadquery_backend import build_document
from cq3d.errors import Cq3dError
from cq3d.parser import parse_document

app = Flask(__name__, static_folder="static")

AGENT_PATH = Path(__file__).with_name("AGENT.md")
DEFAULT_SOURCE = Path(__file__).with_name("examples").joinpath("display_steps.cq3d").read_text()
MAX_PREVIEWS = 12
PREVIEWS: OrderedDict[str, bytes] = OrderedDict()


def _extract_section_lines(title: str) -> list[str]:
    text = AGENT_PATH.read_text()
    pattern = re.compile(rf"^## {re.escape(title)}\n(.*?)(?=^## |\Z)", re.MULTILINE | re.DOTALL)
    match = pattern.search(text)
    if not match:
        return []
    return [line.strip() for line in match.group(1).splitlines()]


def _extract_list_after_marker(title: str, marker: str) -> list[str]:
    lines = _extract_section_lines(title)
    collecting = False
    collected: list[str] = []
    for line in lines:
        if not collecting:
            if line == marker:
                collecting = True
            continue
        if not line:
            if collected:
                break
            continue
        if not line.startswith("- "):
            if collected:
                break
            continue
        collected.append(line)
    return collected


def _extract_backtick_words(lines: list[str]) -> list[str]:
    seen: OrderedDict[str, None] = OrderedDict()
    for line in lines:
        for value in re.findall(r"`([^`]+)`", line):
            token = value.strip()
            function_match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)\(\.\.\.\)", token)
            if function_match:
                seen[function_match.group(1)] = None
                continue
            if token and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", token):
                seen[token] = None
    return list(seen.keys())


def load_keyword_config() -> dict[str, list[str]]:
    reserved = _extract_backtick_words(
        _extract_list_after_marker(
            "Identifiers",
            "Reserved words must not be used as variable names:",
        )
    )
    commands = _extract_backtick_words(
        _extract_list_after_marker(
            "Implemented Commands",
            "Currently implemented top-level commands:",
        )
    )
    expressions = _extract_backtick_words(
        _extract_list_after_marker(
            "Supported Expressions",
            "Allowed functions:",
        )
    )
    unsupported = _extract_backtick_words(_extract_list_after_marker("Things Not To Use Yet", "These are not implemented in the current DSL and should not be emitted:"))

    keywords = sorted(
        {
            *reserved,
            *commands,
            "model",
            "unit",
            "end",
            "union",
            "cut",
        }
    )

    properties = sorted(
        {
            "size",
            "at",
            "center",
            "radius",
            "diameter",
            "height",
            "axis",
            "by",
            "around",
            "angle",
            "origin",
            "safe",
            "edges",
        }
    )

    values = sorted({"true", "false", "x", "y", "z", "mm", "stl", "step", "all"})

    return {
        "keywords": keywords,
        "properties": properties,
        "functions": expressions,
        "values": values,
        "unsupported": unsupported,
    }


def _build_source(source: str):
    document = parse_document(source)
    build = build_document(document)
    if build.final_object is None:
        raise Cq3dError("no final object is available to preview")
    return document, build


def _export_workplane_bytes(obj: cq.Workplane, export_format: str) -> bytes:
    suffix = f".{export_format}"
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / f"model{suffix}"
        cq.exporters.export(obj, str(path))
        return path.read_bytes()


def _store_preview(stl_bytes: bytes) -> str:
    preview_id = uuid4().hex
    PREVIEWS[preview_id] = stl_bytes
    PREVIEWS.move_to_end(preview_id)
    while len(PREVIEWS) > MAX_PREVIEWS:
        PREVIEWS.popitem(last=False)
    return preview_id


def _bbox_payload(obj: cq.Workplane) -> dict[str, float]:
    bbox = obj.val().BoundingBox()
    return {
        "xmin": bbox.xmin,
        "ymin": bbox.ymin,
        "zmin": bbox.zmin,
        "xmax": bbox.xmax,
        "ymax": bbox.ymax,
        "zmax": bbox.zmax,
        "xlen": bbox.xlen,
        "ylen": bbox.ylen,
        "zlen": bbox.zlen,
    }


@app.route("/")
def index() -> Response:
    return send_from_directory("static", "index.html")


@app.route("/api/keywords")
def keywords_endpoint() -> Response:
    return jsonify(load_keyword_config())


@app.route("/api/default-source")
def default_source_endpoint() -> Response:
    return jsonify({"source": DEFAULT_SOURCE})


@app.route("/api/previews/<preview_id>.stl")
def preview_file(preview_id: str) -> Response:
    stl_bytes = PREVIEWS.get(preview_id)
    if stl_bytes is None:
        return jsonify({"error": "preview not found"}), 404
    return send_file(
        io.BytesIO(stl_bytes),
        mimetype="model/stl",
        download_name=f"{preview_id}.stl",
    )


@app.route("/api/compile", methods=["POST"])
def compile_endpoint() -> Response:
    data = request.get_json(force=True, silent=True) or {}
    source = data.get("source", "")

    try:
        _, build = _build_source(source)
        stl_bytes = _export_workplane_bytes(build.final_object, "stl")
        preview_id = _store_preview(stl_bytes)
        return jsonify(
            {
                "error": None,
                "preview_url": f"/api/previews/{preview_id}.stl",
                "final_object_id": build.final_object_id,
                "bbox": _bbox_payload(build.final_object),
            }
        )
    except Cq3dError as exc:
        return jsonify({"error": str(exc), "preview_url": None}), 400
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"Internal error: {exc}", "preview_url": None}), 500


@app.route("/api/export/stl", methods=["POST"])
def export_stl() -> Response:
    data = request.get_json(force=True, silent=True) or {}
    source = data.get("source", "")
    filename = f"{data.get('filename', 'model')}.stl"

    try:
        _, build = _build_source(source)
        stl_bytes = _export_workplane_bytes(build.final_object, "stl")
        return send_file(
            io.BytesIO(stl_bytes),
            mimetype="model/stl",
            as_attachment=True,
            download_name=filename,
        )
    except Cq3dError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"Internal error: {exc}"}), 500


@app.route("/api/export/step", methods=["POST"])
def export_step() -> Response:
    data = request.get_json(force=True, silent=True) or {}
    source = data.get("source", "")
    filename = f"{data.get('filename', 'model')}.step"

    try:
        _, build = _build_source(source)
        step_bytes = _export_workplane_bytes(build.final_object, "step")
        return send_file(
            io.BytesIO(step_bytes),
            mimetype="application/step",
            as_attachment=True,
            download_name=filename,
        )
    except Cq3dError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"Internal error: {exc}"}), 500


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="cq3d_server",
        description="Web editor for .cq3d files with STL preview.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5001, help="Port to listen on (default: 5001)")
    parser.add_argument("--debug", action="store_true", help="Enable Flask debug mode")
    args = parser.parse_args(argv)

    url = f"http://{args.host}:{args.port}"
    print(f"cq3d editor  ->  {url}")
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
