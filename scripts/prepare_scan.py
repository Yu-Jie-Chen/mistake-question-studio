#!/usr/bin/env python3
"""Render a PDF (or normalise an image) into page images for a work folder.

Backends, in order: PyMuPDF, pdf2image, pdftoppm. Only one is required.

Examples:
    python prepare_scan.py page.pdf work/id/source --dpi 300 --pages 1-3
    python prepare_scan.py photo.jpg work/id/source
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

try:
    from PIL import Image, ImageOps
except ImportError as exc:  # pragma: no cover
    print("Missing dependency: pip install pillow", file=sys.stderr)
    raise SystemExit(2) from exc


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_pages(spec: str | None, total: int) -> list[int]:
    if not spec:
        return list(range(1, total + 1))
    pages = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            pages.update(range(int(a), int(b) + 1))
        else:
            pages.add(int(part))
    return sorted(p for p in pages if 1 <= p <= total)


def render_with_fitz(src: Path, out: Path, dpi: int, pages: list[int]) -> str:
    import fitz  # type: ignore
    doc = fitz.open(src)
    for n in pages:
        page = doc[n - 1]
        pix = page.get_pixmap(dpi=dpi, alpha=False)
        pix.save(out / f"page-{n:03d}.png")
    doc.close()
    return "pymupdf"


def render_with_pdf2image(src: Path, out: Path, dpi: int, pages: list[int]) -> str:
    from pdf2image import convert_from_path  # type: ignore
    images = convert_from_path(str(src), dpi=dpi, first_page=min(pages), last_page=max(pages))
    by_page = {p: im for p, im in zip(range(min(pages), max(pages) + 1), images)}
    for n in pages:
        if n in by_page:
            by_page[n].save(out / f"page-{n:03d}.png", "PNG")
    return "pdf2image"


def render_with_pdftoppm(src: Path, out: Path, dpi: int, pages: list[int]) -> str:
    exe = shutil.which("pdftoppm")
    if not exe:
        raise RuntimeError("pdftoppm not found")
    prefix = out / "_render"
    cmd = [exe, "-png", "-r", str(dpi), "-f", str(min(pages)), "-l", str(max(pages)),
           str(src), str(prefix)]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def page_no(p: Path) -> int:
        try:
            return int(p.stem.rsplit("-", 1)[-1])
        except ValueError:
            return 0

    produced = sorted(out.glob("_render-*.png"), key=page_no)
    if not produced:
        raise RuntimeError("pdftoppm produced no pages")
    for p in produced:
        n = page_no(p)
        if n in pages:
            p.rename(out / f"page-{n:03d}.png")
        else:
            p.unlink(missing_ok=True)
    return "pdftoppm"


def main() -> int:
    ap = argparse.ArgumentParser(description="Render a PDF or normalise an image.")
    ap.add_argument("input", type=Path)
    ap.add_argument("output_dir", type=Path)
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--pages", help="1-3,5 (PDF only)")
    ap.add_argument("--max-side", type=int, default=3000, help="resize page images above this side")
    args = ap.parse_args()

    if not args.input.exists():
        print(f"Input not found: {args.input}", file=sys.stderr)
        return 2
    args.output_dir.mkdir(parents=True, exist_ok=True)
    src = args.input.resolve()
    info = {
        "source": str(src),
        "sha256": sha256(src),
        "dpi": args.dpi,
        "pages": [],
        "backend": None,
    }

    suffix = src.suffix.lower()
    if suffix in (".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"):
        im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
        if args.max_side and max(im.size) > args.max_side:
            scale = args.max_side / max(im.size)
            im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
        out = args.output_dir / "page-001.png"
        im.save(out, "PNG")
        info.update({"backend": "image", "pages": [{"page": 1, "file": out.name,
                                                   "width": im.width, "height": im.height}]})
    elif suffix == ".pdf":
        try:
            import fitz  # type: ignore
            doc = fitz.open(src)
            total = len(doc)
            doc.close()
            pages = parse_pages(args.pages, total)
            info["backend"] = render_with_fitz(src, args.output_dir, args.dpi, pages)
        except Exception:
            try:
                from pypdf import PdfReader  # type: ignore
                total = len(PdfReader(str(src)).pages)
            except Exception:
                total = 0
            pages = parse_pages(args.pages, total) if total else [1]
            try:
                info["backend"] = render_with_pdf2image(src, args.output_dir, args.dpi, pages)
            except Exception:
                try:
                    info["backend"] = render_with_pdftoppm(src, args.output_dir, args.dpi, pages)
                except Exception as exc:
                    print("No PDF renderer available. Install PyMuPDF (`pip install pymupdf`), "
                          "pdf2image + Poppler, or Poppler's pdftoppm.", file=sys.stderr)
                    print(f"Details: {exc}", file=sys.stderr)
                    return 3
        info["pages"] = []
        for p in sorted(args.output_dir.glob("page-*.png")):
            im = Image.open(p)
            info["pages"].append({"page": int(p.stem.split("-")[1]), "file": p.name,
                                  "width": im.width, "height": im.height})
    else:
        print(f"Unsupported input: {src.suffix}", file=sys.stderr)
        return 2

    (args.output_dir / "manifest.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"rendered {len(info['pages'])} page(s) with {info['backend']} -> {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
