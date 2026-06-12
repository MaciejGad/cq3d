# CQ3D DSL Feature Extensions for More Accurate Turkish Spindle Models

## Purpose

This document describes proposed extensions to the current `.cq3d` DSL so it can model a Turkish spindle more accurately.

A Turkish spindle is usually built from:

- a long central shaft,
- a lower stop / knob,
- two crossing removable arms,
- rounded paddle-like arm ends,
- central slots where the arms interlock,
- a hole or seat for the shaft,
- small grooves, bevels, and rounded wooden-style edges.

The current DSL can approximate this using `box`, `cylinder`, `combine`, `cut`, `rotate`, and `fillet`, but the result is blocky. The goal of these features is to make the model closer to the real object while keeping the DSL readable and implementation-friendly.

All examples assume millimeters and the same coordinate system as the current DSL:

- `X` = left to right / width
- `Y` = front to back / depth
- `Z` = bottom to top / height
- `Z = 0` is the print bed level

---

## 1. `rounded_box`

### Problem

The current `box` command creates sharp rectangular solids. A Turkish spindle has rounded arms, softened corners, and wooden-looking edges. Applying `fillet edges all` after every box is not precise enough and often rounds unwanted edges.

### Proposed syntax

```cq3d
rounded_box <id>
  size <x> <y> <z>
  radius <r>
  [at <x> <y> <z>]
  [center true|false]
end
```

### Rules

- `size` is required.
- `radius` is required and must be greater than zero.
- Radius should not exceed half of the smallest dimension.
- `at` behaves like in `box`.
- `center` behaves like in `box`.

### Example

```cq3d
rounded_box simple_arm
  size 140 22 10
  radius 5
  at -70 -11 20
end
```

### Implementation notes

In CadQuery this can be implemented as a regular box followed by a fillet on all edges, but it should be exposed as a first-class primitive because it is a common shape.

---

## 2. `rounded_bar`

### Problem

Spindle arms are not only rounded boxes. They are closer to long paddle-like bars with rounded ends. The DSL should provide a convenient primitive for this kind of shape.

### Proposed syntax

```cq3d
rounded_bar <id>
  length <l>
  width <w>
  height <h>
  radius <r>
  [axis x|y]
  [at <x> <y> <z>]
end
```

### Rules

- `length`, `width`, `height`, and `radius` are required.
- `axis` defaults to `x`.
- For `axis x`, the bar extends along X.
- For `axis y`, the bar extends along Y.
- `at` places the lower-front-left corner of the bounding box unless `center` support is added later.

### Example: one spindle arm

```cq3d
rounded_bar arm_x
  length 150
  width 24
  height 10
  radius 6
  axis x
  at -75 -12 18
end
```

### Example: crossing arm

```cq3d
rounded_bar arm_y
  length 150
  width 24
  height 10
  radius 6
  axis y
  at -12 -75 28
end
```

### Implementation notes

A simple implementation can use a rounded rectangle profile extruded along the chosen axis. A first version may use `box + cylinders + union`, but an extruded 2D profile is preferable.

---

## 3. `cone`

### Problem

The central spindle shaft often has a tapered end, rounded tip, or bottom stop. The current DSL supports only cylinders with constant diameter.

### Proposed syntax

```cq3d
cone <id>
  diameter1 <d1>
  diameter2 <d2>
  height <h>
  [axis x|y|z]
  [at <x> <y> <z>]
end
```

Alternative radius syntax:

```cq3d
cone <id>
  radius1 <r1>
  radius2 <r2>
  height <h>
  [axis x|y|z]
  [at <x> <y> <z>]
end
```

### Rules

- `height` is required.
- Either `diameter1`/`diameter2` or `radius1`/`radius2` must be used.
- Values must be greater than or equal to zero.
- At least one end radius/diameter must be greater than zero.
- Default `axis` is `z`.
- `at` places the center of the first end face.

