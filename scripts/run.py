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


def finish(wd: Path, formula_mode="latex", strict=False, docx=None) -> int:
    wd = wd.resolve()
    qjson = wd / "text" / "question.json"
    if not qjson.exists():
        print(f"ERROR missing {disp(qjson)}", file=sys.stderr)
        return 2

    print("== preflight ==")
    code, out, _ = _run("preflight.py", [qjson] + (["--strict"] if strict else []))
    if code != 0:
        print("stop: fix the errors above, then re-run finish")
        return code

    print("== build ==")
    code, _, err = _run("build_card.py", [qjson, "--out", wd / "card.md",
                                         "--question-out", wd / "text" / "question.md",
                                         "--formula-mode", formula_mode])
    if code != 0:
        return code

    print("== validate ==")
    code, _, _ = _run("validate_package.py", [qjson, "--root", wd])
    if code != 0:
        return code

    if docx:
        print("== docx (explicit opt-in) ==")
        _run("build_card.py", [qjson, "--out", wd / "card.md", "--docx", docx,
                               "--formula-mode", "both"])
    return status(wd)


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

    p_st = sub.add_parser("status", help="where am I")
    p_st.add_argument("workdir", type=Path)

    p_fin = sub.add_parser("finish", help="preflight + build + validate")
    p_fin.add_argument("workdir", type=Path)
    p_fin.add_argument("--formula-mode", choices=("latex", "images", "both"), default="latex")
    p_fin.add_argument("--strict", action="store_true")
    p_fin.add_argument("--docx", type=Path, help="explicit opt-in Word export")

    args = ap.parse_args(argv)
    if args.cmd == "new":
        code, _, _ = _run("intake.py", [args.source, "--id", args.id, "--subject", args.subject,
                                        "--grade", args.grade, "--work", args.work,
                                        "--note", args.note, "--tiles", args.tiles]
                          + sum([["--box", b] for b in args.box], []))
        return code
    if args.cmd == "status":
        return status(args.workdir)
    return finish(args.workdir, formula_mode=args.formula_mode, strict=args.strict, docx=args.docx)


if __name__ == "__main__":
    raise SystemExit(main())
