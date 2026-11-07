#!/usr/bin/env python3
"""Render card.md into one standalone, printable HTML card.

This is the hand-over format for teachers: a single file that opens in any
browser, carries its own figures and formula images (inlined as data URIs), and
prints without a network connection.

Card house style, applied here so every card looks the same:

1. Title is ``物理高三 · 王小明 · 错题卡`` — subject+grade in short form, then the
   student's name when the card is issued to one student, then 错题卡.
2. The header block carries the ID only. 状态 / 来源 / 备注 stay in
   ``text/question.json`` and ``review.md``; they are not printed.
3. Figures are printed at 60% of the text column (i.e. shrunk by 40%).
4. The card closes on a single date — no 审核 section, no checkboxes.

Examples:
    python build_card_html.py work/20260101-physics-001/card.md \
        --out work/20260101-physics-001/card.html

    # straight from the source of truth (builds the Markdown in memory first)
    python build_card_html.py work/20260101-physics-001/text/question.json \
        --out work/20260101-physics-001/card.html --formula-mode both
"""
from __future__ import annotations

import argparse
import base64
import html
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

IMG_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
DATE_RE = re.compile(r"^<p>(\d{4}-\d{2}-\d{2})</p>$")
EQ_ONLY_RE = re.compile(r'^<p><img class="formula"[^>]*></p>$')
RAW_MATH_RE = re.compile(r"(?<!\\)\$[^$\n]+?(?<!\\)\$")
MIME = {
    "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
    "webp": "image/webp", "gif": "image/gif", "svg": "image/svg+xml",
}
LI_RE = re.compile(r"^(\s*)(-|\d+\.)\s+(.*)$")

CSS = """
:root { --ink:#1a1a1a; --muted:#5a6470; --line:#d9dee5; --accent:#8b1f1f; }
* { box-sizing: border-box; }
body { margin:0; padding:28px 18px 56px; background:#f4f5f7; color:var(--ink);
  font-family:"Segoe UI","Microsoft YaHei","PingFang SC","Noto Sans CJK SC",sans-serif;
  font-size:16.5px; line-height:1.85; }
main { max-width:860px; margin:0 auto; background:#fff; border:1px solid var(--line);
  border-radius:10px; padding:34px 42px 46px; box-shadow:0 2px 14px rgba(20,30,50,.07); }
h1 { font-size:25px; margin:0 0 14px; padding-bottom:12px; border-bottom:3px solid var(--accent); }
h2 { font-size:20px; margin:30px 0 10px; padding-left:10px; border-left:5px solid var(--accent); }
h3 { font-size:17.5px; margin:22px 0 8px; color:#333a44; }
p { margin:9px 0; }
blockquote { margin:0 0 18px; padding:8px 14px; background:#f7f8fa; border-left:4px solid #b9c2cd;
  color:var(--muted); font-size:14px; line-height:1.7; }
blockquote code { background:#e8ebef; padding:1px 5px; border-radius:4px; }
ul, ol { margin:8px 0 8px; padding-left:24px; }
li { margin:5px 0; }
img.formula { height:auto; max-height:2.4em; vertical-align:middle; margin:0 1px; }
/* 配图：等比例缩到正文宽度的 60%（缩小 40%），居中，不放大到超过原图 */
img.figure { display:block; width:60%; max-width:100%; height:auto; margin:16px auto 4px; }
p.fig-caption { margin:0 auto 18px; text-align:center; color:var(--muted); font-size:14.5px; }
/* 独立成行的公式块。注意不能用 :only-child —— 文本节点不算子元素，
   那样会把「B：把上式解出 m：」里的 m 也撑成整行。 */
p.eq { margin:14px auto; text-align:center; }
p.eq > img.formula { display:block; height:auto; max-height:64px; margin:0 auto; }
hr { border:0; border-top:1px solid var(--line); margin:24px 0; }
table { border-collapse:collapse; width:100%; margin:10px 0 6px; font-size:15px; }
th, td { border:1px solid var(--line); padding:6px 10px; text-align:left; }
th { background:#f1f3f6; }
strong { color:#000; }
.missing { color:#a33; }
/* 卡片只以一个日期收尾 */
p.card-date { margin:34px 0 0; padding-top:12px; border-top:1px solid var(--line);
  color:var(--muted); font-size:14.5px; text-align:right; }
@media print {
  @page { size:A4; margin:18mm 16mm; }
  body { background:#fff; padding:0; font-size:12pt; }
  main { border:0; box-shadow:none; max-width:none; padding:0; }
  h1, h2, h3 { break-after:avoid; }
  img { break-inside:avoid; }
  p.card-date { border-top:1px solid #ccc; }
}
"""


