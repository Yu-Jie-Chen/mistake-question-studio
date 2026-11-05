# Changelog

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
