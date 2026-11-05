# Figure cleanup and redraw

Use this reference for any question that depends on a diagram, graph, apparatus, map, circuit, structural formula, or table-like figure.

The goal is not "a pretty picture". The goal is **the same figure with the same information, minus the solution marks**.

## 1. Classify the figure

| Type | Examples | Default treatment |
|---|---|---|
| Line schematic | force diagram, circuit, optics ray diagram | crop or trace redraw |
| Geometric figure | triangle, circle, coordinate graph | trace redraw with exact constraints |
| Apparatus | chemistry setup, experimental rig | trace redraw; preserve joints and flow |
| Graph | function curve, data plot | crop or rebuild axes/data |
| Map | contour, climate, regional map | crop; preserve scale/north/legend |
| Structural formula | organic molecule | use a chemistry-aware editor or precise SVG |
| Table-like figure | comparison grid, chart | rebuild as table or chart, not a drawing |

If the figure is decorative and the stem is complete without it, omit it and say so.

## 2. Separate the layers

Look for four layers:

1. **Printed question** — black/gray, consistent stroke, stable font.
2. **Printed figure** — same ink as the question, geometric.
3. **Student/teacher handwriting** — colored or black, variable stroke, overlaps.
4. **Solution annotations** — force arrows, labels such as $N$, $f$, $mg$, auxiliary lines, coordinates, "答案" notes.

Only layers 1–2 belong in the clean card. Layer 4 is evidence for diagnosis, not part of the question.

### Mark classification cues

| Cue | Likely layer |
|---|---|
| Color (red, blue, green) | handwriting/teacher mark |
| Stroke width varies abruptly | handwriting |
| Arrowhead added on top of a printed line | solution annotation |
| Label not in the same font/size as printed labels | handwriting |
| Dashed line added to a solid figure | auxiliary/solution |
| Text inside the figure in a different hand | student note |

When color is unavailable (black-and-white scan), use position and stroke continuity. If still ambiguous, keep the mark out and record it in `review.md`.

## 3. Choose the treatment

```text
Is the figure readable and complete?
├─ No → stop; ask for a better source, or rebuild only from explicit evidence
└─ Yes
   ├─ No handwriting over geometry?
   │  └─ Clean crop → deskew → whiten → trim
   ├─ Handwriting only on empty background?
   │  └─ Mask/inpaint → keep printed geometry → compare
   ├─ Handwriting overlaps geometry, or perspective is severe?
   │  └─ Trace redraw from a diagram spec
   └─ Figure is missing/too degraded?
      └─ Rebuild only with a source description; mark confidence low
```

### Clean crop

Use when:

- the printed figure is clear;
- no annotation touches a line, label, or arrow;
- the page is not strongly curved.

Steps:

1. Crop with 8–12 px padding.
2. Rotate by the measured skew (usually −3° to +3°).
3. Normalize the paper to white; keep black lines black.
4. Remove scanner noise without erasing thin dashed lines.
5. Trim margins; export PNG at 300 DPI or ≥1600 px on the long side.

### Mask and keep

Use when:

- the annotation sits in empty space or over a large white area;
- the printed geometry is intact underneath;
- you can fill the masked area with nearby paper texture.

Steps:

1. Record every mask shape in `fig-N.mask.json`.
2. Fill from a nearby clean patch, not from a global average.
3. Feather the patch edges.
4. Re-draw any printed line that the mask crossed.
5. Compare at 100% and at fit-to-page.

Do not mask over a label, arrowhead, intersection, or thin dashed line unless you redraw it.

### Trace redraw

Use when:

- annotations overlap the geometry;
- the photo is perspective-distorted;
- the figure is low-resolution but structurally clear;
- the figure must be edited for a worksheet.

Trace the **structure**, not the pixels. A good redraw looks like a clean textbook figure, not a filtered photo.

### Rebuild

Use only when:

- the original figure is missing and the stem describes it completely;
- the user explicitly asks for a reconstruction;
- the reconstruction can be checked against a textual description.

Mark `figure.confidence = "low"` and list every inferred element.

