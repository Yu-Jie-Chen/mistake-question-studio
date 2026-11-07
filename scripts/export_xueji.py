#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Export a work folder into ``xueji.export.json`` — the ingest payload for xueji-notebook.

    python scripts/export_xueji.py work/20261106-physics-incline-001
    python scripts/export_xueji.py work/<id> --subject-id cmw1o52hg... --grade 高三上
    python scripts/export_xueji.py work/<id> --embed-image      # inline the original photo

The export is *not* the source of truth. ``text/question.json`` is. This file is a
one-way projection into the notebook app's SQLite schema; re-run it after editing the
card. Exit code 0 = written, 2 = blocking gate failed, 1 = unexpected error.
"""
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

try:  # never die on a console that cannot encode Chinese
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "xueji.export"
SCHEMA_VERSION = "1.0"

# --- the app's enums (learned from the running build, see references/xueji-export.md) ---

# gradeSemester is a closed enum: 一年级上..六年级下, 初/高 x 一二三 上下, 大一二三四 上下.
GRADE_ENUM_CORE = ["一年级", "二年级", "三年级", "四年级", "五年级", "六年级",
                   "初一", "初二", "初三", "高一", "高二", "高三",
                   "大一", "大二", "大三", "大四"]

GRADE_ALIASES = {
    "小学一年级": "一年级", "小学二年级": "二年级", "小学三年级": "三年级",
    "小学四年级": "四年级", "小学五年级": "五年级", "小学六年级": "六年级",
    "初中一年级": "初一", "初中二年级": "初二", "初中三年级": "初三",
    "七年级": "初一", "八年级": "初二", "九年级": "初三",
    "高中一年级": "高一", "高中二年级": "高二", "高中三年级": "高三",
    "Grade 10": "高一上", "Grade 11": "高二上", "Grade 12": "高三上",
}

# The app stores errorType as free text (no enum, no stats), so we keep the skill's
# nine-value taxonomy and only translate it for display.
ERROR_TYPE_LABEL = {
    "concept": "概念", "model": "模型", "reading": "审题", "strategy": "策略",
    "algebra": "计算", "unit": "单位", "diagram": "图形", "language": "语言",
    "careless": "粗心",
}

DIFFICULTY_TO_PRACTICE = {1: "easy", 2: "easy", 3: "medium", 4: "hard", 5: "harder"}

# app-side length limits (question-save.ts importSchema)
LIMITS = {"questionText": 20000, "answerText": 20000, "analysis": 50000,
          "wrongAnswerText": 20000, "mistakeAnalysis": 50000}

UNRESOLVED = ("[?]", "[missing]")

TEXT_FIELDS = ("questionText", "answerText", "analysis", "wrongAnswerText", "mistakeAnalysis",
               "userNotes")


class Gate(Exception):
    """A blocking quality gate. Nothing is written."""


# --------------------------------------------------------------------------- helpers

def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        raise Gate(f"missing {path}")
    except json.JSONDecodeError as exc:
        raise Gate(f"{path} is not valid JSON: {exc}")


def _bullets(items) -> str:
    return "\n".join(f"- {str(i).strip()}" for i in (items or []) if str(i).strip())


def is_enum_grade(value: str) -> bool:
    return any(value == f"{core}上" or value == f"{core}下" for core in GRADE_ENUM_CORE)


def norm_grade(raw: str, override: str | None) -> tuple[str, list[str]]:
    """Map free-text grade to the app's closed enum. Returns (value, warnings)."""
    warnings: list[str] = []
    if override:
        return override.strip(), warnings
    value = (raw or "").strip()
    if not value:
        raise Gate("grade is empty — the app cannot infer it (gradeRecognitionMode is 'fixed')")
    if is_enum_grade(value):
        return value, warnings

    mapped = GRADE_ALIASES.get(value, value)
    if is_enum_grade(mapped):
        return mapped, warnings
    if mapped in GRADE_ENUM_CORE:
        warnings.append(f"grade '{raw}' has no semester; defaulted to '{mapped}上' — pass --grade to be exact")
        return f"{mapped}上", warnings

    warnings.append(f"grade '{raw}' is not in the app enum; passed through verbatim")
    return value, warnings


def compose_question(q: dict) -> str:
    parts: list[str] = []
    if (q.get("instruction_md") or "").strip():
        parts.append(q["instruction_md"].strip())
    parts.append((q.get("stem_md") or "").strip())
    for sub in q.get("subquestions") or []:
        label = (sub.get("label") or "").strip()
        text = (sub.get("text_md") or "").strip()
        if text:
            parts.append(f"{label} {text}".strip())
    options = [o for o in (q.get("options") or []) if (o.get("text_md") or "").strip()]
    if options:
        parts.append("\n".join(f"{o.get('label', '')}. {o['text_md'].strip()}" for o in options))
    return "\n\n".join(p for p in parts if p)


