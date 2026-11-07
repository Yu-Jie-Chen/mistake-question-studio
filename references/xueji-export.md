# Exporting into xueji-notebook (学记)

This is the bridge between a work folder and the desktop notebook app. It is an
**optional, one-way projection** — the work folder stays the source of truth.

```text
work/<id>/                        ← truth: question.json + card.md + figures/
        │  scripts/export_xueji.py
        ▼
xueji.export.json                 ← the payload (reviewable, diffable, no side effects)
        │  POST /api/agent/cards  (P2, not shipped in this skill)
        ▼
<appdata>/学记/data/wrong-notebook.db   ← projection: display, filter, stats, review
```

Everything below was read out of the running build on 2026-11-06
(app version `2026.10.19`, SQLite + Prisma, desktop server on `127.0.0.1:39300`).
If a field here disagrees with a newer build, trust the build.

## Command

```bash
python scripts/export_xueji.py work/20261106-physics-incline-001 \
  --subject-id cmw1o52hg0004wclsirwqpkuz \
  --grade 高三上 \
  --embed-image
```

| Flag | Why |
|---|---|
| `--subject-id` | the target notebook (`Subject.id`). Without it the app matches or **creates** a notebook by name — usually not what you want. |
| `--subject-name` | fallback only; `resolveNotebookForSubject` will create a new notebook if the name is unknown. |
| `--grade` | overrides `gradeSemester`. Needed when `question.json` only says `高中三年级`. |
| `--paper-level` | A/B/other group id. Omit → the app picks a group from the star rating. |
| `--embed-image` | inlines the source photo as a `data:` URL. Off by default: the JSON stays small and reviewable. |
| `--tags-index` | a JSON array of tag names allowed in this notebook; anything else will be **created as a custom tag**. |
| `--allow-draft` | export a card whose `review.status` is still `draft`. Do not use for real intake. |
| `--allow-unresolved` | keep going despite gate failures. Debug only. |

Exit codes: `0` written, `2` a gate blocked it (nothing is written), `1` unexpected.

## Output shape

```json
{
  "schema": "xueji.export",
  "schema_version": "1.0",
  "generated_at": "2026-11-06T14:20:00+08:00",
  "source_work": "20261106-physics-incline-001",
  "upsert_key": "dsh:20261106-physics-incline-001",
  "target": { "subjectId": "...", "subjectName": null, "paperLevel": null, "gradeSemester": "高三上" },
  "card": { "...": "ErrorItem columns" },
  "originalImage": { "kind": "file", "path": "source/original.png", "bytes": 582047 },
  "lastPractice": null,
  "export_meta": { "review_status": "reviewed", "confidence": "high", "figure_kind": ["trace-redraw"], "warnings": [] }
}
```

`originalImage` is either `{kind: "file", path}` (the push step reads it) or
`{kind: "data-url", mime, data}` (`--embed-image`). `lastPractice` is `null` when
`meta.variant_md` is empty.

## Field mapping

| `ErrorItem` column | comes from | notes |
|---|---|---|
| `questionText` | `question.instruction_md` + `stem_md` + each `subquestions[].text_md` + `options` | joined with blank lines; LaTeX kept as `$...$` |
| `answerText` | `answer.final_md` | must be a complete answer, not a bare number |
| `analysis` | `analysis.steps_md` + key points + pitfalls | the app renders Markdown + KaTeX |
| `wrongAnswerText` | `diagnosis.student_answer_md` | empty → `mistakeStatus: unknown`, never invented |
| `mistakeAnalysis` | `diagnosis.root_cause_md` + `remedy_md` | |
| `mistakeStatus` | derived | `wrong_attempt` when a student answer exists, else `unknown` |
| `knowledgePoints[]` | `meta.knowledge_points` | **max 5**; names must exist in the notebook's tag set |
| `errorType` | `diagnosis.error_types` | free text in the app — see below |
| `difficultyStars` | `meta.difficulty` (1–5) | unchanged scale |
| `hasFigure` / `figureSvg` | `figures[]` + the `.svg` sidecar | SVG is preferred; it is sanitized again on write |
| `figureScale` / `figureAlign` | fixed `100` / `center` | |
| `source` | `dsh:<question.json id>` | **the upsert key** |
| `userNotes` | work id + review status + open uncertainties | the trace back to the work folder |
| `gradeSemester` | `grade` (mapped) | closed enum, see below |
| `paperLevel` | `--paper-level` | empty → the app assigns by star rating |
| `originalImageUrl` | `source.file` | data URL only with `--embed-image` |
| `lastPractice` | `meta.variant_md` (+ `variant_answer_md`, `variant_analysis_md`) | JSON, validated by `LastPracticeSchema` |

