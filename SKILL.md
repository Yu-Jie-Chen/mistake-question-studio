---
name: mistake-question-studio
description: >
  Turn wrong-question photos, screenshots, and PDF pages into clean, reusable
  study cards. Extract question stems and subquestions, separate printed content
  from student/teacher handwriting, crop or redraw figures without solution
  marks, solve and analyze the problem, diagnose the error, and export Markdown
  or DOCX. Works across physics, chemistry, mathematics, English, biology,
  geography, history, and other subjects. Trigger phrases include 整理错题,
  错题本, 错题卡, 提取题目, 题目去痕, 重绘配图, 从截图/PDF 整理题目,
  生成答案与解析.
metadata:
  version: "0.2.0"
  author: "Yujie Chen"
  license: "MIT"
  repository: "https://github.com/Yu-Jie-Chen/mistake-question-studio"
---

# 错题整理 · Mistake Question Studio

A subject-agnostic workflow that turns one photographed question, one screenshot, or one PDF page into a **clean, teachable, reviewable study card**.

The skill is deliberately split into a short route map plus focused references. Read only the references needed for the current task.

## What this skill produces

A self-contained work folder:

```text
work/<id>/
├── source/                 # untouched original image/PDF, checksum in manifest
├── text/
│   ├── question.md         # optional question-only Markdown
│   └── question.json       # structured source of truth
├── figures/
│   ├── fig-1.before.png    # original crop, for audit
│   ├── fig-1.png           # cleaned or redrawn figure
│   └── fig-1.spec.json     # only when redrawn
├── formulas/               # optional formula images for Markdown
├── card.md                 # teacher/student-facing card — the deliverable
├── card.latex.md           # raw-LaTeX source sidecar (optional)
├── manifest.json           # files, page numbers, tools, confidence
└── review.md               # checks, uncertainties, teacher sign-off
```

> **Delivery default: Markdown only.** `card.md` is what you hand over. Do **not** build
> `card.docx` unless the user explicitly asks for a Word file — in the default flow the whole
> DOCX pipeline (python-docx, OMML, LibreOffice rendering) is skipped, together with the
> `card.docx` items in the quality gates.

## Non-negotiable rules

1. **Source fidelity before beautification.** Never silently change a number, unit, label, option, condition, or subquestion. Mark uncertainty as `[?]` and ask.
2. **Separate layers.** Printed question, student answer, teacher marks, and solution annotations are four different layers. Only the printed question and its original figure belong in the clean card.
3. **No solution marks in the figure.** Force arrows (`N`, `f`, `mg`), auxiliary lines, added coordinates, and "here is the answer" annotations are removed unless they are part of the original question.
4. **Trace, do not invent.** A redrawn figure must preserve topology, connections, directions, dashed/solid style, labels, and proportions stated by the question. If geometry cannot be established, stop and ask.
5. **Solve independently.** The answer must be derived after extraction, not copied from the student's marks or from an answer key alone. Cross-check units, signs, and edge cases.
6. **Teacher confirmation before publishing.** A card can be generated automatically, but it enters a shared question bank only after a human checks the `review.md` gates.
7. **Privacy and copyright.** Remove names, school names, student IDs, and scores. Do not publish third-party questions, scans, or answer keys without permission.
8. **One source of truth.** `text/question.json` is authoritative; `card.md` is its rendering. If they disagree, fix the JSON and rebuild.
9. **Figures are embedded, not merely stored.** If the stem depends on a figure, `card.md` must contain it. A figure that exists only in `figures/` is a failed build.
10. **Formulas are rendered, not left as raw source.** In `card.md`, math must either be rendered by the target viewer (LaTeX/KaTeX-capable viewer) or appear as `formulas/eq-*.png` images; a card that only works with a raw `$...$` dump is not finished. (If a Word file is explicitly requested, it must use native equations or formula images, never raw `$...$`.)

## Choose a route

| User intent | Route | Read |
|---|---|---|
| One screenshot/photo → one complete card | **Quick** | [`references/workflow.md`](references/workflow.md) §Quick |
| PDF, multi-page, or multi-question page | **Standard** | [`references/workflow.md`](references/workflow.md) + [`references/extraction.md`](references/extraction.md) |
| A folder of many questions | **Batch** | [`references/workflow.md`](references/workflow.md) §Batch |
| Only clean/redraw the figure | **Figure-only** | [`references/figure-redraw.md`](references/figure-redraw.md) |
| Only extract text (no card) | **Extract-only** | [`references/extraction.md`](references/extraction.md) |
| Need subject-specific notation or answer style | any | [`references/subject-adapters.md`](references/subject-adapters.md) |
| Before export/review | any | [`references/quality-gates.md`](references/quality-gates.md) |

If the request is ambiguous, default to **Standard** for PDFs and **Quick** for a single image.

## Workflow at a glance

