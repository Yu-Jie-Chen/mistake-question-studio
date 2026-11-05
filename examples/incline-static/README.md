# Demo — static friction on an incline

This is a **synthetic** example created for the repository. It demonstrates the card shape, the figure spec, and the review status.

## What it shows

- A clean, solution-mark-free figure (`figures/fig-1.png`).
- A redraw spec (`figures/fig-1.spec.json`) that records the constraints.
- A complete `question.json` with answer, analysis, diagnosis, knowledge points, and review.
- A rendered `card.md` (formula images) — the default deliverable — plus an optional `card.docx` sample (native Word equations).
- Raw-LaTeX sidecars `question.latex.md` and `card.latex.md`.
- A clean, question-only `question.md`.

## Files

```text
incline-static/
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
│   ├── fig-1.svg
│   └── fig-1.spec.json
├── formulas/
│   └── eq-*.png
└── source/
    └── README.md
```

## Rebuild

```bash
pip install -r ../../requirements-formulas.txt
python ../../scripts/validate_package.py question.json --root .
python ../../scripts/build_card.py question.json \
  --out card.md --question-out question.md \
  --formula-mode both
# --docx card.docx is opt-in, only for testing the Word export
```

## Note

The figure is deliberately simple and does **not** include $N$, $f$, or $mg$. Those are solution marks. A real card may include a separate "student's marked figure" in the diagnosis section, but not in the clean question.
