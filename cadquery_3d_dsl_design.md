# CadQuery 3D Text DSL — Design Document

## 1. Goal

The goal is to create a simple text-based DSL for generating 3D printable objects. The DSL should be easy to edit manually, friendly to Git diffs, and expressive enough to describe practical 3D models such as stands, boxes, clips, organizers, adapters, holders, display steps, brackets, lids, and simple mechanical parts.

The DSL will compile into Python code using CadQuery internally. The primary export target is STL for 3D printing. STEP export should also be supported because it is useful for CAD inspection and further editing.

The language is inspired by the existing leathercraft SVG DSL: it is line-based, block-oriented, uses millimeters by default, supports variables and expressions, and avoids verbose syntax. The user should be able to describe one object after another without writing Python code.

---

## 2. Core principles

1. **Text first**  
   The source of truth is a plain text file, for example `display_steps.cq3d`. Generated `.stl`, `.step`, or `.py` files are build artifacts.

2. **Git friendly**  
   The DSL must avoid binary state, hidden metadata, GUI-only operations, and unstable ordering. A small dimension change should produce a small readable diff.

3. **Millimeters only**  
   All dimensions are in millimeters. Unit suffixes such as `mm`, `cm`, or `in` are not allowed in numeric values.

4. **Parametric by default**  
   Variables and expressions should be supported from the beginning.

5. **Readable over clever**  
   The DSL should be understandable by someone who knows basic geometry but not CadQuery.

6. **CadQuery underneath**  
   The compiler should build CadQuery objects internally and export STL/STEP.

7. **Safe expressions**  
   Expressions should use a safe AST evaluator, not Python `eval`.

8. **Progressive complexity**  
   Simple models should be very easy. Advanced operations should exist, but they should not make basic files noisy.

---

## 3. File extension

Suggested extension:

```text
.cq3d
```

Alternative names:

```text
.model3d
.cad3d
.l3d
```

Recommended: `.cq3d`, because it makes the CadQuery backend explicit without exposing Python code.

---

## 4. Basic file structure

```text
model display_steps
unit mm

front_width = 165
side_depth = 160
step_height = 75

box lower
  size front_width side_depth step_height
  at 0 0 0
end

box upper
  size front_width side_depth / 2 step_height
  at 0 side_depth / 2 step_height
end

combine body
  union lower upper
end

export stl "display_steps.stl"
export step "display_steps.step"
```

A file may contain:

- document metadata,
- variables,
- shape blocks,
- operation blocks,
- export commands.

---

## 5. Coordinate system

The DSL should use a clear 3D coordinate system:

```text
X = width / left-right / front width
Y = depth / front-back / side depth
Z = height / vertical axis
```

Recommended convention:

- `X` grows to the right,
- `Y` grows toward the back,
- `Z` grows upward,
- the print bed is the `XY` plane,
- `Z = 0` is the bottom of the model.

Default object placement should be practical for 3D printing: when possible, objects should sit on `Z = 0`.

---

## 6. Document-level commands

### `model`

```text
model <name>
```

Optional model name. Used as the default export filename if no explicit export filename is given.

Example:

```text
model phone_stand
```

### `unit`

```text
unit mm
```

Only `mm` is supported at the beginning. The command exists to make the file self-documenting.

### Variables

```text
name = expression
```

Examples:

```text
width = 165
height = 75 * 2
wall = 4
radius = min(5, wall)
```

Recommended expression support:

```text
+ - * / parentheses
min max abs round floor ceil
```

Optional later:

```text
sin cos tan sqrt pi
```

Rules:

- variables must be defined before use,
- reassignment is not allowed initially,
- variable names use `[A-Za-z_][A-Za-z0-9_]*`,
- structural keywords such as `box`, `end`, `cut`, `export` are reserved.

---

## 7. Initial supported primitives

The first version should focus on shapes that are useful for real printed parts.

### 7.1 `box`

A rectangular cuboid.

```text
box <id>
  size <x> <y> <z>
  [at <x> <y> <z>]
  [center true|false]
  [fillet <radius>]
  [chamfer <distance>]
end
```

Example:

```text
box base
  size 165 160 75
  at 0 0 0
end
```

Default behavior:

- `at` means lower-front-left corner by default,
- `center false` by default,
- object rests on `Z = 0` if `at z=0`.

CadQuery mapping:

- `cq.Workplane("XY").box(...)`, with placement adjusted for lower-corner positioning.

---

### 7.2 `rounded_box`

A box with selected rounded edges.

