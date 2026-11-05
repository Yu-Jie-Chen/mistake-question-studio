#!/usr/bin/env python3
"""Render question.json into a teacher/student-facing Markdown card and optional DOCX.

Examples:
    python build_card.py text/question.json --out card.md
    python build_card.py text/question.json --out card.md --docx card.docx
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SUBJECT_LABELS = {
    "physics": "物理",
    "chemistry": "化学",
    "mathematics": "数学",
    "english": "英语",
    "biology": "生物",
    "geography": "地理",
    "history": "历史",
    "politics": "政治",
    "other": "其他",
}

SOURCE_LABELS = {
    "screenshot": "截图",
    "photo": "照片",
    "pdf": "PDF",
    "scan": "扫描件",
    "docx": "Word 文档",
    "other": "其他来源",
}

ERROR_LABELS = {
    "concept": "概念理解",
    "model": "模型/受力/结构",
    "reading": "读题/读图",
    "strategy": "方法选择",
    "algebra": "代数运算",
    "unit": "单位/量纲",
    "diagram": "图形理解",
    "language": "语言理解",
    "careless": "笔误/粗心",
}


def default_root(json_path: Path) -> Path:
    # Standard package layout: text/question.json + figures/ at the work root.
    if json_path.parent.name.lower() == "text":
        return json_path.parent.parent
    return json_path.parent


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def figure_path(root: Path, figure: dict) -> Path | None:
    raw = figure.get("path", "")
    if not raw:
        return None
    p = Path(raw)
    return p if p.is_absolute() else root / p


def md_image(root: Path, figure: dict) -> str:
    p = figure_path(root, figure)
    if not p:
        return ""
    try:
        rel = p.relative_to(root)
    except ValueError:
        rel = p
    return f"![{figure.get('id', 'figure')}]({rel.as_posix()})"


def stars(n: int) -> str:
    try:
        n = max(1, min(5, int(n)))
    except Exception:
        n = 3
    return "★" * n + "☆" * (5 - n)


def build_question_markdown(q: dict, root: Path) -> str:
    """Clean question-only Markdown, useful for a question bank or review."""
    lines: list[str] = []
    lines.append(f"# {q.get('grade', '')} · 题目")
    lines.append("")
    question = q.get("question", {})
    if question.get("instruction_md"):
        lines.append(question["instruction_md"].strip())
        lines.append("")
    lines.append(question.get("stem_md", "").strip())
    lines.append("")
    for sub in question.get("subquestions", []) or []:
        lines.append(f"**{sub.get('label', '')}** {sub.get('text_md', '')}".strip())
        lines.append("")
    for opt in question.get("options", []) or []:
        lines.append(f"- **{opt.get('label', '')}.** {opt.get('text_md', '')}")
    for fig in q.get("figures", []) or []:
        img = md_image(root, fig)
        if img:
            lines.append("")
            lines.append(img)
        if fig.get("caption"):
            lines.append(f"*{fig['caption']}*")
    lines.append("")
    return "\n".join(lines).strip() + "\n"


def build_markdown(q: dict, root: Path) -> str:
    subject = SUBJECT_LABELS.get(q.get("subject", "other"), q.get("subject", "其他"))
    lines: list[str] = []
    lines.append(f"# {subject} · {q.get('grade', '')} · 错题卡")
    lines.append("")
    lines.append(f"> ID：`{q.get('id', '')}`　|　状态：`{q.get('review', {}).get('status', 'draft')}`")
    src = q.get("source", {})
    if src:
        bits = [SOURCE_LABELS.get(src.get("type", ""), src.get("type", "")), src.get("file", "")]
        if src.get("page"):
            bits.append(f"第 {src['page']} 页")
        lines.append(f"> 来源：{'，'.join(b for b in bits if b)}")
        if src.get("note"):
            lines.append(f"> 备注：{src['note']}")
    lines.append("")

    question = q.get("question", {})
    lines.append("## 题目")
    lines.append("")
    if question.get("instruction_md"):
        lines.append(question["instruction_md"].strip())
        lines.append("")
    lines.append(question.get("stem_md", "").strip())
    lines.append("")

    for sub in question.get("subquestions", []) or []:
        lines.append(f"**{sub.get('label', '')}** {sub.get('text_md', '')}".strip())
        lines.append("")

    options = question.get("options", []) or []
    if options:
        lines.append("### 选项")
        lines.append("")
        for opt in options:
            lines.append(f"- **{opt.get('label', '')}.** {opt.get('text_md', '')}")
        lines.append("")

    figures = q.get("figures", []) or []
    if figures:
        lines.append("### 配图")
        lines.append("")
        for fig in figures:
            img = md_image(root, fig)
            if img:
                lines.append(img)
            cap = fig.get("caption", "")
            if cap:
                lines.append(f"*{cap}*")
            lines.append("")

    answer = q.get("answer", {})
    lines.append("## 答案")
    lines.append("")
    lines.append(answer.get("final_md", "").strip())
    lines.append("")
    if answer.get("units"):
        lines.append(f"单位：{answer['units']}")
        lines.append("")
    if answer.get("alternate_md"):
        lines.append(f"其他形式：{answer['alternate_md']}")
        lines.append("")
    if answer.get("verification_md"):
        lines.append(f"**检验：** {answer['verification_md']}")
        lines.append("")
    lines.append(f"*答案置信度：{answer.get('confidence', 'medium')}*")
    lines.append("")

    analysis = q.get("analysis", {})
    lines.append("## 解析")
    lines.append("")
    lines.append(analysis.get("steps_md", "").strip())
    lines.append("")
    key_points = analysis.get("key_points", []) or []
    if key_points:
        lines.append("### 关键点")
        lines.append("")
        for item in key_points:
            lines.append(f"- {item}")
        lines.append("")
    pitfalls = analysis.get("pitfalls", []) or []
    if pitfalls:
        lines.append("### 易错点")
        lines.append("")
        for item in pitfalls:
            lines.append(f"- {item}")
        lines.append("")

    diag = q.get("diagnosis", {})
    if any(diag.get(k) for k in ("student_answer_md", "error_types", "root_cause_md", "remedy_md")):
        lines.append("## 错因诊断")
        lines.append("")
        if diag.get("student_answer_md"):
            lines.append(f"**学生答案：** {diag['student_answer_md']}")
            lines.append("")
        if diag.get("error_types"):
            lines.append("**错误类型：** " + "、".join(
                ERROR_LABELS.get(e, e) for e in diag["error_types"]))
            lines.append("")
        if diag.get("root_cause_md"):
            lines.append(f"**根因：** {diag['root_cause_md']}")
            lines.append("")
        if diag.get("remedy_md"):
            lines.append(f"**改进：** {diag['remedy_md']}")
            lines.append("")

    meta = q.get("meta", {})
    lines.append("## 知识点与标签")
    lines.append("")
    for kp in meta.get("knowledge_points", []) or []:
        lines.append(f"- {kp}")
    if meta.get("tags"):
        lines.append(f"- 标签：{', '.join(meta['tags'])}")
    lines.append(f"- 难度：{stars(meta.get('difficulty', 3))}")
    lines.append("")
    if meta.get("variant_md"):
        lines.append("## 变式")
        lines.append("")
        lines.append(meta["variant_md"].strip())
        lines.append("")

    review = q.get("review", {})
    lines.append("## 审核")
    lines.append("")
    lines.append(f"- 状态：`{review.get('status', 'draft')}`")
    if review.get("reviewer"):
        lines.append(f"- 审核人：{review['reviewer']}")
    if review.get("date"):
        lines.append(f"- 日期：{review['date']}")
    uncertainties = review.get("uncertainties", []) or []
    if uncertainties:
        lines.append("- 待确认：")
        for u in uncertainties:
            lines.append(f"  - {u}")
    lines.append("")
    return "\n".join(lines).strip() + "\n"


def md_to_text(s: str) -> str:
    s = re.sub(r"!\[[^\]]*\]\([^)]+\)", "[图]", s)
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
    s = re.sub(r"^#{1,6}\s*", "", s, flags=re.M)
    s = s.replace("**", "").replace("__", "").replace("`", "")
    return s


def build_docx(q: dict, root: Path, out: Path) -> None:
    try:
        from docx import Document
        from docx.shared import Inches, Pt
    except ImportError as exc:
        raise RuntimeError("python-docx is not installed: pip install python-docx") from exc

    subject = SUBJECT_LABELS.get(q.get("subject", "other"), q.get("subject", "其他"))
    doc = Document()
    doc.add_heading(f"{subject} · {q.get('grade', '')} · 错题卡", level=0)
    doc.add_paragraph(f"ID：{q.get('id', '')}　状态：{q.get('review', {}).get('status', 'draft')}")

    question = q.get("question", {})
    doc.add_heading("题目", level=1)
    if question.get("instruction_md"):
        doc.add_paragraph(md_to_text(question["instruction_md"]))
    doc.add_paragraph(md_to_text(question.get("stem_md", "")))
    for sub in question.get("subquestions", []) or []:
        doc.add_paragraph(md_to_text(f"{sub.get('label', '')} {sub.get('text_md', '')}"))
    for opt in question.get("options", []) or []:
        doc.add_paragraph(md_to_text(f"{opt.get('label', '')}. {opt.get('text_md', '')}"))

    for fig in q.get("figures", []) or []:
        p = figure_path(root, fig)
        if p and p.exists() and p.suffix.lower() in (".png", ".jpg", ".jpeg"):
            try:
                doc.add_picture(str(p), width=Inches(5.6))
            except Exception:
                doc.add_paragraph(f"[图：{fig.get('caption', '')}]")
        elif fig.get("caption"):
            doc.add_paragraph(f"[图：{fig['caption']}]")

    answer = q.get("answer", {})
    doc.add_heading("答案", level=1)
    doc.add_paragraph(md_to_text(answer.get("final_md", "")))
    if answer.get("verification_md"):
        doc.add_paragraph(md_to_text("检验：" + answer["verification_md"]))

    analysis = q.get("analysis", {})
    doc.add_heading("解析", level=1)
    for para in md_to_text(analysis.get("steps_md", "")).split("\n\n"):
        if para.strip():
            doc.add_paragraph(para.strip())
    if analysis.get("key_points"):
        doc.add_heading("关键点", level=2)
        for item in analysis["key_points"]:
            doc.add_paragraph(md_to_text(item), style="List Bullet")
    if analysis.get("pitfalls"):
        doc.add_heading("易错点", level=2)
        for item in analysis["pitfalls"]:
            doc.add_paragraph(md_to_text(item), style="List Bullet")

    diag = q.get("diagnosis", {})
    if any(diag.get(k) for k in ("student_answer_md", "error_types", "root_cause_md", "remedy_md")):
        doc.add_heading("错因诊断", level=1)
        if diag.get("student_answer_md"):
            doc.add_paragraph(md_to_text("学生答案：" + diag["student_answer_md"]))
        if diag.get("error_types"):
            doc.add_paragraph("错误类型：" + ", ".join(diag["error_types"]))
        if diag.get("root_cause_md"):
            doc.add_paragraph(md_to_text("根因：" + diag["root_cause_md"]))
        if diag.get("remedy_md"):
            doc.add_paragraph(md_to_text("改进：" + diag["remedy_md"]))

    meta = q.get("meta", {})
    doc.add_heading("知识点与标签", level=1)
    for kp in meta.get("knowledge_points", []) or []:
        doc.add_paragraph(md_to_text(kp), style="List Bullet")
    if meta.get("tags"):
        doc.add_paragraph("标签：" + ", ".join(meta["tags"]))
    doc.add_paragraph("难度：" + stars(meta.get("difficulty", 3)))

    if meta.get("variant_md"):
        doc.add_heading("变式", level=1)
        doc.add_paragraph(md_to_text(meta["variant_md"]))

    review = q.get("review", {})
    doc.add_heading("审核", level=1)
    doc.add_paragraph(f"状态：{review.get('status', 'draft')}")
    if review.get("uncertainties"):
        doc.add_paragraph("待确认：" + "；".join(review["uncertainties"]))

    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out))


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a Markdown/DOCX card from question.json.")
    ap.add_argument("json", type=Path)
    ap.add_argument("--out", type=Path, default=Path("card.md"))
    ap.add_argument("--question-out", type=Path, help="optional clean question-only Markdown")
    ap.add_argument("--docx", type=Path)
    ap.add_argument("--root", type=Path, help="root for relative figure paths (default: JSON parent)")
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    if not args.json.exists():
        print(f"JSON not found: {args.json}", file=sys.stderr)
        return 2
    q = load_json(args.json)
    root = args.root or default_root(args.json)
    missing = [k for k in ("id", "subject", "grade", "question", "answer", "analysis", "review")
               if not q.get(k)]
    if missing:
        print(f"Missing required field(s): {', '.join(missing)}", file=sys.stderr)
        if args.strict:
            return 1
    md = build_markdown(q, root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(md, encoding="utf-8")
    print(f"wrote {args.out}")

    if args.question_out:
        args.question_out.parent.mkdir(parents=True, exist_ok=True)
        args.question_out.write_text(build_question_markdown(q, root), encoding="utf-8")
        print(f"wrote {args.question_out}")

    if args.docx:
        try:
            build_docx(q, root, args.docx)
            print(f"wrote {args.docx}")
        except Exception as exc:
            print(f"DOCX failed: {exc}", file=sys.stderr)
            if args.strict:
                return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
