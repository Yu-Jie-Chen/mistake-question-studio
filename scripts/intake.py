# -*- coding: utf-8 -*-
"""One call does the whole intake: work folder, source copy, hash, contact sheet, stubs.

Instead of a dozen small probes (crop here, zoom there, re-encode, hash), this
script produces everything needed to *read* the question in a single image and
a single report:

* ``source/original.png``   - untouched copy (converted to PNG only if needed)
* ``source/contact.png``    - full view + N zoomed tiles, one image to read
* ``manifest.json``         - stub with sha256, size, rights (skipped if present)
* ``text/question.json``    - stub with id/subject/grade/source filled in
* a printed report          - sha256, ink bbox, an ink-density map, and the
                              next three actions

CLI
---
    python intake.py page.jpg --id 20261105-math-solid-geometry-004 \
        --subject mathematics --grade 高中二年级
    python intake.py page.jpg --id ... --box 508,0,696,97 --box 545,82,700,118

``--box`` adds an extra zoom tile for a region you already care about (the
figure, the answer blank); it is cheap, so pass several if the page is dense.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except Exception:  # pragma: no cover
    Image = None

try:  # shared italic serif font helper
    from draw_solid import _font
except Exception:  # pragma: no cover
    def _font(size):
        return None


WIDE_ASPECT = 2.2


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _ink_mask(im):
    """Binary ink mask with a background estimate that survives photos.

    A phone photo of paper has a grey, uneven background, so a fixed 235
    threshold marks the whole page as ink. Estimate the background from the
    bright end of the histogram instead.
    """
    g = im.convert("L")
    hist = g.histogram()
    total = sum(hist)
    acc, bg = 0, 255
    for value in range(255, -1, -1):
        acc += hist[value]
        if acc >= total * 0.90:
            bg = value
            break
    thr = max(150, min(235, bg - 28))
    return g.point(lambda v: 255 if v < thr else 0), thr


def ink_bbox(im) -> tuple:
    """Bounding box of the inked area."""
    mask, _ = _ink_mask(im)
    return mask.getbbox() or (0, 0, im.width, im.height)


def ink_map(im, cols=8, rows=4) -> list:
    """Coarse ink density in percent, so a crop can be chosen without new probes."""
    mask, _ = _ink_mask(im)
    small = mask.resize((cols * 40, rows * 40))
    out = []
    for r in range(rows):
        row = []
        for c in range(cols):
            box = (c * 40, r * 40, (c + 1) * 40, (r + 1) * 40)
            cell = small.crop(box)
            hist = cell.histogram()
            row.append(round(100.0 * hist[255] / max(1, cell.width * cell.height), 1))
        out.append(row)
    return out


def _fit(im, max_w, max_h, upscale=True):
    s = min(max_w / im.width, max_h / im.height)
    if not upscale:
        s = min(s, 1.0)
    if abs(s - 1.0) < 1e-9:
        return im
    return im.resize((max(1, int(round(im.width * s))), max(1, int(round(im.height * s)))), Image.LANCZOS)


def _tile_boxes(im, tiles, boxes):
    w, h = im.size
    out = []
    if boxes:
        for b in boxes:
            out.append(("BOX", tuple(int(v) for v in b)))
    if tiles:
        if w / h >= WIDE_ASPECT:
            step = w / tiles
            ov = step * 0.12
            for i in range(tiles):
                out.append((f"T{i + 1}", (max(0, int(i * step - ov)), 0,
                                          min(w, int((i + 1) * step + ov)), h)))
        else:
            for i in range(min(tiles, 4)):
                x0 = 0 if i % 2 == 0 else int(w * 0.45)
                y0 = 0 if i < 2 else int(h * 0.45)
                out.append((f"T{i + 1}", (x0, y0, min(w, int(x0 + w * 0.55)),
                                          min(h, int(y0 + h * 0.55)))))
    return out


def contact_sheet(im, out: Path, tiles=4, boxes=None, canvas_w=1450,
                  full_max=(1400, 700), tile_max_h=430, pad=14):
    """Full view on top, zoomed tiles wrapped underneath, one image to read.

    Tiles are sized so that two fit per row at ``canvas_w``; the sheet never
    grows wider than the canvas, because the viewer would downscale it and the
    zoom would be lost.
    """
    if im.width / im.height >= WIDE_ASPECT:
        tiles = min(tiles, 3) if tiles else 0
    full = _fit(im, min(full_max[0], canvas_w - 2 * pad), full_max[1])
    head = 24
    tile_max_w = max(240, (canvas_w - 3 * pad) // 2)

    tiles_img = []
    for label, box in _tile_boxes(im, tiles, boxes):
        crop = im.crop(box)
        scale = min(tile_max_w / crop.width, tile_max_h / crop.height, 10.0)
        tiles_img.append((label, crop.resize((max(1, int(crop.width * scale)),
                                              max(1, int(crop.height * scale))), Image.LANCZOS)))

    # greedy wrap
    rows, cur, cur_w = [], [], 0
    for item in tiles_img:
        w = item[1].width
        if cur and cur_w + pad + w > canvas_w - pad:
            rows.append(cur)
            cur, cur_w = [], 0
        cur.append(item)
        cur_w += w + (pad if cur_w else 0)
    if cur:
        rows.append(cur)

    width = max([full.width + 2 * pad] + [sum(t.width for _, t in r) + pad * (len(r) + 1) for r in rows])
    height = pad + head + full.height
    for r in rows:
        height += pad + head + max(t.height for _, t in r)
    height += pad

    canvas = Image.new("RGB", (width, height), "white")
    canvas.paste(full, (pad, pad + head))
    d = ImageDraw.Draw(canvas)
    f = _font(20)
    if f:
        d.text((pad, pad + 2), "FULL", font=f, fill=(110, 110, 110))
    y = pad + head + full.height
    for r in rows:
        y += pad
        x = pad
        for label, tile in r:
            if f:
                d.text((x, y + 2), label, font=f, fill=(110, 110, 110))
            canvas.paste(tile, (x, y + head))
            d.rectangle([x, y + head, x + tile.width, y + head + tile.height], outline=(205, 205, 205))
            x += tile.width + pad
        y += head + max(t.height for _, t in r)
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, "PNG")
    return out, canvas.size


def question_stub(fid, subject, grade, source_file, rights="private-study", note=""):
    return {
        "schema_version": "1.0",
        "id": fid,
        "subject": subject,
        "grade": grade,
        "source": {"type": "photo", "file": source_file, "page": 1, "pages": [1],
                   "rights": rights, "note": note},
        "question": {"type": "fill", "instruction_md": "", "stem_md": "", "subquestions": [],
                     "options": [], "figure_refs": []},
        "figures": [],
        "answer": {"final_md": "", "units": "", "confidence": "high",
                   "alternate_md": "", "verification_md": ""},
        "analysis": {"steps_md": "", "key_points": [], "pitfalls": []},
        "diagnosis": {"student_answer_md": "", "error_types": [], "root_cause_md": "", "remedy_md": ""},
        "meta": {"knowledge_points": [], "difficulty": 3, "tags": [], "variant_md": ""},
        "review": {"status": "draft", "reviewer": "", "date": "", "uncertainties": []},
    }


def manifest_stub(fid, subject, grade, sha, size, note=""):
    return {
        "id": fid,
        "subject": subject,
        "grade": grade,
        "source": {"file": "source/original.png", "sha256": sha,
                   "dimensions": [size[0], size[1]], "pages": [1],
                   "type": "photo", "rights": "private-study", "note": note},
        "tools": {"extract": "vision + contact sheet", "figure": "trace-redraw"},
        "confidence": {"text": "medium", "figure": "high", "answer": "medium"},
        "files": {"card": "card.md", "question_json": "text/question.json",
                  "figure_png": "figures/fig-1.png", "review": "review.md"},
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Preserve the source and build a contact sheet.")
    ap.add_argument("source", type=Path)
    ap.add_argument("--id", required=True, help="YYYYMMDD-subject-topic-###")
    ap.add_argument("--subject", required=True)
    ap.add_argument("--grade", default="")
    ap.add_argument("--work", type=Path, default=Path("work"))
    ap.add_argument("--rights", default="private-study")
    ap.add_argument("--note", default="")
    ap.add_argument("--tiles", type=int, default=4, help="number of auto zoom tiles (0 = none)")
    ap.add_argument("--box", action="append", default=[], metavar="X0,Y0,X1,Y1",
                    help="extra zoom tile; repeatable")
    ap.add_argument("--force", action="store_true", help="overwrite existing stubs")
    args = ap.parse_args(argv)

    if Image is None:
        print("ERROR pillow is required: pip install pillow", file=sys.stderr)
        return 2
    if not args.source.exists():
        print(f"ERROR source not found: {args.source}", file=sys.stderr)
        return 2
    if args.source.suffix.lower() in (".pdf",):
        print("ERROR PDFs go through prepare_scan.py first", file=sys.stderr)
        return 2

    wd = (args.work / args.id).resolve()
    for sub in ("source", "text", "figures"):
        (wd / sub).mkdir(parents=True, exist_ok=True)

    dst = wd / "source" / "original.png"
    im = Image.open(args.source)
    im.load()
    if dst.suffix.lower() == ".png" and args.source.resolve() == dst.resolve():
        pass
    else:
        im.convert("RGB").save(dst, "PNG")
    im = Image.open(dst).convert("RGB")
    sha = sha256_of(dst)

    boxes = []
    for b in args.box:
        parts = [p for p in b.replace(" ", "").split(",") if p]
        if len(parts) != 4:
            print(f"WARN ignoring --box {b!r}", file=sys.stderr)
            continue
        boxes.append(tuple(parts))

    sheet, sheet_size = contact_sheet(im, wd / "source" / "contact.png",
                                      tiles=args.tiles, boxes=boxes)

    man = wd / "manifest.json"
    if args.force or not man.exists():
        man.write_text(json.dumps(manifest_stub(args.id, args.subject, args.grade, sha,
                                                im.size, args.note),
                                  ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    qj = wd / "text" / "question.json"
    if args.force or not qj.exists():
        qj.write_text(json.dumps(question_stub(args.id, args.subject, args.grade,
                                               "source/original.png", args.rights, args.note),
                                  ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    bbox = ink_bbox(im)
    print(f"WORK   {str(wd).replace(chr(92), '/') if str(wd).isascii() else '(non-ASCII path)'}")
    print(f"SOURCE {dst.name} {im.size[0]}x{im.size[1]} sha256={sha[:16]}...")
    print(f"SHEET  {sheet.name} {sheet_size[0]}x{sheet_size[1]}")
    print(f"INKBOX {bbox}  (x0,y0,x1,y1)")
    print("INKMAP percent ink, 8 cols x 4 rows:")
    for row in ink_map(im):
        print("       " + " ".join(f"{v:5.1f}" for v in row))
    print("NEXT")
    print("  1. read_image source/contact.png   (full view + zoom tiles in one image)")
    print("  2. transcribe the stem into text/question.json  (keep wording and blanks)")
    print("  3. python draw_solid.py figures/fig-1.spec.json --out figures/fig-1.png "
          "--svg figures/fig-1.svg --before figures/fig-1.before.png --compare figures/compare-fig-1.png")
    print("  4. python run.py finish <workdir>   (preflight + build + validate)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
