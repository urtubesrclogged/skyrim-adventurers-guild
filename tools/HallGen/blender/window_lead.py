"""The diamond lattice for a window opening (used in every room): the lead as real bars, the pane as one flat polygon, with the UVs that put
make_seedy_glass.py's quarries between the bars. Plain Python, so guildhall_gen and interior_gen can both call it.

Coordinates are the window's own plane: x across, z up, in game units. The outline must be convex (the hall's openings are: chamfered, cambered and round heads).
No piece here may collide: the 2026-10-30 Havok CTD was glass in the collision, so every key that takes these goes in NOCOLL by its exact name.

    bars, tris = lead_bars(outline, width, proud)   a list of quads and the triangle count; long straight bars, end to end, never one piece per quarry
    uv = window_uv(x, z, centre)                    for the normal map
    picture_uv(x, z, outline)                       for the lit layer: 0..1 over the opening
    python window_lead.py                           self-test: exits 1 if a bar leaves the outline or a cell misses the lead"""
import math, sys

STEP = 15.5     # between bars, square to them, as the design sheet's diamond
ANGLE = 62.0    # a bar's rise from the horizontal: tall diamonds
TILE = 6        # quarries across the texture: keep equal to make_seedy_glass.LATTICE


def axes():
    """the two bar directions, and the unit normal of each"""
    a = math.radians(ANGLE); d1, d2 = (math.cos(a), math.sin(a)), (-math.cos(a), math.sin(a))
    return d1, d2, (-d1[1], d1[0]), (-d2[1], d2[0])


def clip(p, q, poly):
    """Cyrus-Beck: the part of p-q inside the convex poly (either winding)"""
    area = sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1] for i in range(len(poly)))
    s = 1.0 if area > 0 else -1.0; t0, t1 = 0.0, 1.0; dx, dz = q[0] - p[0], q[1] - p[1]
    for i, a in enumerate(poly):
        b = poly[(i + 1) % len(poly)]; nx, nz = -(b[1] - a[1]) * s, (b[0] - a[0]) * s
        d = nx * dx + nz * dz; w = nx * (p[0] - a[0]) + nz * (p[1] - a[1])
        if abs(d) < 1e-9:
            if w < 0: return None
            continue
        t = -w / d
        if d > 0: t0 = max(t0, t)
        else: t1 = min(t1, t)
        if t0 >= t1: return None
    return (p[0] + t0 * dx, p[1] + t0 * dz), (p[0] + t1 * dx, p[1] + t1 * dz)


def centre(outline):
    xs = [p[0] for p in outline]; zs = [p[1] for p in outline]
    return (min(xs) + max(xs)) / 2, (min(zs) + max(zs)) / 2


def segments(outline):
    """the bars as line segments inside the outline"""
    c = centre(outline); d1, d2, n1, n2 = axes(); R = max(math.hypot(p[0] - c[0], p[1] - c[1]) for p in outline) * 1.1; out = []
    for d, n in ((d1, n1), (d2, n2)):
        for k in range(-int(R / STEP) - 1, int(R / STEP) + 2):
            o = (c[0] + n[0] * STEP * k, c[1] + n[1] * STEP * k)
            s = clip((o[0] - d[0] * R, o[1] - d[1] * R), (o[0] + d[0] * R, o[1] + d[1] * R), outline)
            if s and math.dist(*s) > 0.5: out.append(s)
    return out


def lead_bars(outline, width=1.5, proud=0.7):
    """each bar a low box with no ends (the frame hides them): three faces a side, front and back of the glass. Quads of (x, y, z), y out of the pane"""
    quads = []
    for p, q in segments(outline):
        L = math.dist(p, q); nx, nz = -(q[1] - p[1]) / L * width / 2, (q[0] - p[0]) / L * width / 2
        for s in (proud, -proud):
            a, b, c, d = (p[0] + nx, s, p[1] + nz), (q[0] + nx, s, q[1] + nz), (q[0] - nx, s, q[1] - nz), (p[0] - nx, s, p[1] - nz)
            ax, bx, cx, dx = (a[0], 0, a[2]), (b[0], 0, b[2]), (c[0], 0, c[2]), (d[0], 0, d[2])
            quads += [(a, b, c, d) if s > 0 else (d, c, b, a), (ax, bx, b, a) if s > 0 else (a, b, bx, ax), (d, c, cx, dx) if s > 0 else (dx, cx, c, d)]
    return quads, len(quads) * 2


def window_uv(x, z, c):
    """lattice coordinates: one quarry is 1/TILE of the texture, its edges on the bars"""
    d1, d2, n1, n2 = axes(); px, pz = x - c[0], z - c[1]
    return ((px * n2[0] + pz * n2[1]) / STEP + 0.5) / TILE, ((px * n1[0] + pz * n1[1]) / STEP + 0.5) / TILE


def picture_uv(x, z, outline):
    xs = [p[0] for p in outline]; zs = [p[1] for p in outline]
    return (x - min(xs)) / (max(xs) - min(xs)), 1 - (z - min(zs)) / (max(zs) - min(zs))


if __name__ == "__main__":
    W, H, CH = 95.0, 190.0, 20.0
    o = [(-W / 2, 0), (W / 2, 0), (W / 2, H - CH), (W / 2 - CH, H), (-W / 2 + CH, H), (-W / 2, H - CH)]
    segs = segments(o); q, t = lead_bars(o); bad = 0
    for p, r in segs:
        for v in (p, r):
            if not (-W / 2 - 1e-6 <= v[0] <= W / 2 + 1e-6 and -1e-6 <= v[1] <= H + 1e-6): bad += 1
    # a bar's line must fall on a whole number of cells in UV: the cells' edges are the bars, and every UV stays finite
    c = centre(o); d1, d2, n1, n2 = axes(); off = 0
    for k in range(-3, 4):
        x, z = c[0] + n1[0] * STEP * k + d1[0] * 7, c[1] + n1[1] * STEP * k + d1[1] * 7
        v = window_uv(x, z, c)[1] * TILE - 0.5
        if abs(v - round(v)) > 1e-6: off += 1
    print(f"LEAD {len(segs)} bars, {t} triangles a window; {bad} ends outside, {off} bars off the cell lines")
    if not len(segs): print("FAIL LEAD read nothing")
    sys.exit(1 if bad or off or not segs else 0)
