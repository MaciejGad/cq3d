# Extended Geometry Features

This document describes the currently implemented CQ3D extensions beyond the original MVP primitives.
All dimensions remain in millimeters.

## Syntax

### `rounded_box`

```text
rounded_box <id>
  size <x> <y> <z>
  radius <r>
  [at <x> <y> <z>]
  [center true|false]
end
```

### `cone`

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

### `chamfer`

```text
chamfer <id>
  distance <d>
  [safe true|false]
  [edges all]
end
```

### `copy`

```text
copy <new_id> from <source_id>
  [by <x> <y> <z>]
  [rotate around x|y|z angle <degrees> [origin <x> <y> <z>]]
end
```

### `slot`

```text
slot <id>
  size <x> <y> <z>
  [clearance <c>]
  [at <x> <y> <z>]
  [center true|false]
end
```

### `rounded_bar`

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

### Object-specific export

```text
export stl "shaft.stl"
  object shaft
end
```

```text
export step "turkish_spindle_assembly.step"
  objects shaft arm_a arm_b
end
```

## Validation Rules

### `rounded_box`

- `size` is required
- `radius` is required
- all size values must be greater than zero
- radius must be greater than zero
- radius must not be larger than half of the smallest box dimension

### `cone`

- `height` is required
- use either `diameter1`/`diameter2` or `radius1`/`radius2`
- do not mix radius and diameter fields in the same cone
- all dimensions must be greater than zero
- default axis is `z`

### `chamfer`

- target object must already exist
- `distance` is required
- distance must be greater than zero
- only `edges all` is supported in the current implementation
- `safe` defaults to `true`

### `copy`

- new id must be unique
- source object must already exist
- at least one operation is required
- operations are applied in the order they appear

### `slot`

- `size` is required
- size values must be greater than zero
- clearance defaults to `0`
- clearance must be greater than or equal to zero

### `rounded_bar`

- `length`, `width`, `height`, and `radius` are required
- all dimensions must be greater than zero
- radius must not be larger than half of the width or height
- default axis is `x`

### Export blocks

- `object` requires one object id
- `objects` requires one or more object ids
- all referenced objects must exist
- old single-line export syntax remains valid

## Placement Behavior

- `rounded_box` follows `box` placement rules
- `cone` follows `cylinder` placement rules
- `slot` follows `box` placement rules
- `rounded_bar` uses the lower-front-left-bottom corner of the resulting bounding box as the anchor
- `copy` applies transforms after the source geometry is duplicated
- boolean operations preserve world coordinates
- exports preserve world coordinates

## Examples

### Rounded box arm blank

```text
rounded_box arm_blank
  size 140 22 10
  radius 4
  at -70 -11 20
end
```

### Tapered spindle tip

```text
cone shaft_tip
  diameter1 8
  diameter2 3
  height 20
  at 0 0 150
end
```

### Removable arm slot

```text
slot arm_slot
  size 24 12 8
  clearance 0.3
  at -12 -6 21
end
```

### Crossed arm by copy

```text
copy arm_b from arm_a
  rotate around z angle 90 origin 0 0 0
end
```

## Turkish Spindle Example

See:

- [`examples/turkish_spindle_advanced.cq3d`](/Users/bazyl/Code/Essa3d/examples/turkish_spindle_advanced.cq3d)

This example demonstrates:

- crossed rounded arms
- slotted removable parts
- shaft assembly with cones and cylinders
- object-specific part export
- full assembly STEP export

## Known Limitations

- only `edges all` is supported for `fillet` and `chamfer`
- no freeform profiles
- no revolve or sweep
- no selective edge selectors
- no nested blocks
- no hidden construction geometry
- no explicit assembly hierarchy beyond multi-object export

## Migration Notes

- existing `box`, `cylinder`, `combine`, `move`, `rotate`, `fillet`, and single-line export syntax still work
- block export syntax is additive and backward-compatible
- the new commands do not change the existing coordinate system
