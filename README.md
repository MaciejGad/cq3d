# CadQuery 3D DSL

`cq3d` is a small text-first DSL for generating 3D printable models with CadQuery.
The source file is a plain-text `.cq3d` document, and the build pipeline is:

`.cq3d` -> parser -> AST -> validator -> CadQuery backend -> STL / STEP

The MVP is intentionally narrow and focuses on readable source files, Git-friendly diffs, and clear errors with line numbers.

## MVP Features

- `model` and `unit mm`
- Variables with safe arithmetic expressions
- `box`
- `cylinder`
- `combine` with `union` and `cut`
- `move`
- `rotate`
- `fillet` with safe failure handling
- `export stl`
- `export step`
- `cq3d build`
- `cq3d validate`

## Installation

Create a virtual environment and install the project dependencies:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
```

If you want the `cq3d` console script, install the package into the virtualenv:

```bash
.venv/bin/python -m pip install -e .
```

## CLI Usage

Validate a file:

```bash
.venv/bin/python -m cq3d.cli validate examples/display_steps.cq3d
```

Build a file and write the exports declared in the document:

```bash
.venv/bin/python -m cq3d.cli build examples/display_steps.cq3d
```

Build a file into a different output directory:

```bash
.venv/bin/python -m cq3d.cli build examples/display_steps.cq3d --out-dir build
```

Relative export paths are resolved from the source `.cq3d` file directory unless `--out-dir` is provided. Absolute export paths are preserved.

## Web Editor

Run the CQ3D editor server:

```bash
.venv/bin/python cq3d_server.py
```

Then open:

- [http://127.0.0.1:5001](http://127.0.0.1:5001)

The web editor provides:

- a CodeMirror-based `.cq3d` editor with autocomplete and syntax highlighting
- Three.js STL preview rendered from backend-generated STL
- download buttons for `.cq3d`, `.stl`, and `.step`

## Example

[`examples/display_steps.cq3d`](/Users/bazyl/Code/Essa3d/examples/display_steps.cq3d) builds a two-step display model with an expected bounding box of about:

- `165 mm` wide on `X`
- `160 mm` deep on `Y`
- `150 mm` tall on `Z`

Source:

```text
model display_steps
unit mm

front_width = 165
side_depth = 160
step_height = 75
step_depth = side_depth / 2

box lower_step
  size front_width side_depth step_height
  at 0 0 0
end

box upper_step
  size front_width step_depth step_height
  at 0 step_depth step_height
end

combine body
  union lower_step upper_step
end

fillet body
  radius 2
end

export stl "exports/display_steps.stl"
export step "exports/display_steps.step"
```

## Syntax Notes

- All dimensions are millimeters.
- Unit suffixes like `10mm` are rejected.
- Variables must be defined before use.
- Variable reassignment is rejected.
- Object ids must be unique.
- Unknown object references fail validation before CadQuery runs.
- Errors are reported as `line N: ...`.

## Running Tests

Run the full suite:

```bash
.venv/bin/python -m pytest
```

Or use the helper script that runs tests and regenerates coverage artifacts:

```bash
bash test.sh
```

Generate an HTML coverage report:

```bash
.venv/bin/python -m coverage run -m pytest
.venv/bin/python -m coverage html
```

Then open [`htmlcov/index.html`](/Users/bazyl/Code/Essa3d/htmlcov/index.html) in the app or browser to inspect line-by-line coverage.

The tests cover:

- expression parsing and evaluation
- parser behavior
- semantic validation
- CadQuery backend geometry
- STL / STEP export generation
- bounding box verification for the example model

## Adding a New DSL Command

Keep the compiler pipeline intact and extend one layer at a time:

1. Add a typed AST node in [`cq3d/ast_nodes.py`](/Users/bazyl/Code/Essa3d/cq3d/ast_nodes.py).
2. Parse the new syntax in [`cq3d/parser.py`](/Users/bazyl/Code/Essa3d/cq3d/parser.py).
3. Add semantic checks in [`cq3d/validator.py`](/Users/bazyl/Code/Essa3d/cq3d/validator.py).
4. Implement geometry generation in [`cq3d/cadquery_backend.py`](/Users/bazyl/Code/Essa3d/cq3d/cadquery_backend.py).
5. Add focused tests in [`tests/`](/Users/bazyl/Code/Essa3d/tests/).

That separation is important: the parser should build AST, not CadQuery objects directly.
