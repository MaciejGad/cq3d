# STEP Equivalence Report

## Scope

This report covers the first comparison set where:

1. A model is built from `.cq3d`.
2. The same model is built directly in CadQuery Python.
3. Both are exported to STEP.
4. The STEP outputs are compared after re-import.

Current test coverage lives in [`tests/test_step_equivalence.py`](/Users/bazyl/Code/Essa3d/tests/test_step_equivalence.py).

## Initial Cases

The first slice focuses on simple shapes and unions:

- single box
- single cylinder
- union of two boxes

## Comparison Method

The tests currently compare STEP outputs by importing both files back into CadQuery and checking:

- volume
- surface area
- bounding-box dimensions
- solid count
- face count
- edge count
- symmetric-difference volume in both directions

This is intentionally a geometry-level comparison using STEP as the interchange format.

## Current Findings

### Geometry

Current observed results after fixing box placement in the backend:

| Case | Status | Main difference |
| --- | --- | --- |
| `box` | match | no geometric difference observed |
| `cylinder` | match | no geometric difference observed |
| `union_boxes` | match | no geometric difference observed |

Detailed observations:

### `box`

- `cq3d` bbox min: `(0, 0, 0)`
- Python bbox min: `(0, 0, 0)`
- `cq3d` bbox max: `(10, 20, 30)`
- Python bbox max: `(10, 20, 30)`
- both volumes: `6000`
- symmetric-difference volume: `0` in both directions

Interpretation:

- the box now matches the reference model in both dimensions and placement

### `cylinder`

- volume difference: `0`
- area difference: `0`
- bbox difference: `0`
- symmetric-difference volume: `0`

Interpretation:

- current cylinder generation matches the reference model for this simple case

### `union_boxes`

- `cq3d` volume: `8000`
- Python volume: `8000`
- `cq3d` bbox: `(10, 20, 40)`
- Python bbox: `(10, 20, 40)`
- symmetric-difference volumes: `0` and `0`

Interpretation:

- the union now matches the reference model
- fixing box placement also fixed the stacked-box union case

### Raw STEP File Content

The raw `.step` files are not byte-identical even when the geometry is the same.

Observed reason:

- STEP headers include export metadata such as timestamps and Open CASCADE file naming details.
- Entity ordering may also vary between exports.

This means raw text diff is currently noisy and not suitable as the primary equivalence signal.

## Known Gaps

The current comparison set is intentionally small and does not yet cover:

- translated cylinders on rotated axes
- unions with overlapping solids
- cut operations
- fillets
- move and rotate commands
- multi-step models such as `display_steps`
- deterministic export requirements

## Proposal For Remaining Improvements

The geometry mismatch reported in the first version is now fixed. The items below are still proposals only.

### 1. Keep geometry comparison as the main correctness check

Reason:

- It verifies the actual shape rather than unstable STEP serialization details.
- It remains useful even if export metadata changes.

### 2. Add a canonical STEP comparison mode

Potential approach:

- strip or normalize the STEP header block before diffing
- ignore timestamp-bearing fields such as `FILE_NAME(...)`
- compare normalized body sections separately from metadata

Expected benefit:

- produces cleaner Git-friendly diffs for regression reports
- makes it easier to inspect exporter drift

### 3. Add richer geometric diagnostics when a comparison fails

Potential additions:

- report delta in volume, area, and bbox
- report face-count and edge-count deltas
- export both failing STEP files into a stable artifact directory
- generate a machine-readable JSON summary alongside the test failure

Expected benefit:

- faster debugging when a DSL command diverges from the reference CadQuery implementation

### 4. Expand the equivalence matrix incrementally

Recommended next cases:

1. translated box
2. `cylinder` on `x`, `y`, and `z`
3. `combine union` with overlapping solids
4. `combine cut`
5. `move`
6. `rotate`
7. `fillet safe true`
8. `display_steps` as a full example parity case

### 5. Consider a reusable reference-model fixture layer

Potential approach:

- define each equivalence case as:
  - `.cq3d` source
  - Python reference builder
  - expected comparison tolerances
- run all cases through one shared STEP comparison helper

Expected benefit:

- easier to add broader parity coverage without duplicating setup code

## Recommendation

For now, keep the new STEP parity tests focused on simple shapes and unions and use geometry-based assertions as the gate. Add normalized STEP diffing later as a reporting enhancement, not as the first correctness check.
