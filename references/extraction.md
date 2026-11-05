# Text extraction

Use this reference when the source is a screenshot, a photographed page, a scanned page, a PDF with a text layer, or a PDF that needs OCR.

## Evidence hierarchy

1. **PDF text layer** — exact characters and reading order (but not necessarily layout).
2. **High-resolution render + OCR** — good for scans; needs preprocessing.
3. **Vision reading** — best for figures, tables, and ambiguous notation.
4. **Manual confirmation** — required when a symbol could change the answer.

Never let a later layer overwrite an earlier one silently. If the text layer and OCR disagree, record both and ask.

## PDF with a text layer

Try, in order:

```bash
# Poppler
pdftotext -layout input.pdf out.txt

# Python: pypdf
python -c "from pypdf import PdfReader; r=PdfReader('input.pdf'); print('\n\f'.join(p.extract_text() or '' for p in r.pages))"

# Python: pdfminer.six
python -c "from pdfminer.high_level import extract_text; print(extract_text('input.pdf'))"
```

Or use the bundled helper:

```bash
python scripts/extract_pdf.py input.pdf text --pages 1-3
```

Then verify visually against a 300 DPI render. The text layer often loses:

- fractions and stacked expressions;
- subscripts/superscripts;
- table cells and reading order;
- figure labels;
- blanks and answer lines;
- check marks and handwritten annotations.

## PDF without a text layer

1. Render at 300–400 DPI.
2. Deskew and increase contrast.
3. OCR with the right language pack.
4. Read the page visually and compare line by line.

```bash
python scripts/prepare_scan.py input.pdf work/id/source --dpi 300 --pages 1-3
tesseract page-001.png page-001 -l chi_sim+eng --psm 6
```

OCR settings:

| Content | Suggested `--psm` |
|---|---|
| Single block of text | `6` |
| Sparse text / labels | `11` |
| Single column, multi-line | `4` |
| Table | `6` then rebuild manually |

OCR is a draft, not a source of truth. Mark every low-confidence character.

## Two-pass transcription

### Pass A — content

Transcribe exactly:

- numbers, signs, units, powers of ten;
- variables and subscripts;
- punctuation that changes meaning (`，` vs `；`, `不` vs `不?`);
- blanks (`____`), answer lines, and options;
- table headers and units.

Do not fix grammar or style.

### Pass B — structure

Restore:

- question number and subquestion labels;
- options A/B/C/D on separate lines;
- tables as Markdown tables;
- formulas as LaTeX;
- figure/table callouts;
- the relationship between a stem and its subquestions.

If the source uses `(1)`, keep `(1)`, not `1.`.

## Mathematics and formulas

Use inline LaTeX for short expressions and display math for multi-line derivations.

```markdown
已知 $a+b=5$，$ab=6$，求 $a^2+b^2$。

$$
\frac{1}{R}=\frac{1}{R_1}+\frac{1}{R_2}
$$
```

Rules:

- Keep the source's symbol case: $v$ vs $V$, $m$ vs $M$.
- Keep subscripts: $v_1$ is not $v1$.
- Keep units outside math where possible: `$v=2\ \text{m/s}$`.
- Do not convert fractions to decimals unless the question does.
- Do not add parentheses that change grouping.
- For chemistry, the default renderer does **not** support `\ce{}` (mhchem). Use `\mathrm{H_2O}`, `\mathrm{CO_2}`, `\mathrm{Fe^{2+}}`, and `\rightarrow` / `\rightleftharpoons` for equations; or write the equation as plain text with subscripts if the formula is long.
- For vectors, preserve the source's arrow/bold convention; if unclear, note it.
- Keep the LaTeX source in `question.json`; the card builder renders it to formula images for Markdown and native OMML equations for DOCX. Do not pre-render or delete the source.

Common OCR confusions to check:

| Source | OCR may produce |
|---|---|
| `μ` | `u`, `p`, `m` |
| `θ` | `0`, `O`, `8` |
| `×` | `x`, `*` |
| `÷` | `+`, `-` |
| `−` (minus) | `-`, `—` |
| `²` | `2`, `?` |
| `₁` | `1`, `i` |
| `∴` / `∵` | `.'.` / `.'` |
| `∝` | `x`, `oc` |

## Tables

Rebuild tables; do not flatten them into a sentence.

```markdown
| 实验次数 | 电压 $U/\text{V}$ | 电流 $I/\text{A}$ |
|---:|---:|---:|
| 1 | 1.0 | 0.20 |
| 2 | 2.0 | 0.40 |
```

Check:

- header units;
- row/column order;
- merged cells;
- empty cells (keep them empty, do not invent `0`);
- footnotes below the table.

## English passages

Preserve:

- paragraph breaks;
- line numbers if present;
- blanks (`____`) and their numbers;
- options A/B/C/D;
- italics/bold used for emphasis;
- punctuation that affects meaning.

Do not:

- correct grammar;
- translate unless asked;
- split a passage away from its questions if the questions refer to line numbers;
- drop the instructions ("Read the passage and choose...").

For English, the figure pipeline is usually irrelevant; the layout pipeline is not. Keep the passage and the questions together.

## Student handwriting and answer keys

These are **not** part of the clean stem.

### Student handwriting

- Transcribe only when the user asks for diagnosis or wants the original answer preserved.
- Keep it in `diagnosis.student_answer_md`, never in `question.stem_md`.
- Mark unclear words/numbers as `[?]`; do not guess a student's intention.
- If the handwriting is unreadable, leave the field empty and note it.
- Do not let a student's wrong answer influence the extraction of the printed data.

### Answer keys

- Put a provided key in `source/answer-key.md` or `answer.alternate_md`; do not overwrite the clean stem.
- Use it as a cross-check, not as the only solution.
- If your independent answer disagrees, record both and explain why.
- If the key is ambiguous or wrong, flag it; do not silently "fix" it.

## Figure labels inside text

A label such as `如图，A、B...` is a dependency. If the figure is removed, the stem becomes incomplete. Either keep a clean figure or rewrite the stem only with explicit permission.

When a figure has labels $A$, $B$, $O$, $P$, keep the exact letters. A redrawn figure with different letters is a different question.

## Source-language policy

- Keep the source language for the question and answer unless the user asks for translation.
- If translating, keep the original alongside the translation and mark which one is authoritative.
- For bilingual cards, put the source text first.

## Confidence markers

Use these consistently:

| Marker | Meaning |
|---|---|
| `[?]` | Character/word uncertain; answer may change |
| `[sic]` | Source appears wrong or nonstandard; preserved intentionally |
| `[missing]` | Part of the source is cut off or unreadable |
| `[figure: ...]` | Figure/table callout that must resolve to an asset |

A card with `[?]`, `[missing]`, or unresolved `[figure: ...]` cannot pass the text gate.

## Verification diff

After extraction:

1. Put the source crop and the extracted text side by side.
2. Read the extracted text aloud (mentally) against the source.
3. Check every number, unit, sign, subscript, and option.
4. Check the first and last line of each subquestion.
5. Check that no line from the next question leaked in.
6. Record the comparison in `review.md`.

## When to stop

Stop and ask if:

- a digit or sign is unclear and the answer depends on it;
- a formula's grouping is ambiguous;
- a table's row/column alignment is broken;
- the text layer and OCR disagree on a number;
- the question refers to a figure that is missing;
- the source language is mixed and it is unclear which wording is authoritative.
