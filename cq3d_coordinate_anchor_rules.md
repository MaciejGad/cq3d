# CQ3D Coordinate System and Anchor Rules

This document defines the coordinate and positioning rules for the text-based 3D DSL that generates CadQuery models. These rules should be treated as implementation guidelines for the parser, validator, AST, and CadQuery backend.

## Goal

The DSL should make object placement predictable and easy to understand. Users should be able to describe models manually without constantly thinking about CadQuery's default centering behavior.

CadQuery often creates objects centered around the active workplane origin. This is powerful, but it can be confusing in a text-based DSL because `0 0 0` may not correspond to the lower corner or base of the object. The DSL should hide this complexity and use a consistent, user-friendly coordinate model.

## Global coordinate system

The DSL uses a right-handed, millimeter-based coordinate system:

```text
X = width, left to right
Y = depth, front to back
Z = height, bottom to top
```

The global project origin should be interpreted as:

```text
0,0,0 = lower-front-left corner of the whole model space
```

For printable objects, `Z = 0` should normally represent the print bed / bottom plane.

## Default unit

All dimensions are in millimeters.

Unit suffixes are not allowed:

```text
size 100 50 20     # valid
size 100mm 50mm 20mm  # invalid
```

## General positioning rule

Every primitive should have one documented local reference point. The DSL command:

```text
at x y z
```

places that local reference point at the given global coordinate.

The backend must not rely on CadQuery's default centering behavior unless it explicitly compensates for it.

## Default anchor policy

For the MVP, the DSL should use one default anchor policy and avoid optional anchors until the core implementation is stable.

Recommended MVP policy:

```text
Default anchor = min / lower-front-left-bottom, where applicable
```

This means that most solid primitives should start at their `at` coordinate and extend in the positive X, Y, and Z directions.

Later versions may add explicit anchors such as:

```text
anchor min
anchor center
anchor bottom_center
anchor front_left_bottom
```

But the MVP should keep positioning simple and deterministic.

## Primitive-specific anchor rules

### Box

For a box, `at x y z` means:

```text
x,y,z = lower-front-left corner of the box
```

A DSL block:

```text
box body
  size 100 50 20
  at 10 20 0
end
```

should create a box with bounding box:

```text
X: 10 -> 110
Y: 20 -> 70
Z: 0  -> 20
```

CadQuery implementation:

```python
shape = (
    cq.Workplane("XY")
    .box(width, depth, height, centered=(False, False, False))
    .translate((x, y, z))
)
```

Do not use the default:

```python
cq.Workplane("XY").box(width, depth, height)
```

because it creates the box centered around the origin.

### Rounded box

For a rounded box, use the same anchor rule as `box`:

```text
at = lower-front-left-bottom corner of the unrounded bounding box
```

The final rounded object should still fit inside the requested bounding box.

### Cylinder

For a vertical cylinder, `at x y z` means:

```text
x,y,z = center of the bottom circular face
```

A DSL block:

```text
cylinder peg
  radius 5
  height 20
  at 10 15 0
end
```

should create a cylinder with bounding box approximately:

```text
X: 5  -> 15
Y: 10 -> 20
Z: 0  -> 20
```

CadQuery implementation:

```python
shape = (
    cq.Workplane("XY")
    .circle(radius)
    .extrude(height)
    .translate((x, y, z))
)
```

This is preferred because the sketch starts on `Z = 0` and extrusion goes upward.

### Cone

For a vertical cone, `at x y z` means:

```text
x,y,z = center of the bottom circular face
```

The cone should extend upward in positive Z.

### Sphere

For a sphere, `at x y z` means:

```text
x,y,z = center of the sphere
```

This is an exception to the `min corner` style because a sphere has a natural center and no flat bottom unless explicitly cut.

### Prism / extruded profile

For an extruded 2D profile, the anchor depends on the profile definition.

Recommended rule:

```text
The profile points are written in local coordinates.
The `at` command translates the whole extruded profile.
Extrusion should go in the positive direction of the selected axis.
```

For the MVP, prefer extrusion from the `XY` plane upward along positive Z.

### Hole

For a vertical hole, `at x y z` means:

```text
x,y,z = center of the hole start face
```

