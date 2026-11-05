# Changelog

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
