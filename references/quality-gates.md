# Quality gates

Run these gates before a card is marked `reviewed`. A blocking failure stops the card; a warning may be accepted with a note.

## Gate 1 — Source and rights

- [ ] Original file preserved; checksum recorded.
- [ ] Page number(s) and crop recorded.
- [ ] No content from another question leaked in.
- [ ] Source is legible enough to support every number and symbol.
- [ ] Publication rights are `cleared` or the card is for private study only.
- [ ] Student names, school names, ID numbers, and scores removed.

**Blocking:** unreadable source, missing page, unknown rights for publication, personal data present.

## Gate 2 — Text fidelity

- [ ] Stem matches the source.
- [ ] All subquestions present.
- [ ] All options present, in order.
- [ ] Tables preserved with headers and units.
- [ ] Formulas preserve grouping, case, subscripts, and units.
- [ ] Blanks and answer lines preserved.
- [ ] Figure/table callouts resolve.
- [ ] No `[?]`, `[missing]`, or unresolved `[figure: ...]`.
- [ ] No accidental correction of the source's wording.

**Blocking:** any unresolved `[?]` that changes the answer; missing subquestion/option; wrong number/unit/sign.

## Gate 3 — Figure

- [ ] Figure exists if the stem depends on it.
- [ ] Topology matches the source (connections, intersections, inside/outside).
- [ ] Directions and arrows match.
- [ ] Dashed/solid styles match.
- [ ] Labels, subscripts, and units match.
- [ ] Angle/right-angle/equal-length marks preserved.
- [ ] Solution marks removed (`N`, `f`, `mg`, auxiliary lines, added coordinates).
- [ ] No printed label accidentally removed.
- [ ] Before/after images exist.
- [ ] Figure is legible at the card's display size.
- [ ] `figures[].kind` and `confidence` are recorded.

**Blocking:** wrong topology, missing label, solution marks left in, figure unreadable.

## Gate 4 — Answer

- [ ] Answer derived from the clean stem, not from the student's marks.
- [ ] Units and direction included where required.
- [ ] Sign convention consistent.
- [ ] Special cases / domain / constraints checked.
- [ ] Independent verification done (second method or substitution).
- [ ] Answer agrees with any provided key; disagreements explained.
- [ ] Confidence recorded.

**Blocking:** no verification, wrong unit/sign, answer contradicts the source data.

## Gate 5 — Analysis

- [ ] Steps are specific to this question.
- [ ] The key decision point is explained, not just algebra.
- [ ] No skipped step that a student at this level cannot fill.
- [ ] No false statements added for brevity.
- [ ] Final answer clearly separated from the derivation.
- [ ] Diagrams used in the analysis are consistent with the clean figure.

**Blocking:** analysis missing, answer-only card, or an explanation that contradicts the solution.

## Gate 6 — Diagnosis

- [ ] Student's written answer preserved separately (if available).
- [ ] Error type uses the allowed list.
- [ ] Root cause is specific ("ignored tension from B", not "粗心").
- [ ] Remedy is actionable.
- [ ] Diagnosis does not leak into the clean question.
- [ ] If the student answer is unknown, the field is empty, not invented.

**Blocking:** invented student answer; diagnosis that is only a label.

## Gate 7 — Build consistency

- [ ] `question.json` is valid JSON.
- [ ] `validate_package.py` passes.
- [ ] `card.md` renders without broken math or images.
- [ ] `card.docx` opens and images are embedded.
- [ ] Markdown, DOCX, and JSON agree.
- [ ] Figure paths are relative and exist.
- [ ] ID is unique in the batch.
- [ ] `review.status` is correct.

**Blocking:** broken references, invalid JSON, mismatched answer between renderings.

## Gate 8 — Teaching quality

- [ ] Card is understandable without the original page.
- [ ] Language matches the source/user.
- [ ] Difficulty is appropriate for the grade.
- [ ] Knowledge points are precise, not generic.
- [ ] Variant (if present) is solvable from the card.
- [ ] No answer hints in the figure or caption.
- [ ] Card is not overloaded with irrelevant decoration.

**Blocking:** card cannot stand alone; variant is unsolvable; caption gives away the answer.

## Scoring

Use a simple 0–2 score per gate:

| Score | Meaning |
|---:|---|
| 0 | blocking failure |
| 1 | pass with recorded warning |
| 2 | clean pass |

A card can be `reviewed` only if every gate is ≥1 and Gates 1–4 are 2. A card can be `published` only if every gate is 2.

## Review record

Append to `review.md`:

```markdown
## Quality gates
| Gate | Score | Notes |
|---|---:|---|
| Source and rights | 2 | |
| Text fidelity | 2 | |
| Figure | 2 | removed N/f/mg; string topology checked |
| Answer | 2 | verified by energy method |
| Analysis | 2 | |
| Diagnosis | 1 | student answer partially erased |
| Build consistency | 2 | |
| Teaching quality | 2 | |

Result: reviewed
Reviewer:
Date:
```

## Stop conditions

Do not mark `reviewed` if:

- a blocking gate is 0;
- the answer confidence is `low` and no human has checked it;
- the figure is a reconstruction with `confidence: low` and no source description;
- the card contains personal data;
- publication rights are `unknown`.
