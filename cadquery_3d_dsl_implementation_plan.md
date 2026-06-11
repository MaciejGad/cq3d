# CadQuery 3D Text DSL — Implementation Plan and Architecture

## 1. Purpose

This document describes the recommended architecture and implementation steps for the CadQuery-based 3D text DSL described in `cadquery_3d_dsl_design.md`.

The goal is to build a small but extensible compiler that converts human-editable `.cq3d` files into CadQuery models and exports them to STL, STEP, and optionally generated Python.

The implementation should follow the same philosophy as the existing leathercraft DSL: plain text input, line-based blocks, clear validation errors, no hidden state, and build artifacts generated from source files.

---

## 2. High-level architecture

Recommended pipeline:

```text
.cq3d source file
    ↓
Lexer / line reader
    ↓
Parser
    ↓
AST: ModelDocument, ShapeBlocks, OperationBlocks, ExportCommands
    ↓
Validation and semantic analysis
    ↓
CadQuery compiler backend
    ↓
CadQuery objects registry
    ↓
Export: STL / STEP / Python
```

The compiler should be split into small modules so that parsing, validation, CadQuery generation, and CLI behavior can be tested independently.

---

## 3. Suggested project structure

```text
cadquery_3d_dsl/
  pyproject.toml
  README.md
  examples/
    display_steps.cq3d
    display_steps_improved.cq3d
    phone_stand.cq3d
    mounting_plate.cq3d
  src/
    cq3d_dsl/
      __init__.py
      errors.py
      ast_nodes.py
      expressions.py
      parser.py
      validator.py
      compiler.py
      cadquery_backend.py
      exporters.py
      cli.py
      watcher.py
  tests/
    test_expressions.py
    test_parser.py
    test_validation.py
    test_compile_box.py
    test_compile_cylinder.py
    test_boolean_operations.py
    test_exports.py
    test_examples.py
```

For a first version inside an existing project, it is also acceptable to start with fewer files:

```text
cq3d_dsl.py
examples/
tests/
```

But the long-term version should use separate modules.

---

## 4. Main modules

### 4.1 `errors.py`

Defines user-facing compiler errors.

```python
class Cq3dDslError(Exception):
    def __init__(self, message: str, line: int | None = None): ...
```

Error messages should include line numbers wherever possible:

```text
line 12: unknown object 'base_plate'
line 18: box 'body' is missing required field 'size'
line 25: units are not allowed. Use 'size 165 160 75', not 'size 165mm 160mm 75mm'
```

Errors should be designed for manual editing. A user should understand what to fix without reading internal Python tracebacks.

---

### 4.2 `ast_nodes.py`

Contains dataclasses representing parsed DSL structure.

Suggested classes:

```python
@dataclass
class ModelDocument:
    name: str | None
    unit: str
    variables: dict[str, float]
    commands: list[Command]
    exports: list[ExportCommand]

@dataclass
class ShapeCommand:
    kind: str
    id: str
    fields: dict[str, Any]
    line: int

@dataclass
class OperationCommand:
    kind: str
    id: str | None
    fields: dict[str, Any]
    line: int

@dataclass
class ExportCommand:
    format: str
    path: str | None
    line: int
```

At the beginning, AST nodes can be generic. Later, they can be split into strongly typed nodes such as `BoxNode`, `CylinderNode`, `CombineNode`, and `FilletNode`.

Recommended first approach: use generic nodes to move faster, then introduce typed nodes when the grammar stabilizes.

---

### 4.3 `expressions.py`

Implements safe expression evaluation for variables and numeric fields.

Must not use Python `eval`.

Supported from MVP:

```text
+ - * / parentheses unary + unary -
min max abs round floor ceil
```

Optional later:

```text
sqrt sin cos tan pi
```

Example:

```text
step_depth = side_depth / 2
wall = max(3, front_width / 80)
```

Important rules:

- variables must be defined before use,
- reassignment should be disallowed initially,
- division by zero should produce a clear DSL error,
- unit suffixes such as `mm` should be rejected,
- function names must come from a whitelist.

---