def compose_analysis(a: dict) -> str:
    out = []
    steps = (a.get("steps_md") or "").strip()
    if steps:
        out.append(steps)
    if a.get("key_points"):
        out.append("**关键判断点**\n" + _bullets(a["key_points"]))
    if a.get("pitfalls"):
        out.append("**易错点**\n" + _bullets(a["pitfalls"]))
    return "\n\n".join(out)


def compose_diagnosis(d: dict) -> str:
    out = []
    root = (d.get("root_cause_md") or "").strip()
    remedy = (d.get("remedy_md") or "").strip()
    if root:
        out.append(f"**错因**：{root}")
    if remedy:
        out.append(f"**怎么改**：{remedy}")
    return "\n\n".join(out)


def find_svg(wd: Path, figures: list[dict]) -> tuple[str | None, list[str]]:
    """Prefer a spec-derived SVG (draw_solid/draw_scene) over a raster crop."""
    warnings: list[str] = []
    for fig in figures:
        path = (fig.get("path") or "").strip()
        if not path:
            continue
        sidecar = wd / Path(path).with_suffix(".svg")
        if sidecar.is_file():
            text = sidecar.read_text(encoding="utf-8", errors="replace").strip()
            if "<svg" in text[:400].lower():
                return text, warnings
            warnings.append(f"{sidecar.name} does not look like SVG, ignored")
    if figures:
        warnings.append("figures present but no .svg sidecar; the app falls back to the original photo")
    return None, warnings


def image_payload(wd: Path, src: dict, embed: bool, max_bytes: int) -> tuple[dict, list[str]]:
    warnings: list[str] = []
    rel = (src.get("file") or "").strip()
    if not rel:
        raise Gate("source.file is empty — every card needs an original image")
    path = wd / rel
    if not path.is_file():
        raise Gate(f"source.file does not exist: {rel}")
    size = path.stat().st_size
    mime = mimetypes.guess_type(path.name)[0] or ""
    if not mime.startswith("image/"):
        warnings.append(f"source.file is not an image ({mime or 'unknown type'}); the app will show a broken preview")
    if not embed:
        return {"kind": "file", "path": rel, "bytes": size}, warnings
    if size > max_bytes:
        warnings.append(f"source image is {size // 1024} KB > {max_bytes // 1024} KB; the app accepts up to 20 MB but the DB will grow")
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return {"kind": "data-url", "mime": mime, "bytes": size, "data": f"data:{mime};base64,{data}"}, warnings


# --------------------------------------------------------------------------- gates

def gate_text(field: str, value: str, errors: list[str]) -> None:
    if value and value.count("$") % 2:
        errors.append(f"{field}: unbalanced $ ({value.count('$')} occurrences)")
    for marker in UNRESOLVED:
        if marker in (value or ""):
            errors.append(f"{field}: unresolved marker {marker}")
    limit = LIMITS.get(field)
    if limit and len(value or "") > limit:
        errors.append(f"{field}: {len(value)} chars exceeds the app limit {limit}")


# --------------------------------------------------------------------------- build

def find_question_json(wd: Path) -> Path:
    for candidate in (wd / "text" / "question.json", wd / "question.json"):
        if candidate.is_file():
            return candidate
    raise Gate(f"no text/question.json in {wd}")