### Example: tapered top of shaft

```cq3d
cone shaft_tip
  diameter1 8
  diameter2 3
  height 20
  axis z
  at 0 0 150
end
```

### Example: bottom stop

```cq3d
cone bottom_stop
  diameter1 20
  diameter2 12
  height 10
  axis z
  at 0 0 0
end
```

### Implementation notes

CadQuery supports cones directly. For `axis x` and `axis y`, the primitive can be created along Z and rotated into place, or created with the correct workplane orientation.

---

## 4. `revolve`

### Problem

A real spindle shaft is often a turned wooden shape. It can have a knob, narrow waist, long straight section, and rounded or tapered tip. Describing this with many cylinders and cones is possible but clumsy.

### Proposed syntax

```cq3d
revolve <id>
  axis z
  point <radius> <z>
  point <radius> <z>
  point <radius> <z>
end
```

### Rules

- `axis` is required in the first implementation and should initially support only `z`.
- Each `point` defines a 2D profile using `radius` and height coordinate.
- The profile is revolved around the selected axis.
- Radius must be greater than or equal to zero.
- At least three points are required.
- The profile should form a valid closed or closable shape.

### Example: turned spindle shaft

```cq3d
revolve shaft
  axis z
  point 0 0
  point 10 0
  point 10 4
  point 6 8
  point 4 20
  point 4 145
  point 3 158
  point 0 164
end
```

### Implementation notes

This maps naturally to CadQuery `polyline(...).close().revolve(...)`.

Recommended first limitation: support only `axis z`. This keeps the parser and implementation simple while covering the main spindle use case.

---

## 5. 2D `profile` + `extrude`

### Problem

Spindle arms have custom paddle shapes: wider center, narrower ends, rounded or chamfered ends, and sometimes decorative grooves. A primitive like `rounded_bar` is useful, but a reusable profile system is more flexible.

### Proposed syntax

```cq3d
profile <id>
  point <x> <y>
  point <x> <y>
  point <x> <y>
end

extrude <id>
  profile <profile_id>
  height <h>
  [axis x|y|z]
  [at <x> <y> <z>]
end
```

### Rules for `profile`

- A profile contains 2D points.
- At least three points are required.
- The last point does not need to repeat the first point; the implementation should close the wire automatically.
- Profiles are reusable and do not create 3D objects by themselves.

### Rules for `extrude`

- `profile` and `height` are required.
- `axis` defaults to `z`.
- `at` places the profile origin in 3D space.

### Example: paddle-shaped spindle arm profile

```cq3d
profile paddle_arm_profile
  point -75 -8
  point -62 -12
  point 62 -12
  point 75 -8
  point 75 8
  point 62 12
  point -62 12
  point -75 8
end

extrude arm_x
  profile paddle_arm_profile
  height 10
  axis z
  at 0 0 20
end
```

### Example: rotated crossing arm

```cq3d
extrude arm_y
  profile paddle_arm_profile
  height 10
  axis z
  at 0 0 31
end

rotate arm_y
  around z
  angle 90
  origin 0 0 0
end
```

### Implementation notes

This is one of the highest-value additions. It makes the DSL useful for many custom flat shapes, not only spindles.

For the first implementation, profiles can use straight segments only. Curves and arcs can be added later.

---

## 6. Arcs in profiles

### Problem

Using only straight profile segments makes rounded paddle ends polygonal. Turkish spindle arms should have smooth rounded ends.

### Proposed syntax

```cq3d
profile <id>
  point <x> <y>
  arc <x> <y> radius <r>
  point <x> <y>
end
```

Alternative syntax:

```cq3d
profile <id>
  point <x> <y>
  three_point_arc <x1> <y1> <x2> <y2>
  point <x> <y>
end
```

### Example

```cq3d
profile rounded_paddle_profile
  point -70 -10
  point 60 -10
  three_point_arc 75 0 60 10
  point -70 10
  three_point_arc -82 0 -70 -10
end
```