### 4.4 `parser.py`

Responsible for converting text into AST commands.

The parser should be simple and line-based, similar to the leathercraft DSL style.

Supported syntax pattern:

```text
keyword optional_id
  field value value value
  field value
end
```

Example:

```text
box base
  size 165 160 75
  at 0 0 0
end
```

Parser responsibilities:

- remove comments and empty lines,
- track line numbers,
- parse document commands: `model`, `unit`, variable assignments,
- parse blocks: `box`, `cylinder`, `combine`, `fillet`, etc.,
- parse simple inline export commands,
- detect missing `end`,
- detect nested blocks if nesting is not supported.

Comments:

```text
# full line comment
box base  # inline comment should be allowed later, but can be postponed
```

For MVP, full-line comments are enough. Inline comments can be added later.

---

### 4.5 `validator.py`

Performs semantic validation after parsing.

Validation should happen before CadQuery generation so the user receives DSL-level errors instead of CadQuery tracebacks.

Validation responsibilities:

- check required fields for each command,
- check unknown fields,
- check positive dimensions,
- check object IDs are unique,
- check references point to existing objects,
- check export formats are supported,
- check boolean operations have valid input objects,
- check `fillet` and `chamfer` radius/distance are positive,
- check `repeat` count is a positive integer,
- check expressions resolve to numbers,
- check unsupported unit suffixes.

Example validations:

```text
box requires: size
cylinder requires: radius and height, or diameter and height
hole requires: radius/diameter and height, plus target/source depending on chosen syntax
combine requires: one operation and at least two source objects
export requires: stl, step, or python
```

Recommended design: have one validation function per command type:

```python
def validate_box(node, context): ...
def validate_cylinder(node, context): ...
def validate_combine(node, context): ...
```

---

### 4.6 `cadquery_backend.py`

Responsible for creating CadQuery objects from validated AST nodes.

This module should hide all direct CadQuery usage from the parser and validator.

Main concepts:

```python
class BuildContext:
    variables: dict[str, float]
    objects: dict[str, cq.Workplane]
    model_name: str | None
```

Compiler functions:

```python
def build_box(node, ctx) -> cq.Workplane: ...
def build_cylinder(node, ctx) -> cq.Workplane: ...
def build_combine(node, ctx) -> cq.Workplane: ...
def apply_fillet(node, ctx) -> cq.Workplane: ...
```

Important: CadQuery errors should be caught and converted to `Cq3dDslError` where possible.

Example:

```text
line 42: fillet failed on object 'body'. Try a smaller radius or use a more specific edge selector.
```

This is better than exposing:

```text
OCP.OCP.Standard.Standard_Failure: BRep_API: command not done
```

---

### 4.7 `compiler.py`

Coordinates the full build pipeline.

Public functions:

```python
def parse(text: str) -> ModelDocument: ...
def compile_document(doc: ModelDocument) -> BuildResult: ...
def build_file(path: str | Path) -> BuildResult: ...
```

Suggested `BuildResult`:

```python
@dataclass
class BuildResult:
    document: ModelDocument
    objects: dict[str, cq.Workplane]
    final_object: cq.Workplane | None
    exports: list[Path]
```

The compiler should determine the final object by one of these rules:

1. if a `combine body` or `object body` exists, use `body`,
2. otherwise use the last created object,
3. later: support `final <object_id>` command.

Recommended explicit final command for future:

```text
final body
```

---

### 4.8 `exporters.py`

Exports CadQuery objects to files.

Supported MVP exports:

```text
export stl "file.stl"
export step "file.step"
export python "generated.py"
```

CadQuery mapping:

```python
cq.exporters.export(obj, "output.stl")
cq.exporters.export(obj, "output.step")
```

Export behavior:

- if no export command is present, export `<model_name>.stl`,
- create output directories if needed,
- avoid overwriting the source file,
- optionally support `--out-dir` from CLI.

Generated Python export should be useful for debugging and learning CadQuery. It does not need to be perfect in the MVP.

---

### 4.9 `cli.py`

Command-line interface.

Recommended CLI:

```bash
cq3d build model.cq3d
cq3d build model.cq3d --out-dir exports
cq3d validate model.cq3d
cq3d render model.cq3d
cq3d watch examples
```

MVP commands:

```bash
python -m cq3d_dsl build examples/display_steps.cq3d
python -m cq3d_dsl validate examples/display_steps.cq3d
```

Later:

```bash
cq3d build-all examples
cq3d watch examples
cq3d export-python examples/display_steps.cq3d
```

---

### 4.10 `watcher.py`

Optional but useful for development.

A watcher can rebuild `.cq3d` files after every save, similar to the leathercraft watcher.

Minimal implementation:

- scan directory recursively for `*.cq3d`,
- store modification times,
- rebuild changed files every 1 second,
- print errors without stopping the watcher.

Command:

```bash
cq3d watch examples
```

---

## 5. Supported MVP language

The first implementation should be small enough to finish quickly, but useful enough to model real parts.

### MVP document commands

```text
model <name>
unit mm
name = expression
export stl "file.stl"
export step "file.step"
```

### MVP primitives

```text
box
cylinder
prism
```

### MVP operations

```text
combine union/cut/intersect
move
rotate
fillet
chamfer
shell
repeat linear
```

### MVP final object rule

Use this priority:

1. object named `body`,
2. last combined object,
3. last created shape.

Later add:

```text
final body
```

---

## 6. First grammar draft

### 6.1 Variables

```text
front_width = 165
side_depth = 160
step_height = 75
step_depth = side_depth / 2
```

### 6.2 Box

```text
box <id>
  size <x> <y> <z>
  [at <x> <y> <z>]
  [center true|false]
end
```

### 6.3 Cylinder

```text
cylinder <id>
  radius <r>
  height <h>
  [at <x> <y> <z>]
  [axis x|y|z]
end
```

Alternative diameter form:

```text
cylinder peg
  diameter 8
  height 20
end
```

### 6.4 Prism

```text
prism <id>
  height <h>
  points
    <x> <y>
    <x> <y>
    <x> <y>
  end
end
```

This maps to a 2D polygon extruded along Z.

### 6.5 Combine

```text
combine <id>
  union <a> <b> [c...]
end
```

```text
combine <id>
  cut <base> <tool1> [tool2...]
end
```

```text
combine <id>
  intersect <a> <b>
end
```

### 6.6 Move

Two possible styles:

```text
move <source> as <id>
  by <x> <y> <z>
end
```

or simpler:

```text
move <id>
  by <x> <y> <z>
end
```

Recommended MVP: in-place transform by object ID:

```text
move upper
  by 0 80 75
end
```

### 6.7 Rotate

```text
rotate <id>
  around z
  angle 90
end
```

Later support pivot:

```text
rotate bracket
  around z
  angle 45
  origin 0 0 0
end
```

### 6.8 Fillet

```text
fillet <id>
  radius 2
  edges all
end
```

MVP can support only `edges all`.

But because global fillets can fail in CadQuery, the implementation should catch the error and show a helpful message.

Later edge selectors:

```text
edges top
edges bottom
edges vertical
edges x
edges y
edges z
edges visible
```

### 6.9 Chamfer

```text
chamfer <id>
  distance 1
  edges all
end
```

### 6.10 Shell / hollow

```text
shell <id>
  wall 4
  open bottom
end
```

This should map to CadQuery shell operations where possible. If CadQuery shell is unstable for a shape, an alternative implementation can use boolean cutouts for boxes and stair-like shapes.

### 6.11 Repeat linear

```text
repeat linear screw_hole as holes
  count 4
  step 40 0 0
end
```

MVP may instead use explicit `grid` or postpone repeat. If implemented early, repeat should create a combined object or a named group.

---

## 7. Example: display steps MVP

```text
model display_steps
unit mm

front_width = 165
side_depth = 160
step_height = 75
step_depth = side_depth / 2

box lower
  size front_width side_depth step_height
  at 0 0 0
end

box upper
  size front_width step_depth step_height
  at 0 step_depth step_height
end

combine body
  union lower upper
end

fillet body
  radius 2
  edges all
end

export stl "exports/display_steps.stl"
export step "exports/display_steps.step"
```

