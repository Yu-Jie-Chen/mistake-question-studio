# -*- coding: utf-8 -*-
"""One entry point for the whole pipeline, so a fresh session never re-explores.

    python run.py new    page.png --id 20261105-math-solid-geometry-004 \\
                         --subject mathematics --grade 高中二年级
    python run.py status work/20261105-math-solid-geometry-004
    python run.py finish work/20261105-math-solid-geometry-004

``new``    = intake.py (folder, source copy, hash, contact sheet, stubs)
``status`` = where am I, what is stale, what is next
``finish`` = preflight.py -> build_card.py -> validate_package.py -> report

The scripts are invoked as child processes with an explicit UTF-8 decode, so
Chinese paths and messages never turn into mojibake in the report.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

try:  # never die on a console that cannot encode a path
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")
except Exception:
    pass


def disp(p) -> str:
    """ASCII-safe display of a path (Windows consoles are often GBK)."""
    s = str(p).replace("\\", "/")
    return s if s.isascii() else s.encode("ascii", "replace").decode("ascii")


def _run(script, args, quiet=False):
    cmd = [sys.executable, str(HERE / script)] + [str(a) for a in args]
    env = dict(**__import__("os").environ, PYTHONIOENCODING="utf-8")
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env,
                          encoding="utf-8", errors="replace")
    if not quiet:
        out = (proc.stdout or "").rstrip()
        err = (proc.stderr or "").rstrip()
        if out:
            print(out)
        if err:
            print(err, file=sys.stderr)
    return proc.returncode, (proc.stdout or ""), (proc.stderr or "")


def _load(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def status(wd: Path) -> int:
    wd = wd.resolve()
    if not wd.is_dir():
        print(f"ERROR not a folder: {disp(wd)}", file=sys.stderr)
        return 2
    rows = []

    def row(label, path, optional=False):
        p = wd / path
        ok = p.exists()
        mark = "OK " if ok else ("-- " if optional else "MISSING")
        size = f"{p.stat().st_size}B" if ok else ""
        rows.append((mark, label, path, size))
        return ok, p

    row("source image", "source/original.png")
    row("contact sheet", "source/contact.png", optional=True)
    ok_q, qp = row("question json", "text/question.json")
    row("card", "card.md")
    row("review", "review.md")
    row("manifest", "manifest.json")
    figs = sorted(p.name for p in (wd / "figures").glob("fig-*.png")) if (wd / "figures").is_dir() else []
    for name in figs:
        row("figure", f"figures/{name}")

    width = max(len(r[1]) for r in rows) + 2
    print(f"WORKDIR {disp(wd)}")
    for mark, label, path, size in rows:
        print(f"  {mark:8} {label:<{width}} {path}  {size}".rstrip())

    notes = []
    if ok_q:
        q = _load(qp) or {}
        stem = str((q.get("question") or {}).get("stem_md") or "").strip()
        notes.append(f"stem: {'filled' if stem else 'EMPTY'} ({len(stem)} chars)")
        notes.append(f"figures declared: {len(q.get('figures') or [])}")
        notes.append(f"answer: {'filled' if str((q.get('answer') or {}).get('final_md') or '').strip() else 'EMPTY'}")
        notes.append(f"review.status: {(q.get('review') or {}).get('status')}")
        card = wd / "card.md"
        if card.exists() and card.stat().st_mtime < qp.stat().st_mtime:
            notes.append("card.md is OLDER than question.json -> rebuild (run.py finish)")
        for f in (q.get("figures") or []):
            p = wd / str(f.get("path") or "")
            if f.get("path") and not p.exists():
                notes.append(f"figure missing on disk: {f.get('path')}")
    if notes:
        print("  " + " | ".join(notes))

    # Stop signal: the card is already built and up to date -> deliver it and end the
    # session instead of re-entering the folder (each extra round re-bills the history).
    card = wd / "card.md"
    stale = bool(card.exists() and ok_q and qp.exists()
                 and card.stat().st_mtime < qp.stat().st_mtime)
    if card.exists() and not stale:
        print("STOP: card built — deliver it, do not re-enter")

    print("NEXT")
    if not (wd / "text" / "question.json").exists():
        print("  - intake missing: python run.py new <source> --id ... --subject ...")
    elif not str((( _load(wd / "text/question.json") or {}).get("answer") or {}).get("final_md") or "").strip():
        print("  - fill text/question.json (stem -> analysis -> answer -> diagnosis)")
    elif not (wd / "card.md").exists():
        print("  - python run.py finish " + disp(wd))
    else:
        print("  - check card.md against the source, then finish review.md and present the card")
    return 0


def _pick(out: str, *prefixes) -> list:
    """Keep only the informative lines of a child's report."""
    keep = []
    for line in out.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith(prefixes) or "NOT PLANAR" in s:
            keep.append(s)
    return keep


