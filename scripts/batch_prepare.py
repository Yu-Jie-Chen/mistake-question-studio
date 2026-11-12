# -*- coding: utf-8 -*-
"""Prepare N page photos so they can be read in a few bounded rounds.

Why this exists
---------------
A batch of six photos once cost 62 minutes, and 90% of that was *waiting for
the model*, not running tools. The cause was not the work: it was 21 hand-cut
zoom crops, each one read with its own ``read_image`` call and each one left
resident in the context for the rest of the session. Every later request
re-sent all of them, so a single step grew from 7 s to 37 s.

So the rule this script encodes is: **cut once, cut few, read in bounded
rounds, never re-crop.**

* one page -> an ink-gap segmentation into question blocks (no eyeballing);
* each block -> one crop, downscaled to ~1600 px so its cost is capped;
* all crops -> packed into rounds of at most ``--max-per-read`` images and
  ``--max-mpix`` megapixels, printed as an explicit read order;
* one ``overview.png`` (all pages as thumbnails) answers "what is where"
  in a single cheap image instead of one full read per page;
* a text digest (blocks, line counts, ink %) carries the rest, because text
  is re-billed far cheaper than an image.

CLI
---
    # 6 photos -> _inspect/, one call
    python batch_prepare.py src/*.png
    python batch_prepare.py src/ --pattern "*.jpg" --clean

    # wide page, two columns, tighter budget
    python batch_prepare.py src/p1.png --columns 2 --max-per-read 2 --max-mpix 2.0

Output
------
    _inspect/pages/p1.png            normalised page (EXIF-rotated, RGB)
    _inspect/crops/p1-q1.png         one question block per crop
    _inspect/overview.png            every page as a thumbnail, one image
    _inspect/plan.json               blocks, batches, pixel budget, options
    _inspect/plan.md                 the read order, copy-pasteable

Read the digest it prints, then read the images in the order given. Then
write ``text/question.json`` — do not go back for more crops.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageOps
except Exception:  # pragma: no cover
    Image = None

try:
    import numpy as np
except Exception:  # pragma: no cover
    np = None

try:  # keep the print alignment identical to intake.py
    from intake import contact_sheet, _ink_mask
except Exception:  # pragma: no cover
    contact_sheet = None
    _ink_mask = None

IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff")
CROP_MAX_SIDE = 1600          # vision inputs are usually capped near 1568 px
WIDE_ASPECT = 2.2


# ---------------------------------------------------------------------------
# segmentation
# ---------------------------------------------------------------------------

def _mask(im):
    """Ink mask: 255 = ink. Falls back to a fixed threshold without intake.py."""
    if _ink_mask is not None:
        return _ink_mask(im)[0]
    g = im.convert("L")
    hist = g.histogram()
    total, acc, bg = sum(hist), 0, 255
    for value in range(255, -1, -1):
        acc += hist[value]
        if acc >= total * 0.90:
            bg = value
            break
    thr = max(150, min(235, bg - 28))
    return g.point(lambda v: 255 if v < thr else 0)


def _runs(flags):
    """[(start, end)] of consecutive True values, end exclusive."""
    out, start = [], None
    for i, v in enumerate(flags):
        if v and start is None:
            start = i
        elif not v and start is not None:
            out.append((start, i))
            start = None
    if start is not None:
        out.append((start, len(flags)))
    return out


def _column_split(mask, min_gap_ratio=0.035):
    """Detect a real two-column layout; return [(x0, x1)] or [(0, w)]."""
    w, h = mask.size
    ink = np.asarray(mask) > 0
    if not ink.any():
        return [(0, w)]
    col_ink = ink.sum(axis=0)
    empty = col_ink <= max(1, int(h * 0.004))
    need = max(24, int(w * min_gap_ratio))
    best = None
    for x0, x1 in _runs(empty):
        if x1 - x0 < need:
            continue
        # a column gutter must sit in the middle and leave ink on both sides
        mid = (x0 + x1) / 2
        if not (0.30 * w < mid < 0.70 * w):
            continue
        left, right = ink[:, :x0], ink[:, x1:]
        if left.sum() < 0.02 * ink.size and right.sum() < 0.02 * ink.size:
            continue
        if (x1 - x0) > (best[1] - best[0] if best else -1):
            best = (x0, x1)
    if not best:
        return [(0, w)]
    return [(0, best[0]), (best[1], w)]


def _blocks(mask, columns, min_gap_px, min_h_px):
    """Question blocks inside each column: [(x0, y0, x1, y1, lines, ink_pct)]."""
    ink = np.asarray(mask) > 0
    out = []
    for x0, x1 in columns:
        sub = ink[:, x0:x1]
        if not sub.any():
            continue
        width = max(1, x1 - x0)
        row_ink = sub.sum(axis=1)
        has = row_ink > max(2, int(width * 0.004))
        # A hairline rule across the column is a separator, not a text row: let
        # it become part of the gap instead of gluing two questions together.
        ratio = row_ink / width
        for y0, y1 in _runs(ratio > 0.85):
            if y1 - y0 <= 5:
                has[y0:y1] = False
        runs = _runs(has)
        # A fixed gap in pixels splits one question in half as soon as the line
        # spacing drifts (a screenshot reflowed at another zoom, a photo taken
        # closer). Make the threshold adaptive: a real question boundary is a
        # gap several times the page's own median line gap.
        gaps = sorted(b[0] - a[1] for a, b in zip(runs, runs[1:]) if b[0] - a[1] > 0)
        median_gap = gaps[len(gaps) // 2] if gaps else 0
        merge_gap = max(min_gap_px, int(round(2.5 * median_gap)))
        # merge runs separated by less than merge_gap (line spacing / option rows)
        merged = []
        for r in runs:
            if merged and r[0] - merged[-1][1] < merge_gap:
                merged[-1] = (merged[-1][0], r[1])
            else:
                merged.append((r[0], r[1]))
        merged = [tuple(m) for m in merged]
        for y0, y1 in merged:
            if y1 - y0 < min_h_px:
                continue
            band = sub[y0:y1, :]
            ink_pct = 100.0 * band.sum() / max(1, band.size)
            lines = len(_runs(band.sum(axis=1) > max(2, int((x1 - x0) * 0.004))))
            # tight horizontal bounds so the crop does not carry a wide margin
            cols = band.any(axis=0)
            idx = np.flatnonzero(cols)
            bx0 = x0 + int(idx[0]) if idx.size else x0
            bx1 = x0 + int(idx[-1]) + 1 if idx.size else x1
            out.append((bx0, y0, bx1, y1, lines, ink_pct, int(merge_gap)))
    return out


def _merge_slivers(blocks, rel=0.30):
    """Fold fragments into their nearest neighbour instead of dropping them.

    Ink-gap segmentation always leaves a few slivers (a caption, one option row,
    the tail of an answer). Cutting them as separate images is the expensive
    mistake, so grow the nearest block to cover them: no content is lost and
    the number of images read goes down.
    """
    if len(blocks) < 3:
        return blocks, 0
    merged = list(blocks)
    folded = 0
    for _ in range(len(blocks)):
        heights = sorted(b[3] - b[1] for b in merged)
        floor = heights[len(heights) // 2] * rel
        idx = next((i for i, b in enumerate(merged) if (b[3] - b[1]) < floor), None)
        if idx is None or len(merged) == 1:
            break
        cur = merged[idx]

        def gap(j):
            o = merged[j]
            return min(abs(cur[1] - o[3]), abs(o[1] - cur[3]))

        cands = [j for j in (idx - 1, idx + 1) if 0 <= j < len(merged)]
        if not cands:
            break
        j = min(cands, key=gap)
        a, b = merged[idx], merged[j]
        merged[j] = (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]),
                     a[4] + b[4], max(a[5], b[5]), max(a[6], b[6]))
        del merged[idx]
        folded += 1
    return merged, folded


# ---------------------------------------------------------------------------
# packing
# ---------------------------------------------------------------------------

def _pack(items, max_files, max_mpix):
    """Greedy rounds: bounded by image count *and* by total megapixels."""
    rounds, cur, cur_mpix = [], [], 0.0
    for it in items:
        mpix = it["width"] * it["height"] / 1e6
        if cur and (len(cur) >= max_files or cur_mpix + mpix > max_mpix):
            rounds.append(cur)
            cur, cur_mpix = [], 0.0
        cur.append(it)
        cur_mpix += mpix
    if cur:
        rounds.append(cur)
    return rounds


def _fit_crop(im, max_side):
    w, h = im.size
    if max(w, h) <= max_side:
        return im
    s = max_side / max(w, h)
    return im.resize((max(1, int(round(w * s))), max(1, int(round(h * s)))), Image.LANCZOS)


def _overview(images, out: Path, thumb_h=430, pad=12):
    """Every page as a thumbnail, left to right, one image to read."""
    thumbs = []
    for label, im in images:
        s = thumb_h / im.height
        thumbs.append((label, im.resize((max(1, int(im.width * s)), thumb_h), Image.LANCZOS)))
    width = sum(t.width for _, t in thumbs) + pad * (len(thumbs) + 1)
    head = 24
    canvas = Image.new("RGB", (width, thumb_h + head + 2 * pad), "white")
    d = ImageDraw.Draw(canvas)
    font = None
    try:
        from draw_solid import _font
        font = _font(18)
    except Exception:
        pass
    x = pad
    for label, t in thumbs:
        if font:
            d.text((x, pad), label, font=font, fill=(110, 110, 110))
        canvas.paste(t, (x, pad + head))
        d.rectangle([x, pad + head, x + t.width, pad + head + t.height], outline=(205, 205, 205))
        x += t.width + pad
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, "PNG")
    return canvas.size


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def collect(sources, pattern):
    files = []
    for src in sources:
        if src.is_dir():
            files.extend(sorted(p for p in src.glob(pattern) if p.suffix.lower() in IMAGE_SUFFIXES))
        elif src.exists():
            files.append(src)
        else:
            print(f"WARN not found: {src}", file=sys.stderr)
    seen, out = set(), []
    for f in files:
        key = str(f.resolve()).lower()
        if key not in seen:
            seen.add(key)
            out.append(f)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Cut pages into question blocks and plan the reads.")
    ap.add_argument("sources", nargs="+", type=Path, help="page images, or a folder")
    ap.add_argument("--pattern", default="*", help="glob used when a source is a folder")
    ap.add_argument("--out", type=Path, default=Path("_inspect"), help="output folder (default: ./_inspect)")
    ap.add_argument("--split", choices=("auto", "bands", "page"), default="auto",
                    help="auto = whole page when it already fits, bands only for big images")
    ap.add_argument("--columns", choices=("auto", "1", "2"), default="auto")
    ap.add_argument("--min-gap", type=float, default=0.012,
                    help="gap that separates two questions, as a fraction of page height")
    ap.add_argument("--min-block", type=float, default=0.010,
                    help="smallest block kept, as a fraction of page height")
    ap.add_argument("--max-side", type=int, default=CROP_MAX_SIDE, help="crop long side in px")
    ap.add_argument("--max-per-read", type=int, default=3, help="images per read_image round")
    ap.add_argument("--max-mpix", type=float, default=4.0, help="megapixels per reading round")
    ap.add_argument("--no-overview", action="store_true", help="skip the all-page thumbnail")
    ap.add_argument("--clean", action="store_true", help="delete the output folder first (use every batch)")
    ap.add_argument("--max-print", type=int, default=48, help="cap printed block lines")
    args = ap.parse_args(argv)

    try:
        sys.stdout.reconfigure(errors="replace")
        sys.stderr.reconfigure(errors="replace")
    except Exception:
        pass

    if Image is None:
        print("ERROR pillow is required: pip install pillow", file=sys.stderr)
        return 2
    if np is None:
        print("ERROR numpy is required: pip install numpy", file=sys.stderr)
        return 2

    files = collect([Path(s) for s in args.sources], args.pattern)
    if not files:
        print("ERROR no input images", file=sys.stderr)
        return 2
    for f in files:
        if f.suffix.lower() == ".pdf":
            print("ERROR PDFs go through prepare_scan.py first", file=sys.stderr)
            return 2

    out = args.out
    if args.clean and out.exists():
        import shutil
        shutil.rmtree(out)
    (out / "pages").mkdir(parents=True, exist_ok=True)
    (out / "crops").mkdir(parents=True, exist_ok=True)

    pages, items, thumbs, notes, warns = [], [], [], [], []
    for n, src in enumerate(files, start=1):
        stem = f"p{n}"
        try:
            im = Image.open(src)
            im.load()
            im = ImageOps.exif_transpose(im).convert("RGB")
        except Exception as exc:
            print(f"WARN skip {src.name}: {exc}", file=sys.stderr)
            continue
        page_path = out / "pages" / f"{stem}.png"
        im.save(page_path, "PNG")
        thumbs.append((stem.upper(), im))

        w, h = im.size
        page_blocks = []
        pad = max(4, int(min(w, h) * 0.006))

        def add(entry):
            page_blocks.append(entry)
            items.append(entry)

        # Cutting is a *zoom* strategy, not a default. A page whose long side
        # already fits the vision budget is just as cheap to read whole, and a
        # whole page can never split a question in half. Only big images (a
        # 2400 px photo) need the cuts, because there the downscale eats the
        # small print.
        mode = args.split
        if mode == "auto":
            mode = "page" if max(w, h) <= args.max_side else "bands"
        elif mode == "page" and max(w, h) > args.max_side:
            warns.append(f"{stem}: page mode forced, image is downscaled and small print may blur")

        blocks = []
        if mode == "bands":
            mask = _mask(im)
            cols = _column_split(mask)
            if args.columns == "1":
                cols = [(0, w)]
            elif args.columns == "2" and len(cols) == 1:
                cols = [(0, w // 2), (w // 2, w)]
                warns.append(f"{stem}: --columns 2 forced, may cut a wide figure in half")
            blocks = _blocks(mask, cols, int(h * args.min_gap), int(h * args.min_block))
            blocks, folded = _merge_slivers(blocks)
            if folded:
                notes.append(f"{stem}: folded {folded} sliver block(s) into their neighbours")
            tallest = max((b[3] - b[1] for b in blocks), default=0)
            if len(blocks) <= 1 or tallest > 0.60 * h:
                # One block covering the page means the gaps were not found
                # (screenshots with shaded bands do exactly this). Fall back to
                # a single readable view instead of pretending the cut worked.
                notes.append(f"{stem}: no usable question gap - reading the page whole")
                blocks = []

        if blocks:
            for k, (x0, y0, x1, y1, lines, ink_pct, merge_gap) in enumerate(blocks, start=1):
                box = (max(0, x0 - pad), max(0, y0 - pad), min(w, x1 + pad), min(h, y1 + pad))
                crop = _fit_crop(im.crop(box), args.max_side)
                rel = Path("crops") / f"{stem}-q{k}.png"
                crop.save(out / rel, "PNG")
                hint = "figure-ish" if ink_pct < 6 else "text"
                add({"id": f"{stem}-q{k}", "bbox": list(box), "crop": rel.as_posix(),
                     "width": crop.width, "height": crop.height,
                     "lines": int(lines), "ink_pct": round(float(ink_pct), 1),
                     "merge_gap": int(merge_gap), "hint": hint})
        else:
            if max(w, h) <= args.max_side:
                view, size, note = im, (w, h), "whole page, full resolution"
            elif contact_sheet is not None:
                view, size = contact_sheet(im, out / "crops" / f"{stem}-full.png", tiles=3)
                note = "tiled page sheet (full view + 3 zooms)"
            else:
                view, size, note = _fit_crop(im, args.max_side), None, "scaled whole page"
            rel = Path("crops") / f"{stem}-full.png"
            if view is not im:
                view.save(out / rel, "PNG")
                size = view.size
            else:
                im.save(out / rel, "PNG")
            add({"id": f"{stem}-full", "bbox": [0, 0, w, h], "crop": rel.as_posix(),
                 "width": size[0], "height": size[1], "lines": 0, "ink_pct": 0.0,
                 "hint": "page-view"})
            if mode == "page":
                notes.append(f"{stem}: {note}")
        pages.append({"page": stem, "source": src.name, "file": f"pages/{stem}.png",
                      "size": [w, h], "columns": len(cols) if mode == "bands" else 1,
                      "mode": mode, "blocks": page_blocks})

    if not items:
        print("ERROR no question block detected; try --min-block 0.004 or --columns 2", file=sys.stderr)
        return 2

    overview = None
    if not args.no_overview and len(thumbs) > 0:
        size = _overview(thumbs, out / "overview.png")
        overview = {"file": "overview.png", "size": list(size)}

    rounds = _pack(items, max(1, args.max_per_read), max(0.2, args.max_mpix))
    plan = {
        "tool": "batch_prepare.py",
        "options": {"columns": args.columns, "max_side": args.max_side,
                    "max_per_read": args.max_per_read, "max_mpix": args.max_mpix,
                    "min_gap": args.min_gap, "min_block": args.min_block},
        "pages": pages,
        "overview": overview,
        "read_plan": [{"round": i + 1,
                       "blocks": [it["id"] for it in r],
                       "files": [(Path("_inspect") / it["crop"]).as_posix() for it in r],
                       "mpix": round(sum(it["width"] * it["height"] for it in r) / 1e6, 2)}
                      for i, r in enumerate(rounds)],
        "notes": notes,
        "warnings": warns,
    }
    (out / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
                                   encoding="utf-8")

    lines = ["# Read plan", "", "One call produced this. Follow it in order; do not re-crop.", ""]
    if overview:
        lines += [f"- Layout only: `_inspect/{overview['file']}` "
                  f"({overview['size'][0]}x{overview['size'][1]}) - read once if the page order is unclear.", ""]
    lines += ["| round | images | MPix | blocks |", "|---|---|---|---|"]
    for r in plan["read_plan"]:
        lines.append(f"| {r['round']} | {', '.join('`' + f.split('/', 1)[-1] + '`' for f in r['files'])} "
                     f"| {r['mpix']} | {', '.join(r['blocks'])} |")
    lines += ["", "After the last round write `text/question.json`; the blocks above already "
              "cover every question on the pages.", ""]
    (out / "plan.md").write_text("\n".join(lines), encoding="utf-8")

    # ---- digest (keep it short: every printed line is re-billed later) ------
    total_mpix = sum(it["width"] * it["height"] for it in items) / 1e6
    print(f"PREP  {len(pages)} page(s) -> {len(items)} block(s), {len(rounds)} read round(s) "
          f"(<= {args.max_per_read} img, {args.max_mpix} MPix each)")
    if overview:
        print(f"OVER  _inspect/overview.png {overview['size'][0]}x{overview['size'][1]}  (layout only)")
    shown = 0
    for page in pages:
        w, h = page["size"]
        print(f"PAGE  {page['file']} {w}x{h} blocks={len(page['blocks'])} cols={page['columns']}")
        for b in page["blocks"]:
            if shown >= args.max_print:
                continue
            shown += 1
            view = b["hint"] == "page-view"
            ink = "    --" if view else f"{b['ink_pct']:>5.1f}%"
            lines = "--" if view else b["lines"]
            print(f"      {b['id']:<8} lines={lines:<3} ink={ink} "
                  f"{b['hint']:<10} {b['width']}x{b['height']} -> _inspect/{b['crop']}")
    for r in plan["read_plan"]:
        print(f"ROUND {r['round']}  ({r['mpix']} MPix)  " + "  ".join(f.split("_inspect/")[-1] for f in r["files"]))
    for w_ in warns:
        print("WARN  " + w_)
    for note in notes:
        print("NOTE  " + note)
    print(f"TOTAL {total_mpix:.1f} MPix across all crops; plan: _inspect/plan.md")
    print("NEXT")
    print("  1. read_image in ROUND order above (one call per round, several files per call)")
    print("  2. write text/question.json per work folder; do not cut more crops")
    print("  3. python card_lint.py work/            (all math traps, all cards, one call)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
