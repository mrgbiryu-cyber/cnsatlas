# PPT To Reference Mapping Summary

This document summarizes how the current PPT intermediate candidates map to the
high-quality reference Figma JSON exported from the benchmark plugin.

## Inputs

- Intermediate: `docs/ppt-intermediate-candidates-12-19-29.json`
- Reference:
  - `scripts/reference-page-1.json`
  - `scripts/reference-page-2.json`
  - `scripts/reference-page-3.json`
- Full mapping report:
  - `docs/ppt-to-reference-mapping-report.json`

## High-Level Findings

### Stable mappings

- `text_block -> TEXT`
  - This is the strongest mapping across all benchmark pages.
- `connector -> VECTOR`
  - This is also stable, but only at the coarse type level. The route/shape is
    still not reconstructed correctly.
- `group/section_block -> GROUP or FRAME`
  - Slide-level grouping can be recovered at a coarse level.

### Weak mappings

- `labeled_shape`
  - Slide 12 tends to map to `GROUP`
  - Slide 29 tends to map to `FRAME`
  - This means a single global rule for labeled shapes is not reliable.
- `shape`
  - Slide 12 often maps to `GROUP` or `VECTOR`
  - Slide 29 often maps to `FRAME`
  - Pure shape recreation is context-sensitive.
- `table_row` / `table_cell`
  - Current row-level mapping is weak.
  - The reference side is not preserving rows as editable row containers in a
    way that matches our current intermediate model.

## Slide-Specific Patterns

### Slide 12

- `text_block -> TEXT` is strong.
- `connector -> VECTOR` is strong.
- `labeled_shape -> GROUP` is the dominant pattern.
- This slide behaves like a flow/process diagram.

Recommended interpretation:
- Reconstruct this page around `GROUP + VECTOR + TEXT`.
- Avoid `FRAME` shells for most decision/process boxes unless a strong grouping
  reason exists.

### Slide 19

- `table_cell -> TEXT` dominates.
- `table_row -> FRAME` exists in the best-match report, but average confidence
  is weak.
- The actual reference visual is closer to a visual table block than a semantic
  row tree.

Recommended interpretation:
- Treat the table as a visual block first.
- Overlay cell text on top of a visual grid/background structure.
- Do not assume row-level semantic containers are the correct visual output.

### Slide 29

- `labeled_shape -> FRAME` dominates.
- `shape -> FRAME` also dominates.
- `image -> FRAME` is consistent.
- `connector -> VECTOR` remains valid but sparse.

Recommended interpretation:
- This slide behaves more like a UI/mockup composition.
- Use `FRAME` blocks more aggressively than on Slide 12.

## What This Means For The Next Engine

### Keep

- Position/size extraction
- Rotation/flip extraction
- Text run extraction
- Connector source facts
- Table geometry facts

### Stop assuming

- One global visual rule for all `labeled_shape`
- One global visual rule for all tables
- That rows/cells should be recreated as the primary visual structure

### Build next

1. A slide-type-aware visual strategy selector
   - Flow/process page
   - Table-heavy page
   - UI/mockup page
2. A connector builder that stays `VECTOR`-first
3. A table builder that is visual-block-first
4. A shape builder that can choose between `GROUP` and `FRAME` depending on
   slide pattern

## Concrete Confidence Signals

### Average top-match score by subtype

- Slide 12
  - `text_block`: `0.766`
  - `connector`: `0.711`
  - `labeled_shape`: `0.487`
  - `shape`: `0.498`
- Slide 19
  - `text_block`: `0.680`
  - `connector`: `0.680`
  - `table_cell`: `0.485`
  - `table_row`: `0.300`
- Slide 29
  - `text_block`: `0.744`
  - `connector`: `0.560`
  - `labeled_shape`: `0.392`
  - `shape`: `0.395`
  - `table_cell`: `0.432`

Interpretation:
- Text is the most reliable direct mapping.
- Connectors have the right coarse target type but not enough shape fidelity.
- Tables and labeled shapes should not be handled with a single generic rule.
