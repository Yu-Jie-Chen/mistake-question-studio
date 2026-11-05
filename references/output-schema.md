# Output schema

`text/question.json` is the single source of truth. `card.md` and `card.docx` are generated from it.

The validator in [`../scripts/validate_package.py`](../scripts/validate_package.py) checks the required fields and referenced files.

## Top-level shape

```json
{
  "schema_version": "1.0",
  "id": "20260101-physics-incline-001",
  "subject": "physics",
  "grade": "高中一年级",
  "source": {},
  "question": {},
  "figures": [],
  "answer": {},
  "analysis": {},
  "diagnosis": {},
  "meta": {},
  "review": {}
}
```

## Field reference

### `schema_version` (required)

String. Use `"1.0"` for this version.

### `id` (required)

Stable, unique. Recommended:

```text
YYYYMMDD-subject-topic-###
```

Do not reuse an ID after changing the question.

### `subject` (required)

One of:

```text
physics | chemistry | mathematics | english | biology | geography | history | politics | other
```

Use `other` only when none fit; add a `meta.tags` entry.

### `grade` (required)

Free text, e.g. `初中二年级`, `高中一年级`, `Grade 10`, `大学先修`.

### `source` (required)

```json
{
  "type": "screenshot",
  "file": "source/original.png",
  "page": 1,
  "pages": [1],
  "rights": "private-study",
  "note": " photographed at an angle; top edge cropped"
}
```

| Field | Required | Notes |
|---|---|---|
| `type` | yes | `screenshot`, `photo`, `pdf`, `scan`, `docx`, `other` |
| `file` | yes | relative to the work folder |
| `page` | no | page number for PDF/scan |
| `pages` | no | all pages the question spans |
| `rights` | yes | `private-study`, `cleared`, `unknown` |
| `note` | no | crop, blur, missing edge, etc. |

### `question` (required)

```json
{
  "type": "calculation",
  "instruction_md": "求下列各题。",
  "stem_md": "质量 $m=1\\ \\text{kg}$ 的物块静止在倾角 $37^\\circ$ 的固定斜面上……",
  "subquestions": [
    {"label": "(1)", "text_md": "求斜面对物块的摩擦力大小。", "answer_md": "$6\\ \\text{N}$"}
  ],
  "options": [
    {"label": "A", "text_md": "……"}
  ],
  "figure_refs": ["fig-1"]
}
```

| Field | Required | Notes |
|---|---|---|
| `type` | yes | `calculation`, `choice`, `fill`, `proof`, `reading`, `experiment`, `other` |
| `instruction_md` | no | shared instruction above the stem |
| `stem_md` | yes | complete stem, including conditions and data |
| `subquestions` | no | preserve labels exactly |
| `options` | no | choice questions only |
| `figure_refs` | no | IDs that must exist in `figures` |

Use Markdown + LaTeX. Keep the source language.

### `figures` (required if the question depends on a figure)

```json
[
  {
    "id": "fig-1",
    "path": "figures/fig-1.png",
    "before_path": "figures/fig-1.before.png",
    "kind": "trace-redraw",
    "caption": "物块置于倾角 37° 的固定斜面上。",
    "confidence": "high",
    "removed_marks": ["N", "f", "mg"],
    "labels_preserved": ["m", "37°"]
  }
]
```

| Field | Required | Notes |
|---|---|---|
| `id` | yes | `fig-1`, `fig-2`, ... |
| `path` | yes | relative to the work folder |
| `before_path` | no | original crop, for audit |
| `kind` | yes | `clean-crop`, `masked`, `trace-redraw`, `rebuild` |
| `caption` | yes | one sentence; no solution hints |
| `confidence` | yes | `high`, `medium`, `low` |
| `removed_marks` | no | list of hand-drawn marks removed |
| `labels_preserved` | no | exact labels retained |

Every figure must be embedded in both `card.md` and `card.docx`; a figure that exists only in `figures/` is a failed build. For DOCX embedding, use PNG/JPG/JPEG/WebP. Keep SVG alongside as an editable source, not as the only figure.

### `answer` (required)