## 4. Build a diagram spec before drawing

Do not start with a drawing tool. First write down what must be true.

```json
{
  "figure_id": "fig-1",
  "kind": "physics-mechanics",
  "canvas": {"width": 1600, "height": 1200, "background": "white"},
  "elements": [
    {"id": "incline", "type": "line", "p1": [200, 900], "p2": [1100, 350], "style": "solid"},
    {"id": "block", "type": "polygon", "points": [[...]], "fill": "white"},
    {"id": "string", "type": "line", "p1": [...], "p2": [...], "constraint": "parallel to incline"},
    {"id": "pulley", "type": "circle", "center": [...], "r": 32},
    {"id": "label-A", "type": "label", "text": "A", "at": [...]}
  ],
  "constraints": [
    "string is parallel to the incline",
    "block sits on the incline",
    "pulley is fixed",
    "angle 37° is measured from the horizontal"
  ],
  "removed_marks": ["N arrow", "f label", "mg arrow"],
  "labels_to_preserve": ["A", "B", "v1", "v2", "L = 5 m"],
  "source_crop": [120, 80, 980, 720]
}
```

### What the spec must capture

- **Topology:** what connects to what, what is inside/outside, what crosses.
- **Directions:** arrows, flow, current, light rays, forces that are part of the question.
- **Styles:** solid vs. dashed, thick vs. thin, open vs. filled.
- **Labels:** exact letters, subscripts, units, prime marks.
- **Constraints:** parallel, perpendicular, tangent, equal length, angle value, midpoint.
- **Scale/orientation:** north arrow, axes, tick marks, legend.

If a constraint is not stated and not visually obvious, mark it `[assumed]` and do not rely on it silently.

## 5. Draw

Preferred order:

1. **SVG** — editable, crisp, diffable.
2. **TikZ / GeoGebra / chemistry editor** — when the subject needs exact constructions.
3. **Matplotlib / PIL** — when a raster is the only option; draw at 3× and downsample.
4. **PowerPoint shapes** — when the teacher needs to edit in Office.

Guidelines:

- Use a restrained stroke palette: black lines, light gray fills, one accent color at most.
- Use a serif font for labels to match textbook style; keep math italic.
- Keep label sizes consistent.
- Keep arrows away from line intersections.
- Leave breathing room around labels; do not let a label touch a line.
- Draw the figure at 1600–2400 px on the long side, then export.
- Export a white-background PNG for documents and, if useful, a transparent PNG for slides.

### Label typography

- Variables: italic serif, e.g. $v$, $m$, $L$.
- Subscripts: smaller, baseline-shifted, upright digits: $v_1$, not `v1`.
- Units: upright, with a thin space: $5\ \text{m/s}$.
- Chinese labels: a clean sans/serif; keep the same size as Latin labels.
- Do not use a decorative font that differs from the rest of the card.

## 6. Compare before and after

Put `fig-N.before.png` and `fig-N.png` side by side at the same scale. Check:

- [ ] Same number of objects.
- [ ] Same connections and intersections.
- [ ] Same arrows and directions.
- [ ] Same dashed/solid style.
- [ ] Same labels, subscripts, and units.
- [ ] Same angle marks and right-angle marks.
- [ ] Same relative positions (left/right, above/below).
- [ ] No solution marks remain.
- [ ] No printed labels were accidentally removed.
- [ ] The figure still makes sense without the original page.

If a difference is intentional, record it in `review.md` with the reason.

## 7. Subject-specific reminders

Detailed rules are in [`subject-adapters.md`](subject-adapters.md). Quick reminders:

### Physics

- Keep the original force arrows only if the question provides them; remove $N$, $f$, $mg$ added by the student.
- Preserve circuit symbols, polarity, meter positions, and switch state.
- Preserve ray directions and normals; do not "tidy" an angle.
- Keep the pulley/string topology exact: which side is fixed, which end is free.
- Keep the direction of motion and the belt/ground frame.

### Mathematics