---

## 8. Example: display steps with practical features

```text
model display_steps_improved
unit mm

front_width = 165
side_depth = 160
step_height = 75
step_depth = side_depth / 2
wall = 4
lip_height = 5
lip_thickness = 4
rib_thickness = 4

box lower
  size front_width side_depth step_height
  at 0 0 0
end

box upper
  size front_width step_depth step_height
  at 0 step_depth step_height
end

box lip_front
  size front_width lip_thickness lip_height
  at 0 0 step_height
end

box lip_upper
  size front_width lip_thickness lip_height
  at 0 step_depth step_height * 2
end

box rib_left
  size rib_thickness side_depth step_height * 2
  at front_width / 3 0 0
end

box rib_right
  size rib_thickness side_depth step_height * 2
  at front_width * 2 / 3 0 0
end

combine body
  union lower upper lip_front lip_upper rib_left rib_right
end

fillet body
  radius 1.5
  edges all
end

export stl "exports/display_steps_improved.stl"
export step "exports/display_steps_improved.step"
```

This example is intentionally still simple. True hollowing can be added with `shell` or with cutout primitives once the MVP is stable.

---

## 9. Implementation phases

## Phase 0 — Project setup

Goal: create a runnable package and test harness.

Tasks:

1. Create project structure.
2. Add `pyproject.toml`.
3. Add dependencies:
   - `cadquery`,
   - `pytest`,
   - optional: `watchdog` for file watching.
4. Add `examples/display_steps.cq3d`.
5. Add CLI entry point.

Suggested `pyproject.toml` dependencies:

```toml
[project]
dependencies = [
  "cadquery",
]

[project.optional-dependencies]
dev = [
  "pytest",
]
```

Acceptance criteria:

```bash
python -m cq3d_dsl --help
pytest
```

---

## Phase 1 — Safe expressions

Goal: evaluate numbers and variables safely.

Tasks:

1. Implement AST-based expression evaluator.
2. Support arithmetic operators.
3. Support `min`, `max`, `abs`, `round`, `floor`, `ceil`.
4. Reject unit suffixes.
5. Reject unknown variables.
6. Add line-number-aware errors.

Tests:

```text
width = 165
height = width / 2
radius = min(5, width / 20)
```

Test errors:

```text
size 10mm 20 30
unknown variable
unsupported function
reassignment
division by zero
```

Acceptance criteria:

- all numeric fields can use expressions,
- invalid expressions produce clear DSL errors.

---

## Phase 2 — Parser MVP

Goal: parse document commands, variables, and simple blocks.

Tasks:

1. Parse `model`.
2. Parse `unit mm`.
3. Parse variable assignments.
4. Parse block commands:
   - `box`,
   - `cylinder`,
   - `combine`,
   - `fillet`,
   - `chamfer`.
5. Parse `export` commands.
6. Preserve line numbers.
7. Detect missing `end`.

Acceptance criteria:

The parser can parse `examples/display_steps.cq3d` into a `ModelDocument`.

---

## Phase 3 — Validation MVP

Goal: validate DSL semantics before calling CadQuery.

Tasks:

1. Ensure object IDs are unique.
2. Ensure references exist.
3. Validate required fields.
4. Validate dimensions are positive.
5. Validate export formats.
6. Validate `combine` syntax.
7. Validate `fillet` and `chamfer` values.

Acceptance criteria:

Invalid files fail with clear messages such as:

```text
line 11: box 'upper' is missing required field 'size'
line 20: combine 'body' references unknown object 'uppper'
```

---

## Phase 4 — CadQuery backend MVP

Goal: generate real CadQuery objects.

Tasks:

1. Implement `box`.
2. Implement `cylinder`.
3. Implement `combine union`.
4. Implement `combine cut`.
5. Implement `fillet` with error handling.
6. Implement `chamfer` with error handling.
7. Store objects in registry by ID.
8. Determine final object.

Important implementation detail for `box`:

CadQuery boxes are centered by default. The DSL should use lower-front-left corner placement by default. Implement helper:

```python
def make_box(size_x, size_y, size_z, at_x, at_y, at_z):
    return (
        cq.Workplane("XY")
        .box(size_x, size_y, size_z)
        .translate((at_x + size_x / 2, at_y + size_y / 2, at_z + size_z / 2))
    )
```

Acceptance criteria:

`display_steps.cq3d` exports a valid STL and STEP.

---

## Phase 5 — Exporter MVP

Goal: write STL and STEP files.

Tasks:

1. Implement `export stl`.
2. Implement `export step`.
3. Create output directories automatically.
4. Use default export when no explicit export is present.
5. Print generated paths.

Example output:

```text
Generated:
exports/display_steps.stl
exports/display_steps.step
```

Acceptance criteria:

Running:

```bash
cq3d build examples/display_steps.cq3d
```

produces:

```text
exports/display_steps.stl
exports/display_steps.step
```

---

## Phase 6 — CLI

Goal: make the tool convenient to use from terminal.

Tasks:

1. `build` command.
2. `validate` command.
3. `--out-dir` option.
4. `--verbose` option.
5. Good exit codes:
   - `0` success,
   - `1` DSL error,
   - `2` unexpected internal error.

Commands:

```bash
cq3d validate examples/display_steps.cq3d
cq3d build examples/display_steps.cq3d
cq3d build examples/display_steps.cq3d --out-dir exports
```

Acceptance criteria:

A broken DSL file prints a clean error and exits with non-zero status.

---

## Phase 7 — More useful primitives

Goal: make the DSL practical for common 3D printed models.

Add:

```text
rounded_box
sphere
cone
wedge
text3d
screw_hole
rib
lip
```

Recommended order:

1. `rounded_box`
2. `hole` / `screw_hole`
3. `rib`
4. `lip`
5. `text3d`

These are high-value because they map to common printed parts.

---

## Phase 8 — Better operations

Goal: improve expressive power without making the language hard to learn.

Add:

```text
mirror
repeat linear
repeat grid
shell / hollow
align
copy
```

Example:

```text
repeat grid foot as feet
  count 2 2
  step 130 120 0
end
```

Example:

```text
shell body
  wall 4
  open bottom
end
```

---

## Phase 9 — Edge selectors

Goal: avoid fragile global fillets.

Global `edges all` can fail in CadQuery. Edge selectors should allow filleting only selected groups.

Initial selector tokens:

```text
all
top
bottom
vertical
x
 y
z
front
back
left
right
```

Recommended implementation approach:

- start with broad CadQuery selectors where possible,
- expose only stable selectors,
- if selector is unsupported for a shape, produce a clear error.

Example DSL:

```text
fillet body
  radius 2
  edges top vertical
end
```

Possible backend mapping:

```python
obj.edges("|Z").fillet(radius)    # vertical edges
obj.edges(">Z").fillet(radius)    # top-facing edges, depending on actual selector needs
```

Selectors should be introduced carefully and tested with real models.

---

## Phase 10 — Generated Python export

Goal: support debugging and learning.

Command:

```text
export python "generated/display_steps.py"
```

The generated Python should:

- import CadQuery,
- define variables,
- create objects in the same order as DSL,
- export final STL/STEP,
- include comments with source line numbers where useful.

This is valuable because users can inspect how the DSL maps to CadQuery.

---

## Phase 11 — Watch mode

Goal: fast iteration while editing `.cq3d` files.

Command:

```bash
cq3d watch examples
```

Behavior:

- rebuild changed files,
- print success or DSL errors,
- do not crash on errors,
- optionally rebuild all files at startup with `--build-all`.

---

## Phase 12 — Documentation and examples

Goal: make the DSL easy to learn.

Documents to create:

```text
README.md
CQ3D_DSL_REFERENCE.md
CQ3D_EXAMPLES.md
CQ3D_IMPLEMENTATION.md
```

Examples to include:

```text
display_steps.cq3d
display_steps_improved.cq3d
phone_stand.cq3d
mounting_plate.cq3d
rounded_box_with_lid.cq3d
clip.cq3d
```