### Implementation notes

A `three_point_arc` is often easier to implement robustly than `arc radius`, because it maps directly to CadQuery-style arc creation.

This feature can be postponed until after basic `profile + extrude` works.

---

## 7. `chamfer`

### Problem

The current DSL supports `fillet`, but not chamfering. Printed mechanical parts often need small chamfers around openings and edges. The spindle arms also look better with slight bevels near slots and ends.

### Proposed syntax

```cq3d
chamfer <id>
  distance <d>
  [edges all]
  [safe true|false]
end
```

### Rules

- `distance` is required and must be greater than zero.
- `edges all` should be supported first.
- `safe` defaults to `true`, matching current `fillet` behavior.

### Example

```cq3d
chamfer arm_x
  distance 1
  edges all
  safe true
end
```

### Implementation notes

This should mirror the structure of the existing `fillet` command.

---

## 8. Selective `fillet` and `chamfer`

### Problem

The current `fillet` command supports only `edges all`. For a more accurate spindle, the DSL needs to round only specific edges, for example only vertical outside edges of an arm or only the top edges.

### Proposed syntax

```cq3d
fillet <id>
  radius <r>
  edges all|top|bottom|vertical|outer
  [safe true|false]
end
```

```cq3d
chamfer <id>
  distance <d>
  edges all|top|bottom|vertical|outer
  [safe true|false]
end
```

### Example

```cq3d
fillet arm_x
  radius 4
  edges outer
  safe true
end

chamfer center_slot_cut
  distance 0.6
  edges top
  safe true
end
```

### Implementation notes

This can be implemented in stages:

1. `edges all`
2. `edges vertical`
3. `edges top`
4. `edges bottom`
5. `edges outer`

The meaning of each selector must be documented carefully because edge selection can become ambiguous after boolean operations.

---

## 9. `copy`

### Problem

A Turkish spindle is symmetrical. The two arms are almost identical, just rotated 90 degrees. Currently the DSL forces repeated definitions or destructive transformations on existing objects.

### Proposed syntax

```cq3d
copy <new_id> from <source_id>
  [by <x> <y> <z>]
  [rotate around x|y|z angle <degrees> origin <x> <y> <z>]
end
```

### Rules

- `new_id` must be unique.
- `source_id` must already exist.
- `by` is optional.
- `rotate` is optional.
- If both `by` and `rotate` are present, transformations should be applied in document order.

### Example

```cq3d
copy arm_y from arm_x
  rotate around z angle 90 origin 0 0 0
  by 0 0 12
end
```

### Implementation notes

This is simpler and safer than using `move` and `rotate` on the same object repeatedly. It also makes generated DSL easier to read.

---

## 10. `radial_repeat`

### Problem

Many models need repeated geometry around an axis. In the spindle case, this is useful for decorative notches or repeated supports.

### Proposed syntax

```cq3d
radial_repeat <id>
  source <source_id>
  count <n>
  around x|y|z
  angle <degrees>
  origin <x> <y> <z>
end
```

### Rules

- `source` is required.
- `count` must be at least 2.
- `around` is required.
- `angle` is the angle between copies.
- The command creates a union of the repeated objects under `<id>`.

### Example

```cq3d
radial_repeat four_grooves
  source groove_cut
  count 4
  around z
  angle 90
  origin 0 0 0
end
```

### Implementation notes

This should probably create a combined object rather than multiple named objects. If separate naming is needed later, use `copy` instead.

---

## 11. `slot`

### Problem

Turkish spindle arms interlock through rectangular or rounded slots. Modeling slots manually with boxes is possible, but it is error-prone. A dedicated `slot` primitive would make mechanical joinery easier.

### Proposed syntax

```cq3d
slot <id>
  size <x> <y> <z>
  clearance <c>
  [at <x> <y> <z>]
  [radius <r>]
end
```

