"""Generates the Cairn logo SVGs (variant A4c of the Cairn logo canvas).

A cairn of three flat-shaded, low-poly stones topped by a tilted 3D cube (the guide on top of the pile is the
object being made), an orbit ring with two keyframes around the bottom stone (a turntable camera path),
viewfinder brackets at the bottom left and top right, and the record dot at the bottom right.
Faces are computed, not stroked: outer edges stay on the shape's lines, faces are separated by a constant
seam, and corners are rounded with quadratic curves.
Run: py -I make_logo.py   (writes the SVGs next to this file; then copy logo-icon.svg to web/public/logo.svg
and docs/assets/logo.svg, and run make_icons.py)
"""
import math
from pathlib import Path

# Isometric cube in a 128 x 128 box, scaled down onto the cairn.
T, UR, LR, B, LL, UL, C = (64, 30), (92, 46), (92, 78), (64, 94), (36, 78), (36, 46), (64, 62)
FACES = {  # vertices in order, and whether each edge v[i] -> v[i+1] is an inner seam
    "left": ([UL, C, B, LL], [True, True, False, False]),
    "right": ([UR, LR, B, C], [False, False, True, True]),
    "top": ([T, UR, C, UL], [False, True, True, False]),
}
FACE_COLORS = {"left": "#e07b2e", "right": "#b5520e", "top": "#f2a35a"}
STONE_COLORS = ("#c3c8d4", "#8f97aa", "#646c80")  # top, front-left, front-right: same light as the cube
STONES = [(64, 34, 11, 1.5), (61, 25, 9, -1.5), (65, 17, 7, 1.0)]  # center x, half width, half height, tilt; bottom up
STONE_GAP, CUBE_SCALE, CUBE_TILT = 1.2, 0.45, -16
RING = (40, 14)  # orbit radii around the bottom stone
KEYS = [(-16, 4.6), (20, 3.6)]  # keyframes on the front of the ring: x offset from the stone's center, half size
BRACKETS = "M14 84 V100 A14 14 0 0 0 28 114 H44 M84 14 H100 A14 14 0 0 1 114 28 V44"
DOT, KEY = "#f08080", "#f2a35a"
INK_ON_DARK, INK_ON_LIGHT = "#e6e9f0", "#1c2232"
BRACKET_ON_DARK, BRACKET_ON_LIGHT = "#9aa3b8", "#5b6378"
ACCENT_ON_DARK, ACCENT_ON_LIGHT = "#f2a35a", "#b5520e"


def _sub(a, b): return (a[0] - b[0], a[1] - b[1])
def _add(a, b): return (a[0] + b[0], a[1] + b[1])
def _mul(a, k): return (a[0] * k, a[1] * k)
def _unit(a): n = math.hypot(*a); return (a[0] / n, a[1] / n)


def _intersect(l1, l2):
    (p, d), (q, e) = l1, l2
    t = ((q[0] - p[0]) * e[1] - (q[1] - p[1]) * e[0]) / (d[0] * e[1] - d[1] * e[0])
    return _add(p, _mul(d, t))


def face_path(vertices, seams, gap, r_out, r_in):
    """Convex face outline with seam edges pushed inward by gap/2 and every corner rounded."""
    cx = sum(p[0] for p in vertices) / len(vertices)
    cy = sum(p[1] for p in vertices) / len(vertices)
    lines = []
    for i, a in enumerate(vertices):
        d = _unit(_sub(vertices[(i + 1) % len(vertices)], a))
        n = (-d[1], d[0])
        if (cx - a[0]) * n[0] + (cy - a[1]) * n[1] < 0:
            n = (-n[0], -n[1])
        lines.append((_add(a, _mul(n, gap / 2 if seams[i] else 0)), d))
    count = len(vertices)
    corners = [_intersect(lines[i - 1], lines[i]) for i in range(count)]
    fmt = lambda q: f"{q[0]:.2f} {q[1]:.2f}"
    rounded = []
    for i, p in enumerate(corners):
        r = r_in if (seams[i - 1] or seams[i]) else r_out
        rounded.append((_add(p, _mul(_unit(_sub(corners[i - 1], p)), r)), p,
                        _add(p, _mul(_unit(_sub(corners[(i + 1) % count], p)), r))))
    d = f"M{fmt(rounded[0][2])}"
    for i in range(1, count + 1):
        a, p, b = rounded[i % count]
        d += f" L{fmt(a)} Q{fmt(p)} {fmt(b)}"
    return d + " Z"


def stone_facets(cx, cy, w, h, tilt):
    """Blunt octagonal pebble split into a lit top facet and two shaded front facets (all convex)."""
    t = lambda x, y: (cx + x * w, cy + y * h - tilt * x)  # tilt raises the right end
    LU, TL, TR, RU = t(-1, -0.2), t(-0.55, -1), t(0.5, -0.95), t(1, -0.25)
    RD, BR, BL, LD = t(0.9, 0.5), t(0.45, 1), t(-0.55, 1), t(-0.95, 0.5)
    K = t(0.1, 0.15)  # ridge point where the three facets meet
    return [
        ([LU, TL, TR, RU, K], [False, False, False, True, True]),
        ([LU, K, BR, BL, LD], [True, True, False, False, False]),
        ([K, RU, RD, BR], [True, False, False, True]),
    ]


