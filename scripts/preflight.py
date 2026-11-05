# -*- coding: utf-8 -*-
"""Catch the build-time traps *before* build_card.py runs.

Every check here exists because it actually cost a rebuild in a real session:

* a decoy image in ``figures/`` gets auto-embedded into the student card
  (``build_card.resolve_figures`` globs ``fig-*`` and skips only ``.before.``);
* ``error_types: ["model"]`` renders as "模型/受力/结构", which reads like a
  physics error on a maths card;
* a field that already starts with "其他形式：" gets a second prefix;
* an odd number of ``$`` silently breaks math rendering;
* ``[?]`` / ``TODO`` placeholders ship in the card.

CLI
---
    python preflight.py work/<id>            # exit 1 on error, 0 otherwise
    python preflight.py text/question.json --strict   # warnings become errors
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ERROR_LABELS = {
    "concept": "概念理解",
    "model": "模型/受力/结构",
    "reading": "读题/读数",
    "strategy": "方法选择",
    "algebra": "代数运算",
    "unit": "单位",
    "diagram": "图形判读",
    "language": "语言理解",
    "careless": "粗心",
}

PREFIXED_FIELDS = [
    # only where the card's own lead-in is a full sentence: "其他形式：<value>".
    # "**检验：** 验证一（构造）：…" reads fine, so verification_md is not checked.
    ("answer", "alternate_md", "其他形式："),
]

PLACEHOLDERS = ["[?]", "[missing]", "TODO", "XXX", "待补", "待填"]
MD_FIELDS = [
    ("question", "stem_md"), ("question", "instruction_md"),
    ("answer", "final_md"), ("answer", "alternate_md"), ("answer", "verification_md"),
    ("analysis", "steps_md"), ("diagnosis", "student_answer_md"),
    ("diagnosis", "root_cause_md"), ("diagnosis", "remedy_md"),
    ("meta", "variant_md"),
]


def _dollars_balanced(text: str) -> bool:
    """Count unescaped '$'; also accept '$$' pairs."""
    n = len(re.findall(r"(?<!\\)\$", text))
    return n % 2 == 0


def _walk_strings(obj, path=""):
    if isinstance(obj, str):
        yield path, obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk_strings(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk_strings(v, f"{path}[{i}]")


def check(qjson: Path, strict=False):
    errors, warnings = [], []
    root = qjson.parent.parent if qjson.parent.name == "text" else qjson.parent

    try:
        q = json.loads(qjson.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return [f"{qjson.name}: invalid JSON ({exc})"], []

    for key in ("schema_version", "id", "subject", "grade", "source", "question",
                "answer", "analysis", "diagnosis", "meta", "review"):
        if key not in q:
            errors.append(f"missing top-level key: {key}")
    if errors:
        return errors, warnings

    fid = str(q["id"])
    if root.name != fid:
        warnings.append(f"id {fid!r} does not match folder {root.name!r} (fine for a rename, confusing later)")

    # --- figures -----------------------------------------------------------
    figs = q.get("figures") or []
    declared = {str(f.get("id")) for f in figs if isinstance(f, dict)}
    for f in figs:
        for key in ("path", "before_path"):
            raw = f.get(key)
            if raw and not (root / raw).exists():
                errors.append(f"figure {f.get('id')}: {key} does not exist ({raw})")
        if not str(f.get("caption") or "").strip():
            warnings.append(f"figure {f.get('id')}: empty caption")
        cap = str(f.get("caption") or "")
        if re.search(r"答案|解得|R\s*=|即为", cap):
            warnings.append(f"figure {f.get('id')}: caption may hint at the answer")
    fig_dir = root / "figures"
    if fig_dir.is_dir():
        for p in sorted(fig_dir.glob("fig-*")):
            if p.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp", ".svg"):
                continue  # spec/mask JSON sidecars are never embedded
            stem = p.stem
            if stem in declared or ".before." in p.name:
                continue
            warnings.append(f"figures/{p.name} is not declared in figures[] and WILL be "
                            "auto-embedded into the card (rename it, e.g. compare-*.png)")

    # --- subject-aware wording --------------------------------------------
    if q.get("subject") != "physics":
        for et in q.get("diagnosis", {}).get("error_types", []) or []:
            if et in ("model", "diagram"):
                warnings.append(f"error_types contains {et!r} -> renders as "
                                f"{ERROR_LABELS.get(et, et)!r}, which reads like a physics error "
                                "on a non-physics card; consider concept/strategy")

    # --- template prefix duplication --------------------------------------
    for section, key, prefix in PREFIXED_FIELDS:
        val = str((q.get(section) or {}).get(key) or "").strip()
        if not val:
            continue
        hint = val.startswith(prefix) or re.match(r"^[^\s：]{1,8}：", val)
        if hint:
            warnings.append(f"{section}.{key} starts with a short 'xx：' label, but the card "
                            f"already prints {prefix!r} -> reads as a double colon")
    for key in ("stem_md", "final_md"):
        if not str((q.get("question" if key == "stem_md" else "answer") or {}).get(key) or "").strip():
            errors.append(f"{key} is empty")

    # --- math + placeholders ---------------------------------------------
    for section, key in MD_FIELDS:
        val = (q.get(section) or {}).get(key)
        if not isinstance(val, str) or not val:
            continue
        if not _dollars_balanced(val):
            errors.append(f"{section}.{key}: unbalanced '$' ({len(re.findall(r'(?<!\\)\$', val))} delimiters)")
    for path, text in _walk_strings(q):
        for ph in PLACEHOLDERS:
            if ph in text:
                errors.append(f"{path}: unresolved placeholder {ph!r}")

    # --- question / figure callouts --------------------------------------
    stem = str(q["question"].get("stem_md", ""))
    if re.search(r"如图|图中|图示|下表|如表", stem) and not (q["question"].get("figure_refs") or figs):
        warnings.append("stem refers to a figure/table but none is declared")

    # --- answer / meta sanity --------------------------------------------
    ans = q.get("answer", {})
    if ans.get("confidence") not in ("high", "medium", "low"):
        warnings.append(f"answer.confidence = {ans.get('confidence')!r} (expected high/medium/low)")
    diff = q.get("meta", {}).get("difficulty", 3)
    if not (isinstance(diff, int) and 1 <= diff <= 5):
        warnings.append(f"meta.difficulty = {diff!r} (expected 1..5)")
    rev = q.get("review", {})
    if rev.get("status") not in ("draft", "reviewed", "published"):
        errors.append(f"review.status = {rev.get('status')!r}")
    if rev.get("status") in ("reviewed", "published") and not (rev.get("reviewer") and rev.get("date")):
        errors.append("review.status is reviewed/published but reviewer/date is empty")
    if rev.get("status") in ("reviewed", "published") and not rev.get("uncertainties"):
        pass  # an empty uncertainty list is allowed once a human cleared the gates

    if strict:
        errors.extend(f"(strict) {w}" for w in warnings)
        warnings = []
    return errors, warnings


def main(argv=None):
    ap = argparse.ArgumentParser(description="Pre-build checks for text/question.json.")
    ap.add_argument("target", type=Path, help="work folder or question.json")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    try:
        sys.stdout.reconfigure(errors="replace")
        sys.stderr.reconfigure(errors="replace")
    except Exception:
        pass

    target = args.target
    qjson = target
    if target.is_dir():
        qjson = None
        for cand in (target / "text" / "question.json", target / "question.json"):
            if cand.exists():
                qjson = cand
                break
        if qjson is None:
            print(f"ERROR not found: {target}/text/question.json", file=sys.stderr)
            return 2
    if not qjson.exists():
        print(f"ERROR not found: {qjson}", file=sys.stderr)
        return 2

    errors, warnings = check(qjson, strict=args.strict)
    if not args.quiet:
        for e in errors:
            print("ERROR " + e)
        for w in warnings:
            print("WARN  " + w)
        print(f"preflight: {len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
