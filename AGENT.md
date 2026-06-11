# CQ3D Authoring Guide For Agents

This file is for agents that need to create valid `.cq3d` source files.
It describes only the currently implemented DSL behavior.

## Purpose

Use `.cq3d` files to describe 3D printable geometry in a simple line-based text format.
All dimensions are in millimeters.

## Global Coordinate System

The implemented DSL uses a right-handed coordinate system:

- `X` = left to right / width
- `Y` = front to back / depth
- `Z` = bottom to top / height

The global origin is:

```text
0 0 0 = lower-front-left corner of project space
```

Practical meaning:

- `Z = 0` is the bottom plane / print bed level
- positive `X` moves right
- positive `Y` moves toward the back
- positive `Z` moves upward

## File Rules

- Use plain text files with the `.cq3d` extension.
- Syntax is line-based and block-oriented.
- Blocks end with `end`.
- Nested blocks are not supported.
- Full-line comments starting with `#` are allowed.
- Inline comments are not part of the implemented syntax, so avoid them.
- Empty lines are allowed.

## Required Document Structure

A valid file should usually start with:

```text
model some_name
unit mm
```

Rules:

- `model` is optional but recommended.
- `unit mm` is required.
- Only `mm` is supported.
- `model` and `unit` may appear at most once.

## Identifiers

Variable names and object ids must match:

```text
[A-Za-z_][A-Za-z0-9_]*
```

Examples:

- valid: `body`, `step_height`, `peg2`
- invalid: `2body`, `front-width`, `upper step`

Reserved words must not be used as variable names:

- `box`
- `cylinder`
- `combine`
- `move`
- `rotate`
- `fillet`
- `model`
- `unit`
- `end`
- `export`
- `union`
- `cut`
- `size`
- `at`
- `radius`
- `diameter`
- `height`
- `axis`
- `by`
- `around`
- `angle`
- `origin`
- `safe`
- `center`

## Variables

Variables are defined with:

```text
name = expression
```

Example:

```text
front_width = 165
side_depth = 160
step_depth = side_depth / 2
```

Rules:

- Variables must be defined before use.
- Reassignment is not allowed.
- Expressions must evaluate to numbers.
- Unit suffixes such as `10mm` are rejected.

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

Avoid anything else. There is no `eval`, no custom functions, and no unit literals.

## Implemented Commands

Currently implemented top-level commands:

- variable assignment
- `box`
- `cylinder`
- `combine`
- `move`
- `rotate`
- `fillet`
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

- `size` is required.
- all three size values must be greater than zero
- `at` is optional
- `center` is optional
- default `center` is `false`

Implemented placement behavior:

- when `center false` is used or omitted, the box is treated as lower-corner placed
- `at x y z` places the lower-front-left-bottom corner at that coordinate
- with `center true`, CadQuery centered placement is used

Example:

```text
box base
  size 100 60 10
  at 0 0 0
end
```

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

Implemented placement behavior:

- default vertical cylinder is extruded along `+z`
- `at x y z` places the center of the bottom face at that coordinate
- for `axis x` and `axis y`, the cylinder extends in the positive axis direction from the anchor point

Example:

```text
cylinder peg
  diameter 8
  height 20
  at 10 10 0
end
```

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
- implemented operations are only `union` and `cut`
- `union` requires at least two object references
- `cut` requires one base object and at least one cutter
- referenced objects must already exist
- the new combine result gets its own id

Notes:

- operations are processed in order
- object references must point to previously created objects

Example:

```text
combine body
  union lower upper
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

Example:

```text
move body
  by 0 20 0
end
```

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

Example:

```text
rotate bracket
  around z
  angle 90
  origin 0 0 0
end
```

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

Implemented behavior:

- fillet is applied to all edges
- if CadQuery fillet fails and `safe true` is used, the object is left unchanged
- if CadQuery fillet fails and `safe false` is used, the build fails

Example:

```text
fillet body
  radius 2
  safe true
end
```

## Export Commands

Syntax:

```text
export stl "file.stl"
export step "file.step"
```

Path is optional:

```text
export stl
export step
```

Rules:

- only `stl` and `step` are supported
- export paths may be relative or absolute
- relative export paths are resolved from the `.cq3d` file directory
- if no path is given, the default is `<model_name>.<format>` or `model.<format>`

Example:

```text
export stl "exports/sample.stl"
export step "exports/sample.step"
```

## Object Rules

- Shape ids must be unique.
- Combine result ids must also be unique.
- `move`, `rotate`, and `fillet` operate on an existing object id.
- Unknown object references fail validation.

## Final Object Behavior

The build system exports the final object using this priority:

1. an object named `body`, if it exists
2. otherwise the last created or modified object

For best results, name the intended final object `body`.

## Recommended Authoring Pattern

Use this order:

1. `model`
2. `unit mm`
3. variables
4. primitive shapes
5. `combine`
6. transforms
7. `fillet`
8. exports

## Good Example

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

These are not implemented in the current DSL and should not be emitted:

- `rounded_box`
- `sphere`
- `cone`
- `prism`
- `mirror`
- `repeat`
- `grid`
- `chamfer`
- `shell`
- `text3d`
- `intersect`
- inline comments
- nested blocks
- unit suffixes like `mm`

## Practical Guidance For Agents

- Prefer simple variables over repeating numeric literals.
- Keep object ids descriptive: `base`, `upper_step`, `body`, `peg`, `hole`.
- Use `body` as the final combined object name.
- Emit one command per line and keep blocks clean for Git diffs.
- Assume world coordinates are preserved through `combine`, `move`, exports, and previews.
- When in doubt, stay within the currently implemented commands only.