```text
rounded_box <id>
  size <x> <y> <z>
  [at <x> <y> <z>]
  radius <r>
  [edges all|vertical|top|bottom|front|back|left|right]
end
```

Example:

```text
rounded_box body
  size 165 160 150
  at 0 0 0
  radius 3
  edges vertical top
end
```

Implementation note: avoid global `model.edges().fillet(...)` on complex models. Fillets should be applied as early and as locally as possible.

---

### 7.3 `cylinder`

A cylinder or round hole cutter.

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

Example:

```text
cylinder screw_hole
  diameter 4
  height 20
  at 20 20 0
  axis z
end
```

---

### 7.4 `sphere`

Useful for decorative shapes, knobs, rounded endpoints, and tests.

```text
sphere <id>
  radius <r>
  at <x> <y> <z>
end
```

---

### 7.5 `cone`

Useful for countersinks, funnels, tapered feet, and decorative shapes.

```text
cone <id>
  radius1 <bottom_radius>
  radius2 <top_radius>
  height <h>
  [at <x> <y> <z>]
  [axis x|y|z]
end
```

Example:

```text
cone countersink
  radius1 5
  radius2 2
  height 3
  axis z
end
```

---

### 7.6 `wedge`

A sloped prism, useful for ramps, angled stands, and supports.

```text
wedge <id>
  size <x> <y> <z>
  slope along_x|along_y
  [at <x> <y> <z>]
end
```

Example:

```text
wedge ramp
  size 100 60 30
  slope along_y
  at 0 0 0
end
```

---

### 7.7 `prism`

Extrudes a 2D polygon along one axis. This is important because it gives the DSL a simple way to describe custom profiles.

```text
prism <id>
  plane xy|xz|yz
  height <h>
  points
    <a> <b>
    <a> <b>
    <a> <b>
  end
  [at <x> <y> <z>]
end
```

Example: two-step side profile extruded across width.

```text
prism steps
  plane yz
  height 165
  points
    0 0
    160 0
    160 150
    80 150
    80 75
    0 75
  end
end
```

---

### 7.8 `text3d`

Optional for v1, but useful for labels and embossing.

```text
text3d <id>
  text "YARN"
  size 12
  depth 1.2
  at <x> <y> <z>
  plane xy|xz|yz
end
```

This can be used with `union` for raised text or `cut` for engraved text.

---

## 8. Object placement and transforms

Transforms should be available either inside shape blocks or as standalone operation blocks.

### 8.1 Inline placement

```text
box base
  size 100 60 10
  at 0 0 0
end
```

### 8.2 Move

```text
move <object_id>
  by <x> <y> <z>
end
```

or inline:

```text
box peg
  size 10 10 20
  move 20 0 0
end
```

Recommended for the initial version: support `at` inside blocks and postpone standalone `move` if needed.

### 8.3 Rotate

```text
rotate <object_id>
  x <deg>
  y <deg>
  z <deg>
end
```

Alternative inline:

```text
rotate x=90 y=0 z=0
```

### 8.4 Mirror

```text
mirror <object_id>
  axis x|y|z
  origin <x> <y> <z>
end
```

Useful for symmetric brackets, pairs of holes, and repeated features.

### 8.5 Scale

Scale should be supported carefully. For 3D printing it is often better to change dimensions directly. If included:

```text
scale <object_id>
  factor <s>
end
```

Optional non-uniform:

```text
scale <object_id>
  factors <x> <y> <z>
end
```

---

## 9. Boolean operations

Boolean operations are essential.

### 9.1 `union`

Combines objects.

```text
combine body
  union base back support
end
```

### 9.2 `cut`

Subtracts cutters from a target.

```text
combine body
  union base back
  cut cable_hole screw_hole_1 screw_hole_2
end
```

### 9.3 `intersect`

Keeps only overlapping volume.

```text
combine result
  intersect part_a part_b
end
```

### 9.4 Recommended combine block syntax

```text
combine <id>
  union <object_id> <object_id> ...
  cut <object_id> <object_id> ...
end
```

Example:

```text
combine body
  union lower_step upper_step lip_front lip_upper rib_1 rib_2
  cut foot_recess_1 foot_recess_2 foot_recess_3 foot_recess_4
end
```

The compiler should process operations in order.

---

## 10. Repetition and patterns

Repetition is very important for holes, ribs, pegs, vents, grids, and decorative patterns.

### 10.1 Repeat along one axis

```text
repeat x from -60 to 60 count 4
  cylinder hole
    diameter 4
    height 20
    at $x 20 0
  end
end
```

