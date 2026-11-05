# -*- coding: utf-8 -*-
"""Derive a solid-geometry figure from a 3D model: spec JSON -> PNG + SVG + checks.

Why this exists
---------------
A geometric figure must be *computed*, not traced from a photo: tracing loses
the hidden-line logic, and hand-drawing the projection costs many rounds of
trial and error. This module answers, in one call, the three questions that are
otherwise re-derived by hand every time:

1. the 2D projection (orthographic, from a stated eye direction);
2. which edges are hidden (computed from face normals, not guessed);
3. whether the model actually satisfies the question's data (edge lengths,
   face coplanarity, a sphere through every vertex).

Spec (JSON). Only ``vertices`` and ``faces`` are required::

    {
      "figure_id": "fig-1",
      "vertices": {"A": [0,0,0], "B": [2,0,0], "C": [2,2,0],
                   "D": [0,2,0], "E": [-1,1,1.41421356], "F": [3,1,1.41421356]},
      "faces": [["A","B","F","E"], ["D","C","F","E"], ["A","B","C","D"],
                ["A","D","E"], ["B","C","F"]],
      "projection": {"eye": [0.45, -0.85, 0.35], "scale": 300, "up": [0,0,1]},
      "style": {"line_width": 2.4, "dash": [0.085, 0.052],
                "font_size": 0.155, "label_distance": 0.21,
                "label_overrides": {"C": 0.26, "D": 0.30}},
      "expect": {"AB": 2, "AD": 2, "EF": 4, "AE": 2},
      "sphere": true
    }

Face winding matters: list each face counter-clockwise **as seen from outside**
the solid. Hidden-line classification then follows from the eye direction.

CLI
---
    python draw_solid.py spec.json --out figures/fig-1.png --svg figures/fig-1.svg
    python draw_solid.py spec.json --out f.png --before figures/fig-1.before.png \
        --compare figures/compare-fig-1.png
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except Exception:  # pragma: no cover
    Image = None

# ---------------------------------------------------------------------------
# small vector helpers
# ---------------------------------------------------------------------------

Vec = tuple


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _len(a):
    return math.sqrt(_dot(a, a))


def _unit(a):
    n = _len(a)
    if n < 1e-12:
        raise ValueError("zero-length vector")
    return (a[0] / n, a[1] / n, a[2] / n)


def _newell(verts, face):
    """Newell normal of a (possibly non-planar) polygon; length = 2 * area."""
    nx = ny = nz = 0.0
    m = len(face)
    for i in range(m):
        a = verts[face[i]]
        b = verts[face[(i + 1) % m]]
        nx += (a[1] - b[1]) * (a[2] + b[2])
        ny += (a[2] - b[2]) * (a[0] + b[0])
        nz += (a[0] - b[0]) * (a[1] + b[1])
    return (nx, ny, nz)


def _edge_key(a, b):
    return (a, b) if a <= b else (b, a)


# ---------------------------------------------------------------------------
# geometry
# ---------------------------------------------------------------------------

def load_spec(path):
    # utf-8-sig: users often write specs with editors that prepend a BOM
    spec = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if "vertices" not in spec or "faces" not in spec:
        raise ValueError("spec needs at least 'vertices' and 'faces'")
    verts = {k: (float(v[0]), float(v[1]), float(v[2])) for k, v in spec["vertices"].items()}
    faces = [list(f) for f in spec["faces"]]
    for f in faces:
        for name in f:
            if name not in verts:
                raise ValueError(f"face references unknown vertex {name!r}")
    spec["_verts"] = verts
    spec["_faces"] = faces
    return spec


def camera(spec):
    proj = spec.get("projection", {})
    eye = _unit(tuple(float(c) for c in proj.get("eye", (0.45, -0.85, 0.35))))
    up = tuple(float(c) for c in proj.get("up", (0.0, 0.0, 1.0)))
    # screen x: the world x-axis made perpendicular to the eye direction
    base = (1.0, 0.0, 0.0)
    d = _dot(base, eye)
    u = _unit(tuple(base[i] - d * eye[i] for i in range(3)))
    w = _cross(eye, u)
    if _dot(w, up) < 0:  # keep the world "up" axis pointing up on screen
        w = (-w[0], -w[1], -w[2])
    return eye, u, w


def classify(spec):
    """Return ({edge: 'solid'|'dashed'}, {face_index: bool visible}, normals)."""
    verts, faces = spec["_verts"], spec["_faces"]
    eye, _, _ = camera(spec)
    auto = bool(spec.get("auto_orient", True))
    centroid = tuple(sum(v[i] for v in verts.values()) / len(verts) for i in range(3))
    normals, visible = [], []
    for f in faces:
        n = _newell(verts, f)
        if auto:
            fc = tuple(sum(verts[name][i] for name in f) / len(f) for i in range(3))
            if _dot(n, _sub(fc, centroid)) < 0:
                n = (-n[0], -n[1], -n[2])
        normals.append(n)
        visible.append(_dot(n, eye) > 1e-12)
    adj = {}
    for i, f in enumerate(faces):
        m = len(f)
        for j in range(m):
            adj.setdefault(_edge_key(f[j], f[(j + 1) % m]), []).append(i)
    style = {}
    for key, face_ids in adj.items():
        style[key] = "solid" if any(visible[i] for i in face_ids) else "dashed"
    return style, visible, normals


def edges_of(spec):
    style, _, _ = classify(spec)
    return sorted(style.items(), key=lambda kv: (kv[1], kv[0]))


def checks(spec):
    """Numeric self-check of the model. Returns (report dict, list of warnings)."""
    verts, faces = spec["_verts"], spec["_faces"]
    warnings = []
    report = {"edges": {}, "planarity": {}, "sphere": None}

    for a, b in itertools.combinations(sorted(verts), 2):
        report["edges"][a + b] = _len(_sub(verts[a], verts[b]))

    for i, f in enumerate(faces):
        if len(f) < 4:
            continue
        p0 = verts[f[0]]
        ref = None
        dev = 0.0
        for tri in itertools.combinations(f[1:], 3):
            v1, v2, v3 = (_sub(verts[t], p0) for t in tri)
            n = _cross(v1, v2)
            if _len(n) < 1e-12:
                continue
            if ref is None:
                ref = _unit(n)
            else:
                dev = max(dev, abs(_dot(_unit(n), ref) - 1.0))
        report["planarity"]["".join(f)] = dev

    expect = spec.get("expect") or {}
    if expect:
        for name, want in expect.items():
            key = "".join(sorted(name))
            got = report["edges"].get(key)
            if got is None:
                warnings.append(f"expect key {name!r} is not a vertex pair")
            elif abs(got - float(want)) > 1e-6:
                warnings.append(f"edge {name} = {got:.6f}, expected {want}")

    if spec.get("sphere", True):
        report["sphere"] = _fit_sphere(verts)
        if report["sphere"] is None:
            warnings.append("no sphere through all vertices (fewer than 5 points?)")
    return report, warnings


def _fit_sphere(verts):
    """Sphere through the vertices: solve on 4-point subsets, keep the consensus.

    Points on a sphere satisfy  |p|^2 - 2 c.p + k = 0  with  k = |c|^2 - R^2,
    which is linear in (c, k).
    """
    names = sorted(verts)
    if len(names) < 5:
        return None
    best, tally = None, 0
    solutions = []
    for quad in itertools.combinations(names, 4):
        a, b = [], []
        for name in quad:
            p = verts[name]
            a.append([2 * p[0], 2 * p[1], 2 * p[2], -1.0])
            b.append(_dot(p, p))
        sol = _solve4(a, b)
        if sol is None:
            continue
        c = (sol[0], sol[1], sol[2])
        r2 = _dot(c, c) - sol[3]
        if r2 <= 1e-9:
            continue
        solutions.append((c, math.sqrt(r2)))
    if not solutions:
        return None
    # consensus: the solution that puts every vertex on the same sphere
    best = None
    for c, r in solutions:
        dev = max(abs(_len(_sub(verts[n], c)) - r) for n in names)
        if best is None or dev < best[3]:
            best = (c, r, len(solutions), dev)
        tally += 1
    c, r, n_sol, dev = best
    return {
        "center": tuple(round(x, 6) for x in c),
        "radius": round(r, 6),
        "max_deviation": dev,
        "solutions": n_sol,
        "agreement": round(sum(1 for cc, rr in solutions
                               if max(abs(_len(_sub(verts[n], cc)) - rr) for n in names) < 1e-6
                               ) / len(solutions), 3),
    }


def _solve4(a, b):
    """4x4 linear solve with partial pivoting; None when (near) singular."""
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    n = 4
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[piv][col]) < 1e-9:
            return None
        m[col], m[piv] = m[piv], m[col]
        pv = m[col][col]
        for r in range(n):
            if r == col:
                continue
            f = m[r][col] / pv
            if f:
                for k in range(col, n + 1):
                    m[r][k] -= f * m[col][k]
    return [m[i][n] / m[i][i] for i in range(n)]


# ---------------------------------------------------------------------------
# layout + rendering
# ---------------------------------------------------------------------------

FONT_CANDIDATES = [
    ("C:/Windows/Fonts/timesi.ttf", 0),
    ("C:/Windows/Fonts/cambriai.ttf", 0),
    ("C:/Windows/Fonts/DejaVuSerif-Italic.ttf", 0),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf", 0),
]


def _font(size):
    for path, idx in FONT_CANDIDATES:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size, index=idx)
            except Exception:
                continue
    return ImageFont.load_default()


def layout(spec):
    eye, u, w = camera(spec)
    verts = spec["_verts"]
    proj = spec.get("projection", {})
    scale = float(proj.get("scale", 300.0))
    style = spec.get("style", {})
    margin = style.get("margin", {"lr": 0.42, "t": 0.40, "b": 0.42})

    p2 = {k: (_dot(v, u), _dot(v, w)) for k, v in verts.items()}
    xs = [p[0] for p in p2.values()]
    ys = [p[1] for p in p2.values()]
    width = (max(xs) - min(xs) + 2 * margin["lr"]) * scale
    height = (max(ys) - min(ys) + margin["t"] + margin["b"]) * scale
    ox = (margin["lr"] - min(xs)) * scale
    oy = (margin["b"] + max(ys)) * scale

    def to_px(p, ss=1.0):
        return (ox * ss + p[0] * scale * ss, oy * ss - p[1] * scale * ss)

    label_dist = float(style.get("label_distance", 0.21))
    overrides = style.get("label_overrides", {}) or {}
    cx = sum(p[0] for p in p2.values()) / len(p2)
    cy = sum(p[1] for p in p2.values()) / len(p2)
    offsets = {}
    for name, p in p2.items():
        vx, vy = p[0] - cx, p[1] - cy
        n = math.hypot(vx, vy) or 1.0
        d = float(overrides.get(name, label_dist))
        offsets[name] = (vx / n * d, vy / n * d)

    return {
        "p2": p2, "width": width, "height": height, "scale": scale,
        "to_px": to_px, "offsets": offsets,
        "font_size": float(style.get("font_size", 0.155)) * scale,
        "line_width": float(style.get("line_width", 2.4)),
        "dash": tuple(float(c) * scale for c in style.get("dash", (0.085, 0.052))),
        "colour": style.get("colour", "#000000"),
    }


def render_png(spec, out_path, supersample=4):
    if Image is None:
        raise RuntimeError("Pillow is required: pip install pillow")
    lay = layout(spec)
    style, _, _ = classify(spec)
    ss = supersample
    img = Image.new("RGB", (int(lay["width"] * ss), int(lay["height"] * ss)), "white")
    d = ImageDraw.Draw(img)
    w_solid = max(1, int(round(lay["line_width"] * ss)))
    w_dash = max(1, int(round(lay["line_width"] * 0.92 * ss)))

    def line(a, b, width, dashed):
        x1, y1 = lay["to_px"](lay["p2"][a], ss)
        x2, y2 = lay["to_px"](lay["p2"][b], ss)
        if not dashed:
            d.line([(x1, y1), (x2, y2)], fill="#000000", width=width)
            return
        seg = math.hypot(x2 - x1, y2 - y1)
        if seg < 1e-6:
            return
        dx, dy = (x2 - x1) / seg, (y2 - y1) / seg
        dash, gap = lay["dash"][0] * ss, lay["dash"][1] * ss
        t = 0.0
        while t < seg:
            e = min(t + dash, seg)
            d.line([(x1 + dx * t, y1 + dy * t), (x1 + dx * e, y1 + dy * e)], fill="#000000", width=width)
            t = e + gap

    for (a, b), kind in sorted(style.items()):
        line(a, b, w_solid if kind == "solid" else w_dash, kind == "dashed")

    font = _font(int(round(lay["font_size"] * ss)))
    for name, p in lay["p2"].items():
        dx, dy = lay["offsets"][name]
        px, py = lay["to_px"]((p[0] + dx, p[1] + dy), ss)
        d.text((px, py), name, font=font, fill="#000000", anchor="mm")

    img = img.resize((int(lay["width"]), int(lay["height"])), Image.LANCZOS)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG")
    return out, img.size


def render_svg(spec, out_path):
    lay = layout(spec)
    style, _, _ = classify(spec)

    def f(v):
        return f"{v:.2f}"

    pts = {k: lay["to_px"](p) for k, p in lay["p2"].items()}
    svg = ['<?xml version="1.0" encoding="UTF-8"?>',
           f'<svg xmlns="http://www.w3.org/2000/svg" width="{int(lay["width"])}" '
           f'height="{int(lay["height"])}" viewBox="0 0 {int(lay["width"])} {int(lay["height"])}">',
           f'  <rect width="{int(lay["width"])}" height="{int(lay["height"])}" fill="#ffffff"/>',
           f'  <g stroke="{lay["colour"]}" stroke-width="{lay["line_width"]}" '
           'stroke-linecap="round" fill="none">']
    for (a, b), kind in sorted(style.items()):
        if kind != "solid":
            continue
        svg.append(f'    <line x1="{f(pts[a][0])}" y1="{f(pts[a][1])}" x2="{f(pts[b][0])}" y2="{f(pts[b][1])}"/>')
    svg.append('  </g>')
    svg.append(f'  <g stroke="{lay["colour"]}" stroke-width="{f(lay["line_width"] * 0.92)}" '
               f'stroke-linecap="butt" fill="none" stroke-dasharray="{f(lay["dash"][0])} {f(lay["dash"][1])}">')
    for (a, b), kind in sorted(style.items()):
        if kind != "dashed":
            continue
        svg.append(f'    <line x1="{f(pts[a][0])}" y1="{f(pts[a][1])}" x2="{f(pts[b][0])}" y2="{f(pts[b][1])}"/>')
    svg.append('  </g>')
    svg.append('  <g font-family="Times New Roman, Nimbus Roman, serif" font-style="italic" '
               f'font-size="{f(lay["font_size"])}" fill="{lay["colour"]}" text-anchor="middle">')
    for name, p in lay["p2"].items():
        dx, dy = lay["offsets"][name]
        px, py = lay["to_px"]((p[0] + dx, p[1] + dy))
        svg.append(f'    <text x="{f(px)}" y="{f(py + lay["font_size"] * 0.35)}">{name}</text>')
    svg.append('  </g>')
    svg.append('</svg>')
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(svg) + "\n", encoding="utf-8")
    return out


def build_compare(before_path, after_path, out_path, height=420, titles=("source", "redraw")):
    if Image is None:
        raise RuntimeError("Pillow is required")
    b = Image.open(before_path).convert("RGB")
    a = Image.open(after_path).convert("RGB")

    def fit(im, h):
        return im.resize((max(1, int(round(im.width * h / im.height))), h), Image.LANCZOS)

    b, a = fit(b, height), fit(a, height)
    pad, cap = 22, 34
    w = pad + b.width + 2 * pad + a.width + pad
    canvas = Image.new("RGB", (w, cap + height + pad), "white")
    canvas.paste(b, (pad, cap))
    canvas.paste(a, (pad + b.width + 2 * pad, cap))
    d = ImageDraw.Draw(canvas)
    font = _font(22)
    d.text((pad, 6), titles[0], font=font, fill=(90, 90, 90))
    d.text((pad + b.width + 2 * pad, 6), titles[1], font=font, fill=(90, 90, 90))
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, "PNG")
    return out, canvas.size


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description="Render a solid-geometry figure from a 3D model.")
    ap.add_argument("spec", type=Path, help="figure spec JSON (vertices + faces)")
    ap.add_argument("--out", type=Path, required=True, help="output PNG")
    ap.add_argument("--svg", type=Path, help="optional SVG sidecar")
    ap.add_argument("--before", type=Path, help="original crop, for the compare sheet")
    ap.add_argument("--compare", type=Path, help="output compare sheet")
    ap.add_argument("--no-check", action="store_true", help="skip the numeric report")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    spec = load_spec(args.spec)
    style, visible, _ = classify(spec)
    out, size = render_png(spec, args.out)
    hidden = sorted(k for k, v in style.items() if v == "dashed")
    vis_faces = [i for i, v in enumerate(visible) if v]

    lines = [f"PNG  {out}  {size[0]}x{size[1]}"]
    lines.append("visible faces: " + (", ".join("".join(spec['_faces'][i]) for i in vis_faces) or "none"))
    lines.append("hidden edges : " + (", ".join(a + b for a, b in hidden) or "none"))
    if args.svg:
        lines.append(f"SVG  {render_svg(spec, args.svg)}")
    if args.before and args.compare:
        cmp_out, cmp_size = build_compare(args.before, out, args.compare)
        lines.append(f"CMP  {cmp_out}  {cmp_size[0]}x{cmp_size[1]}")

    if not args.no_check:
        report, warnings = checks(spec)
        for name, dev in report["planarity"].items():
            lines.append(f"planar {name}: deviation {dev:.2e} {'OK' if dev < 1e-9 else 'NOT PLANAR'}")
        if report["sphere"]:
            s = report["sphere"]
            lines.append(f"sphere: centre {s['center']} R={s['radius']} "
                         f"max_dev={s['max_deviation']:.2e} agreement={s['agreement']}")
        if spec.get("expect"):
            lines.append("edge lengths: " + ", ".join(
                f"{k}={v:.4f}" for k, v in sorted(report["edges"].items()) if k in
                {"".join(sorted(n)) for n in spec["expect"]}))
        for w in warnings:
            lines.append("WARN " + w)

    if not args.quiet:
        print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
