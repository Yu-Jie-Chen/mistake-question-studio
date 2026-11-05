# Changelog

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
