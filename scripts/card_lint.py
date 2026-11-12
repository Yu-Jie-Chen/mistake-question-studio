# -*- coding: utf-8 -*-
"""Every formula trap and every card inconsistency, in one call.

Why this exists
---------------
Building nine cards once took eight rebuild rounds, and seven of them were the
same two mistakes: CJK characters inside ``$...$`` (mathtext draws a missing
glyph) and ``\\le`` / ``\\ge`` (mathtext has only ``\\leq`` / ``\\geq``). Each
round was one ``run.py finish``, one failure, one edit, one retry -- hundreds of
seconds spent to learn one character at a time.

``build_card.FormulaRenderer.render`` swallows the parser exception and returns
``None``, so the builder degrades quietly until the HTML step refuses to ship
raw LaTeX. This script asks mathtext directly and reports **all** failures at
once, for **all** cards at once, before anything is rebuilt.

It runs standalone (no ``finish``, no HTML step) so it can be used the moment a
``question.json`` exists, and it also checks the built card for the things that
only show up afterwards: raw ``$`` that survived the build, image references
that point nowhere, missing sections, a ``card.md`` older than its source.

CLI
---
    python card_lint.py work/20261112-physics-sensor-graph-007
    python card_lint.py work/                 # whole batch: one call, all cards
    python card_lint.py work/ --strict        # warnings become errors
    python card_lint.py work/ --no-render     # skip the mathtext probe (no matplotlib)
    python card_lint.py --math "\le 5" --math "速度 $v$ 的方向"   # while drafting

Exit codes: 0 clean, 1 findings, 2 usage/IO.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REQUIRED_SECTIONS = ("题目", "答案", "解析", "错因诊断", "知识点", "变式")
MD_HINT = ("stem_md", "instruction_md", "final_md", "alternate_md", "verification_md",
           "steps_md", "student_answer_md", "root_cause_md", "remedy_md", "variant_md",
           "caption")

# CJK ideographs, CJK punctuation, fullwidth forms: mathtext has no glyphs for
# these, so they render as a box and the formula is silently wrong.
CJK_RE = re.compile(r"[\u2e80-\u9fff\uf900-\ufaff\uff00-\uffef\u3000-\u303f]")

# Commands mathtext does not implement. The render probe catches the rest;
# these get a message that says what to write instead.
BAD_CMDS = [
    # (regex, how it was written, what mathtext accepts instead)
    (r"\\le(?![a-zA-Z])", r"\le", r"write \leq"),
    (r"\\ge(?![a-zA-Z])", r"\ge", r"write \geq"),
    (r"\\lt(?![a-zA-Z])", r"\lt", "write < directly"),
    (r"\\gt(?![a-zA-Z])", r"\gt", "write > directly"),
    (r"\\begin\{", r"\begin{...}", "environments are not supported; write the formula by hand"),
    (r"\\end\{", r"\end{...}", "environments are not supported"),
    (r"\\ce\{", r"\ce{...}", "mhchem is absent; plain mathtext has no chemistry"),
    (r"\\SI\{", r"\SI{...}", "siunitx is absent; write the number and unit as text"),
    (r"\\qty\{", r"\qty{...}", "siunitx is absent; write the digits plainly"),
    (r"\\boxed\{", r"\boxed{...}", "not supported; drop the box"),
    (r"\\overset\{", r"\overset{...}", "not supported; use a superscript"),
    (r"\\underset\{", r"\underset{...}", "not supported; use a subscript"),
    (r"\\substack\{", r"\substack{...}", "not supported; split the formula"),
    (r"\\color\{", r"\color{...}", "colors are not supported"),
    (r"\\textcolor\{", r"\textcolor{...}", "colors are not supported"),
    (r"\\bm\{", r"\bm{...}", r"bold-math is \mathbf"),
    (r"\\tag\{", r"\tag{...}", "amsmath numbering is not supported"),
    (r"\\label\{", r"\label{...}", "amsmath labels are not supported"),
    (r"\\ref\{", r"\ref{...}", "amsmath references are not supported"),
    (r"\\nonumber", r"\nonumber", "amsmath macro"),
    (r"\\hline", r"\hline", "table rule"),
    (r"\\degree", r"\degree", r"write ^\circ"),
]

DOLLAR_RE = re.compile(r"(?<!\\)\$")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def walk_strings(obj, path=""):
    if isinstance(obj, str):
        yield path, obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk_strings(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk_strings(v, f"{path}[{i}]")


def split_math(text: str):
    """(is_math, chunk) pairs using the builder's own splitter when available."""
    try:
        from build_card import split_math as _split  # same directory in practice
        return [(kind != "text", value) for kind, value in _split(text)]
    except Exception:
        out, pos = [], 0
        for m in re.finditer(r"\$\$(.+?)\$\$|\$(.+?)\$", text, re.S):
            if m.start() > pos:
                out.append((False, text[pos:m.start()]))
            out.append((True, m.group(1) if m.group(1) is not None else m.group(2)))
            pos = m.end()
        if pos < len(text):
            out.append((False, text[pos:]))
        return out