0. **Intake** — subject, grade, source, desired output, rights, and whether the student's answer should be preserved.
1. **Preserve** — copy the source unchanged; record checksum, page, and crop coordinates.
2. **Segment** — find question boundaries, subquestions, options, tables, and figure regions.
3. **Extract text** — PDF text layer first, OCR only as fallback; preserve math, blanks, units, and line structure.
4. **Handle figures** — classify, crop/clean/redraw, and compare before/after.
5. **Solve and analyze** — solve independently; write steps, key points, pitfalls, and a compact diagnosis.
6. **Diagnose** — separate "what the student wrote" from "why it is wrong"; classify the error.
7. **Build** — render `card.md` from `question.json`; no DOCX unless explicitly requested.
8. **Validate and review** — run the quality gates; record uncertainties and teacher sign-off.

## Minimum output contract

Every finished card must contain:

- a complete stem and every subquestion/option;
- correct units and all data actually stated;
- at least one figure if the original depends on a figure, embedded in `card.md`;
- formulas readable in `card.md` — rendered images or a math-rendering viewer, never a raw `$...$` dump;
- the final answer, with confidence level;
- a step-by-step analysis that a student can follow;
- knowledge points, common pitfalls, and one error diagnosis;
- a source note and a review status.

The exact fields are defined in [`references/output-schema.md`](references/output-schema.md).

## Quality gates (summary)

| Gate | Blocking question |
|---|---|
| Source | Is the original preserved and traceable? |
| Text | Does the extracted text match the source, including notation and blanks? |
| Figure | Is the topology correct, are solution marks gone, and is the figure embedded in `card.md`? |
| Formula | Are formulas readable in `card.md` — rendered images or a math renderer, not raw `$...$`? |
| Answer | Is the answer independently verified, with units and signs? |
| Diagnosis | Is the error classification specific and actionable? |
| Export | Do `card.md` and `question.json` agree? |
| Privacy | Are names, schools, IDs, and scores removed? |
| Rights | Is publication permitted? |

Full checklist: [`references/quality-gates.md`](references/quality-gates.md).

## Stop and ask when

- the host cannot view images or run OCR — ask for a text/PDF text layer instead of guessing;
- the page is cut off, blurred, or missing a subquestion;
- a symbol could be read two ways and the answer changes;
- the figure's topology cannot be recovered from the image;
- the source is copyrighted and the user wants to publish it;
- the answer requires a syllabus convention you cannot confirm (e.g., significant figures, `g` value, state symbols);
- the student's handwriting is being confused with printed content.

Do not guess silently. Ask one focused question with the smallest crop or excerpt needed.

## Batch mode

For a folder of images/PDFs:

1. Create one work folder per question; never merge unrelated questions.
2. Use stable IDs: `YYYYMMDD-subject-topic-###`.
3. Generate `index.md` with [`scripts/build_index.py`](scripts/build_index.py).
4. Run validation on every card before indexing.
5. Keep a `batch-review.md` that lists skipped pages and why.

## Helper scripts

The scripts are optional accelerators. Use them when Python 3.10+ is available; otherwise follow the same steps with the host's native tools.

```bash
# 1. Render PDF pages or normalise images
python scripts/prepare_scan.py input.pdf work/20260101-physics-001/source --dpi 300

# 2. Crop/deskew/whiten a figure (and optionally apply a manual erase mask)
python scripts/clean_figure.py raw.png figures/fig-1.png \
  --crop 120,80,980,720 --rotate -1.2 --trim --max-side 2400

# 3. Extract PDF text when a text layer exists
python scripts/extract_pdf.py input.pdf text --pages 1-3

# 4. Build the card from question.json (Markdown only — no DOCX)
pip install -r requirements-formulas.txt   # only if you render formulas/eq-*.png
python scripts/build_card.py text/question.json \
  --out card.md --question-out text/question.md \
  --formula-mode both

# 5. Validate references, required fields, and placeholders
python scripts/validate_package.py text/question.json --root .

# 6. Build a batch index
python scripts/build_index.py work --out index.md
```

Core dependency: `pillow` and `numpy`. Formula images: `requirements-formulas.txt` (`matplotlib`; `python-docx`/`latex2mathml`/`mathml2omml` only for an explicitly requested Word file). PDF/OCR: `pymupdf`/`pypdf`/`pdf2image`, `pytesseract`.

## First-run checklist

- [ ] Read the route table and select one route.
- [ ] Read the subject adapter **before** solving.
- [ ] Read the figure rules **before** touching the figure.
- [ ] Read the output schema **before** writing `question.json`.
- [ ] Install `requirements-formulas.txt` only if `card.md` needs `formulas/eq-*.png`.
- [ ] Run the quality gates **before** calling the card finished.
- [ ] Record every uncertainty in `review.md`.

## Repository layout

```text
mistake-question-studio/
├── SKILL.md
├── README.md
├── README.en.md
├── LICENSE
├── CONTRIBUTING.md
├── scripts/
├── references/
├── templates/
├── examples/
└── .github/
```

## Design principle

The skill encodes **decisions and evidence**, not a hidden chain of thought. Every non-trivial choice should leave a trace: a crop rectangle, a diagram spec, a confidence level, or a review note. That is what makes a card reproducible by another teacher.