def build(wd: Path, args) -> dict:
    q = _read_json(find_question_json(wd))
    warnings: list[str] = []
    errors: list[str] = []

    status = (q.get("review") or {}).get("status") or "draft"
    if status == "draft" and not args.allow_draft:
        errors.append("review.status is 'draft' — run the quality gates and mark it 'reviewed' first")

    grade, gw = norm_grade(str(q.get("grade") or ""), args.grade)
    warnings += gw

    card = {
        "questionText": compose_question(q.get("question") or {}),
        "answerText": ((q.get("answer") or {}).get("final_md") or "").strip(),
        "analysis": compose_analysis(q.get("analysis") or {}),
        "wrongAnswerText": ((q.get("diagnosis") or {}).get("student_answer_md") or "").strip(),
        "mistakeAnalysis": compose_diagnosis(q.get("diagnosis") or {}),
    }
    if not card["questionText"]:
        errors.append("questionText is empty (question.stem_md)")
    if not card["answerText"]:
        errors.append("answerText is empty (answer.final_md)")
    if not card["analysis"]:
        errors.append("analysis is empty (analysis.steps_md)")

    if card["wrongAnswerText"]:
        card["mistakeStatus"] = "wrong_attempt"
    else:
        card["mistakeStatus"] = "unknown"
        warnings.append("no student answer captured — mistakeStatus=unknown, the stats stay honest")

    kp = [str(t).strip() for t in ((q.get("meta") or {}).get("knowledge_points") or []) if str(t).strip()]
    if len(kp) > 5:
        warnings.append(f"{len(kp)} knowledge points, the app shows 5 — trimmed")
        kp = kp[:5]
    card["knowledgePoints"] = kp

    raw_types = [str(t).strip() for t in ((q.get("diagnosis") or {}).get("error_types") or []) if str(t).strip()]
    unknown = [t for t in raw_types if t not in ERROR_TYPE_LABEL]
    if unknown:
        warnings.append(f"error_types outside the nine-value taxonomy: {unknown}")
    card["errorType"] = "/".join(ERROR_TYPE_LABEL.get(t, t) for t in raw_types[:2]) or None

    try:
        stars = int((q.get("meta") or {}).get("difficulty"))
        card["difficultyStars"] = max(1, min(5, stars)) if stars else None
    except (TypeError, ValueError):
        card["difficultyStars"] = None
        warnings.append("meta.difficulty is not 1-5; left empty")

    figures = q.get("figures") or []
    for fig in figures:
        if fig.get("path") and not (wd / fig["path"]).is_file():
            errors.append(f"figure missing on disk: {fig['path']}")
    svg, sw = find_svg(wd, figures)
    warnings += sw
    card["hasFigure"] = bool(figures) or bool((q.get("question") or {}).get("figure_refs"))
    card["figureSvg"] = svg
    card["figureScale"] = 100
    card["figureAlign"] = "center"

    img, iw = image_payload(wd, q.get("source") or {}, args.embed_image, 1500 * 1024)
    warnings += iw

    unc = [u for u in ((q.get("review") or {}).get("uncertainties") or []) if str(u).strip()]
    card["userNotes"] = "\n".join([f"work:{q.get('id') or wd.name}", f"review:{status}"]
                                  + ([f"待确认：{u}" for u in unc] if unc else []))
    card["source"] = f"dsh:{q.get('id') or wd.name}"

    last = None
    variant = ((q.get("meta") or {}).get("variant_md") or "").strip()
    if variant:
        last = {
            "questionText": variant,
            "answerText": ((q.get("meta") or {}).get("variant_answer_md") or "").strip(),
            "analysis": ((q.get("meta") or {}).get("variant_analysis_md") or "").strip(),
            "subject": q.get("subject"),
            "difficulty": DIFFICULTY_TO_PRACTICE.get(card["difficultyStars"] or 3, "medium"),
            "generatedAt": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        }
        if not last["answerText"]:
            warnings.append("variant_md has no variant_answer_md — the notebook can show it but not grade it")

    for field in TEXT_FIELDS:
        gate_text(field, card.get(field) or "", errors)

    if args.tags_index:
        index = set(_read_json(Path(args.tags_index)))
        missing = [t for t in kp if t not in index]
        if missing:
            warnings.append(f"tags not in the notebook tag set (will be created as custom tags): {missing}")

    if errors and not args.allow_unresolved:
        raise Gate("\n".join(errors))

    return {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source_work": wd.name,
        "upsert_key": card["source"],
        "target": {
            "subjectId": args.subject_id or None,
            "subjectName": args.subject_name or None,
            "paperLevel": args.paper_level or None,
            "gradeSemester": grade,
        },
        "card": card,
        "originalImage": img,
        "lastPractice": last,
        "export_meta": {
            "review_status": status,
            "confidence": (q.get("answer") or {}).get("confidence"),
            "figure_kind": [f.get("kind") for f in figures],
            "warnings": warnings,
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Export a work folder as xueji.export.json")
    ap.add_argument("workdir")
    ap.add_argument("--out", default=None)
    ap.add_argument("--subject-id", default=None, help="target Subject.id in the notebook app")
    ap.add_argument("--subject-name", default=None, help="fallback: match/create a notebook by name")
    ap.add_argument("--grade", default=None, help="override gradeSemester (e.g. 高三上)")
    ap.add_argument("--paper-level", default=None, help="paper group id (A/B/other or custom)")
    ap.add_argument("--tags-index", default=None, help="JSON array of tag names allowed in this notebook")
    ap.add_argument("--embed-image", action="store_true", help="inline the original photo as a data URL")
    ap.add_argument("--allow-draft", action="store_true")
    ap.add_argument("--allow-unresolved", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    wd = Path(args.workdir).resolve()
    try:
        find_question_json(wd)
    except Gate as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2
    try:
        payload = build(wd, args)
    except Gate as exc:
        for line in str(exc).splitlines():
            print(f"GATE {line}", file=sys.stderr)
        return 2

    out = Path(args.out) if args.out else wd / "xueji.export.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    warnings = payload["export_meta"]["warnings"]
    if args.quiet:
        print(f"OK {out}")
    else:
        print(f"OK {out.name}  key={payload['upsert_key']}  grade={payload['target']['gradeSemester']}")
        print(f"   tags={payload['card']['knowledgePoints']}  stars={payload['card']['difficultyStars']}  "
              f"svg={'y' if payload['card']['figureSvg'] else 'n'}  variant={'y' if payload['lastPractice'] else 'n'}")
        print(f"   warnings={len(warnings)}" + ("" if not warnings else " → " + "; ".join(warnings[:3])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