def _one_line(out: str, *prefixes) -> str:
    """Collapse a renderer report into a single line (paths and OK-planarity dropped)."""
    parts = []
    for raw in out.splitlines():
        s = " ".join(raw.split())
        if not s:
            continue
        if s.startswith("PNG "):
            bits = s.split()
            parts.append(f"PNG {Path(bits[1]).name} {bits[2]}" if len(bits) > 2 else s)
            continue
        if s.startswith(("SVG", "CMP")):
            continue
        if s.startswith("planar") and "OK" in s:
            continue
        if s.startswith(prefixes):
            parts.append(s)
    return " | ".join(parts)


def finish(wd: Path, formula_mode="latex", strict=False, docx=None, verbose=False) -> int:
    """preflight + build + validate, then a 2-3 line report.

    Quiet by default: the card session should see one summary line, one STOP and one
    NEXT line, because every line of output is re-billed on every later request.
    ``--verbose`` restores the full child output.
    """
    wd = wd.resolve()
    qjson = wd / "text" / "question.json"
    if not qjson.exists():
        print(f"ERROR missing {disp(qjson)}", file=sys.stderr)
        return 2

    code, out, err = _run("preflight.py", [qjson] + (["--strict"] if strict else []), quiet=True)
    if code != 0:
        print(out.rstrip())
        print(err.rstrip(), file=sys.stderr)
        print("finish: blocked by preflight (nothing was written)")
        return code

    code, out2, err2 = _run("build_card.py", [qjson, "--out", wd / "card.md",
                                              "--question-out", wd / "text" / "question.md",
                                              "--formula-mode", formula_mode], quiet=True)
    if code != 0:
        print(out2.rstrip())
        print(err2.rstrip(), file=sys.stderr)
        print("finish: build failed")
        return code

    code, out3, err3 = _run("validate_package.py", [qjson, "--root", wd], quiet=True)
    if code != 0:
        print(out3.rstrip())
        print(err3.rstrip(), file=sys.stderr)
        print("finish: validate failed")
        return code

    if verbose:
        print(out.rstrip())
        print(out2.rstrip())
        print(out3.rstrip())

    warn_lines = [ln for ln in out.splitlines() if ln.strip().startswith("WARN")]
    pre = [ln for ln in out.splitlines() if ln.strip().startswith("preflight:")]
    val = [ln for ln in out3.splitlines() if "error(s)" in ln]
    summary = " | ".join([
        pre[-1].strip() if pre else "preflight ok",
        "build ok",
        val[-1].strip() if val else "validate ok",
    ])
    print(summary)
    for ln in warn_lines:
        print(ln.strip())

    if docx:
        print("== docx (explicit opt-in) ==")
        _run("build_card.py", [qjson, "--out", wd / "card.md", "--docx", docx,
                               "--formula-mode", "both"])
    return brief(wd)


def brief(wd: Path) -> int:
    """Two lines: is the card ready to hand over, and what is left."""
    wd = wd.resolve()
    card, qjson = wd / "card.md", wd / "text" / "question.json"
    stale = bool(card.exists() and qjson.exists()
                 and card.stat().st_mtime < qjson.stat().st_mtime)
    if card.exists() and not stale:
        print("STOP: card built — deliver it, do not re-enter")
        print("NEXT: check card.md against the source, finish review.md, present")
    elif card.exists() and stale:
        print("NEXT: card.md is older than question.json -> re-run finish")
    elif not qjson.exists():
        print("NEXT: run.py new <source> --id ... --subject ...")
    else:
        print("NEXT: fill text/question.json, then run.py finish " + disp(wd))
    return 0