- Preserve exact construction marks: right angles, equal segments, parallel marks, arcs.
- Keep point labels and their order.
- For function graphs, preserve axes, intercepts, asymptotes, and marked points.
- Do not redraw a "similar" triangle with different proportions if the problem depends on lengths.

### Chemistry

- Preserve apparatus joints, stoppers, delivery tubes, heating, and gas flow.
- Keep liquid levels and labels.
- For structural formulas, preserve bond order and stereochemistry.
- Do not replace a specific apparatus with a generic flask if the question asks about the apparatus.

### Biology

- Keep leader lines attached to the correct structure.
- Preserve labels and orientation (left/right, upper/lower).
- Do not simplify away a structure the question asks to identify.

### Geography

- Keep north arrow, scale, legend, contour values, and direction.
- Do not redraw a map from memory; crop it or use a licensed base.

### English

- Figures are usually tables or line-numbered passages; preserve layout and line numbers.
- Do not turn a passage into a paragraph if line numbers matter.

## 8. Anti-patterns

| Anti-pattern | Why it is wrong |
|---|---|
| Adding $N$, $f$, $mg$ "to make it a physics diagram" | These are solution marks, not the question |
| Straightening a tilted belt but changing the angle | The angle may be the given data |
| Replacing $v_1$ with $v$ | Changes the symbol and the answer |
| Removing a dashed line because it looks messy | Dashed/solid can encode a condition |
| Using a generic apparatus | The question may ask about a specific setup |
| Tracing a photo's shadow | Produces a dirty, non-reusable figure |
| Redrawing a graph without its axes | The graph's meaning is lost |
| Cropping off a label or dimension | The stem no longer matches the figure |
| Using AI image generation for a technical figure | Invents geometry and labels |

## 9. Worked example (anonymized): conveyor belt + pulley

A real cleanup often looks like this.

### What was printed

- an inclined conveyor belt;
- block A on the belt, connected by a string over a fixed pulley to hanging block B;
- printed labels $A$, $B$, $v_1$, $v_2$, $L=5\ \text{m}$;
- an arrow for the belt direction.

### What was handwritten

- $N$ above A;
- $f_{\text{滑}}$ beside A;
- $mg$ below A;
- several force arrows crossing the block and the string.

### Decision

**Trace redraw**, not a clean crop.

Why:

- the force arrows crossed the block outline and the string;
- the block was small and partly hidden by labels;
- the figure needed to be reused in a worksheet.

### Diagram-spec constraints

- A sits on the belt, with its base parallel to the belt;
- the string is parallel to the belt;
- the pulley is fixed above the upper end;
- B hangs vertically;
- $v_1$ points down the belt; $v_2$ points down the belt;
- $L$ is the belt length, not the horizontal projection.

### What was removed

- $N$, $f_{\text{滑}}$, $mg$;
- all hand-drawn force arrows;
- handwritten answer text outside the figure.

### What was preserved

- A, B, the pulley, the belt, the string;
- $v_1$, $v_2$, $L=5\ \text{m}$;
- the slope direction and the belt-motion direction.

### A small layout lesson

If the string is drawn from the top-right corner and is collinear with the block's top edge, the block can look like two compartments. Attach the string to the centre of the side edge, or add a small knot at the attachment, so the block outline remains readable.

### Validation

- The string is parallel to the belt in the redraw.
- The pulley is fixed, not floating.
- B hangs vertically.
- No force arrow remains.
- The labels $v_1$ and $v_2$ are subscripts, not `v1`/`v2`.
- The figure can be understood without the original page.

## 10. Minimal output set

For each figure:

```text
figures/
├── fig-1.before.png
├── fig-1.png
├── fig-1.spec.json      # if redrawn
└── fig-1.mask.json      # if masked
```

Record in `manifest.json`:

```json
{
  "figure": {
    "kind": "trace-redraw",
    "source_crop": [120, 80, 980, 720],
    "canvas": [1600, 1200],
    "removed_marks": ["N", "f", "mg"],
    "labels_preserved": ["A", "B", "v1", "v2", "L=5m"],
    "confidence": "high"
  }
}
```
