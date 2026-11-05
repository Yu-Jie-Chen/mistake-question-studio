# Examples

## `incline-static/`

A synthetic high-school physics problem used to demonstrate the full output:

- `question.json` — structured source of truth;
- `question.md` — clean question-only text with formula images;
- `question.latex.md` — raw-LaTeX question source;
- `card.md` — teacher/student-facing card with formula images and embedded figure;
- `card.latex.md` — raw-LaTeX card source;
- `card.docx` — editable Word version with native equations and embedded figure;
- `review.md` — quality-gate record and sign-off;
- `figures/fig-1.png` — clean figure with no solution marks;
- `figures/fig-1.before.png` — original crop (for the demo, identical to the clean version because the demo was drawn clean);
- `figures/fig-1.spec.json` — the geometry/constraint record;
- `formulas/eq-*.png` — rendered formula images used by Markdown.

See [`incline-static/README.md`](incline-static/README.md).

## Adding an example

Use your own question or a synthetic one. Do not add textbook pages or exam papers without permission.

Recommended layout:

```text
examples/<name>/
├── README.md
├── question.json
├── question.md
├── question.latex.md
├── card.md
├── card.latex.md
├── card.docx
├── review.md
├── figures/
│   ├── fig-1.before.png
│   ├── fig-1.png
│   └── fig-1.spec.json
├── formulas/
│   └── eq-*.png
└── source/
    └── README.md
```

Run:

```bash
python ../scripts/validate_package.py question.json --root .
python ../scripts/build_card.py question.json \
  --out card.md --question-out question.md --docx card.docx \
  --formula-mode both
```