def inline(text: str, base: Path) -> str:
    """Escape inline Markdown, inline every local image as a data URI.

    Images are stashed behind placeholders first, so emphasis that spans a
    formula (``*推力 ![formula](...) 与水平面成…*``) still pairs correctly; a
    per-segment pass would leave the asterisks on screen.
    """
    slots: list[str] = []

    def stash(m: re.Match) -> str:
        slots.append(_image(m.group(1), m.group(2), base))
        return f"\x00{len(slots) - 1}\x00"

    tmp = _inline_text(IMG_RE.sub(stash, text))
    return re.sub(r"\x00(\d+)\x00", lambda m: slots[int(m.group(1))], tmp)


def _inline_text(seg: str) -> str:
    seg = html.escape(seg, quote=False)
    seg = re.sub(r"`([^`]+)`", r"<code>\1</code>", seg)
    seg = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", seg)
    seg = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", seg)
    return seg


def _image(alt: str, src: str, base: Path) -> str:
    p = Path(src)
    if not p.is_absolute():
        p = base / src
    if not p.exists():
        return f'<span class="missing">[图片缺失: {html.escape(alt)}]</span>'
    mime = MIME.get(p.suffix.lower().lstrip("."), "image/png")
    data = base64.b64encode(p.read_bytes()).decode("ascii")
    cls = "formula" if alt.strip().lower() == "formula" else "figure"
    return f'<img class="{cls}" alt="{html.escape(alt)}" src="data:{mime};base64,{data}">'


def _list(lines: list[str], start: int, base: Path) -> tuple[str, int]:
    """Flat or indented list -> nested <ul>/<ol>."""
    first = LI_RE.match(lines[start])
    ordered = not first.group(2).startswith("-")
    items: list[str] = []
    i = start
    while i < len(lines):
        m = LI_RE.match(lines[i])
        if not m:
            break
        indent = len(m.group(1).expandtabs(2))
        if indent >= 2 and items:
            sub, i = _list(lines, i, base)
            items[-1] = items[-1][:-len("</li>")] + sub + "</li>"
            continue
        items.append(f"<li>{inline(m.group(3), base)}</li>")
        i += 1
    tag = "ol" if ordered else "ul"
    return f"<{tag}>" + "".join(items) + f"</{tag}>", i


def convert(md: str, base: Path) -> str:
    body: list[str] = []
    lines = md.splitlines()
    i = 0
    while i < len(lines):
        raw = lines[i]
        s = raw.strip()
        if not s:
            i += 1
            continue
        if s.startswith("```"):
            i += 1
            buf: list[str] = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            body.append("<pre><code>" + html.escape("\n".join(buf)) + "</code></pre>")
            continue
        if s.startswith("#"):
            level = len(s) - len(s.lstrip("#"))
            body.append(f"<h{level}>{inline(s[level:].strip(), base)}</h{level}>")
            i += 1
            continue
        if s.startswith(">"):
            buf = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                buf.append(inline(lines[i].strip()[1:].strip(), base))
                i += 1
            body.append("<blockquote>" + "<br>".join(buf) + "</blockquote>")
            continue
        if s.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:|-]+\|$", lines[i + 1].strip()):
            head = [c.strip() for c in s.strip("|").split("|")]
            rows: list[list[str]] = []
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            th = "".join(f"<th>{inline(c, base)}</th>" for c in head)
            trs = "".join("<tr>" + "".join(f"<td>{inline(c, base)}</td>" for c in r) + "</tr>"
                          for r in rows)
            body.append(f"<table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>")
            continue
        if LI_RE.match(raw):
            block, i = _list(lines, i, base)
            body.append(block)
            continue
        if set(s) <= {"-", "*"} and len(s) >= 3:
            body.append("<hr>")
            i += 1
            continue
        buf = []
        while i < len(lines) and lines[i].strip() and not re.match(
                r"^(#{1,6}\s|>|\||```)", lines[i]) and not LI_RE.match(lines[i]):
            buf.append(inline(lines[i].strip(), base))
            i += 1
        if buf:
            body.append("<p>" + "<br>".join(buf) + "</p>")

    # A caption is the emphasised paragraph that directly follows a figure.
    for idx in range(1, len(body)):
        if body[idx].startswith("<p><em>") and body[idx].endswith("</em></p>") \
                and 'class="figure"' in body[idx - 1]:
            body[idx] = body[idx].replace("<p>", '<p class="fig-caption">', 1)
    # A paragraph that is nothing but one display formula is a formula block.
    for idx, block in enumerate(body):
        if EQ_ONLY_RE.match(block):
            body[idx] = block.replace("<p>", '<p class="eq">', 1)
    # The closing date gets its own rule instead of a hanging paragraph.
    if body:
        m = DATE_RE.match(body[-1])
        if m:
            body[-1] = f'<p class="card-date">{m.group(1)}</p>'
    return "\n".join(body)


