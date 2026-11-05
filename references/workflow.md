# Workflow

This file is the operating procedure for **Quick**, **Standard**, and **Batch** routes. Read `SKILL.md` first. Load only the sections you need.

## Phase 0 — Intake

Collect or infer:

| Field | Why it matters |
|---|---|
| Subject | Selects notation, figure rules, and answer style |
| Grade / level | Controls vocabulary, allowed methods, and difficulty |
| Source type | Screenshot, photo, scanned page, PDF, DOCX, or already-cropped image |
| Source rights | Local use vs. public sharing |
| Output | Markdown card (default), figure only, or text only; ask before producing a Word file |
| Student answer | Preserve for diagnosis, but keep it out of the clean question |
| Answer key | Use only as a cross-check, never as the sole source |

If the user does not specify, default to: Markdown card, preserve student answer in a separate diagnosis field, do not publish.

Create the work folder:

```text
work/<id>/
├── source/
├── text/
├── figures/
├── card.md
├── manifest.json
└── review.md
```

Use `YYYYMMDD-subject-topic-###` for the ID, e.g. `20260101-physics-incline-001`.

## Phase 1 — Preserve the source

1. Copy the original file, never edit it in place.
2. Record SHA-256, page number, and original dimensions in `manifest.json`.
3. If the source is a PDF, record the page range and render DPI.
4. If the source is a photo, record the crop rectangle used later.
5. Keep `source/` out of the public repository unless rights allow.

Minimal manifest:

```json
{
  "id": "20260101-physics-incline-001",
  "source": {
    "file": "source/original.jpg",
    "sha256": "...",
    "pages": [1],
    "rights": "private-study"
  },
  "tools": {"extract": "vision+manual", "figure": "redraw"},
  "confidence": {"text": "high", "figure": "high", "answer": "high"}
}
```

## Phase 2 — Segment the page

### Quick (single image)

1. Rotate to upright; crop out the desk, fingers, and page edges.
2. Identify the question number and the end of the question (next number, answer line, or large margin).
3. If the page contains several questions, switch to Standard and split them.
4. Crop with 8–12 px padding so no printed stroke is cut.

### Standard (PDF or multi-question page)

1. Prefer the PDF text layer for reading order.
2. Render the page at 300 DPI for visual verification.
3. Build a block map: stem, subquestions, options, table, figure, student answer, teacher marks.
4. For two-column pages, read one column at a time.
5. For a question that spans pages, join by question number and record both page numbers.
6. Never merge two independent questions into one card.

### Segmentation checklist

- [ ] Question number included or deliberately omitted.
- [ ] All subquestions included.
- [ ] All options included.
- [ ] Tables kept as tables, not flattened prose.
- [ ] Figure callouts (如图, 表中, 图中) still point to an existing figure/table.
- [ ] Student answer and teacher marks excluded from the clean stem.

## Phase 3 — Extract text

Read [`extraction.md`](extraction.md) before extracting formulas, tables, or English passages.

Core order:

1. **PDF text layer** — fastest and most faithful when available.
2. **High-resolution OCR** — for scans and photos; preprocess first.
3. **Vision reading** — for layout, diagrams, and ambiguous symbols.
4. **Manual confirmation** — for anything that changes the answer.

Two-pass rule:

- **Pass A (content):** transcribe what is written.
- **Pass B (structure):** restore subquestion labels, options, tables, formulas, units, and blanks.

Do not "improve" the wording. Keep the source's notation, even if it is nonstandard; add a note if it is ambiguous.

## Phase 4 — Handle the figure

Read [`figure-redraw.md`](figure-redraw.md) before editing pixels.

Decision order:

1. **Clean crop** — printed figure is clear, no overlap.
2. **Mask and keep** — handwriting only touches empty background, not geometry.
3. **Trace redraw** — handwriting overlaps geometry, perspective is severe, or resolution is too low.
4. **Rebuild** — figure is missing or unreadable; only with explicit evidence and a note.

For every figure, keep:

- `fig-N.before.png` — original crop;
- `fig-N.png` — clean output;
- `fig-N.spec.json` — if redrawn;
- a one-line caption describing what the figure shows.

Do not put force arrows, auxiliary lines, coordinates, or answer labels into the clean figure unless the original question includes them.

## Phase 5 — Solve and analyze

1. Load the subject adapter: [`subject-adapters.md`](subject-adapters.md).
2. Solve from the clean stem, not from the student's marks.
3. Write the final answer with units and sign/direction.
4. Check by a second method when possible (substitution, limiting case, energy vs. force, graph vs. algebra).
5. Record confidence: `high`, `medium`, or `low`.
6. If low, state exactly what is uncertain and what would resolve it.

Analysis structure:

```markdown
### 解析
1. 研究对象 / 已知条件
2. 关键关系或公式
3. 代入与求解
4. 结果与检验
```

Keep the analysis teachable: show the decision point, not every algebraic manipulation.

## Phase 6 — Diagnose the error

Separate three things:

| Layer | Example |
|---|---|
| Student's written answer | `a = 8 m/s²` |
| Error mechanism | ignored the tension from B; took friction down the slope |
| Remediation | draw the system boundary; check relative motion before choosing friction direction |

Error categories (use one primary, optionally one secondary):

- `concept` — wrong principle or definition;
- `model` — wrong object/system, forces missing, circuit misread;
- `reading` — misread data, unit, option, or figure;
- `strategy` — chose an unworkable method;
- `algebra` — manipulation/sign error;
- `unit` — unit conversion or dimension;
- `diagram` — misread or mis-drew the figure;
- `language` — English passage/option misunderstanding;
- `careless` — transcription or arithmetic slip.

The diagnosis must be specific enough to suggest an action. "粗心" alone is not a diagnosis.

## Phase 7 — Build the card

1. Fill `text/question.json` using [`../templates/question.json`](../templates/question.json).
2. Validate it:

   ```bash
   python scripts/validate_package.py text/question.json --root .
   ```

3. Install the formula dependencies **only if** `card.md` needs `formulas/eq-*.png`:

   ```bash
   pip install -r requirements-formulas.txt
   ```

4. Render the Markdown card (no DOCX in the default flow):

   ```bash
   python scripts/build_card.py text/question.json \
     --out card.md --question-out text/question.md \
     --formula-mode both
   ```

   Add `--docx card.docx` **only** when the user explicitly asks for a Word file.

5. Check the output package:
   - `card.md` references every figure and every formula image;
   - `card.latex.md` is the raw-LaTeX sidecar;
   - `formulas/` contains the formula images used by Markdown (if any).
   - `card.docx` is out of scope unless the user asked for Word; then check that it
     contains every figure and native equations (not raw `$...$`).

6. Open the Markdown and compare with the source.
7. Record the comparison in `review.md`.

The card should be usable by a student without the original page. If the reader needs the original to understand the question, extraction is incomplete.

## Phase 8 — Review and export

Run every gate in [`quality-gates.md`](quality-gates.md).

Minimum review record:

```markdown
## Review
- [ ] Text matches source
- [ ] All subquestions/options present
- [ ] Figure topology checked
- [ ] Figure embedded in card.md
- [ ] Formulas readable in card.md (rendered images or math renderer)
- [ ] Answer independently verified
- [ ] Units and signs checked
- [ ] Student data removed
- [ ] Publication rights confirmed
- Reviewer:
- Date:
- Remaining uncertainty:
```

Only after sign-off should the card enter a shared bank or public repository.

## Quick route (one image)

Use when the user supplies one screenshot or one photo and wants one card.
Intake is **one command** — do not probe the image with a dozen crops.

1. `python scripts/run.py new <image> --id <id> --subject <subject> --grade <grade>`
   copies the source, records the sha256, writes the `manifest.json` /
   `text/question.json` stubs and a `source/contact.png` that holds the full view
   **and** the zoom tiles in one image.
2. Read `source/contact.png` once, then transcribe into `text/question.json`.
   The printed report also gives the ink bbox and an 8×4 ink-density map, which is
   usually enough to choose a figure crop without another probe.
3. Figure: for a solid, write `figures/fig-1.spec.json` from
   `templates/figure-spec-3d.json` and run `scripts/draw_solid.py` — the
   projection, the hidden edges (from face normals), the compare sheet and the
   numeric checks (edge lengths, coplanarity, circumsphere) all come out of it.
   For flat figures use `clean_figure.py`.
4. `python scripts/run.py finish <workdir>` — preflight, build, validate, status.
   Preflight catches the traps that otherwise cost a rebuild: decoy images in
   `figures/` that get auto-embedded, subject-inappropriate `error_types`, a
   duplicated "xx：" prefix, unbalanced `$`, leftover `[?]`/`TODO`.
5. Fill `review.md`, then present the card.

Do not build a batch index for a single card.

## Standard route (PDF / multi-question)

Use when the source has a text layer, multiple pages, or more than one question.

1. Render pages at 300 DPI.
2. Extract text per page; keep page boundaries.
3. Segment by question number.
4. Process each question into its own work folder.
5. Build a batch index at the end.
6. Report skipped pages and reasons.

## Batch route (folder)

Use when the user supplies a folder or a large PDF.

1. Inventory files and page counts.
2. Create a naming plan before processing.
3. Process one question per folder; never merge.
4. Run `validate_package.py` on every `question.json`.
5. Run `build_index.py` to create `index.md`.
6. Produce `batch-review.md` with:
   - processed count;
   - skipped count and reasons;
   - low-confidence cards;
   - duplicate IDs;
   - missing figures.

Batch quality beats batch speed. A smaller, correct bank is more useful than a large, unverified one.

## Handoff format

When handing work to another teacher or agent, provide:

```text
ID:
Subject / grade:
Source:
Card: card.md
Figure: figures/fig-1.png
Confidence: text / figure / answer
Open questions:
Review status:
```

Do not hand off a card with unresolved `[?]` markers without listing them.