def render(wd: Path, spec: Path = None, spec_json: str = None, fig="fig-1") -> int:
    """Write the figure spec, render PNG+SVG, build the compare sheet — one call.

    The engine is picked from the spec: a spec with ``vertices`` + ``faces`` goes to
    draw_solid.py (3D), anything else to draw_scene.py (flat).
    """
    wd = wd.resolve()
    fig_dir = wd / "figures"
    sp = Path(spec) if spec else fig_dir / f"{fig}.spec.json"
    if spec_json:
        raw = str(spec_json).strip()
        if raw.startswith("@"):                      # @file works on every shell
            raw = Path(raw[1:]).read_text(encoding="utf-8-sig")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            print(f"ERROR inline spec JSON is invalid ({exc}). Windows shells strip the "
                  "double quotes from a native command line — write the spec to a file and "
                  "pass --spec <file>, or use --spec-json @spec.json", file=sys.stderr)
            return 2
        sp.parent.mkdir(parents=True, exist_ok=True)
        sp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not sp.exists():
        print(f"ERROR spec not found: {disp(sp)}", file=sys.stderr)
        return 2
    data = json.loads(sp.read_text(encoding="utf-8-sig"))
    engine = "draw_solid.py" if ("vertices" in data and "faces" in data) else "draw_scene.py"

    out_png = fig_dir / f"{fig}.png"
    out_svg = fig_dir / f"{fig}.svg"
    args = [sp, "--out", out_png, "--svg", out_svg]
    before = fig_dir / f"{fig}.before.png"
    cmp_path = fig_dir / f"compare-{fig}.png"
    if before.exists():
        args += ["--before", before, "--compare", cmp_path]

    code, out, err = _run(engine, args, quiet=True)
    if code != 0:
        print(out.rstrip())
        print(err.rstrip(), file=sys.stderr)
        print(f"render: {engine} failed")
        return code

    tag = "solid" if engine.startswith("draw_solid") else "flat"
    detail = _one_line(out, "PNG", "visible faces", "hidden edges", "sphere", "planar", "WARN")
    print(f"fig {fig}: {tag} | {detail}" + (" | compare ok" if cmp_path.exists() and before.exists() else ""))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Mistake-question pipeline runner.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_new = sub.add_parser("new", help="intake a source image")
    p_new.add_argument("source", type=Path)
    p_new.add_argument("--id", required=True)
    p_new.add_argument("--subject", required=True)
    p_new.add_argument("--grade", default="")
    p_new.add_argument("--work", type=Path, default=Path("work"))
    p_new.add_argument("--note", default="")
    p_new.add_argument("--tiles", type=int, default=4)
    p_new.add_argument("--box", action="append", default=[])

    p_st = sub.add_parser("status", help="full state table")
    p_st.add_argument("workdir", type=Path)

    p_fin = sub.add_parser("finish", help="preflight + build + validate (quiet)")
    p_fin.add_argument("workdir", type=Path)
    p_fin.add_argument("--formula-mode", choices=("latex", "images", "both"), default="latex")
    p_fin.add_argument("--strict", action="store_true")
    p_fin.add_argument("--docx", type=Path, help="explicit opt-in Word export")
    p_fin.add_argument("--verbose", action="store_true", help="print the child output in full")

    p_re = sub.add_parser("render", help="spec -> PNG + SVG + compare (engine auto-picked)")
    p_re.add_argument("workdir", type=Path)
    p_re.add_argument("--spec", type=Path, help="default <workdir>/figures/fig-1.spec.json")
    p_re.add_argument("--spec-json", help="inline spec JSON (written to --spec first)")
    p_re.add_argument("--fig", default="fig-1")

    args = ap.parse_args(argv)
    if args.cmd == "new":
        code, _, _ = _run("intake.py", [args.source, "--id", args.id, "--subject", args.subject,
                                        "--grade", args.grade, "--work", args.work,
                                        "--note", args.note, "--tiles", args.tiles]
                          + sum([["--box", b] for b in args.box], []))
        return code
    if args.cmd == "status":
        return status(args.workdir)
    if args.cmd == "render":
        return render(args.workdir, spec=args.spec, spec_json=args.spec_json, fig=args.fig)
    return finish(args.workdir, formula_mode=args.formula_mode, strict=args.strict,
                  docx=args.docx, verbose=args.verbose)


if __name__ == "__main__":
    raise SystemExit(main())