`meta.variant_answer_md` and `meta.variant_analysis_md` are **optional additions** to
`question.json`. Without them the notebook can show the variant but not grade it — which
is fine when grading happens on the DSH side.

## Enums that are actually closed

### `gradeSemester`

Only these are accepted (the app rejects anything else silently, leaving the grade empty):

```text
一年级上/下 二年级上/下 三年级上/下 四年级上/下 五年级上/下 六年级上/下
初一上/下 初二上/下 初三上/下 高一上/下 高二上/下 高三上/下 大一..大四 上/下
```

`高中三年级` → `高三上` (with a warning: the semester is a guess). Note the tag tree uses
`高三`, but the *item* field needs the semester.

### `paperLevel`

A `PaperGroup.id`, not a label. Defaults are `A卷` / `B卷` / `其他`; the app assigns
4★ and above to B. Omit and let the app decide unless you mean it.

### `errorType`

The app stores **free text**, has no enum, no UI editor and no statistics on it.
So the skill's nine-value taxonomy is kept and only translated for display:

```text
concept→概念  model→模型  reading→审题  strategy→策略  algebra→计算
unit→单位  diagram→图形  language→语言  careless→粗心
```

Two values are joined with `/`; extras are dropped with a warning.

## The upsert key, and the trap it avoids

`source = "dsh:<id>"` is stable across re-exports. Re-ingesting must **update** that
row, never insert.

> The app's normal save path de-duplicates by question similarity (default 90%). A
> second save of the same card is therefore recorded as *the student got it wrong
> again* — silently corrupting the practice history. The ingest route must look up
> `source` first and update in place; only unseen keys may go through
> `saveQuestionForUser`.

## Figures and formulas

- **SVG wins.** `draw_solid.py --svg` and `draw_scene.py --svg` produce geometry that is
  computed (hidden edges from face normals, parabolas integrated from v₀/g), and the app
  sanitizes SVG before storing it. A raster crop of the same figure is strictly worse.
- Figure files must exist on disk (`kind: trace-redraw` still needs `fig-1.png` for
  `card.md`); the `.svg` sidecar is what gets exported.
- **Formulas: the app wants LaTeX, not images.** Rule 10 of `SKILL.md` says a delivered
  `card.md` must not contain raw `$...$`; the notebook renders `$...$` with KaTeX. These
  are not in conflict — the export deliberately uses the LaTeX form, `card.md` keeps the
  rendered form.

## Blocking gates

The exporter refuses to write when:

1. `review.status` is `draft` (unless `--allow-draft`);
2. a text field still contains `[?]` or `[missing]`;
3. `questionText`, `answerText` or `analysis` is empty;
4. `$` is unbalanced in any text field;
5. a figure referenced by `question.json` is missing on disk;
6. the source image is missing;
7. a field exceeds the app limit (`questionText` 20k, `analysis` 50k, `mistakeAnalysis` 50k).

Non-blocking warnings always land in `export_meta.warnings` — read them before pushing.

### Producing the tags index

The allowed tag names for one notebook, straight from the app's database (read-only, safe
while the app is running):

```bash
python -c "import sqlite3,json,sys; c=sqlite3.connect('file:%APPDATA%/学记/data/wrong-notebook.db?mode=ro',uri=True); print(json.dumps([r[0] for r in c.execute(\"select name from KnowledgeTag where subject='physics' order by name\")], ensure_ascii=False))" > tags-physics.json
```

Names are matched case-sensitively and must be unique within the notebook's tag set.

## Known traps

| Trap | What happens | What to do |
|---|---|---|
| Tag name not in the notebook's tag set | the app **creates a custom tag** under the grade's chapter, permanently | pass `--tags-index` and pick real tags |
| `gradeSemester` missing | stays empty; the notebook filters and stats lose the item | always supply it (`--grade`) |
| Backup restore into the app | the app's import merges and de-duplicates by similarity, so restored data and DSH data can collide | keep `work/` in git; it is the master copy |
| Re-export after editing | must update, not insert (see upsert key) | the ingest route decides; the key is `dsh:<id>` |
| Writing the SQLite file directly while the app runs | `SQLITE_BUSY`, and business rules are skipped | always go through the HTTP ingest route |
| Huge photos | `originalImageUrl` is a base64 data URL inside SQLite | crop before export, or let `--embed-image` warn you |

## Do not

- Do not edit cards inside the app. One editor: `text/question.json`. The app is a viewer.
- Do not let the app's AI touch a DSH card (grading, mastery, variants) — see the division
  of labour in the project notes.
- Do not treat `xueji.export.json` as a deliverable. It is a wire format; regenerate it.
