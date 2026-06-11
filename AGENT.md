# AGENT Guide

## Project Goal

This repository implements a text-based DSL for generating 3D printable objects with CadQuery.
The current target is the MVP defined in:

- [`cadquery_3d_dsl_design.md`](/Users/bazyl/Code/Essa3d/cadquery_3d_dsl_design.md)
- [`cadquery_3d_dsl_implementation_plan.md`](/Users/bazyl/Code/Essa3d/cadquery_3d_dsl_implementation_plan.md)

Treat those documents as the product source of truth.

## Current Architecture

Core pipeline:

1. Parse `.cq3d` text into an internal AST.
2. Validate semantics and evaluate variables safely.
3. Build CadQuery geometry through the backend registry.
4. Export the final object to STL and STEP.

Primary modules:

- [`cq3d/errors.py`](/Users/bazyl/Code/Essa3d/cq3d/errors.py): user-facing exceptions with line numbers
- [`cq3d/ast_nodes.py`](/Users/bazyl/Code/Essa3d/cq3d/ast_nodes.py): typed AST dataclasses
- [`cq3d/expressions.py`](/Users/bazyl/Code/Essa3d/cq3d/expressions.py): safe expression evaluator
- [`cq3d/parser.py`](/Users/bazyl/Code/Essa3d/cq3d/parser.py): line-based parser
- [`cq3d/validator.py`](/Users/bazyl/Code/Essa3d/cq3d/validator.py): semantic validation
- [`cq3d/cadquery_backend.py`](/Users/bazyl/Code/Essa3d/cq3d/cadquery_backend.py): CadQuery object generation
- [`cq3d/exporters.py`](/Users/bazyl/Code/Essa3d/cq3d/exporters.py): STL / STEP export
- [`cq3d/cli.py`](/Users/bazyl/Code/Essa3d/cq3d/cli.py): `build` and `validate`
- [`cq3d/compiler.py`](/Users/bazyl/Code/Essa3d/cq3d/compiler.py): file-level orchestration

## MVP Rules

- Do not use Python `eval`.
- Use the safe AST whitelist in `expressions.py`.
- Keep syntax line-based and block-oriented.
- Preserve readable validation errors with source line numbers.
- Resolve relative export paths from the input file directory.
- Keep the parser AST-only; no direct CadQuery construction in parser code.

## Supported MVP Commands

- `model`
- `unit mm`
- variable assignment
- `box`
- `cylinder`
- `combine` with `union` and `cut`
- `move`
- `rotate`
- `fillet`
- `export stl`
- `export step`

## Development Workflow

Set up dependencies:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
```

Run tests:

```bash
.venv/bin/python -m pytest
```

Validate the example:

```bash
.venv/bin/python -m cq3d.cli validate examples/display_steps.cq3d
```

Build the example:

```bash
.venv/bin/python -m cq3d.cli build examples/display_steps.cq3d
```

## When Extending the DSL

- Add tests before or alongside new commands.
- Prefer typed AST nodes over ad hoc dictionaries.
- Keep validation separate from geometry generation.
- Verify geometry with bounding boxes, not only by checking files exist.
- Do not add post-MVP features until the current MVP remains green.