Each example should include:

- DSL source,
- generated STL path,
- expected bounding box,
- print notes.

---

## 10. Testing strategy

Testing should be layered.

### 10.1 Expression tests

Test safe evaluator independently.

Examples:

```python
def test_expression_uses_previous_variable(): ...
def test_expression_rejects_unknown_variable(): ...
def test_expression_rejects_eval_escape(): ...
```

### 10.2 Parser tests

Input text → AST.

Test:

- blocks,
- missing `end`,
- variable parsing,
- export parsing,
- line numbers.

### 10.3 Validation tests

Invalid AST/text → clear error.

Test:

- unknown object references,
- missing fields,
- negative dimensions,
- duplicate object IDs.

### 10.4 Backend geometry tests

Generated CadQuery object → expected bounding box.

Example:

```python
bbox = result.val().BoundingBox()
assert bbox.xlen == pytest.approx(165)
assert bbox.ylen == pytest.approx(160)
assert bbox.zlen == pytest.approx(150)
```

This is the most important practical test for the DSL.

### 10.5 Export tests

Build example file and verify files exist:

```python
assert Path("display_steps.stl").exists()
assert Path("display_steps.step").exists()
```

Do not check binary file contents in detail at first.

### 10.6 Example tests

Every example in `examples/` should compile successfully.

```python
@pytest.mark.parametrize("path", Path("examples").glob("*.cq3d"))
def test_example_builds(path): ...
```

### 10.7 Regression tests

When a real model fails, add a minimal `.cq3d` file reproducing the issue.

Especially important for:

- failed fillets,
- shell failures,
- boolean operation failures,
- invalid geometry.

---

## 11. Error handling strategy

The DSL compiler should avoid exposing raw CadQuery/OCP tracebacks for expected modeling problems.

For example, this raw error:

```text
OCP.OCP.Standard.Standard_Failure: BRep_API: command not done
```

Should become:

```text
line 38: fillet failed on object 'body' with radius 2.
Try a smaller radius or select fewer edges.
```

Recommended approach:

```python
try:
    obj = obj.edges().fillet(radius)
except Exception as exc:
    raise Cq3dDslError(
        f"fillet failed on object '{object_id}' with radius {radius}. "
        "Try a smaller radius or select fewer edges.",
        line=node.line,
    ) from exc
```

---

## 12. Object registry

The backend should maintain an object registry.

```python
objects = {
    "lower": cq.Workplane,
    "upper": cq.Workplane,
    "body": cq.Workplane,
}
```

Rules:

- Shape blocks create new objects.
- `combine <id>` creates a new object.
- Transform operations can either mutate an existing object or create a new object.
- For MVP, use in-place mutation for simple operations like `move body`.
- Later, add `as <new_id>` for non-destructive operations.

Future syntax:

```text
move body as shifted_body
  by 10 0 0
end
```

---

## 13. Coordinate and placement policy

CadQuery often centers shapes by default. The DSL should use more practical placement.

Recommended DSL default:

- `at x y z` means lower-front-left corner for `box`,
- `at x y z` means center of bottom face for `cylinder`,
- objects sit on the print bed if `z = 0`,
- `center true` can be added for users who want CAD-style center placement.

Box mapping:

```python
box(size_x, size_y, size_z)
translate((x + size_x/2, y + size_y/2, z + size_z/2))
```

Cylinder mapping along Z:

```python
cylinder(height, radius)
translate((x, y, z + height/2))
```

---

## 14. Implementation details for key primitives

### 14.1 Box

DSL:

```text
box base
  size 100 50 20
  at 0 0 0
end
```

CadQuery:

```python
cq.Workplane("XY").box(100, 50, 20).translate((50, 25, 10))
```

### 14.2 Cylinder

DSL:

```text
cylinder peg
  diameter 8
  height 20
  at 20 20 0
end
```

CadQuery:

```python
cq.Workplane("XY").cylinder(20, 4).translate((20, 20, 10))
```

### 14.3 Combine union

DSL:

```text
combine body
  union lower upper
end
```

