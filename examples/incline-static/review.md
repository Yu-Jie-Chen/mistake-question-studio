# Review — 20260101-physics-incline-001

## Source
- File: `source/README.md` (synthetic demo)
- Page: 1
- Crop: full figure
- Rights: cleared (synthetic)
- SHA-256: recorded in `manifest.json` by the intake script in a real run

## Text fidelity
- [x] Stem matches
- [x] All subquestions (none)
- [x] All options (none)
- [x] Formulas / units / signs
- [x] Tables (none)
- [x] Figure callouts
- Remaining `[?]`: none
- Other notes: synthetic demo; not from a textbook.

## Figure
- Kind: `trace-redraw`
- Before: `figures/fig-1.before.png`
- After: `figures/fig-1.png`
- Embedded in `card.md`: yes
- Embedded in `card.docx`: yes
- Removed marks: none (the demo was drawn clean)
- Preserved labels: `m`, `37°`
- Topology check: block on incline; angle from horizontal; no force arrows.
- Confidence: high

## Formulas
- Markdown mode: `both` (formula images + `card.latex.md`)
- `card.md` formula images resolve: yes (`formulas/eq-*.png`)
- `card.docx` native equations or images: native OMML
- Raw `$...$` left in DOCX: none
- `card.latex.md` present: yes

## Answer
- Final: 6 N, up the incline.
- Independent check: \(mg\sin37^\circ=6\ \text{N}\); \(f_{\max}=\mu mg\cos37^\circ=6.4\ \text{N}\); 6 < 6.4, so static friction balances at 6 N.
- Units / direction: N; up the incline.
- Confidence: high

## Diagnosis
- Student answer: \(f=6.4\ \text{N}\), down the incline.
- Error type(s): model, diagram.
- Root cause: used the maximum static friction as the actual friction; reversed the direction.
- Remedy: compare the down-slope component with \(f_{\max}\) first; then use the relative-motion tendency for direction.

## Build
- [x] `question.json` valid
- [x] `card.md` renders
- [x] `card.docx` opens
- [x] Figure paths resolve
- [x] Figure embedded in both outputs
- [x] Formulas rendered in both outputs
- [x] `review.status` correct (`reviewed`)

## Privacy and rights
- [x] Names / school / ID / scores removed
- [x] Publication rights: `cleared` (synthetic)

## Sign-off
- Reviewer: Demo
- Date: 2026-01-01
- Result: `reviewed`