def page(md: str, base: Path, title: str) -> str:
    return (
        "<!DOCTYPE html>\n<html lang=\"zh-CN\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        f"<title>{html.escape(title)}</title>\n<style>{CSS}</style>\n</head>\n<body>\n<main>\n"
        + convert(md, base)
        + "\n</main>\n</body>\n</html>\n"
    )


def heading_title(md: str) -> str:
    m = re.search(r"^#\s+(.+)$", md, re.M)
    return re.sub(r"[*`]", "", m.group(1)).strip() if m else "错题卡"


def from_json(json_path: Path, root: Path, formula_mode: str) -> tuple[str, Path]:
    """Build the Markdown in memory, so one command produces a finished card."""
    import build_card

    q = build_card.load_json(json_path)
    q["figures"] = build_card.resolve_figures(q, root)
    md = build_card.build_markdown(q, root, root)
    if formula_mode != "latex" and build_card.has_math(md):
        renderer = build_card.FormulaRenderer(root)
        if not renderer.available:
            raise SystemExit(f"formula renderer unavailable: {renderer.error}")
        md, _ = build_card.render_markdown_math(md, renderer, root)
    return md, root


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Render card.md into a standalone printable HTML card.")
    ap.add_argument("source", type=Path, help="card.md, or text/question.json")
    ap.add_argument("--out", type=Path, help="default: <card dir>/card.html")
    ap.add_argument("--title", default="", help="browser title; default: the card's H1")
    ap.add_argument("--root", type=Path, help="root for relative image paths (default: card dir)")
    ap.add_argument("--formula-mode", choices=("both", "images", "latex"), default="both",
                    help="only used with a .json source")
    ap.add_argument("--allow-raw-math", action="store_true",
                    help="permit un-rendered $...$ (normally a build error)")
    args = ap.parse_args(argv)

    src = args.source
    if not src.exists():
        print(f"not found: {src}", file=sys.stderr)
        return 2

    if src.suffix.lower() == ".json":
        root = args.root or (src.parent.parent if src.parent.name.lower() == "text" else src.parent)
        md, base = from_json(src, root, args.formula_mode)
        out = args.out or (root / "card.html")
    else:
        root = args.root or src.parent
        md = src.read_text(encoding="utf-8-sig")
        base = root
        out = args.out or src.with_suffix(".html")

    if not args.allow_raw_math and RAW_MATH_RE.search(md):
        snippet = RAW_MATH_RE.search(md).group(0)
        print(f"raw LaTeX left in the card ({snippet}); rebuild card.md with "
              f"--formula-mode both|images, or pass --allow-raw-math", file=sys.stderr)
        return 3

    title = args.title or heading_title(md)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page(md, base, title), encoding="utf-8")
    html_text = out.read_text(encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size} bytes, "
          f"{html_text.count('data:image')} inlined images, "
          f"{'dated' if 'card-date' in html_text else 'no date'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
