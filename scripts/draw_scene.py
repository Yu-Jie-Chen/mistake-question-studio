# -*- coding: utf-8 -*-
"""Derive a flat (2D) physics/maths figure from a declarative scene: spec JSON -> PNG + SVG.

Companion to ``draw_solid.py`` (which handles 3D solids). This one covers the
figures that dominate mistake cards: inclines, blocks, trajectories, circuits
drawn as line scenes, angle marks, hatching, labels.

Everything is expressed in *data* coordinates (metres, or whatever the problem
uses) and mapped to the canvas by ``view``; the script never guesses proportions
from a photo. Parabolas are integrated from the physics parameters, so a
projectile arc is exact rather than eyeballed.

Spec::

    {
      "figure_id": "fig-1",
      "view": {"x0": -3.8, "x1": 2.1, "y0": -0.25, "y1": 2.35},
      "canvas": {"width": 1200},
      "style": {"line_width": 2.2, "font_size": 0.10, "dash": [9, 6]},
      "elements": [
        {"type": "polyline", "points": [[-3.46, 2.0], [0, 0]], "style": "solid"},
        {"type": "line",   "p1": [-3.46, 0], "p2": [1.9, 0]},
        {"type": "arrow",  "p1": [-3.46, 2.0], "p2": [-2.46, 2.0]},
        {"type": "arc",    "center": [0, 0], "r": 0.42, "a0": 150, "a1": 180},
        {"type": "label",  "text": "v", "sub": "0", "at": [-2.95, 2.12]},
        {"type": "dot",    "at": [-3.46, 2.0], "r": 3.5},
        {"type": "parabola", "from": [-3.46, 2.0], "vx": 5.23, "vy": 0,
                             "g": 10, "t1": 0.604, "style": "dashed"},
        {"type": "hatch",  "p1": [-3.46, 0], "p2": [1.9, 0], "spacing": 0.10,
                           "length": 0.10, "angle": -55}
      ]
    }

Notes
-----
* angles are in degrees, measured anticlockwise from +x (maths convention);
* ``style`` on an element overrides the global dash/solid choice;
* ``font_size`` and ``hatch`` sizes are in data units, so the figure stays
  proportional when the view changes;
* ``label`` supports ``sub``/``sup`` for v_0, v_x, R^2 ...
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except Exception:  # pragma: no cover
    Image = None

FONT_ITALIC = [
    "C:/Windows/Fonts/timesi.ttf",
    "C:/Windows/Fonts/cambriai.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf",
]
FONT_UPRIGHT = [
    "C:/Windows/Fonts/times.ttf",
    "C:/Windows/Fonts/cambria.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
]


def _font(size, italic=True):
    for path in (FONT_ITALIC if italic else FONT_UPRIGHT):
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, max(6, int(round(size))))
            except Exception:
                continue
    return ImageFont.load_default()


class Scene:
    def __init__(self, spec: dict):
        self.spec = spec
        v = spec["view"]
        self.x0, self.x1 = float(v["x0"]), float(v["x1"])
        self.y0, self.y1 = float(v["y0"]), float(v["y1"])
        st = spec.get("style", {}) or {}
        self.color = st.get("color", "#111111")
        self.lw = float(st.get("line_width", 2.2))
        self.fs = float(st.get("font_size", 0.10))
        self.dash = tuple(float(c) for c in st.get("dash", (9, 6)))
        cw = spec.get("canvas", {}) or {}
        self.width = int(cw.get("width", 1200))
        span_x, span_y = self.x1 - self.x0, self.y1 - self.y0
        self.height = int(cw.get("height", round(self.width * span_y / span_x)))
        self.scale = min(self.width / span_x, self.height / span_y)
        self.ox = (self.width - span_x * self.scale) / 2
        self.oy = (self.height - span_y * self.scale) / 2

    def px(self, p):
        x = self.ox + (float(p[0]) - self.x0) * self.scale
        y = self.height - (self.oy + (float(p[1]) - self.y0) * self.scale)
        return (x, y)

    def unit(self, u):
        """data-length -> pixels"""
        return float(u) * self.scale


def render(spec, out_path, supersample=3):
    if Image is None:
        raise RuntimeError("Pillow is required: pip install pillow")
    sc = Scene(spec)
    ss = supersample
    img = Image.new("RGB", (sc.width * ss, sc.height * ss), "white")
    d = ImageDraw.Draw(img)

    def P(p):
        x, y = sc.px(p)
        return (x * ss, y * ss)

    def line_seg(p1, p2, dashed=False, width=None):
        a, b = P(p1), P(p2)
        w = int(round((width or sc.lw) * ss))
        if not dashed:
            d.line([a, b], fill=sc.color, width=w)
            return
        seg = math.hypot(b[0] - a[0], b[1] - a[1])
        if seg < 1e-6:
            return
        ux, uy = (b[0] - a[0]) / seg, (b[1] - a[1]) / seg
        dash, gap = sc.dash[0] * ss, sc.dash[1] * ss
        t = 0.0
        while t < seg:
            e = min(t + dash, seg)
            d.line([(a[0] + ux * t, a[1] + uy * t), (a[0] + ux * e, a[1] + uy * e)],
                   fill=sc.color, width=w)
            t = e + gap

    def path(points, dashed=False, width=None):
        """Draw a polyline; dashing continues across vertices (dash phase is global)."""
        px = [P(p) for p in points]
        w = int(round((width or sc.lw) * ss))
        if not dashed:
            for i in range(len(px) - 1):
                d.line([px[i], px[i + 1]], fill=sc.color, width=w)
            return
        dash, gap = sc.dash[0] * ss, sc.dash[1] * ss
        period = dash + gap
        pos = 0.0
        for i in range(len(px) - 1):
            (x1, y1), (x2, y2) = px[i], px[i + 1]
            seg = math.hypot(x2 - x1, y2 - y1)
            if seg < 1e-9:
                continue
            ux, uy = (x2 - x1) / seg, (y2 - y1) / seg
            s = 0.0
            while s < seg - 1e-9:
                phase = (pos + s) % period
                if phase < dash:
                    run = min(dash - phase, seg - s)
                    d.line([(x1 + ux * s, y1 + uy * s),
                            (x1 + ux * (s + run), y1 + uy * (s + run))],
                           fill=sc.color, width=w)
                    s += run
                else:
                    s += min(period - phase, seg - s)
            pos += seg

    def arrow_head(tip, tail, size=None):
        size = (size or sc.unit(0.09)) * ss
        ang = math.atan2(tip[1] - tail[1], tip[0] - tail[0])
        for delta in (math.radians(25), -math.radians(25)):
            p = (tip[0] - size * math.cos(ang + delta), tip[1] - size * math.sin(ang + delta))
            d.line([tip, p], fill=sc.color, width=int(round(sc.lw * 0.85 * ss)))

    def label(el, anchor="lm"):
        text = str(el.get("text", ""))
        sub = el.get("sub")
        sup = el.get("sup")
        italic = el.get("italic", text.isalpha() and len(text) <= 3)
        size = sc.unit(el.get("size", sc.fs)) * ss
        f = _font(size, italic)
        pos = P(el["at"])
        dx, dy = el.get("dx", 0), el.get("dy", 0)
        pos = (pos[0] + sc.unit(dx) * ss, pos[1] - sc.unit(dy) * ss)
        d.text(pos, text, font=f, fill=sc.color, anchor=anchor)
        # width of the main run, to place sub/superscript
        try:
            wdt = d.textlength(text, font=f)
        except Exception:
            wdt = size * 0.6 * len(text)
        if sub:
            fs2 = _font(size * 0.62, italic)
            d.text((pos[0] + wdt, pos[1] + size * 0.32), str(sub), font=fs2,
                   fill=sc.color, anchor="lm")
        if sup:
            fs2 = _font(size * 0.62, italic)
            d.text((pos[0] + wdt, pos[1] - size * 0.36), str(sup), font=fs2,
                   fill=sc.color, anchor="lm")

    for el in spec.get("elements", []):
        kind = el.get("type")
        dashed = (el.get("style") == "dashed")
        if kind == "line" or kind == "polyline":
            pts = el["points"] if kind == "polyline" else [el["p1"], el["p2"]]
            path(pts, dashed, el.get("width"))
        elif kind == "arrow":
            a, b = P(el["p1"]), P(el["p2"])
            line_seg(el["p1"], el["p2"], dashed, el.get("width"))
            arrow_head(b, a)
        elif kind == "arc":
            cx, cy = el["center"]
            r = float(el["r"])
            # screen top-left is the data point (cx-r, cy+r)
            box = [P((cx - r, cy + r)), P((cx + r, cy - r))]
            a0, a1 = float(el["a0"]), float(el["a1"])
            start, end = -a1, -a0          # PIL measures clockwise from +x
            d.arc([box[0][0], box[0][1], box[1][0], box[1][1]], start, end,
                  fill=sc.color, width=int(round(sc.lw * 0.8 * ss)))
        elif kind == "dot":
            p = P(el["at"])
            r = sc.unit(el.get("r", 0.035)) * ss
            d.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], outline=sc.color,
                      width=int(round(sc.lw * 0.8 * ss)))
        elif kind == "parabola":
            x0, y0 = el["from"]
            vx, vy = float(el.get("vx", 0)), float(el.get("vy", 0))
            g = float(el.get("g", 10))
            t0, t1 = float(el.get("t0", 0)), float(el["t1"])
            n = int(el.get("samples", 90))
            pts = []
            for i in range(n + 1):
                t = t0 + (t1 - t0) * i / n
                pts.append((x0 + vx * t, y0 + vy * t - 0.5 * g * t * t))
            path(pts, dashed, el.get("width"))
        elif kind == "hatch":
            p1, p2 = el["p1"], el["p2"]
            spacing = sc.unit(el.get("spacing", 0.10))
            length = sc.unit(el.get("length", 0.10))
            ang = math.radians(float(el.get("angle", -60)))
            a, b = P(p1), P(p2)
            seg = math.hypot(b[0] - a[0], b[1] - a[1])
            if seg < 1e-6:
                continue
            ux, uy = (b[0] - a[0]) / seg, (b[1] - a[1]) / seg
            n = int(seg // spacing)
            for i in range(n + 1):
                s = i * spacing
                bx, by = a[0] + ux * s, a[1] + uy * s
                d.line([(bx, by), (bx + length * math.cos(ang), by - length * math.sin(ang))],
                       fill=sc.color, width=max(1, int(round(sc.lw * 0.7 * ss))))
        elif kind == "label":
            label(el, el.get("anchor", "lm"))
        else:
            raise ValueError(f"unknown element type {kind!r}")

    img = img.resize((sc.width, sc.height), Image.LANCZOS)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG")
    return out, (sc.width, sc.height)


def render_svg(spec, out_path):
    sc = Scene(spec)

    def f(v):
        return f"{v:.2f}"

    def pts_of(el):
        if el.get("type") == "polyline":
            return el["points"]
        return [el["p1"], el["p2"]]

    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           f'<svg xmlns="http://www.w3.org/2000/svg" width="{sc.width}" height="{sc.height}" '
           f'viewBox="0 0 {sc.width} {sc.height}">',
           f'  <rect width="{sc.width}" height="{sc.height}" fill="#ffffff"/>']
    solid, dashed = [], []
    for el in spec.get("elements", []):
        kind = el.get("type")
        if kind not in ("line", "polyline", "arrow"):
            continue
        p = pts_of(el)
        seg = " ".join(f"{f(sc.px(q)[0])},{f(sc.px(q)[1])}" for q in p)
        item = (f'  <polyline points="{seg}" fill="none"/>')
        (dashed if el.get("style") == "dashed" else solid).append(item)
    out.append(f'  <g stroke="{sc.color}" stroke-width="{sc.lw}" stroke-linecap="round">')
    out.extend(solid)
    out.append('  </g>')
    out.append(f'  <g stroke="{sc.color}" stroke-width="{sc.lw * 0.92}" fill="none" '
               f'stroke-dasharray="{sc.dash[0]} {sc.dash[1]}">')
    out.extend(dashed)
    out.append('  </g>')
    for el in spec.get("elements", []):
        if el.get("type") == "dot":
            x, y = sc.px(el["at"])
            r = sc.unit(el.get("r", 0.035))
            out.append(f'  <circle cx="{f(x)}" cy="{f(y)}" r="{f(r)}" fill="none" stroke="{sc.color}"/>')
        elif el.get("type") == "label":
            x, y = sc.px(el["at"])
            size = sc.unit(el.get("size", sc.fs))
            out.append(f'  <text x="{f(x)}" y="{f(y)}" font-family="Times New Roman, serif" '
                       f'font-style="italic" font-size="{f(size)}" fill="{sc.color}">{el.get("text", "")}</text>')
    out.append('</svg>')
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return out_path


def main(argv=None):
    ap = argparse.ArgumentParser(description="Render a 2D scene from a spec JSON.")
    ap.add_argument("spec", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--svg", type=Path)
    ap.add_argument("--before", type=Path, help="original crop, for the compare sheet")
    ap.add_argument("--compare", type=Path)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    spec = json.loads(args.spec.read_text(encoding="utf-8-sig"))
    out, size = render(spec, args.out)
    lines = [f"PNG  {args.out}  {size[0]}x{size[1]}"]
    if args.svg:
        lines.append(f"SVG  {render_svg(spec, args.svg)}")
    if args.before and args.compare:
        try:
            from draw_solid import build_compare
            c, cs = build_compare(args.before, out, args.compare,
                                  titles=("source", "redraw"))
            lines.append(f"CMP  {c}  {cs[0]}x{cs[1]}")
        except Exception as exc:  # pragma: no cover
            lines.append(f"CMP skipped ({exc})")
    if not args.quiet:
        print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