### 10.2 Repeat with step

```text
repeat x from 10 to 150 step 20
  cylinder vent
    diameter 5
    height 6
    at $x 20 0
  end
end
```

### 10.3 Grid

```text
grid holes
  x from 20 to 140 count 4
  y from 20 to 80 count 3
  make cylinder
    diameter 4
    height 20
    at $x $y 0
  end
end
```

### 10.4 Mirror copies

```text
mirror_copy screw_hole
  axis x
  origin 82.5 0 0
end
```

or for a pair:

```text
pair screw_holes
  around x=82.5
  distance 60
  make cylinder
    diameter 4
    height 20
    at $x 20 0
  end
end
```

Initial implementation can start with `repeat` and postpone `grid`/`pair`.

---

## 11. Higher-level helper features

These are not primitive shapes but practical shortcuts that make the DSL powerful.

### 11.1 Holes

```text
hole <id>
  diameter <d>
  depth <h|through>
  at <x> <y> <z>
  axis x|y|z
end
```

A `hole` should compile to a cylinder cutter.

Example:

```text
hole cable
  diameter 14
  depth through
  at 82.5 0 35
  axis y
end
```

### 11.2 Screw holes

```text
screw_hole <id>
  diameter 4
  countersink 8 depth 3
  depth through
  at <x> <y> <z>
  axis z
end
```

This should generate one or two cutters: a through cylinder and optional countersink cone/cylinder.

### 11.3 Fillet and chamfer commands

```text
fillet body
  radius 3
  edges top front vertical
end
```

```text
chamfer body
  distance 1
  edges bottom
end
```

Important implementation note: CadQuery can fail when filleting complex shapes after many boolean operations. The compiler should prefer targeted fillets and provide clear warnings.

### 11.4 Shell / hollow

```text
shell body
  wall 4
  open bottom
end
```

This is useful for saving filament.

Potential mapping:

- CadQuery `.shell(-wall)` on selected face,
- or manual creation of internal cutters for predictable shapes.

For v1, `shell` can be postponed if it is difficult to implement reliably. A more predictable alternative is to provide a `hollow_box` primitive.

### 11.5 Ribs

```text
rib <id>
  size <x> <y> <z>
  at <x> <y> <z>
end
```

A rib can just compile to a thin `box`, but naming it makes files easier to read.

### 11.6 Lips / retaining edges

Useful for display stands and trays.

```text
lip <id>
  along front|back|left|right
  length <l>
  thickness <t>
  height <h>
  at <x> <y> <z>
end
```

Could compile to a small rounded or rectangular box.

---

## 12. Suggested v1 supported operations

Minimum useful set:

```text
union
cut
move / at
rotate
repeat
fillet
chamfer
export stl
export step
```

Recommended near-term set:

```text
mirror
shell or hollow_box
grid
screw_hole
text3d
```

Later advanced set:

```text
loft
sweep
thread
helix
offset
workplane selection
face selection
edge selection
assemblies
```

---

## 13. Edge and face selection

CadQuery has powerful selectors, but exposing them directly would make the DSL harder to learn. The DSL should start with named, human-friendly selectors.

### Named faces

```text
top
bottom
front
back
left
right
```

Mapping:

```text
top    = +Z
bottom = -Z
front  = -Y
back   = +Y
left   = -X
right  = +X
```

### Named edge groups

```text
all
top
bottom
vertical
horizontal
front
back
left
right
visible
```

`visible` can mean top/front/vertical aesthetic edges, but it should be clearly documented because it is subjective.

### Advanced selector escape hatch

Optional later:

```text
cadquery_selector ">Z"
```

This should not be required for normal models.

---

## 14. Exports

### STL

```text
export stl "output.stl"
```

### STEP

```text
export step "output.step"
```

### Python debug export

```text
export python "generated_model.py"
```

This can be very useful for debugging and learning CadQuery.

### Default export

If the file has:

```text
model display_steps
```

and no export command, default outputs could be:

```text
display_steps.stl
display_steps.step
```

---

## 15. Example files

### 15.1 Simple two-step display stand

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
  edges vertical top
end