```json
{
  "final_md": "$6\\ \\text{N}$，方向沿斜面向上。",
  "units": "N",
  "confidence": "high",
  "alternate_md": "",
  "verification_md": "沿斜面方向：$mg\\sin37^\\circ=6\\ \\text{N}$；最大静摩擦力 $\\mu mg\\cos37^\\circ=6.4\\ \\text{N}$，故静摩擦力为 $6\\ \\text{N}$。"
}
```

`final_md` must be a complete answer, not just a number. Include direction/units where relevant.

### `analysis` (required)

```json
{
  "steps_md": "1. 对物块受力分析……\n2. 沿斜面方向列平衡方程……\n3. 解得……",
  "key_points": ["静摩擦力方向的判断", "最大静摩擦力与滑动摩擦力的区别"],
  "pitfalls": ["把摩擦力方向画反", "忽略最大静摩擦力不足时物体会滑动"]
}
```

The analysis should be teachable and specific to this question, not a textbook chapter.

### `diagnosis` (required)

```json
{
  "student_answer_md": "$f=8\\ \\text{N}$，方向沿斜面向下。",
  "error_types": ["model", "diagram"],
  "root_cause_md": "没有先判断物块是否静止，直接把动摩擦力当成静摩擦力，并把方向画反。",
  "remedy_md": "先算最大静摩擦力，与重力沿斜面分力比较；再根据相对运动趋势定方向。"
}
```

Allowed `error_types`:

```text
concept | model | reading | strategy | algebra | unit | diagram | language | careless
```

If the student answer is unknown, use an empty string and `error_types: []`; do not invent it.

### `meta` (required)

```json
{
  "knowledge_points": ["共点力平衡", "静摩擦力"],
  "difficulty": 3,
  "tags": ["斜面", "摩擦力", "平衡"],
  "variant_md": "若 $\\mu=0.5$，物块是否仍能静止？"
}
```

`difficulty` is 1–5. `variant_md` is optional but recommended for review.

### `review` (required)

```json
{
  "status": "reviewed",
  "reviewer": "T.",
  "date": "2026-01-01",
  "uncertainties": []
}
```

Allowed `status`: `draft`, `reviewed`, `published`.

- `draft`: extracted, not yet checked.
- `reviewed`: a human checked all gates.
- `published`: approved for a shared bank.

## Markdown conventions

- Inline math: `$...$` in `question.json`; the builder renders it to `formulas/eq-*.png` for `card.md` and to OMML for `card.docx`.
- Display math: `$$...$$` on its own lines in the source; rendered as a centered formula block in the outputs.
- Blanks: `____` (four underscores) or the source's line.
- Options: one per line, `A. ...`.
- Tables: Markdown tables with units in the header.
- Figures: `![fig-1]` + `(figure-path)`; use the actual relative path.
- Unknown text: `[?]`; missing content: `[missing]`.
- Do not use HTML unless the target renderer requires it.

## Minimal valid example

```json
{
  "schema_version": "1.0",
  "id": "20260101-mathematics-algebra-001",
  "subject": "mathematics",
  "grade": "初中二年级",
  "source": {
    "type": "screenshot",
    "file": "source/original.png",
    "rights": "private-study"
  },
  "question": {
    "type": "calculation",
    "stem_md": "已知 $a+b=5$，$ab=6$，求 $a^2+b^2$。",
    "subquestions": [],
    "options": [],
    "figure_refs": []
  },
  "figures": [],
  "answer": {
    "final_md": "$13$",
    "units": "",
    "confidence": "high",
    "verification_md": "$a^2+b^2=(a+b)^2-2ab=25-12=13$。"
  },
  "analysis": {
    "steps_md": "利用完全平方公式：$a^2+b^2=(a+b)^2-2ab$。代入得 $25-12=13$。",
    "key_points": ["完全平方公式的变形"],
    "pitfalls": ["把 $(a+b)^2$ 展开成 $a^2+b^2$"]
  },
  "diagnosis": {
    "student_answer_md": "",
    "error_types": [],
    "root_cause_md": "",
    "remedy_md": ""
  },
  "meta": {
    "knowledge_points": ["完全平方公式"],
    "difficulty": 1,
    "tags": ["代数变形"],
    "variant_md": "已知 $a-b=1$，$ab=6$，求 $a^2+b^2$。"
  },
  "review": {
    "status": "draft",
    "reviewer": "",
    "date": "",
    "uncertainties": []
  }
}
```
