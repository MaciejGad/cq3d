from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from cq3d.compiler import build_file, validate_file
from cq3d.errors import Cq3dError


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cq3d")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build", help="Build a .cq3d file and export geometry")
    build_parser.add_argument("path", type=Path)
    build_parser.add_argument("--out-dir", type=Path, default=None)

    validate_parser = subparsers.add_parser("validate", help="Validate a .cq3d file")
    validate_parser.add_argument("path", type=Path)

    args = parser.parse_args(argv)

    try:
        if args.command == "build":
            result = build_file(args.path, out_dir=args.out_dir)
            for path in result.exports:
                print(path)
            return 0
        if args.command == "validate":
            validate_file(args.path)
            print(f"{args.path}: OK")
            return 0
    except Cq3dError as exc:
        print(exc)
        return 1

    parser.error(f"unknown command {args.command!r}")
    return 2
