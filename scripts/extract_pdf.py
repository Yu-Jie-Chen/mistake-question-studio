#!/usr/bin/env python3
"""Extract a PDF text layer, or OCR rendered pages as a fallback.

Text layer backends: pypdf, PyPDF2, pdfminer.six, pdftotext.
OCR backend: pytesseract + tesseract (optional).

Examples:
    python extract_pdf.py input.pdf text --pages 1-3
    python extract_pdf.py input.pdf text --ocr --lang chi_sim+eng
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


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


def page_texts_pypdf(src: Path) -> list[str]:
    from pypdf import PdfReader  # type: ignore
    return [(p.extract_text() or "") for p in PdfReader(str(src)).pages]


def page_texts_pypdf2(src: Path) -> list[str]:
    from PyPDF2 import PdfReader  # type: ignore
    return [(p.extract_text() or "") for p in PdfReader(str(src)).pages]


def page_texts_pdfminer(src: Path) -> list[str]:
    from pdfminer.high_level import extract_text  # type: ignore
    txt = extract_text(str(src))
    return txt.split("\f")


def page_texts_pdftotext(src: Path) -> list[str]:
    exe = shutil.which("pdftotext")
    if not exe:
        raise RuntimeError("pdftotext not found")
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "out.txt"
        subprocess.run([exe, "-layout", str(src), str(out)], check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        txt = out.read_text(encoding="utf-8", errors="replace")
    return txt.split("\f")


def ocr_pages(src: Path, pages: list[int], lang: str, dpi: int) -> list[str]:
    import pytesseract  # type: ignore
    from PIL import Image
    try:
        import fitz  # type: ignore
    except ImportError as exc:
        raise RuntimeError("OCR needs PyMuPDF: pip install pymupdf") from exc
    doc = fitz.open(src)
    out = []
    for n in pages:
        pix = doc[n - 1].get_pixmap(dpi=dpi, alpha=False)
        tmp = src.parent / f".ocr-{n}.png"
        pix.save(tmp)
        out.append(pytesseract.image_to_string(Image.open(tmp), lang=lang))
        tmp.unlink(missing_ok=True)
    doc.close()
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Extract text from a PDF.")
    ap.add_argument("input", type=Path)
    ap.add_argument("output_dir", type=Path)
    ap.add_argument("--pages", help="1-3,5")
    ap.add_argument("--ocr", action="store_true", help="force OCR instead of the text layer")
    ap.add_argument("--lang", default="chi_sim+eng")
    ap.add_argument("--dpi", type=int, default=300)
    args = ap.parse_args()

    if not args.input.exists():
        print(f"Input not found: {args.input}", file=sys.stderr)
        return 2
    args.output_dir.mkdir(parents=True, exist_ok=True)

    backend = None
    texts = []
    total = 1
    if not args.ocr:
        for name, fn in (("pypdf", page_texts_pypdf),
                         ("PyPDF2", page_texts_pypdf2),
                         ("pdfminer", page_texts_pdfminer),
                         ("pdftotext", page_texts_pdftotext)):
            try:
                texts = fn(args.input)
                backend = name
                total = max(1, len(texts))
                break
            except Exception:
                continue
    if not texts or not any(t.strip() for t in texts):
        try:
            # Determine page count without a text backend.
            try:
                import fitz  # type: ignore
                total = len(fitz.open(args.input))
            except Exception:
                total = 1
            pages = parse_pages(args.pages, total)
            texts = ocr_pages(args.input, pages, args.lang, args.dpi)
            backend = "pytesseract"
        except Exception as exc:
            print("No text layer and OCR unavailable.", file=sys.stderr)
            print("Install pypdf/pdftotext for text, or pytesseract + PyMuPDF for OCR.", file=sys.stderr)
            print(f"Details: {exc}", file=sys.stderr)
            return 3

    total = len(texts)
    pages = parse_pages(args.pages, total)
    manifest = {"source": str(args.input), "backend": backend, "pages": []}
    for n in pages:
        txt = texts[n - 1] if n - 1 < len(texts) else ""
        path = args.output_dir / f"page-{n:03d}.txt"
        path.write_text(txt.strip() + "\n", encoding="utf-8")
        manifest["pages"].append({"page": n, "file": path.name, "chars": len(txt.strip())})
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"extracted {len(manifest['pages'])} page(s) with {backend}")
    if backend != "pytesseract" and all(p["chars"] < 20 for p in manifest["pages"]):
        print("Warning: very little text found. Try --ocr or inspect the PDF visually.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
