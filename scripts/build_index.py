#!/usr/bin/env python3
"""Build a Markdown index for a folder of question cards.

Example:
    python build_index.py work --out work/index.md
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

SUBJECTS = {
    "physics": "物理", "chemistry": "化学", "mathematics": "数学",
    "english": "英语", "biology": "生物", "geography": "地理",
    "history": "历史", "politics": "政治", "other": "其他",
}


def load(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Build an index.md for a question-card folder.")
    ap.add_argument("workdir", type=Path)
    ap.add_argument("--out", type=Path, default=Path("index.md"))
    args = ap.parse_args()

    files = sorted(args.workdir.glob("**/question.json"))
    rows = []
    skipped = []
    for f in files:
        q = load(f)
        if not q:
            skipped.append((f, "invalid JSON"))
            continue
        card = f.parent / "card.md"
        if not card.exists():
            skipped.append((f, "card.md missing"))
        rows.append((q, f, card))

    rows.sort(key=lambda x: (x[0].get("subject", ""), x[0].get("grade", ""), x[0].get("id", "")))
    lines = ["# 错题卡索引", ""]
    lines.append(f"共 {len(rows)} 张卡，{len(skipped)} 个跳过项。")
    lines.append("")
    current = None
    for q, f, card in rows:
        subject = q.get("subject", "other")
        if subject != current:
            current = subject
            lines.append(f"## {SUBJECTS.get(subject, subject)}")
            lines.append("")
            lines.append("| ID | 年级 | 知识点 | 难度 | 状态 | 卡片 |")
            lines.append("|---|---|---|---:|---|---|")
        kps = "、".join(q.get("meta", {}).get("knowledge_points", [])[:3]) or "—"
        diff = q.get("meta", {}).get("difficulty", "")
        status = q.get("review", {}).get("status", "draft")
        link = ""
        if card.exists():
            try:
                link = card.relative_to(args.out.parent).as_posix()
            except ValueError:
                link = card.as_posix()
        link_md = f"[打开]({link})" if link else "—"
        lines.append(f"| `{q.get('id', '')}` | {q.get('grade', '')} | {kps} | {diff} | {status} | {link_md} |")
    lines.append("")

    if skipped:
        lines.append("## 跳过项")
        lines.append("")
        for f, reason in skipped:
            lines.append(f"- `{f}`：{reason}")
        lines.append("")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {args.out} ({len(rows)} cards, {len(skipped)} skipped)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
