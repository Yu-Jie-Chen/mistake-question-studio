#!/usr/bin/env python3
"""Crop, deskew, whiten, and lightly clean a scanned/photo figure.

This script handles geometry and paper cleanup. It does not understand the
figure and cannot reliably remove black handwriting that overlaps printed
geometry; use the mask option for simple cases and the redraw workflow for
complex ones.

Examples:
    python clean_figure.py in.jpg out.png --crop 120,80,980,720 --rotate -1.2
    python clean_figure.py in.jpg out.png --trim --max-side 2400
    python clean_figure.py in.jpg out.png --mask-json erase.json --remove-color
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

try:
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
except ImportError as exc:  # pragma: no cover
    print("Missing dependency: pip install pillow numpy", file=sys.stderr)
    raise SystemExit(2) from exc


def parse_crop(value: str | None, width: int, height: int):
    if not value:
        return None
    parts = [p.strip() for p in value.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("crop must be x0,y0,x1,y1")
    nums = []
    for p in parts:
        if p.endswith("%"):
            nums.append(float(p[:-1]) / 100.0)
        else:
            nums.append(float(p))
    if all(0 <= n <= 1 for n in nums):
        x0, y0, x1, y1 = (round(nums[0] * width), round(nums[1] * height),
                          round(nums[2] * width), round(nums[3] * height))
    else:
        x0, y0, x1, y1 = (round(n) for n in nums)
    x0, x1 = sorted((max(0, x0), min(width, x1)))
    y0, y1 = sorted((max(0, y0), min(height, y1)))
    if x1 - x0 < 8 or y1 - y0 < 8:
        raise argparse.ArgumentTypeError("crop is empty or too small")
    return x0, y0, x1, y1


def normalize_paper(img: Image.Image, strength: float = 1.0) -> Image.Image:
    """Push paper to white while keeping dark line work."""
    gray = ImageOps.grayscale(img)
    arr = np.asarray(gray).astype(np.float32)
    # Robust black/white points; ignore a few extreme pixels.
    black = np.percentile(arr, 0.5)
    white = np.percentile(arr, 99.0)
    if white - black < 20:
        return gray
    arr = (arr - black) * (255.0 / (white - black))
    arr = np.clip(arr, 0, 255)
    # Gentle S-curve: keep mid-tones, clean the paper.
    arr = 255.0 * np.clip((arr / 255.0) ** (0.92 * strength), 0, 1)
    out = Image.fromarray(arr.astype(np.uint8), mode="L")
    # Snap near-white and near-black without destroying anti-aliasing.
    lut = []
    for v in range(256):
        if v >= 246:
            lut.append(255)
        elif v <= 18:
            lut.append(0)
        else:
            lut.append(v)
    return out.point(lut)


def remove_colored_marks(img: Image.Image, sat_threshold: float = 0.28,
                         val_threshold: float = 0.96) -> Image.Image:
    """Replace saturated colored pixels with white.

    Warning: this can erase colored printed diagrams. Use only for pages where
    the printed figure is black/gray and the teacher used a colored pen.
    """
    arr = np.asarray(img.convert("RGB")).astype(np.float32) / 255.0
    mx = arr.max(axis=2)
    mn = arr.min(axis=2)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    mask = (sat > sat_threshold) & (mx < val_threshold)
    if not mask.any():
        return img
    out = arr.copy()
    out[mask] = 1.0
    return Image.fromarray((out * 255).astype(np.uint8), mode="RGB")


def load_mask(path: Path):
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    rects = data.get("rects", [])
    polygons = data.get("polygons", [])
    return rects, polygons


def mask_to_image(size, rects, polygons) -> Image.Image:
    mask = Image.new("L", size, 0)
    d = ImageDraw.Draw(mask)
    for r in rects:
        if len(r) != 4:
            raise ValueError("each rect must be [x0,y0,x1,y1]")
        d.rectangle(tuple(round(v) for v in r), fill=255)
    for poly in polygons:
        if len(poly) < 3:
            raise ValueError("each polygon needs at least 3 points")
        d.polygon([tuple(round(v) for v in p) for p in poly], fill=255)
    return mask


def apply_mask(img: Image.Image, mask: Image.Image, feather: float = 1.2) -> Image.Image:
    """Fill masked areas with the median of a surrounding ring."""
    arr = np.asarray(img.convert("RGB")).astype(np.float32)
    m = np.asarray(mask) > 0
    if not m.any():
        return img
    # Dilate the mask to get a clean surrounding ring.
    ring_img = mask.filter(ImageFilter.MaxFilter(21))
    ring = (np.asarray(ring_img) > 0) & (~m)
    if ring.any():
        fill = np.median(arr[ring], axis=0)
    else:
        fill = np.array([255.0, 255.0, 255.0], dtype=np.float32)
    arr[m] = fill
    filled = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), mode="RGB")
    # Feather only the filled patch.
    soft = mask.filter(ImageFilter.GaussianBlur(radius=feather))
    return Image.composite(filled.filter(ImageFilter.GaussianBlur(radius=feather * 0.6)),
                           img.convert("RGB"), soft)


def trim_white(img: Image.Image, padding: int = 18) -> Image.Image:
    gray = ImageOps.grayscale(img)
    # Anything darker than 250 is content.
    mask = gray.point(lambda v: 255 if v < 250 else 0)
    bbox = mask.getbbox()
    if not bbox:
        return img
    x0, y0, x1, y1 = bbox
    x0 = max(0, x0 - padding)
    y0 = max(0, y0 - padding)
    x1 = min(img.width, x1 + padding)
    y1 = min(img.height, y1 + padding)
    return img.crop((x0, y0, x1, y1))


def make_preview(before: Image.Image, after: Image.Image, out: Path) -> None:
    target_h = 900
    def fit(im):
        scale = min(1.0, target_h / im.height)
        return im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
    a, b = fit(before.convert("RGB")), fit(after.convert("RGB"))
    gap = 40
    canvas = Image.new("RGB", (a.width + b.width + gap * 3, max(a.height, b.height) + 90), "white")
    canvas.paste(a, (gap, 60))
    canvas.paste(b, (gap * 2 + a.width, 60))
    d = ImageDraw.Draw(canvas)
    try:
        f = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 26)
    except Exception:
        f = ImageFont.load_default()
    d.text((gap, 18), "before", fill="#444444", font=f)
    d.text((gap * 2 + a.width, 18), "after", fill="#444444", font=f)
    canvas.save(out)


def main() -> int:
    p = argparse.ArgumentParser(description="Clean a figure crop for a question card.")
    p.add_argument("input", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--crop", help="x0,y0,x1,y1 in pixels or percentages (e.g. 10%%,10%%,90%%,90%%)")
    p.add_argument("--rotate", type=float, default=0.0, help="degrees clockwise; negative = counterclockwise")
    p.add_argument("--trim", action="store_true", help="trim near-white margins")
    p.add_argument("--max-side", type=int, default=2400, help="maximum output side in pixels (0 = keep)")
    p.add_argument("--remove-color", action="store_true", help="replace saturated colored pen marks with white")
    p.add_argument("--mask-json", type=Path, help="manual erase mask: rects/polygons")
    p.add_argument("--keep-color", action="store_true", help="do not convert to grayscale")
    p.add_argument("--preview", type=Path, help="write a before/after preview PNG")
    p.add_argument("--no-paper", action="store_true", help="skip paper whitening")
    args = p.parse_args()

    if not args.input.exists():
        print(f"Input not found: {args.input}", file=sys.stderr)
        return 2

    img = Image.open(args.input)
    img = ImageOps.exif_transpose(img).convert("RGB")
    before = img.copy()

    crop = parse_crop(args.crop, img.width, img.height)
    if crop:
        img = img.crop(crop)

    if args.rotate:
        img = img.rotate(-args.rotate, expand=True, resample=Image.BICUBIC,
                         fillcolor=(255, 255, 255))

    if args.remove_color:
        img = remove_colored_marks(img)

    if args.mask_json:
        if not args.mask_json.exists():
            print(f"Mask not found: {args.mask_json}", file=sys.stderr)
            return 2
        rects, polygons = load_mask(args.mask_json)
        mask = mask_to_image(img.size, rects, polygons)
        img = apply_mask(img, mask)

    if not args.keep_color:
        img = normalize_paper(img) if not args.no_paper else ImageOps.grayscale(img)
    elif not args.no_paper:
        img = ImageOps.autocontrast(img, cutoff=0.5)

    if args.trim:
        img = trim_white(img)

    if args.max_side and max(img.size) > args.max_side:
        scale = args.max_side / max(img.size)
        img = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    suffix = args.output.suffix.lower()
    if suffix in (".jpg", ".jpeg"):
        img.convert("RGB").save(args.output, quality=95, subsampling=0)
    else:
        img.save(args.output, "PNG")

    if args.preview:
        args.preview.parent.mkdir(parents=True, exist_ok=True)
        make_preview(before, img, args.preview)

    print(f"saved {args.output} ({img.width}x{img.height})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