def formulas_in(text: str):
    """Every math chunk in a markdown string, unescaped and stripped."""
    return [chunk.strip() for is_math, chunk in split_math(text) if is_math and chunk.strip()]


def _clean_latex(latex: str) -> str:
    try:
        from build_card import FormulaRenderer
        return FormulaRenderer.clean_latex(latex)
    except Exception:
        return latex.replace(r"\dfrac", r"\frac")


class RenderProbe:
    """Ask mathtext to draw each unique formula; collect the failures.

    This is the same code path the builder uses, so a pass here is a pass
    there. Rendering goes to a temp directory: a lint run must not leave
    ``formulas/`` looking like the card was built.
    """

    def __init__(self, enabled: bool):
        self.enabled = enabled
        self.dir = None
        self.cache: dict[str, str] = {}
        self.reason = ""
        if not enabled:
            return
        try:
            import tempfile
            import matplotlib
            matplotlib.use("Agg")
            matplotlib.rcParams["mathtext.fontset"] = "stix"
            import logging
            logging.getLogger("matplotlib").setLevel(logging.ERROR)
            from matplotlib import mathtext  # noqa: F401
            self._tmp = tempfile.TemporaryDirectory(prefix="card-lint-")
            self.dir = Path(self._tmp.name)
        except Exception as exc:
            self.enabled = False
            self.reason = str(exc)

    def check(self, latex: str) -> str:
        """'' when it renders, else the parser's complaint."""
        if not self.enabled:
            return ""
        if latex in self.cache:
            return self.cache[latex]
        message = ""
        try:
            from matplotlib import mathtext
            from matplotlib.font_manager import FontProperties
            out = self.dir / "probe.png"
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")   # missing-glyph chatter is our finding
                mathtext.math_to_image(f"${_clean_latex(latex)}$", str(out), dpi=80,
                                       format="png", prop=FontProperties(size=10))
            out.unlink(missing_ok=True)
        except Exception as exc:
            message = str(exc).strip().splitlines()[0][:160]
        self.cache[latex] = message
        return message


# ---------------------------------------------------------------------------
# checks
# ---------------------------------------------------------------------------

def lint_math(latex: str, where: str, probe: RenderProbe):
    """All the ways one formula can waste a rebuild."""
    errors, warnings = [], []
    if CJK_RE.search(latex):
        bad = "".join(sorted({c for c in latex if CJK_RE.match(c)}))[:8]
        errors.append(f"{where}: CJK/fullwidth {bad!r} inside $...$ will render as "
                      "a missing glyph; move the words outside the math")
    for pattern, written, advice in BAD_CMDS:
        if re.search(pattern, latex):
            errors.append(f"{where}: {written} is not mathtext -> {advice}")
    if "\\\\" in latex:
        errors.append(f"{where}: a line break '\\\\' inside $...$ is not supported")
    if latex.count("$"):
        errors.append(f"{where}: nested '$' inside $...$")
    if re.fullmatch(r"[\s,;:]*", latex):
        warnings.append(f"{where}: empty $...$")
    message = probe.check(latex)
    if message and not errors:
        errors.append(f"{where}: mathtext cannot render it -> {message}")
    return errors, warnings


