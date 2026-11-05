#!/usr/bin/env python3
"""Render question.json into a Markdown card (DOCX only on explicit request).

The builder enforces two things that are easy to lose in a hand-written card:

1. Every figure in ``figures/`` is embedded in the Markdown card
   (and in DOCX as well when ``--docx`` is passed).
2. LaTeX math is rendered: formula images in the Markdown card, optional
   native Word equations (OMML) in DOCX, with image fallback.

Markdown is the default deliverable. Do not pass ``--docx`` unless the user
explicitly asked for a Word file — that keeps the whole python-docx / OMML
pipeline out of the normal flow.

Examples:
    python build_card.py text/question.json --out card.md
    python build_card.py text/question.json --out card.md --formula-mode both
    python build_card.py text/question.json --out card.md --docx card.docx  # only on request
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
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

# $$...$$ first, then $...$, then the LaTeX bracket forms.
MATH_RE = re.compile(r"(\$\$.*?\$\$|\$[^$\n]+?\$|\\\[.*?\\\]|\\\(.*?\\\))", re.S)
CODE_RE = re.compile(r"(```.*?```|`[^`]+`)", re.S)


def default_root(json_path: Path) -> Path:
    if json_path.parent.name.lower() == "text":
        return json_path.parent.parent
    return json_path.parent


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def relpath(path: Path, base: Path) -> str:
    try:
        return Path(os.path.relpath(path, base)).as_posix()
    except Exception:
        return path.as_posix()


def stars(n: int) -> str:
    try:
        n = max(1, min(5, int(n)))
    except Exception:
        n = 3
    return "★" * n + "☆" * (5 - n)


def md_to_text(s: str) -> str:
    s = re.sub(r"!\[[^\]]*\]\([^)]+\)", "[图]", s)
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
    s = re.sub(r"^#{1,6}\s*", "", s, flags=re.M)
    s = s.replace("**", "").replace("__", "").replace("`", "")
    return s


def figure_path(root: Path, figure: dict) -> Path | None:
    raw = figure.get("path", "")
    if not raw:
        return None
    p = Path(raw)
    return p if p.is_absolute() else root / p


def resolve_figures(q: dict, root: Path) -> list[dict]:
    """Use declared figures, then fill gaps from figures/fig-* images."""
    figures: list[dict] = []
    seen: set[str] = set()
    for fig in q.get("figures", []) or []:
        if not isinstance(fig, dict):
            continue
        figures.append(fig)
        if fig.get("id"):
            seen.add(str(fig["id"]))

    fig_dir = root / "figures"
    if fig_dir.is_dir():
        for p in sorted(fig_dir.glob("fig-*")):
            if p.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp", ".svg"):
                continue
            if ".before." in p.name:
                continue
            fid = p.stem
            if fid in seen:
                continue
            figures.append({
                "id": fid,
                "path": relpath(p, root),
                "kind": "clean-crop",
                "caption": "",
                "confidence": "medium",
            })
            seen.add(fid)
    return figures


def md_image(root: Path, card_dir: Path, figure: dict) -> str:
    p = figure_path(root, figure)
    if not p:
        return ""
    return f"![{figure.get('id', 'figure')}]({relpath(p, card_dir)})"


def figure_warnings(q: dict, root: Path) -> list[str]:
    warnings: list[str] = []
    for fig in q.get("figures", []) or []:
        p = figure_path(root, fig)
        if not p or not p.exists():
            warnings.append(f"figure asset missing: {p}")
        elif p.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
            warnings.append(f"figure is not DOCX-embeddable (export PNG/JPG): {p}")
    return warnings


# ---------------------------------------------------------------------------
# Math parsing
# ---------------------------------------------------------------------------

def _strip_delims(s: str) -> str:
    s = s.strip()
    if s.startswith("$$") and s.endswith("$$"):
        return s[2:-2].strip()
    if s.startswith("$") and s.endswith("$") and len(s) >= 2:
        return s[1:-1].strip()
    if s.startswith(r"\[") and s.endswith(r"\]"):
        return s[2:-2].strip()
    if s.startswith(r"\(") and s.endswith(r"\)"):
        return s[2:-2].strip()
    return s


def split_math(text: str) -> list[tuple[str, str]]:
    """Return (kind, value) where kind is text/inline/display.

    Code fences and inline code are kept as text and never converted.
    """
    out: list[tuple[str, str]] = []
    for chunk in CODE_RE.split(text):
        if not chunk:
            continue
        if chunk.startswith("```") or (chunk.startswith("`") and chunk.endswith("`")):
            out.append(("text", chunk))
            continue
        for part in MATH_RE.split(chunk):
            if not part:
                continue
            if MATH_RE.fullmatch(part):
                latex = _strip_delims(part)
                if not latex:
                    out.append(("text", part))
                    continue
                display = part.startswith("$$") or part.startswith(r"\[")
                out.append(("display" if display else "inline", latex))
            else:
                out.append(("text", part))
    return out


def has_math(text: str) -> bool:
    return any(kind != "text" for kind, _ in split_math(text))


# ---------------------------------------------------------------------------
# Formula images for Markdown
# ---------------------------------------------------------------------------

class FormulaRenderer:
    def __init__(self, root: Path):
        self.dir = root / "formulas"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.cache: dict[tuple[str, bool], Path] = {}
        self.available = True
        self.error = ""
        try:
            import matplotlib
            matplotlib.use("Agg")
            matplotlib.rcParams["mathtext.fontset"] = "stix"
            from matplotlib import mathtext  # noqa: F401
            from PIL import Image, ImageChops, ImageOps  # noqa: F401
        except Exception as exc:
            self.available = False
            self.error = f"matplotlib/Pillow unavailable: {exc}"

    @staticmethod
    def clean_latex(latex: str) -> str:
        latex = latex.strip()
        latex = latex.replace(r"\displaystyle", "")
        latex = latex.replace(r"\left", "").replace(r"\right", "")
        latex = latex.replace(r"\dfrac", r"\frac")
        latex = re.sub(r"\\text\{([^{}]*)\}", r"\\mathrm{\1}", latex)
        # Common shorthand: \frac12 -> \frac{1}{2}.
        latex = re.sub(r"\\frac(\d)(\d)", r"\\frac{\1}{\2}", latex)
        latex = latex.replace(r"\%", "%")
        return latex

    def render(self, latex: str, display: bool = False) -> Path | None:
        if not self.available:
            return None
        key = (latex, display)
        if key in self.cache:
            return self.cache[key]
        digest = hashlib.sha1(f"{latex}|{display}".encode("utf-8")).hexdigest()[:12]
        path = self.dir / f"eq-{digest}.png"
        if not path.exists():
            try:
                from matplotlib import mathtext
                from matplotlib.font_manager import FontProperties
                from PIL import Image, ImageChops, ImageOps

                source = f"${self.clean_latex(latex)}$"
                mathtext.math_to_image(
                    source, str(path), dpi=210 if display else 160,
                    format="png",
                    prop=FontProperties(size=14 if display else 10),
                )
                # Trim the generous white border so inline images are compact.
                im = Image.open(path).convert("RGBA")
                rgb = im.convert("RGB")
                bg = Image.new("RGB", rgb.size, "white")
                bbox = ImageChops.difference(rgb, bg).getbbox()
                if bbox:
                    im = im.crop(bbox)
                im = ImageOps.expand(im, border=3, fill=(255, 255, 255, 0))
                im.save(path, "PNG")
            except Exception:
                path.unlink(missing_ok=True)
                return None
        self.cache[key] = path
        return path


def render_markdown_math(text: str, renderer: FormulaRenderer | None,
                         card_dir: Path) -> tuple[str, list[str]]:
    """Replace $...$ with local formula images; keep code blocks untouched."""
    warnings: list[str] = []
    if renderer is None:
        return text, warnings
    out: list[str] = []
    for kind, value in split_math(text):
        if kind == "text":
            out.append(value)
            continue
        path = renderer.render(value, display=(kind == "display"))
        if not path:
            warnings.append(f"formula render failed: {value[:80]}")
            out.append(f"${value}$" if kind == "inline" else f"$${value}$$")
            continue
        img = f"![formula]({relpath(path, card_dir)})"
        out.append(f"\n\n{img}\n\n" if kind == "display" else img)
    return "".join(out), warnings


# ---------------------------------------------------------------------------
# Native Word equations
# ---------------------------------------------------------------------------

class FormulaDocx:
    def __init__(self):
        self.available = True
        self.error = ""
        try:
            import latex2mathml.converter  # noqa: F401
            import mathml2omml  # noqa: F401
            from lxml import etree  # noqa: F401
        except Exception as exc:
            self.available = False
            self.error = f"latex2mathml/mathml2omml/lxml unavailable: {exc}"

    def element(self, latex: str):
        if not self.available:
            return None
        try:
            import latex2mathml.converter as l2m
            import mathml2omml
            from lxml import etree

            mathml = l2m.convert(latex)
            omml = mathml2omml.convert(mathml)
            if "xmlns:m" not in omml:
                omml = omml.replace(
                    "<m:oMath>",
                    '<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">',
                    1,
                )
            return etree.fromstring(omml.encode("utf-8"))
        except Exception:
            return None


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------

def build_question_markdown(q: dict, root: Path, card_dir: Path) -> str:
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
    for fig in resolve_figures(q, root):
        img = md_image(root, card_dir, fig)
        if img:
            lines.append("")
            lines.append(img)
        if fig.get("caption"):
            lines.append(f"*{fig['caption']}*")
    lines.append("")
    return "\n".join(lines).strip() + "\n"


def build_markdown(q: dict, root: Path, card_dir: Path) -> str:
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

    figures = resolve_figures(q, root)
    if figures:
        lines.append("### 配图")
        lines.append("")
        for fig in figures:
            img = md_image(root, card_dir, fig)
            if img:
                lines.append(img)
                lines.append("")
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


# ---------------------------------------------------------------------------
# DOCX
# ---------------------------------------------------------------------------

def add_text_runs(p, text: str) -> None:
    """Add plain/bold Markdown text; math is handled by the caller."""
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "[图]", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = text.replace("`", "")
    for piece in re.split(r"(\*\*.*?\*\*|__.*?__)", text):
        if not piece:
            continue
        bold = (piece.startswith("**") and piece.endswith("**")) or (
            piece.startswith("__") and piece.endswith("__"))
        value = piece[2:-2] if bold else piece
        if value:
            run = p.add_run(value)
            if bold:
                run.bold = True


def add_inline_math(p, latex: str, docx_math: FormulaDocx,
                    renderer: FormulaRenderer | None, warnings: list[str]) -> None:
    el = docx_math.element(latex)
    if el is not None:
        p._p.append(el)
        return
    if renderer:
        path = renderer.render(latex, display=False)
        if path:
            from docx.shared import Inches
            run = p.add_run()
            run.add_picture(str(path), height=Inches(0.22))
            return
    warnings.append(f"Word equation failed, kept raw LaTeX: {latex[:80]}")
    p.add_run(f"${latex}$")


def add_display_math(doc, latex: str, docx_math: FormulaDocx,
                     renderer: FormulaRenderer | None, warnings: list[str]) -> None:
    p = doc.add_paragraph()
    p.alignment = 1  # WD_ALIGN_PARAGRAPH.CENTER
    el = docx_math.element(latex)
    if el is not None:
        p._p.append(el)
        return
    if renderer:
        path = renderer.render(latex, display=True)
        if path:
            from docx.shared import Inches
            run = p.add_run()
            run.add_picture(str(path), height=Inches(0.42))
            return
    warnings.append(f"Word display equation failed, kept raw LaTeX: {latex[:80]}")
    p.add_run(f"$${latex}$$")


def add_rich_text(doc, text: str, docx_math: FormulaDocx,
                  renderer: FormulaRenderer | None, warnings: list[str],
                  style: str | None = None) -> None:
    """Add text with inline/display equations, splitting on display math."""
    buffer: list[tuple[str, str]] = []

    def flush():
        if not buffer:
            return
        p = doc.add_paragraph(style=style)
        for kind, value in buffer:
            if kind == "text":
                add_text_runs(p, value)
            else:
                add_inline_math(p, value, docx_math, renderer, warnings)
        buffer.clear()

    for kind, value in split_math(text):
        if kind == "display":
            flush()
            add_display_math(doc, value, docx_math, renderer, warnings)
        else:
            buffer.append((kind, value))
    flush()


def build_docx(q: dict, root: Path, out: Path,
               renderer: FormulaRenderer | None = None,
               strict: bool = False) -> list[str]:
    try:
        from docx import Document
        from docx.shared import Inches
    except ImportError as exc:
        raise RuntimeError("python-docx is not installed: pip install python-docx") from exc

    warnings: list[str] = []
    docx_math = FormulaDocx()
    subject = SUBJECT_LABELS.get(q.get("subject", "other"), q.get("subject", "其他"))
    doc = Document()
    doc.add_heading(f"{subject} · {q.get('grade', '')} · 错题卡", level=0)
    doc.add_paragraph(f"ID：{q.get('id', '')}　状态：{q.get('review', {}).get('status', 'draft')}")

    question = q.get("question", {})
    doc.add_heading("题目", level=1)
    if question.get("instruction_md"):
        add_rich_text(doc, question["instruction_md"], docx_math, renderer, warnings)
    add_rich_text(doc, question.get("stem_md", ""), docx_math, renderer, warnings)
    for sub in question.get("subquestions", []) or []:
        add_rich_text(doc, f"**{sub.get('label', '')}** {sub.get('text_md', '')}",
                      docx_math, renderer, warnings)
    for opt in question.get("options", []) or []:
        add_rich_text(doc, f"**{opt.get('label', '')}.** {opt.get('text_md', '')}",
                      docx_math, renderer, warnings, style="List Bullet")

    figures = resolve_figures(q, root)
    if figures:
        doc.add_heading("配图", level=2)
        for fig in figures:
            p = figure_path(root, fig)
            if p and p.exists() and p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
                try:
                    doc.add_picture(str(p), width=Inches(5.8))
                except Exception as exc:
                    warnings.append(f"figure embed failed: {p} ({exc})")
                    doc.add_paragraph(f"[图缺失：{fig.get('id', '')}]")
            else:
                warnings.append(f"figure missing or unsupported for DOCX: {p}")
                doc.add_paragraph(f"[图缺失：{fig.get('id', '')}]")
            if fig.get("caption"):
                add_rich_text(doc, fig["caption"], docx_math, renderer, warnings)

    answer = q.get("answer", {})
    doc.add_heading("答案", level=1)
    add_rich_text(doc, answer.get("final_md", ""), docx_math, renderer, warnings)
    if answer.get("units"):
        add_rich_text(doc, "单位：" + answer["units"], docx_math, renderer, warnings)
    if answer.get("verification_md"):
        add_rich_text(doc, "**检验：** " + answer["verification_md"],
                      docx_math, renderer, warnings)

    analysis = q.get("analysis", {})
    doc.add_heading("解析", level=1)
    for line in analysis.get("steps_md", "").splitlines():
        if line.strip():
            add_rich_text(doc, line, docx_math, renderer, warnings)
    if analysis.get("key_points"):
        doc.add_heading("关键点", level=2)
        for item in analysis["key_points"]:
            add_rich_text(doc, item, docx_math, renderer, warnings, style="List Bullet")
    if analysis.get("pitfalls"):
        doc.add_heading("易错点", level=2)
        for item in analysis["pitfalls"]:
            add_rich_text(doc, item, docx_math, renderer, warnings, style="List Bullet")

    diag = q.get("diagnosis", {})
    if any(diag.get(k) for k in ("student_answer_md", "error_types", "root_cause_md", "remedy_md")):
        doc.add_heading("错因诊断", level=1)
        if diag.get("student_answer_md"):
            add_rich_text(doc, "**学生答案：** " + diag["student_answer_md"],
                          docx_math, renderer, warnings)
        if diag.get("error_types"):
            doc.add_paragraph("错误类型：" + "、".join(
                ERROR_LABELS.get(e, e) for e in diag["error_types"]))
        if diag.get("root_cause_md"):
            add_rich_text(doc, "**根因：** " + diag["root_cause_md"],
                          docx_math, renderer, warnings)
        if diag.get("remedy_md"):
            add_rich_text(doc, "**改进：** " + diag["remedy_md"],
                          docx_math, renderer, warnings)

    meta = q.get("meta", {})
    doc.add_heading("知识点与标签", level=1)
    for kp in meta.get("knowledge_points", []) or []:
        add_rich_text(doc, kp, docx_math, renderer, warnings, style="List Bullet")
    if meta.get("tags"):
        doc.add_paragraph("标签：" + "、".join(meta["tags"]))
    doc.add_paragraph("难度：" + stars(meta.get("difficulty", 3)))

    if meta.get("variant_md"):
        doc.add_heading("变式", level=1)
        add_rich_text(doc, meta["variant_md"], docx_math, renderer, warnings)

    review = q.get("review", {})
    doc.add_heading("审核", level=1)
    doc.add_paragraph(f"状态：{review.get('status', 'draft')}")
    if review.get("uncertainties"):
        doc.add_paragraph("待确认：" + "；".join(review["uncertainties"]))

    raw_dollars = [p.text for p in doc.paragraphs if "$" in p.text]
    if raw_dollars:
        warnings.append(f"raw LaTeX left in DOCX: {raw_dollars[0][:100]}")

    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out))

    if strict and warnings:
        raise RuntimeError("; ".join(warnings))
    return warnings


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="Build a Markdown card from question.json (DOCX opt-in).")
    ap.add_argument("json", type=Path)
    ap.add_argument("--out", type=Path, default=Path("card.md"))
    ap.add_argument("--question-out", type=Path, help="optional clean question-only Markdown")
    ap.add_argument("--docx", type=Path,
                    help="opt-in Word export; pass only when the user explicitly asks for Word")
    ap.add_argument("--root", type=Path, help="root for relative figure paths (default: JSON parent)")
    ap.add_argument("--formula-mode", choices=("both", "images", "latex"), default="both",
                    help="both: card.md images + card.latex.md; images: only rendered images; latex: raw source")
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    if not args.json.exists():
        print(f"JSON not found: {args.json}", file=sys.stderr)
        return 2
    q = load_json(args.json)
    root = args.root or default_root(args.json)
    q["figures"] = resolve_figures(q, root)

    warnings: list[str] = figure_warnings(q, root)
    if warnings and args.strict:
        for warning in warnings:
            print("ERROR: " + warning, file=sys.stderr)
        return 1
    missing = [k for k in ("id", "subject", "grade", "question", "answer", "analysis", "review")
               if not q.get(k)]
    if missing:
        print(f"Missing required field(s): {', '.join(missing)}", file=sys.stderr)
        if args.strict:
            return 1

    stem = str(q.get("question", {}).get("stem_md", ""))
    if any(word in stem for word in ("如图", "图中", "图示", "下表", "如表")) and not q["figures"]:
        warnings.append("stem refers to a figure/table but no figure asset was found")
        if args.strict:
            print("ERROR: " + warnings[-1], file=sys.stderr)
            return 1

    renderer: FormulaRenderer | None = None
    if args.formula_mode != "latex" or args.docx:
        renderer = FormulaRenderer(root)
        if not renderer.available:
            warnings.append(renderer.error)
            if args.strict:
                print("ERROR: " + renderer.error, file=sys.stderr)
                return 1

    raw_md = build_markdown(q, root, args.out.parent)
    if args.formula_mode == "latex" or not has_math(raw_md):
        md = raw_md
    else:
        md, formula_warnings = render_markdown_math(raw_md, renderer, args.out.parent)
        warnings.extend(formula_warnings)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(md, encoding="utf-8")
    print(f"wrote {args.out}")

    if args.formula_mode == "both":
        latex_path = args.out.with_name(args.out.stem + ".latex.md")
        latex_path.write_text(raw_md, encoding="utf-8")
        print(f"wrote {latex_path}")

    if args.question_out:
        raw_q = build_question_markdown(q, root, args.question_out.parent)
        if args.formula_mode == "latex" or not has_math(raw_q):
            qmd = raw_q
        else:
            qmd, qw = render_markdown_math(raw_q, renderer, args.question_out.parent)
            warnings.extend(qw)
        args.question_out.parent.mkdir(parents=True, exist_ok=True)
        args.question_out.write_text(qmd, encoding="utf-8")
        print(f"wrote {args.question_out}")
        if args.formula_mode == "both":
            q_latex = args.question_out.with_name(args.question_out.stem + ".latex.md")
            q_latex.write_text(raw_q, encoding="utf-8")
            print(f"wrote {q_latex}")

    if args.docx:
        try:
            docx_warnings = build_docx(q, root, args.docx, renderer, strict=args.strict)
            warnings.extend(docx_warnings)
            print(f"wrote {args.docx}")
        except Exception as exc:
            print(f"DOCX failed: {exc}", file=sys.stderr)
            if args.strict:
                return 1

    if warnings:
        print("Warnings:", file=sys.stderr)
        for w in warnings:
            print(f"  - {w}", file=sys.stderr)
        if args.strict:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
