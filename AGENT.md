# CQ3D Authoring Guide For Agents

This file is for agents that need to create valid `.cq3d` source files.
It documents the currently implemented DSL behavior only.

## Purpose

Use `.cq3d` files to describe 3D printable geometry in a line-based text format.
All dimensions are millimeters.

## Global Coordinate System

The implemented DSL uses a right-handed coordinate system:

- `X` = left to right / width
- `Y` = front to back / depth
- `Z` = bottom to top / height

Global origin:

```text
0 0 0 = lower-front-left corner of project space
```

Practical meaning:

- `Z = 0` is the print bed / bottom plane
- positive `X` moves right
- positive `Y` moves toward the back
- positive `Z` moves upward

## File Rules

- Use `.cq3d` extension.
- Syntax is line-based and block-oriented.
- Blocks end with `end`.
- Nested blocks are not supported.
- Full-line comments starting with `#` are allowed.
- Inline comments are not supported.
- Empty lines are allowed.

## Required Document Structure

Recommended start:

```text
model some_name
unit mm
```

Rules:

- `model` is optional but recommended
- `unit mm` is required
- only `mm` is supported
- `model` and `unit` may appear at most once

## Identifiers

Identifiers must match:

```text
[A-Za-z_][A-Za-z0-9_]*
```

Examples:

- valid: `body`, `step_height`, `peg2`
- invalid: `2body`, `front-width`, `upper step`

Reserved words must not be used as variable names:

- `box`
- `rounded_box`
- `rounded_bar`
- `cylinder`
- `cone`
- `slot`
- `combine`
- `move`
- `rotate`
- `copy`
- `fillet`
- `chamfer`
- `model`
- `unit`
- `end`
- `export`
- `union`
- `cut`
- `size`
- `at`
- `radius`
- `radius1`
- `radius2`
- `diameter`
- `diameter1`
- `diameter2`
- `height`
- `axis`
- `by`
- `around`
- `angle`
- `origin`
- `safe`
- `center`
- `distance`
- `clearance`
- `from`
- `object`
- `objects`

## Variables

Variables are defined with:

```text
name = expression
```

Rules:

- variables must be defined before use
- reassignment is not allowed
- expressions must evaluate to numbers
- unit suffixes like `10mm` are rejected

## Supported Expressions

Allowed operators:

- `+`
- `-`
- `*`
- `/`
- parentheses
- unary `+`
- unary `-`

Allowed functions:

- `min(...)`
- `max(...)`
- `abs(...)`
- `round(...)`
- `floor(...)`
- `ceil(...)`

Examples:

```text
width = 165
depth = 160
step_depth = depth / 2
wall = max(3, width / 80)
offset = -(depth / 4)
```

No `eval`, no custom functions, no unit literals.

## Implemented Commands

Currently implemented top-level commands:

- variable assignment
- `box`
- `rounded_box`
- `rounded_bar`
- `cylinder`
- `cone`
- `slot`
- `combine`
- `move`
- `rotate`
- `copy`
- `fillet`
- `chamfer`
- `export stl`
- `export step`

## `box`

Syntax:

```text
box <id>
  size <x> <y> <z>
  [at <x> <y> <z>]
  [center true|false]
end
```

Rules:

- `size` is required
- all size values must be greater than zero
- `at` is optional
- `center` is optional
- default `center` is `false`

Placement:

- with `center false`, `at x y z` places the lower-front-left-bottom corner
- with `center true`, CadQuery centered placement is used

## `rounded_box`

Syntax:

```text
rounded_box <id>
  size <x> <y> <z>
  radius <r>
  [at <x> <y> <z>]
  [center true|false]
end
```

Rules:

- `size` is required
- `radius` is required
- all size values must be greater than zero
- radius must be greater than zero
- radius must not exceed half of the smallest dimension
- `at` and `center` behave like `box`

Behavior:

- built from a box
- fillet applied to all edges
- if the fillet fails, the build fails with a clear error

## `rounded_bar`

Syntax:

```text
rounded_bar <id>
  length <l>
  width <w>
  height <h>
  radius <r>
  [at <x> <y> <z>]
  [axis x|y|z]
end
```

Rules:

- `length`, `width`, `height`, and `radius` are required
- all dimensions must be greater than zero
- radius must not exceed half of the width or height
- default axis is `x`

Behavior:

- `axis x`: length runs along `X`
- `axis y`: length runs along `Y`
- `axis z`: length runs along `Z`
- `at` places the lower-front-left-bottom corner of the resulting bounding box

## `cylinder`

Syntax:

```text
cylinder <id>
  radius <r>
  height <h>
  [at <x> <y> <z>]
  [axis x|y|z]
end
```

or:

```text
cylinder <id>
  diameter <d>
  height <h>
  [at <x> <y> <z>]
  [axis x|y|z]
end
```

Rules:

- `height` is required
- exactly one of `radius` or `diameter` must be provided
- radius, diameter, and height must be greater than zero
- default axis is `z`
- allowed axes: `x`, `y`, `z`

Placement:

- `at x y z` places the center of the bottom face
- default vertical cylinder extends along `+z`
- `axis x` and `axis y` extend in the positive axis direction

## `cone`

Syntax:

```text
cone <id>
  diameter1 <d1>
  diameter2 <d2>
  height <h>
  [at <x> <y> <z>]
  [axis x|y|z]
end
```

or:

```text
cone <id>
  radius1 <r1>
  radius2 <r2>
  height <h>
  [at <x> <y> <z>]
  [axis x|y|z]
end
```

Rules:

- `height` is required
- use either the diameter pair or the radius pair
- do not mix diameter and radius fields
- all dimensions must be greater than zero
- default axis is `z`

Placement:

- `at x y z` places the center of the bottom face
- `axis z` extends upward in `+z`
- `axis x` and `axis y` extend in the positive axis direction

## `slot`

Syntax:

```text
slot <id>
  size <x> <y> <z>
  [clearance <c>]
  [at <x> <y> <z>]
  [center true|false]
end
```

Rules:

- `size` is required
- size values must be greater than zero
- clearance defaults to `0`
- clearance must be greater than or equal to zero
- placement follows `box`

Behavior:

- `slot` creates normal visible geometry intended for `combine cut`
- clearance enlarges the cutter dimensions

## `combine`

Syntax:

```text
combine <id>
  union <obj1> <obj2> [obj3 ...]
  [cut <base> <tool1> [tool2 ...]]
end
```

Rules:

- at least one operation is required
- only `union` and `cut` are implemented
- `union` requires at least two object references
- `cut` requires one base object and at least one cutter
- referenced objects must already exist
- the new combine result gets its own id

Notes:

- operations are processed in order
- a later operation may refer to the in-progress result by the combine id

Example:

```text
combine body
  union part_a part_b
  cut body cutter
end
```

## `move`

Syntax:

```text
move <id>
  by <x> <y> <z>
end
```

Rules:

- the object must already exist
- exactly one `by` line is allowed
- this is a relative translation applied after object creation

## `rotate`

Syntax:

```text
rotate <id>
  around x|y|z
  angle <degrees>
  [origin <x> <y> <z>]
end
```

Rules:

- the object must already exist
- `around` is required
- `angle` is required
- `origin` is optional
- default origin is `0 0 0`

## `copy`

Syntax:

```text
copy <new_id> from <source_id>
  [by <x> <y> <z>]
  [rotate around x|y|z angle <degrees> [origin <x> <y> <z>]]
end
```

Rules:

- new id must be unique
- source object must already exist
- at least one operation is required
- operations are applied in block order

Implemented operations:

- `by`
- `rotate around ... angle ... origin ...`

## `fillet`

Syntax:

```text
fillet <id>
  radius <r>
  [safe true|false]
  [edges all]
end
```

Rules:

- the object must already exist
- `radius` is required and must be greater than zero
- only `edges all` is currently supported
- `safe` defaults to `true`

Behavior:

- if fillet fails and `safe true` is used, the object is left unchanged
- if fillet fails and `safe false` is used, the build fails

## `chamfer`

Syntax:

```text
chamfer <id>
  distance <d>
  [safe true|false]
  [edges all]
end
```

Rules:

- the object must already exist
- `distance` is required
- distance must be greater than zero
- only `edges all` is currently supported
- `safe` defaults to `true`

Behavior:

- if chamfer fails and `safe true` is used, the object is left unchanged
- if chamfer fails and `safe false` is used, the build fails

## Export Commands

Inline syntax:

```text
export stl "file.stl"
export step "file.step"
```

Path is optional:

```text
export stl
export step
```

Block syntax is also supported:

```text
export stl "shaft.stl"
  object shaft
end
```

```text
export step "assembly.step"
  objects shaft arm_a arm_b
end
```

Rules:

- only `stl` and `step` are supported
- export paths may be relative or absolute
- relative export paths are resolved from the `.cq3d` file directory
- if no path is given, the default is `<model_name>.<format>` or `model.<format>`
- `object` exports one named object
- `objects` exports multiple named objects as one payload
- all referenced export objects must already exist

## Object Rules

- object ids must be unique
- `move`, `rotate`, `copy`, `fillet`, and `chamfer` refer to existing objects
- unknown references fail validation

## Final Object Behavior

If no export object is specified, the build/export system uses:

1. object named `body`
2. otherwise the last created or modified object

## Recommended Authoring Pattern

Recommended order:

1. `model`
2. `unit mm`
3. variables
4. primitive shapes
5. `combine`
6. transforms and copies
7. `fillet` or `chamfer`
8. exports

## Example

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

export stl "display_steps.stl"
export step "display_steps.step"
```

## Things Not To Use Yet

These are still not implemented:

- `sphere`
- `prism`
- `mirror`
- `repeat`
- `grid`
- `shell`
- `text3d`
- `intersect`
- freeform profile
- revolve
- sweep
- selective edge selectors beyond `edges all`
- inline comments
- nested blocks
- unit suffixes like `mm`

## Practical Guidance For Agents

- Prefer simple variables over repeated numeric literals
- Keep object ids descriptive: `shaft`, `arm_a`, `arm_slot`, `body`
- Use `body` as the final combined object name when you want default export behavior
- Emit one command per line
- Assume world coordinates are preserved through `combine`, `move`, copy transforms, exports, and preview
- Stay within the implemented commands only