### Rules

- `size` is the nominal size of the inserted part.
- `clearance` expands the slot dimensions.
- `radius` is optional and creates rounded slot corners.
- A slot creates a cutter object. It does not cut automatically.

### Example: arm interlock slot

```cq3d
slot arm_x_center_slot
  size 26 11 6
  clearance 0.3
  radius 1
  at -13 -5.5 22
end

combine arm_x_cut
  cut arm_x arm_x_center_slot
end
```

### Example: shaft hole as slot alternative

```cq3d
cylinder shaft_hole
  diameter 8.4
  height 20
  axis z
  at 0 0 15
end

combine arm_x_with_hole
  cut arm_x_cut shaft_hole
end
```

### Implementation notes

For the first version, `slot` can be implemented as a box expanded by `clearance`:

- final X = nominal X + 2 * clearance
- final Y = nominal Y + 2 * clearance
- final Z = nominal Z + 2 * clearance

Rounded slots can be added later.

---

## 12. Multi-object export

### Problem

A real Turkish spindle is an assembly. It should often be exported as multiple printable parts: shaft, arm A, and arm B. The current final-object behavior exports `body` or the last object, which is not enough for assemblies.

### Proposed syntax

```cq3d
export step "turkish_spindle_assembly.step"
  objects shaft arm_x arm_y
end

export stl "shaft.stl"
  object shaft
end

export stl "arm_x.stl"
  object arm_x
end

export stl "arm_y.stl"
  object arm_y
end
```

### Rules

- Existing single-line export syntax should remain supported.
- Block export syntax allows explicit object selection.
- `object` exports one object.
- `objects` exports multiple objects as an assembly or combined export depending on file type.

### Implementation notes

For STL, exporting multiple objects can either:

- export them as a single combined mesh, or
- reject multiple objects and require one object per STL.

For STEP, multiple objects should ideally remain separate solids in one assembly-like file.

---

## 13. `assembly`

### Problem

For models made from separate parts, it is useful to group objects without permanently boolean-unioning them.

### Proposed syntax

```cq3d
assembly <id>
  add <object_id>
  add <object_id>
  add <object_id>
end
```

### Example

```cq3d
assembly body
  add shaft
  add arm_x
  add arm_y
end

export step "turkish_spindle_assembly.step"
  object body
end
```

### Rules

- `assembly` references existing objects.
- It does not perform a boolean union.
- It preserves separate solids if the export format supports that.

### Implementation notes

This feature is especially useful for STEP export. For STL, the assembly can be converted into a combined mesh.

---

## 14. `sweep`

### Problem

Some spindle arms are slightly curved rather than perfectly straight. A `sweep` command would allow a rounded rectangular profile to follow a path.

### Proposed syntax, simple version

```cq3d
sweep <id>
  path line <x1> <y1> <z1> <x2> <y2> <z2>
  section rounded_rect width <w> height <h> radius <r>
end
```

### Proposed syntax, curve version

```cq3d
sweep <id>
  path curve
    point <x> <y> <z>
    point <x> <y> <z>
    point <x> <y> <z>
  end
  section rounded_rect width <w> height <h> radius <r>
end
```

### Example

```cq3d
sweep curved_arm
  path curve
    point -75 0 20
    point -30 0 24
    point 30 0 24
    point 75 0 20
  end
  section rounded_rect width 22 height 10 radius 4
end
```

### Implementation notes

This is a later-stage feature. It is powerful but more complex to parse because it introduces nested blocks. Since the current DSL does not support nested blocks, either nested blocks must be added generally, or `sweep` must use a simpler line-based syntax.

A non-nested alternative:

```cq3d
path arm_path
  point -75 0 20
  point -30 0 24
  point 30 0 24
  point 75 0 20
end

sweep curved_arm
  path arm_path
  section rounded_rect 22 10 4
end
```

This alternative is easier to fit into the current block model.

---

