#!/usr/bin/env python3
"""Validate a question.json card package.

Examples:
    python validate_package.py text/question.json --root .
    python validate_package.py work --root work --strict
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SUBJECTS = {"physics", "chemistry", "mathematics", "english", "biology",
            "geography", "history", "politics", "other"}
STATUSES = {"draft", "reviewed", "published"}
FIG_KINDS = {"clean-crop", "masked", "trace-redraw", "rebuild"}
CONFIDENCE = {"high", "medium", "low"}
ERROR_TYPES = {"concept", "model", "reading", "strategy", "algebra",
               "unit", "diagram", "language", "careless"}
PLACEHOLDERS = ("TODO", "TBD", "待补充", "PLACEHOLDER")


def add(errors, warnings, level, msg):
    (errors if level == "error" else warnings).append(msg)


def default_root(json_path: Path) -> Path:
    if json_path.parent.name.lower() == "text":
        return json_path.parent.parent
    return json_path.parent


def validate_one(path: Path, root: Path, allow_uncertain: bool, strict: bool):
    errors, warnings = [], []
    try:
        q = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return [f"{path}: invalid JSON: {exc}"], []
    if not isinstance(q, dict):
        return [f"{path}: root must be an object"], []

    required = ["schema_version", "id", "subject", "grade", "source", "question",
                "figures", "answer", "analysis", "diagnosis", "meta", "review"]
    for key in required:
        if key not in q:
            add(errors, warnings, "error", f"missing top-level field: {key}")

    if q.get("schema_version") != "1.0":
        add(errors, warnings, "error", "schema_version must be '1.0'")
    if q.get("subject") not in SUBJECTS:
        add(errors, warnings, "error", f"invalid subject: {q.get('subject')!r}")
    if not str(q.get("id", "")).strip():
        add(errors, warnings, "error", "id is empty")
    elif not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{2,80}", str(q["id"])):
        add(errors, warnings, "warning", "id should be a stable slug (letters/digits/._-)")

    source = q.get("source") or {}
    for key in ("type", "file", "rights"):
        if not source.get(key):
            add(errors, warnings, "error", f"source.{key} is required")
    if source.get("file"):
        src = Path(source["file"])
        src = src if src.is_absolute() else root / src
        if not src.exists():
            add(errors, warnings, "warning", f"source file not found: {src}")
    if source.get("rights") not in (None, "private-study", "cleared", "unknown"):
        add(errors, warnings, "error", "source.rights must be private-study, cleared, or unknown")

    question = q.get("question") or {}
    if not str(question.get("stem_md", "")).strip():
        add(errors, warnings, "error", "question.stem_md is empty")
    if question.get("type") not in (None, "calculation", "choice", "fill", "proof",
                                    "reading", "experiment", "other"):
        add(errors, warnings, "error", f"invalid question.type: {question.get('type')!r}")

    answer = q.get("answer") or {}
    if not str(answer.get("final_md", "")).strip():
        add(errors, warnings, "error", "answer.final_md is empty")
    if answer.get("confidence") not in (None, *CONFIDENCE):
        add(errors, warnings, "error", "answer.confidence must be high/medium/low")

    analysis = q.get("analysis") or {}
    if not str(analysis.get("steps_md", "")).strip():
        add(errors, warnings, "error", "analysis.steps_md is empty")

    review = q.get("review") or {}
    if review.get("status") not in STATUSES:
        add(errors, warnings, "error", "review.status must be draft/reviewed/published")
    if review.get("status") in ("reviewed", "published") and review.get("uncertainties"):
        add(errors, warnings, "error", "reviewed/published card still has uncertainties")

    diag = q.get("diagnosis") or {}
    for et in diag.get("error_types", []) or []:
        if et not in ERROR_TYPES:
            add(errors, warnings, "error", f"invalid diagnosis.error_types entry: {et!r}")

    figures = q.get("figures") or []
    fig_ids = set()
    for i, fig in enumerate(figures):
        if not isinstance(fig, dict):
            add(errors, warnings, "error", f"figures[{i}] must be an object")
            continue
        fid = fig.get("id")
        if not fid:
            add(errors, warnings, "error", f"figures[{i}].id is required")
        else:
            fig_ids.add(fid)
        if fig.get("kind") not in FIG_KINDS:
            add(errors, warnings, "error", f"figures[{i}].kind invalid: {fig.get('kind')!r}")
        if fig.get("confidence") not in CONFIDENCE:
            add(errors, warnings, "error", f"figures[{i}].confidence invalid")
        for key in ("path", "before_path"):
            raw = fig.get(key)
            if not raw:
                continue
            p = Path(raw)
            p = p if p.is_absolute() else root / p
            if not p.exists():
                add(errors, warnings, "error", f"figure file missing: {p}")

    for ref in question.get("figure_refs", []) or []:
        if ref not in fig_ids:
            add(errors, warnings, "error", f"question.figure_refs references missing figure: {ref}")

    stem_text = str(question.get("stem_md", ""))
    if any(word in stem_text for word in ("如图", "图中", "图示", "下表", "如表")) and not figures:
        add(errors, warnings, "error",
            "stem refers to a figure/table but figures[] is empty")

    # Placeholder / uncertainty scan.
    text_fields = [
        ("question.stem_md", question.get("stem_md", "")),
        ("analysis.steps_md", analysis.get("steps_md", "")),
        ("answer.final_md", answer.get("final_md", "")),
    ]
    for name, value in text_fields:
        s = str(value or "")
        for ph in PLACEHOLDERS:
            if ph in s:
                add(errors, warnings, "error", f"{name} contains placeholder {ph!r}")
        if not allow_uncertain and ("[?]" in s or "[missing]" in s):
            add(errors, warnings, "error", f"{name} contains uncertain/missing marker")
        elif allow_uncertain and ("[?]" in s or "[missing]" in s):
            add(warnings, warnings, "warning", f"{name} contains uncertain/missing marker")

    if strict and warnings:
        errors.extend(warnings)

    return errors, warnings


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate question.json card packages.")
    ap.add_argument("paths", nargs="+", type=Path)
    ap.add_argument("--root", type=Path, help="base for relative figure paths")
    ap.add_argument("--strict", action="store_true", help="treat warnings as errors")
    ap.add_argument("--allow-uncertain", action="store_true", help="allow [?]/[missing] as warnings")
    args = ap.parse_args()

    files: list[Path] = []
    for p in args.paths:
        if p.is_dir():
            files.extend(sorted(p.glob("**/question.json")))
        elif p.is_file():
            files.append(p)
        else:
            print(f"Not found: {p}", file=sys.stderr)
            return 2
    if not files:
        print("No question.json files found.", file=sys.stderr)
        return 2

    total_errors = 0
    total_warnings = 0
    for f in files:
        root = args.root or default_root(f)
        errors, warnings = validate_one(f, root, args.allow_uncertain, args.strict)
        total_errors += len(errors)
        total_warnings += len(warnings)
        if errors or warnings:
            print(f"\n{f}")
            for e in errors:
                print(f"  ERROR: {e}")
            for w in warnings:
                print(f"  WARN:  {w}")
        else:
            print(f"OK  {f}")

    print(f"\n{len(files)} file(s), {total_errors} error(s), {total_warnings} warning(s)")
    return 1 if total_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