def check_question_json(qjson: Path, probe: RenderProbe):
    import json
    errors, warnings = [], []
    try:
        q = json.loads(qjson.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return [f"invalid JSON -> {exc}"], warnings, None

    root = qjson.parent.parent if qjson.parent.name == "text" else qjson.parent
    seen = set()
    for path, text in walk_strings(q):
        key = path.split(".")[-1].split("[")[0]
        if key not in MD_HINT:
            continue
        n = len(DOLLAR_RE.findall(text))
        if n % 2:
            errors.append(f"{path}: {n} unescaped '$' - odd count, the pair never closes")
        for latex in formulas_in(text):
            if latex in seen:
                continue
            seen.add(latex)
            e, w = lint_math(latex, f"{path} ${latex[:40]}$", probe)
            errors.extend(e)
            warnings.extend(w)

    # declared figures must exist, or the card ships a broken image
    for f in q.get("figures") or []:
        if not isinstance(f, dict):
            continue
        for key in ("path", "before_path"):
            raw = f.get(key)
            if raw and not (root / raw).exists():
                errors.append(f"figures[{f.get('id')}].{key}: {raw} does not exist")
    return errors, warnings, q


def check_card_md(card: Path, qjson: Path, probe: RenderProbe):
    errors, warnings = [], []
    text = card.read_text(encoding="utf-8")
    root = card.parent

    # The formula gate: a raw '$' in the shipped card means the build degraded.
    body = re.sub(r"```.*?```", "", text, flags=re.S)
    if DOLLAR_RE.search(body):
        for line in body.splitlines():
            if DOLLAR_RE.search(line):
                errors.append(f"card.md: raw '$' survived the build -> {line.strip()[:60]!r}")
                break

    # image references must resolve (figures and formulas both live here)
    for m in re.finditer(r"!\[[^\]]*\]\(([^)\s]+)", text):
        target = m.group(1)
        if target.startswith(("http://", "https://", "data:")):
            continue
        if not (root / target).exists():
            errors.append(f"card.md: image {target!r} does not exist")

    heads = "\n".join(re.findall(r"^#{1,6}\s*(.+)$", text, re.M))
    for name in REQUIRED_SECTIONS:
        if name not in heads:
            errors.append(f"card.md: missing section '## {name}'")
    if not re.search(r"^\s*\d{4}-\d{2}-\d{2}\s*$", text, re.M):
        warnings.append("card.md: no bare date line at the end (the 日期 field)")

    if qjson and qjson.exists() and card.stat().st_mtime < qjson.stat().st_mtime - 1:
        warnings.append("card.md is older than text/question.json - rerun run.py finish")

    html = card.with_suffix(".html")
    if html.exists():
        head = html.read_text(encoding="utf-8", errors="replace")
        if not re.search(r'src="data:', head):
            warnings.append("card.html: no inlined image found (not self-contained)")
        if re.search(r"\$\$?[^$\n]{2,60}\$\$?", head):
            warnings.append("card.html: a raw $...$ string is still visible in the markup")
    return errors, warnings


def find_qjson(wd: Path):
    """text/question.json first (the normal layout), then a root question.json."""
    for cand in (wd / "text" / "question.json", wd / "question.json"):
        if cand.exists():
            return cand
    return None


def check_work_dir(wd: Path, probe: RenderProbe):
    qjson = find_qjson(wd)
    if qjson is None:
        return [f"{wd.name}: no text/question.json"], []
    errors, warnings, _q = check_question_json(qjson, probe)
    card = wd / "card.md"
    if card.exists():
        e, w = check_card_md(card, qjson, probe)
        errors.extend(e)
        warnings.extend(w)
    return errors, warnings


def _work_dirs(target: Path):
    """Every folder under target that holds text/question.json (skips dot dirs)."""
    if find_qjson(target) is not None:
        return [target]
    found = []
    if target.is_dir():
        for child in sorted(target.iterdir()):
            if child.is_dir() and not child.name.startswith((".", "_")):
                if find_qjson(child) is not None:
                    found.append(child)
    return found


def main(argv=None):
    ap = argparse.ArgumentParser(description="Formula and card consistency lint.")
    ap.add_argument("target", nargs="?", type=Path,
                    help="a work folder, a question.json, or a folder of cards")
    ap.add_argument("--math", action="append", default=[], metavar="LATEX",
                    help="lint one formula string right now (repeatable)")
    ap.add_argument("--strict", action="store_true", help="warnings become errors")
    ap.add_argument("--no-render", action="store_true", help="skip the mathtext probe")
    ap.add_argument("--quiet", action="store_true", help="summary line only")
    ap.add_argument("--max-items", type=int, default=30, help="cap printed findings")
    args = ap.parse_args(argv)

    try:
        sys.stdout.reconfigure(errors="replace")
        sys.stderr.reconfigure(errors="replace")
    except Exception:
        pass

    probe = RenderProbe(not args.no_render)
    if not args.quiet and probe.enabled:
        print("lint  mathtext probe active (matplotlib)")
    elif not args.quiet and probe.reason:
        print(f"lint  mathtext probe OFF ({probe.reason[:60]}); static checks only")

    if args.math:
        errors, warnings = [], []
        for i, raw in enumerate(args.math, start=1):
            text = raw.strip()
            where = f"--math[{i}]"
            if "$" in text:
                n = len(DOLLAR_RE.findall(text))
                if n % 2:
                    errors.append(f"{where}: {n} unescaped '$' - the pair never closes")
                for latex in formulas_in(text):
                    e, w = lint_math(latex, f"{where} ${latex[:40]}$", probe)
                    errors.extend(e)
                    warnings.extend(w)
            else:
                e, w = lint_math(text.strip("$").strip(), where, probe)
                errors.extend(e)
                warnings.extend(w)
        for e in errors:
            print("ERROR " + e)
        for w in warnings:
            print("WARN  " + w)
        print(f"card_lint: {len(args.math)} formula(s), {len(errors)} error(s), {len(warnings)} warning(s)")
        return 1 if errors else 0

    if args.target is None:
        ap.error("give a target folder, or --math LATEX")
    target = args.target
    if not target.exists():
        print(f"ERROR not found: {target}", file=sys.stderr)
        return 2

    if target.is_file():
        dirs = [target.parent.parent if target.parent.name == "text" else target.parent]
        qfile = target
    else:
        dirs = _work_dirs(target)
        qfile = None
    if not dirs and qfile is None:
        print(f"ERROR no text/question.json under {target}", file=sys.stderr)
        return 2

    total_e = total_w = 0
    printed = 0
    batch = len(dirs) > 1
    for wd in dirs:
        if qfile is not None:
            errors, warnings, _q = check_question_json(qfile, probe)
            card = wd / "card.md"
            if card.exists():
                e, w = check_card_md(card, qfile, probe)
                errors.extend(e)
                warnings.extend(w)
        else:
            errors, warnings = check_work_dir(wd, probe)
        total_e += len(errors)
        total_w += len(warnings)
        if args.strict:
            errors = errors + [f"(strict) {w}" for w in warnings]
            warnings = []
        if batch:
            mark = "ERR " if errors else ("WARN" if warnings else "OK  ")
            print(f"{mark} {wd.name:<44} {len(errors)} error {len(warnings)} warn")
        if not args.quiet:
            for e in errors:
                if printed >= args.max_items:
                    print("... more findings suppressed (--max-items)")
                    printed = args.max_items + 1
                    break
                print(("      " if batch else "") + "ERROR " + e)
                printed += 1
            for w in warnings:
                if printed > args.max_items:
                    break
                print(("      " if batch else "") + "WARN  " + w)
                printed += 1

    print(f"card_lint: {len(dirs)} card(s), {total_e} error(s), {total_w} warning(s)")
    return 1 if total_e else 0


if __name__ == "__main__":
    raise SystemExit(main())
