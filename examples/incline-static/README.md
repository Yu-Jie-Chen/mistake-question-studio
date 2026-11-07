# Demo — static friction on an incline

This is a **synthetic** example created for the repository. It demonstrates the card shape, the figure spec, and the review status.

## What it shows

- A clean, solution-mark-free figure (`figures/fig-1.png`).
- A redraw spec (`figures/fig-1.spec.json`) that records the constraints.
- A complete `question.json` with answer, analysis, diagnosis, knowledge points, and review.
- A rendered `card.md` (formula images) — the default deliverable — and `card.html`, the same card as one self-contained printable file.
- Raw-LaTeX sidecars `question.latex.md` and `card.latex.md`.
- A clean, question-only `question.md`.

## Files

```text
incline-static/
├── question.json
├── question.md
├── question.latex.md
├── card.md
├── card.html
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
python ../../scripts/build_card_html.py card.md --out card.html
# --docx card.docx is opt-in, only for testing the Word export; the file here
# is a snapshot from before the current card layout
```

## Note

The figure is deliberately simple and does **not** include $N$, $f$, or $mg$. Those are solution marks. A real card may include a separate "student's marked figure" in the diagnosis section, but not in the clean question.
