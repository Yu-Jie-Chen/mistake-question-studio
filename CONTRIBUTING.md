# Contributing

Thanks for helping teachers turn marked-up questions into reusable cards.

## Before you submit

- Use your own question, a public-domain question, or content you have permission to share.
- Remove student names, school names, student IDs, scores, and faces.
- Do not submit a textbook page scan "for example" unless you own the rights.
- Keep the examples small and focused.

## What we welcome

- new subject adapters (especially non-Chinese curricula);
- figure-redraw examples with before/after images;
- PDF/OCR improvements;
- better quality gates;
- translations of `README.md` and `SKILL.md`;
- bug reports with a sanitized sample.

## Adding a subject adapter

1. Add a section to `references/subject-adapters.md`.
2. Cover: must preserve, common extraction errors, figure rules, analysis style, answer formatting.
3. Add a small example under `examples/` if possible.
4. Update the subject table in `README.md` if the subject is new.

## Adding a figure example

Include:

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

The `before` image should show the actual problem (handwriting, perspective, etc.). The `after` image should show the clean result. Do not stage a fake "before" unless the README says it is simulated.

## Testing

```bash
pip install -r requirements-formulas.txt
python scripts/validate_package.py examples/incline-static/question.json \
  --root examples/incline-static
python scripts/build_card.py examples/incline-static/question.json \
  --out /tmp/card.md --docx /tmp/card.docx --formula-mode both
python scripts/build_index.py examples --out /tmp/index.md
```

If you change a script, run it on at least one real image and one synthetic example.

## Commit style

- `feat: add chemistry apparatus adapter`
- `fix: preserve subscripts in PDF extraction`
- `docs: clarify figure redraw gate`
- `example: add math circle proof`

## Pull request checklist

- [ ] No copyrighted content added.
- [ ] No student data.
- [ ] Scripts run on Python 3.10+.
- [ ] `validate_package.py` passes for new examples.
- [ ] README/schema updated if fields changed.
- [ ] New figure examples include before/after and a spec.

## Code of conduct

Be respectful, assume good faith, and keep criticism about the work rather than the person. Teachers are the users; clarity beats cleverness.
