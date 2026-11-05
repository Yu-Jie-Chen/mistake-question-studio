# Examples

## `incline-static/`

A synthetic high-school physics problem used to demonstrate the full output:

- `question.json` — structured source of truth;
- `question.md` — clean question-only text;
- `card.md` — teacher/student-facing card;
- `card.docx` — editable Word version;
- `review.md` — quality-gate record and sign-off;
- `figures/fig-1.png` — clean figure with no solution marks;
- `figures/fig-1.before.png` — original crop (for the demo, identical to the clean version because the demo was drawn clean);
- `figures/fig-1.spec.json` — the geometry/constraint record.

See [`incline-static/README.md`](incline-static/README.md).

## Adding an example

Use your own question or a synthetic one. Do not add textbook pages or exam papers without permission.

Recommended layout:

```text
examples/<name>/
├── README.md
├── question.json
├── card.md
├── card.docx
├── figures/
│   ├── fig-1.before.png
│   ├── fig-1.png
│   └── fig-1.spec.json
└── source/
    └── README.md
```

Run:

```bash
python ../scripts/validate_package.py question.json --root .
python ../scripts/build_card.py question.json --out card.md --docx card.docx
```
