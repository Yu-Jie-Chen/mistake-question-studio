# Changelog

## 0.6.0 — 2026-11-07

- **The card layout is the builder's job, not the model's.** Five rules, applied in
  `build_card.py` and inherited by every output (Markdown, HTML, DOCX):
  - title is `物理高三 · 王小明 · 错题卡` — subject + short grade (`高中三年级 → 高三`),
    then the student's name when `student.name` is set, then 错题卡;
  - the header carries the ID only — 状态 / 来源 / 备注 stay in `question.json` and
    `review.md` instead of on paper;
  - the closing 审核 section is gone; the card ends on one date, the sign-off day;
  - figures print at 60% of the text column (shrunk by 40%), centred, caption underneath.
- **`scripts/build_card_html.py` (new).** `card.md` → one standalone, printable HTML file:
  figures and `formulas/eq-*.png` inlined as data URIs, A4 `@page`, no network needed.
  Takes `card.md` or `text/question.json`; refuses to emit a card that still has raw
  `$...$` (exit 3) unless `--allow-raw-math`. `run.py finish --html` runs it after the
  build, and `run.py status` now lists `card.html`.
- **New optional `student` field** in `question.json` (`{"name": "王小明"}`), documented in
  `references/output-schema.md`. The privacy rule follows it: a personal card may name its
  student; a shared or published card may not.
- Two rendering bugs fixed while porting the renderer: emphasis that spans a formula image
  (`*推力 ![formula](…) 与水平面成…*`) no longer shows literal asterisks, and inline
  formulas no longer turn into full-width blocks — `:only-child` ignores text nodes, so the
  old `p > img.formula:only-child` selector also matched 「B：把上式解出 $m$：」.
- The bundled example (`examples/incline-static/`) is rebuilt in the new layout and gains
  `card.html`; its `card.docx` is left as a pre-layout snapshot (Word export is opt-in).

## 0.5.1 — 2026-11-06

- **`run.py finish` is quiet**: the four child reports collapse into one summary line, then
  `STOP`/`NEXT`. Output that lands in the transcript is re-billed on every later request, so
  the default report is 3 lines and `--verbose` is opt-in for failures.
- **`run.py render <workdir>`**: writes the spec (path, or `--spec-json @file`), renders
  PNG + SVG, and builds the compare sheet in one call. The engine is picked from the spec
  (`vertices` + `faces` → `draw_solid.py`, otherwise `draw_scene.py`), so a card session
  does not have to know which renderer to invoke. Inline `--spec-json` is refused with a
  hint instead of a stack trace: Windows shells strip the double quotes from a native
  command line, so `@file` is the portable form.
- Net effect on a card: two fewer round trips (render, figure-engine lookup) and a much
  shorter build report.

## 0.5.0 — 2026-11-06

- **`draw_scene.py`: flat figures are now derived, not eyeballed.** A declarative scene
  (data coordinates + `view`) with the primitives that physics cards actually need:
  `line`/`polyline`/`arrow`/`arc`/`dot`/`label` (with sub/superscript)/`hatch`/`parabola`.
  Projectile arcs are integrated from $v_0$ and $g$, so a trajectory is exact; dashing is
  continuous across vertices (a per-segment dash pattern silently turns a sampled curve
  into a solid line).
  Companion to `draw_solid.py`: 3D solids and 2D scenes are both spec-driven now.
- Worked example: the 双斜面 projectile card (`figures/fig-1.spec.json` in its work folder).

## 0.4.0 — 2026-11-05

- **Low-loss pipeline: the intake is now one command.** `run.py new` copies the source,
  records the sha256, writes the `manifest.json` / `text/question.json` stubs and builds
  `source/contact.png` — the full view **plus** zoom tiles in a single image, so the page
  is read with one `read_image` instead of eight. It also prints the ink bbox and an 8×4
  ink-density map, which is usually enough to pick a figure crop without another probe.
- **`draw_solid.py` renders solid-geometry figures from a 3D model.** Orthographic
  projection from a stated eye direction, hidden edges computed from face normals
  (`auto_orient` fixes inconsistent winding), PNG + SVG + compare sheet, and the numeric
  checks that used to be redone by hand: edge lengths, face coplanarity, and a circumsphere
  fitted through every 4-point subset (centre, radius, agreement).
  Template: `templates/figure-spec-3d.json`.
- **`preflight.py`** stops the build-time traps that each cost a rebuild: a decoy image in
  `figures/` (auto-embedded into the student card), an `error_types` value that renders
  with physics wording on a maths card, a duplicated "xx：" prefix, an odd number of `$`,
  and leftover `[?]` / `TODO`.
- **`run.py status`** reports what exists, what is stale (card older than the JSON) and the
  next action, so a resumed session does not re-explore the folder.
- `workflow.md` Quick route rewritten around the three commands; helper-script list updated.
- Console safety: scripts print ASCII-safe paths and force UTF-8 for child processes, so
  non-ASCII folder names no longer crash or mojibake the report.

## 0.3.0 — 2026-11-05

- **Markdown is now the only default deliverable.** `card.md` is what the skill hands over;
  the DOCX pipeline is opt-in and runs only when the user explicitly asks for Word.
- Skill, references, template, README and CLI updated to drop the "md **and** docx" contract:
  - quality gates, output schema, review template and the delivery checklist no longer require
    `card.docx`;
  - `build_card.py` keeps `--docx` but documents it as an explicit opt-in;
  - `requirements-formulas.txt` is only needed when the card uses `formulas/eq-*.png`.
- Rationale: building Word cost time and tokens (python-docx, OMML, LibreOffice rendering) that
  most sessions never use. Skipping it removes an entire stage from the default flow.

## 0.2.0 — 2026-11-05

- Figures are now discovered from `figures/` and embedded in both Markdown and DOCX.
- Added formula rendering:
  - Markdown uses `formulas/eq-*.png`;
  - DOCX uses native Word equations (OMML), with image fallback;
  - raw-LaTeX sidecars `card.latex.md` / `question.latex.md`.
- Added `requirements-formulas.txt`.
- Added figure/formula quality gates and a Word/PDF visual check.
- Updated the demo with a native-equation DOCX and formula images.

## 0.1.0 — 2026-11-05

Initial public release.

- Added the subject-agnostic workflow: intake → segmentation → text extraction → figure cleanup/redraw → solve/analyze → diagnosis → card → review.
- Added references for text extraction, figure redraw, subject adapters, output schema, and quality gates.
- Added Python helpers:
  - `prepare_scan.py`
  - `clean_figure.py`
  - `extract_pdf.py`
  - `build_card.py`
  - `validate_package.py`
  - `build_index.py`
- Added a synthetic physics demo with a clean figure and card.
- Added MIT license and contribution guidelines.