export stl "display_steps.stl"
export step "display_steps.step"
```

---

### 15.2 Improved display stand with lips and ribs

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

box lower_step
  size front_width side_depth step_height
  at 0 0 0
end

box upper_step
  size front_width step_depth step_height
  at 0 step_depth step_height
end

lip lower_lip
  along front
  length front_width
  thickness lip_thickness
  height lip_height
  at 0 0 step_height
end

lip upper_lip
  along front
  length front_width
  thickness lip_thickness
  height lip_height
  at 0 step_depth step_height * 2
end

rib rib_left
  size rib_thickness side_depth step_height * 2
  at front_width * 0.25 0 0
end

rib rib_right
  size rib_thickness side_depth step_height * 2
  at front_width * 0.75 0 0
end

hole foot_recess_1
  diameter 14
  depth 1.5
  at 15 15 0
  axis z
end

hole foot_recess_2
  diameter 14
  depth 1.5
  at front_width - 15 15 0
  axis z
end

hole foot_recess_3
  diameter 14
  depth 1.5
  at 15 side_depth - 15 0
  axis z
end

hole foot_recess_4
  diameter 14
  depth 1.5
  at front_width - 15 side_depth - 15 0
  axis z
end

combine body
  union lower_step upper_step lower_lip upper_lip rib_left rib_right
  cut foot_recess_1 foot_recess_2 foot_recess_3 foot_recess_4
end

fillet body
  radius 2
  edges visible
end

export stl "display_steps_improved.stl"
export step "display_steps_improved.step"
```

---

### 15.3 Phone stand

```text
model phone_stand
unit mm

width = 90
depth = 75
base_height = 8
back_height = 85
wall = 5
slot_width = 14
slot_depth = 10

box base
  size width depth base_height
  at 0 0 0
end

box back
  size width wall back_height
  at 0 depth - wall base_height
end

box front_lip
  size width wall 8
  at 0 0 base_height
end

box phone_slot
  size width - 20 slot_depth base_height + 2
  at 10 8 0
end

hole cable
  diameter 16
  depth through
  axis y
  at width / 2 depth - wall / 2 25
end

combine body
  union base back front_lip
  cut phone_slot cable
end

fillet body
  radius 3
  edges visible
end

export stl "phone_stand.stl"
```

---

### 15.4 Box with screw holes

```text
model mounting_plate
unit mm

width = 100
depth = 60
height = 5
hole_d = 4
margin = 10

box plate
  size width depth height
  at 0 0 0
end

repeat x from margin to width - margin count 2
  repeat y from margin to depth - margin count 2
    hole screw
      diameter hole_d
      depth through
      axis z
      at $x $y 0
    end
  end
end

combine body
  union plate
  cut screw
end

fillet body
  radius 2
  edges top
end

export stl "mounting_plate.stl"
export step "mounting_plate.step"
```

Compiler note: repeated blocks should generate unique internal object IDs, for example `screw_1`, `screw_2`, etc. The `cut screw` command should be able to refer to all generated objects from the repeated block, or the compiler should provide an explicit group name.

---

### 15.5 Custom side profile using prism

```text
model custom_steps_from_profile
unit mm

front_width = 165
side_depth = 160
step_height = 75

prism body
  plane yz
  height front_width
  points
    0 0
    side_depth 0
    side_depth step_height * 2
    side_depth / 2 step_height * 2
    side_depth / 2 step_height
    0 step_height
  end
end

fillet body
  radius 2
  edges visible
end

export stl "custom_steps_from_profile.stl"
```

---

## 16. Compiler architecture

Suggested Python modules:

```text
cadquery_dsl/
  __init__.py
  ast.py
  parser.py
  expressions.py
  compiler.py
  exporters.py
  errors.py
  cli.py
  watch.py
examples/
  display_steps.cq3d
  phone_stand.cq3d
  mounting_plate.cq3d
```

### 16.1 Parser

The parser should:

- read line-based blocks,
- ignore empty lines and comments,
- support nested blocks later for `repeat`,
- produce a typed AST,
- attach line numbers to all nodes for good errors.

### 16.2 Expression evaluator

The expression evaluator should:

- use Python AST safely,
- support numeric operations only,
- support a whitelist of functions,
- reject unknown variables,
- reject strings except where explicitly expected, such as export filenames.

### 16.3 Compiler

The compiler should:

- convert each shape block into a CadQuery object,
- store named objects in a registry,
- process `combine` blocks in order,
- process transform and post-processing operations,
- export final object.

### 16.4 Object registry

The compiler should keep:

```python
objects: dict[str, cq.Workplane]
groups: dict[str, list[str]]
model_name: str
variables: dict[str, float]
exports: list[ExportCommand]
```

### 16.5 Build flow

```text
read file
parse lines into AST
validate structure
evaluate variables and expressions
compile primitives into CadQuery objects
compile operations into final object
export STL/STEP/Python
```

---

## 17. CLI