A vertical hole normally cuts along positive or negative Z depending on the command options.

Recommended MVP behavior:

```text
hole direction z
hole cuts through the target object along Z
```

For a simple through-hole, the backend may create a cutting cylinder longer than the target object and position it so that it fully passes through the solid.

### Text3D

Text is more complex because fonts have their own baseline and bounding box rules.

Recommended initial rule:

```text
at x y z = lower-left corner of the text bounding box, after conversion to geometry
```

If this is difficult to implement consistently, document the first supported behavior clearly and add tests.

## Transform rules

### `at`

`at` sets the initial position of the object's local reference point.

Example:

```text
box panel
  size 100 50 10
  at 20 30 0
end
```

### `move`

`move dx dy dz` translates an object relative to its current position.

```text
move 10 0 0
```

means: move the object 10 mm in positive X.

### `rotate`

Rotations should be explicit and predictable.

Recommended syntax:

```text
rotate x 90
rotate y 45
rotate z 180
```

By default, rotation should happen around the object's local anchor or around the global origin only if explicitly documented.

For the MVP, avoid complex rotation semantics if possible. If rotation is implemented, define and test the pivot behavior.

Recommended MVP rule:

```text
rotate uses the object's local anchor point as the pivot
```

### `mirror`

Mirroring should require an explicit plane:

```text
mirror x
mirror y
mirror z
```

or, in a later version:

```text
mirror plane x=0
mirror plane y=80
mirror plane z=0
```

## Combining objects

Boolean operations should preserve global coordinates.

Example:

```text
combine body
  union lower_step upper_step
end
```

The resulting `body` object should keep the exact global position of the input objects.

Do not recenter combined objects automatically.

## Export rules

Exported STL and STEP files should preserve the model's global coordinates.

Do not automatically center the model during export unless an explicit option is added later, such as:

```text
export stl "model.stl" centered
```

For 3D printing, preserving `Z = 0` as the bottom plane is useful because the model imports into slicers in a predictable position.

## Debugging and validation

The backend should provide a way to inspect bounding boxes during tests and optionally in CLI debug mode.

Recommended helper:

```python
def get_bounding_box(obj):
    bbox = obj.val().BoundingBox()
    return {
        "xmin": bbox.xmin,
        "xmax": bbox.xmax,
        "xlen": bbox.xlen,
        "ymin": bbox.ymin,
        "ymax": bbox.ymax,
        "ylen": bbox.ylen,
        "zmin": bbox.zmin,
        "zmax": bbox.zmax,
        "zlen": bbox.zlen,
    }
```

Tests should verify bounding boxes for basic primitives.

Example box test:

```text
box test_box
  size 100 50 20
  at 10 20 0
end
```

Expected bounding box:

```text
X length = 100
Y length = 50
Z length = 20
X min = 10
Y min = 20
Z min = 0
```

## Example: two-step display stand

DSL input:

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

export stl "display_steps.stl"
export step "display_steps.step"
```

Expected final bounding box:

```text
X: 0 -> 165   width  = 165
Y: 0 -> 160   depth  = 160
Z: 0 -> 150   height = 150
```

## Common implementation mistakes

### Mistake: using CadQuery's default centered box

Wrong:

```python
cq.Workplane("XY").box(width, depth, height)
```

Correct:

```python
cq.Workplane("XY").box(width, depth, height, centered=(False, False, False))
```

### Mistake: mixing centered and non-centered primitives

Do not create one object centered around the origin and another object from the minimum corner unless this is explicitly intended and tested.

### Mistake: recentering after union/cut

Boolean results should remain in global model coordinates.

### Mistake: assuming STL preview will show origin clearly

STL viewers and slicers may center or reposition objects visually. Use bounding box tests to verify real coordinates.

## Recommended MVP rule summary

```text
Use millimeters only.
Use X = width, Y = depth, Z = height.
Use Z = 0 as the bottom plane.
Do not use CadQuery's default centered box behavior.
For box-like objects, `at` means lower-front-left-bottom corner.
For vertical cylinders and cones, `at` means center of the bottom face.
For spheres, `at` means center.
Boolean operations must preserve global coordinates.
Exports must not automatically recenter objects.
Add bounding box tests for every primitive.
```