def cairn(ring_color, small=False):
    """The cairn, its bottom stone resting on y = 110. Returns (svg, top y, keyframe centers)."""
    seam, r_out, ring_w = (3, 4, 4.5) if small else (2, 3.5, 3.2)
    parts, keys, bottom = [], [], 110
    for i, (cx, w, h, tilt) in enumerate(STONES):
        cy = bottom - h
        stone = "".join(f'<path d="{face_path(v, s, seam, r_out, 0.8)}" fill="{c}"/>'
                        for (v, s), c in zip(stone_facets(cx, cy, w, h, tilt), STONE_COLORS))
        if i == 0:  # orbit: back half behind the stone, front half and keyframes over it
            (rx, ry), y = RING, cy + 1
            ring = f'fill="none" stroke="{ring_color}" stroke-linecap="round"'
            parts.append(f'<path d="M{cx - rx} {y} A{rx} {ry} 0 0 1 {cx + rx} {y}" {ring} stroke-width="{ring_w - 0.2}" opacity="0.5"/>')
            stone += f'<path d="M{cx + rx} {y} A{rx} {ry} 0 0 1 {cx - rx} {y}" {ring} stroke-width="{ring_w}"/>'
            for dx, k in KEYS:
                kx, ky = cx + dx, y + ry * math.sqrt(1 - (dx / rx) ** 2)
                keys.append((kx, ky))
                stone += f'<path d="M{kx:.1f} {ky - k:.1f} l{k} {k} l{-k} {k} l{-k} {-k} Z" fill="{KEY}"/>'
        parts.append(stone)
        bottom = cy - h - STONE_GAP
    dy = bottom + 2.2  # the top stone is curved: the cube's point sinks a little into the gap
    cube = "".join(f'<path d="{face_path([(66 + (x - 64) * CUBE_SCALE, dy + (y - 94) * CUBE_SCALE) for x, y in v], s, seam * 0.9, 2.1, 0.8)}" '
                   f'fill="{FACE_COLORS[k]}"/>' for k, (v, s) in FACES.items())
    parts.append(f'<g transform="rotate({CUBE_TILT} 66 {dy:.1f})">{cube}</g>')
    return "".join(parts), dy - 64 * CUBE_SCALE, keys


def icon_body(bracket_color, small=False):
    body, top, _ = cairn(bracket_color, small)
    mid = (top + 110) / 2
    if small:  # favicon and tray: no brackets, bigger cairn and dot
        return (f'<g transform="translate(62 60) scale(0.88) translate(-64 {-mid:.1f})">{body}</g>'
                f'<circle cx="106" cy="106" r="12" fill="{DOT}"/>')
    return (f'<path d="{BRACKETS}" fill="none" stroke="{bracket_color}" stroke-width="6.5" stroke-linecap="round"/>'
            f'<g transform="translate(64 64) scale(0.8) translate(-64 {-mid:.1f})">{body}</g>'
            f'<circle cx="104" cy="104" r="9" fill="{DOT}"/>')


def icon_svg(bracket_color, small=False):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" role="img" aria-label="Cairn">'
            f'{icon_body(bracket_color, small)}</svg>\n')


def wordmark_svg(bracket_color, ink, accent):
    font = 'font-family="Outfit, \'Segoe UI\', sans-serif"'
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 440 128" role="img" aria-label="Cairn">'
            f'{icon_body(bracket_color)}'
            f'<text x="146" y="78" {font} font-weight="700" font-size="64" letter-spacing="-1" fill="{ink}">Cairn</text>'
            f'<text x="149" y="106" {font} font-weight="600" font-size="15" letter-spacing="5.2" fill="{accent}">3D PRODUCTION</text>'
            '</svg>\n')


def _self_check():
    top_face = face_path(*FACES["top"], gap=4, r_out=0, r_in=0)
    assert top_face.startswith("M64.00 30.00"), top_face  # outer corners do not move
    _, top, keys = cairn(BRACKET_ON_DARK)
    assert 15 < top < 40, top  # the tilted cube stays clear of the top-right bracket after fitting
    assert all(k[1] < 118 for k in keys), keys  # keyframes stay inside the box


if __name__ == "__main__":
    _self_check()
    out = Path(__file__).parent
    files = {
        "logo-icon.svg": icon_svg(BRACKET_ON_DARK),
        "logo-icon-on-light.svg": icon_svg(BRACKET_ON_LIGHT),
        "logo-icon-small.svg": icon_svg(BRACKET_ON_DARK, small=True),
        "logo.svg": wordmark_svg(BRACKET_ON_LIGHT, INK_ON_LIGHT, ACCENT_ON_LIGHT),
        "logo-on-dark.svg": wordmark_svg(BRACKET_ON_DARK, INK_ON_DARK, ACCENT_ON_DARK),
    }
    for name, text in files.items():
        (out / name).write_text(text, encoding="utf-8")
        print("wrote", name)