### Build one file

```bash
python -m cadquery_dsl build models/display_steps.cq3d
```

### Build with explicit output directory

```bash
python -m cadquery_dsl build models/display_steps.cq3d -o exports
```

### Watch directory

```bash
python -m cadquery_dsl watch models
```

### Validate only

```bash
python -m cadquery_dsl validate models/display_steps.cq3d
```

### Export generated Python for debugging

```bash
python -m cadquery_dsl build models/display_steps.cq3d --emit-python
```

---

## 18. Validation and error messages

The DSL should fail early with clear messages.

Examples:

```text
line 12: unknown object 'basee'. Did you mean 'base'?
line 18: box 'body' is missing required field 'size'
line 24: radius must be greater than 0
line 31: units are not allowed. Use 'size 100 60 10', not 'size 100mm 60mm 10mm'
line 40: cannot fillet object 'body': CadQuery failed. Try smaller radius or fewer edges.
line 44: export target must be one of: stl, step, python
```

---

## 19. Important implementation notes for CadQuery

1. **Avoid global fillets after complex boolean operations**  
   `model.edges().fillet(radius)` can fail on complex geometry. Prefer targeted fillets and apply them before complex boolean combinations where possible.

2. **Keep cutters slightly oversized**  
   Through holes should usually be a little longer than the target body, for example `height + 2`, to avoid coplanar issues.

3. **Use STEP for debugging**  
   STL is the print target, but STEP is much easier to inspect in CAD tools.

4. **Preserve generated Python optionally**  
   Emitting generated Python helps debug and teaches the user how the DSL maps to CadQuery.

5. **Use groups for repeated objects**  
   Repeated holes or ribs should be grouped so that `cut screw_holes` or `union ribs` is easy.

---

## 20. Suggested MVP scope

The first implementation should include:

### Commands

```text
model
unit
variables
box
cylinder
hole
prism
combine
fillet
chamfer
repeat
export
```

### Exports

```text
stl
step
python optional
```

### Expression support

```text
+ - * / parentheses
min max abs round floor ceil
```

### Omitted from MVP

```text
shell
text3d
loft
sweep
threads
assemblies
advanced CadQuery selectors
```

These can be added later once the base language is stable.

---

## 21. Longer-term roadmap

### Phase 1 — MVP

- parser,
- variables and expressions,
- box/cylinder/hole/prism,
- union/cut,
- export STL/STEP,
- clear errors,
- several examples.

### Phase 2 — Practical modeling helpers

- rounded_box,
- lip,
- rib,
- screw_hole,
- grid/repeat improvements,
- targeted fillets,
- generated Python output,
- watch mode.

### Phase 3 — Advanced shapes

- text3d,
- shell/hollow,
- loft,
- sweep,
- revolve,
- threads,
- chamfer/fillet selectors,
- parametric libraries.

### Phase 4 — Quality and automation

- visual regression tests,
- bounding box tests,
- STL export tests,
- GitHub Actions,
- example gallery,
- documentation site.

---

## 22. Recommended naming style

Use descriptive object IDs:

```text
base
back_wall
front_lip
left_rib
right_rib
cable_hole
screw_hole_left
```

Avoid generic names in larger files:

```text
box1
part2
thing
```

---

## 23. Testing strategy

### Parser tests

- valid blocks parse correctly,
- missing `end` gives good error,
- unknown commands are rejected,
- comments and empty lines are ignored.

### Expression tests

- arithmetic works,
- variables work,
- unknown variables fail,
- division by zero fails,
- unsupported functions fail.

### Compiler tests

- simple box exports,
- cylinder holes cut correctly,
- repeated holes create expected count,
- combine order works,
- prism creates expected bounding box.

### Geometry tests

Use CadQuery bounding boxes:

```python
bbox = result.val().BoundingBox()
assert bbox.xlen == pytest.approx(165)
assert bbox.ylen == pytest.approx(160)
assert bbox.zlen == pytest.approx(150)
```

### Export tests

- STL file is created,
- STEP file is created,
- files are non-empty,
- invalid model does not produce stale output silently.

---

## 24. Final recommendation

Start with a small but useful DSL that can already create real printable objects:

```text
box
cylinder
hole
prism
combine union/cut
repeat
fillet/chamfer
export stl/step
```

Then add convenience blocks such as:

```text
rounded_box
rib
lip
screw_hole
hollow_box
```

This gives a good balance between simplicity and power. The user can quickly write practical models by hand, while the compiler still uses CadQuery as a robust geometric backend.