## 15. Recommended implementation order

### Phase 1: High-value simple primitives

Implement these first:

1. `rounded_box`
2. `cone`
3. `chamfer`
4. `copy`
5. multi-object export with explicit `object` / `objects`

These additions are relatively small and immediately improve spindle models.

### Phase 2: Better spindle arms and joinery

Implement next:

1. `rounded_bar`
2. `slot`
3. selective `fillet` and `chamfer`
4. `assembly`

These features make it possible to model the spindle as printable, separate, interlocking parts.

### Phase 3: Custom profiles and turned shapes

Implement after the parser is stable:

1. `profile`
2. `extrude`
3. `revolve`
4. profile arcs

These make the DSL much more expressive and allow realistic paddle shapes and turned shafts.

### Phase 4: Advanced organic shapes

Implement last:

1. `sweep`
2. curved paths
3. reusable path definitions

These are useful for high-quality organic or ergonomic models, but they are not required for the first accurate spindle implementation.

---

## 16. Target DSL example for a more accurate Turkish spindle

This example shows what the DSL could look like after implementing the most important proposed features.

```cq3d
model turkish_spindle_v2
unit mm

shaft_diameter = 8
shaft_hole_clearance = 0.4
arm_length = 150
arm_width = 24
arm_height = 10
arm_gap = 0.4
slot_width = arm_width + arm_gap
slot_height = arm_height + arm_gap

revolve shaft
  axis z
  point 0 0
  point 10 0
  point 10 4
  point 6 8
  point 4 20
  point 4 150
  point 3 160
  point 0 166
end

profile paddle_profile
  point -75 -8
  point -62 -12
  point 62 -12
  point 75 -8
  point 75 8
  point 62 12
  point -62 12
  point -75 8
end

extrude arm_x_raw
  profile paddle_profile
  height arm_height
  axis z
  at 0 0 24
end

fillet arm_x_raw
  radius 3
  edges outer
  safe true
end

slot arm_x_slot
  size slot_width slot_height 6
  clearance 0.2
  radius 1
  at -slot_width / 2 -slot_height / 2 26
end

cylinder arm_x_shaft_hole
  diameter shaft_diameter + shaft_hole_clearance
  height 20
  axis z
  at 0 0 20
end

combine arm_x
  cut arm_x_raw arm_x_slot arm_x_shaft_hole
end

copy arm_y from arm_x
  rotate around z angle 90 origin 0 0 0
  by 0 0 12
end

assembly body
  add shaft
  add arm_x
  add arm_y
end

export step "turkish_spindle_assembly.step"
  object body
end

export stl "shaft.stl"
  object shaft
end

export stl "arm_x.stl"
  object arm_x
end

export stl "arm_y.stl"
  object arm_y
end
```

---

## 17. Parser and validation requirements

For every new command, the implementation should include:

- clear validation errors,
- tests for missing required fields,
- tests for invalid numeric values,
- tests for unknown object references,
- tests for duplicate ids,
- tests for export behavior,
- at least one visual regression example if the project supports visual tests.

Recommended validation examples:

```text
rounded_box arm is missing radius
cone shaft_tip must define diameter1 and diameter2, or radius1 and radius2
copy arm_y references unknown object arm_x
slot arm_slot clearance must be greater than or equal to zero
export object shaft references unknown object
```

---

## 18. Minimal implementation needed specifically for Turkish spindle

If the goal is only to make a good Turkish spindle model and not to expand the DSL broadly, the minimum useful set is:

1. `rounded_bar`
2. `cone`
3. `copy`
4. `slot`
5. multi-object export
6. selective `fillet`

With these features, the DSL can create:

- a tapered central shaft,
- rounded crossing arms,
- proper interlocking slots,
- realistic rounded edges,
- separate printable parts.

`profile + extrude` and `revolve` are not strictly required for the first version, but they are the best long-term solution for accurate and reusable modeling.
