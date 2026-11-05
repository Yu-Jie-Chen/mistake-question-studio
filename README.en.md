# Mistake Question Studio

> Turn wrong-question photos, screenshots, and PDF pages into clean, teachable study cards.

**Project:** `mistake-question-studio`　|　**Author:** [Yujie Chen](https://github.com/Yu-Jie-Chen)　|　**Repository:** [Yu-Jie-Chen/mistake-question-studio](https://github.com/Yu-Jie-Chen/mistake-question-studio)

Mistake Question Studio is a subject-agnostic AI skill and lightweight Python toolkit for teachers who organize wrong questions.

## What it does

- extracts the stem, subquestions, options, formulas, and tables;
- separates printed content from student/teacher handwriting;
- crops, cleans, or redraws figures without solution marks;
- solves the question independently and writes a teachable analysis;
- diagnoses the error instead of only marking it wrong;
- exports Markdown and DOCX cards;
- builds a searchable index for a question bank.

It supports physics, chemistry, mathematics, English, biology, geography, history, politics, and other subjects through subject adapters.

## Quick start

Clone and place the folder where your agent discovers skills; the entry point is [`SKILL.md`](SKILL.md).

```bash
git clone https://github.com/Yu-Jie-Chen/mistake-question-studio.git
```

> **DSH note:** the DSH Plugin Manager only installs npm bundles that declare `dsh.bundle.patch`. This repository is a **Skill**, not a plugin package. Install it under `~/.dsh/skills/`, not through “Install plugin”. The “no bundle declaration” error from the Plugin Manager is expected.

Then ask:

```text
Turn this wrong question into a clean study card:
extract the stem, remove the handwriting from the figure,
redraw the figure, and give the answer, analysis, and error diagnosis.
```

Or use the scripts directly:

```bash
python scripts/prepare_scan.py input.pdf work/id/source --dpi 300
python scripts/clean_figure.py raw.png figures/fig-1.png --crop 120,80,980,720 --trim
python scripts/extract_pdf.py input.pdf text --pages 1-3
python scripts/build_card.py text/question.json --out card.md --question-out text/question.md --docx card.docx
python scripts/validate_package.py text/question.json --root .
python scripts/build_index.py work --out work/index.md
```

Core dependencies: `pillow`, `numpy`. Optional: `pymupdf`, `pypdf`, `python-docx`, `pytesseract`.

## Design principles

1. Source fidelity before beautification.
2. Separate the question, the student's answer, and the solution marks.
3. Trace, do not invent, when redrawing a figure.
4. Solve independently and record confidence.
5. Keep every decision traceable: crop, mask, diagram spec, review note.
6. Require a human review gate before publishing.

## Demo

See [`examples/incline-static/`](examples/incline-static/): a synthetic physics question with a clean figure, `question.json`, `card.md`, and a figure spec.

## Documentation

- [Workflow](references/workflow.md)
- [Text extraction](references/extraction.md)
- [Figure cleanup and redraw](references/figure-redraw.md)
- [Subject adapters](references/subject-adapters.md)
- [Output schema](references/output-schema.md)
- [Quality gates](references/quality-gates.md)

## Privacy and copyright

Use only content you own or have permission to reproduce. Remove student names, school names, IDs, and scores before sharing. The examples in this repository are synthetic.

## License

MIT. See [`LICENSE`](LICENSE).