CadQuery:

```python
body = lower.union(upper)
```

### 14.4 Combine cut

DSL:

```text
combine body
  cut base hole1 hole2
end
```

CadQuery:

```python
body = base.cut(hole1).cut(hole2)
```

### 14.5 Fillet

DSL:

```text
fillet body
  radius 2
  edges all
end
```

CadQuery:

```python
body = body.edges().fillet(2)
```

But this must be wrapped in error handling.

---

## 15. Milestone plan

### Milestone 1 — First working build

Scope:

- variables,
- `box`,
- `combine union`,
- `export stl`,
- CLI `build`.

Example should generate a simple two-step display stand.

### Milestone 2 — Useful modeling

Add:

- `cylinder`,
- `combine cut`,
- `fillet`,
- `chamfer`,
- `export step`,
- bounding box reporting.

### Milestone 3 — Practical 3D printing features

Add:

- `shell`,
- `rib`,
- `lip`,
- `screw_hole`,
- `repeat linear`,
- `repeat grid`.

### Milestone 4 — Developer experience

Add:

- `validate`,
- `watch`,
- generated Python export,
- example tests,
- improved error messages.

### Milestone 5 — Advanced CAD operations

Add:

- `loft`,
- `sweep`,
- better edge selectors,
- text engraving/embossing,
- threads or approximate printable threads.

---

## 16. Recommended MVP implementation order

The most efficient order is:

1. `Cq3dDslError`
2. expression evaluator
3. parser for variables and blocks
4. AST dataclasses
5. validator for `box` and `combine`
6. CadQuery backend for `box`
7. CadQuery backend for `combine union`
8. STL export
9. CLI build
10. tests for bounding box
11. `cylinder`
12. `combine cut`
13. STEP export
14. `fillet` with safe error handling
15. examples and documentation

Do not start with `shell`, `loft`, or advanced selectors. They are useful but will slow down the first working version.

---

## 17. Minimal public Python API

The library should expose a small API:

```python
from cq3d_dsl import parse, compile_document, build_file, Cq3dDslError
```

Usage:

```python
from cq3d_dsl import build_file

result = build_file("examples/display_steps.cq3d")
print(result.exports)
```

---

## 18. Example CLI output

Successful build:

```text
Building examples/display_steps.cq3d
Model: display_steps
Final object: body
Bounding box:
  X: 165.00 mm
  Y: 160.00 mm
  Z: 150.00 mm
Generated:
  exports/display_steps.stl
  exports/display_steps.step
```

Validation error:

```text
Build failed:
line 14: combine 'body' references unknown object 'uppper'
```

CadQuery modeling error:

```text
Build failed:
line 24: fillet failed on object 'body' with radius 3.
Try a smaller radius or select fewer edges.
```

---

## 19. Design decisions to keep stable

These decisions should not change casually after users start writing files:

1. file extension `.cq3d`,
2. millimeters only,
3. `end` closes blocks,
4. `at` placement policy,
5. source files are the source of truth,
6. generated STL/STEP are artifacts,
7. variables use `name = expression`, no `let`,
8. clear line-numbered errors,
9. CadQuery is an implementation detail, not part of DSL syntax.

---

## 20. Future extension ideas

Possible future features:

```text
include "common_parts.cq3d"
module / component definitions
parameters from CLI
materials and print profiles
preview PNG generation
automatic orientation suggestions
support warnings for thin walls
thread generation
snap-fit helper primitives
rounded stair/profile helper
```

Example future module syntax:

```text
component screw_mount name
  diameter = 8
  height = 12

  cylinder body
    diameter diameter
    height height
  end
end
```

This should be postponed until the basic compiler is reliable.

---

## 21. Summary

The implementation should start small: variables, parser, AST, validation, `box`, `combine union`, STL export, and CLI. Once this pipeline works, add cylinders, cuts, STEP export, fillets, and 3D-printing helpers such as ribs, lips, screw holes, and shelling.

The most important architectural rule is to keep the DSL independent from CadQuery internals. CadQuery should be the backend, not the language users have to learn.
