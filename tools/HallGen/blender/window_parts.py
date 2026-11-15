"""One real window for one opening (the diamond lattice in every room, seedy glass): frame, lit pane, reflection and lead, all inside the
opening's existing rectangle, so nothing outside the old picture's footprint changes. No hole in the wall: the frame stands proud of it and the glass sits back in it, as
deep as vanilla's Solitude frames recess (11.5). Plain Python, so guildhall_gen and interior_gen can both call it.

Coordinates are the opening's own: x across from its centre, z up from its foot, y out of the wall toward whoever is looking. A wall W = (origin, right, normal), with
right x up = normal, takes (x, y, z) to  origin + right * (uc + x) + up * (z0 + z) + normal * (d + y):  see place(). Every face here is wound for that mapping.

    parts(kind, w, h, side, seed=0)  {key: [(points, uvs), ...]}: side "out" or "in", seed any whole number: it mirrors the picture and slides the normal map by whole quarries, so two
                             windows of a size differ and every quarry still lands inside the lead. Keys:
        wframe, sframe   the frame, timber or stone     (solid, but out of collision: the keys go in NOCOLL by exact name, as does everything else here)
        gpane            the lit pane                   (inside: its size's cell of make_seedy_glass's atlas, External Emittance on: the reference's region is its day and night)
        gcoat            the reflection layer           (window_lead.window_uv, for the quarries' normal map)
        glead            the lead, the room side only: it stands on an opaque pane
    place(faces, W, uc, z0, d)  the same, in world space
    python window_parts.py      self-test: exits 1 if a face looks the wrong way, a piece leaves the opening, or it read nothing"""
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from window_lead import STEP, TILE, axes, centre, clip, picture_uv, segments, window_uv

S = 256.0            # one texture tile, as guildhall_gen
COAT = 0.6           # the reflection, off the pane (its opaque layer behind it, so it can't fight)
LEAD = 1.4           # the lead's face off the pane: in front of the reflection, or the lead would wear the glass's shine
CAME_BASE, CAME_TOP = 1.7, 0.9   # a came's width at the glass and on its face: the bevel catches the light
STYLE = {  # kind: outside (frame key, ring width, how proud), inside. Timber storeys' windows already stand in real jambs, sill and lintel, so their ring only fills the corners
    "arched": (("sframe", 12, 11), ("wframe", 11, 9)), "gothic": (("wframe", 12, 9), ("wframe", 13, 9)), "fan": (("sframe", 8, 6), ("wframe", 8, 6)),
    "leaded": (("wframe", 7, 9), ("wframe", 9, 9)), "grid": (("wframe", 4, 9), ("wframe", 5, 7)),
    "small": (("wframe", 4, 9), ("wframe", 5, 7)), "panes": (("wframe", 5, 5), ("wframe", 5, 5))}


KIND_PATTERN = {"fan": "fan_knot", "gothic": "lights_knot"}                                  # the hall's two great windows; a dormer's cross is named by its caller
LIGHT = 15.0                                                                                # the great window's square panes
SIZES = [("arched", 110, 171), ("arched", 120, 186), ("gothic", 190, 308), ("leaded", 80, 160), ("leaded", 90, 180), ("leaded", 96, 192), ("grid", 84, 111),
         ("small", 60, 81), ("small", 76, 102), ("small", 122, 128), ("panes", 65, 196), ("fan", 223, 112)]    # every opening the hall has: each its cell in the glass atlas
CELLS = (4, 3); PAD = 0.012                                                                 # columns and rows; a cell's margin, so mips don't bleed across


def cell(kind, w, h):
    """the atlas rectangle (u0, v0, u1, v1) of an opening; an opening with no cell is a mistake, so it stops the build"""
    i = next(k for k, (a, b, c) in enumerate(SIZES) if a == kind and abs(b - w) < 1 and abs(c - h) < 1)
    col, row = i % CELLS[0], i // CELLS[0]
    return ((col + PAD) / CELLS[0], (row + PAD) / CELLS[1], (col + 1 - PAD) / CELLS[0], (row + 1 - PAD) / CELLS[1])


def outline(kind, w, h):
    """the opening, counter-clockwise from its foot, convex, as the old pictures' silhouettes: Solitude's arch springs at 63% of the height, the leaded head is chamfered"""
    x = w / 2
    if kind == "fan":
        n = 16
        return [(-x, 0), (x, 0)] + [(x * math.cos(math.pi * i / n), h * math.sin(math.pi * i / n)) for i in range(1, n)]
    if kind in ("arched", "gothic"):
        s = h * 0.63; n = 14
        return [(-x, 0), (x, 0), (x, s)] + [(x * math.cos(math.pi * i / n), s + (h - s) * math.sin(math.pi * i / n)) for i in range(1, n)] + [(-x, s)]
    if kind == "leaded":
        c, cz = 0.2 * w, 0.165 * h
        return [(-x, 0), (x, 0), (x, h - cz), (x - c, h), (-x + c, h), (-x, h - cz)]
    return [(-x, 0), (x, 0), (x, h), (-x, h)]


def inset(poly, d):
    """a convex counter-clockwise outline moved in by d: each edge shifted, neighbours met"""
    n = len(poly); lines = []
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]; L = math.dist(a, b); nx, nz = -(b[1] - a[1]) / L, (b[0] - a[0]) / L
        lines.append(((a[0] + nx * d, a[1] + nz * d), (b[0] - a[0], b[1] - a[1])))
    out = []
    for i in range(n):
        (p, u), (q, v) = lines[i - 1], lines[i]; det = u[0] * v[1] - u[1] * v[0]
        t = ((q[0] - p[0]) * v[1] - (q[1] - p[1]) * v[0]) / det
        out.append((p[0] + u[0] * t, p[1] + u[1] * t))
    return out


def strip_uv(pts, a, b):
    """grain along the edge a-b: u along it, v across, a tile 256 units"""
    L = math.dist(a, b); dx, dz = (b[0] - a[0]) / L, (b[1] - a[1]) / L
    return [((p[0] * dx + p[2] * dz) / S, (-p[0] * dz + p[2] * dx + p[1]) / S) for p in pts]


def ring(outer, inner, proud, stone=False):
    """the frame: its face, the reveal down to the glass, its outer side down to the wall. Stone is cut, so each edge starts the texture anew and the arch reads as voussoirs;
    timber runs one grain round the ring, or every facet of an arch would read as its own block"""
    faces = []; run = 0.0; wide = math.dist(outer[0], inner[0])
    for i in range(len(outer)):
        j = (i + 1) % len(outer); o0, o1, n0, n1 = outer[i], outer[j], inner[i], inner[j]; L = math.dist(o0, o1)
        P = lambda q, y: (q[0], y, q[1])
        f = [P(o0, proud), P(o1, proud), P(n1, proud), P(n0, proud)]
        r = [P(n1, 0), P(n0, 0), P(n0, proud), P(n1, proud)]
        s = [P(o0, 0), P(o1, 0), P(o1, proud), P(o0, proud)]
        if stone: faces += [(f, strip_uv(f, o0, o1)), (r, strip_uv(r, n0, n1)), (s, strip_uv(s, o0, o1))]
        else:
            a, b = run / S, (run + L) / S
            faces += [(f, [(a, 0), (b, 0), (b, wide / S), (a, wide / S)]), (r, [(b, proud / S), (a, proud / S), (a, 0), (b, 0)]), (s, [(a, 0.4), (b, 0.4), (b, 0.4 + proud / S), (a, 0.4 + proud / S)])]
        run += L
    return faces


def lead(opening, segs=None):
    """the cames, room side only: a flat face on two bevels. One direction stands a hair over the other, so crossing bars don't share a plane"""
    d1 = axes()[0]; faces = []
    for k_, (p, q) in enumerate(segments(opening) if segs is None else segs):
        L = math.dist(p, q); dx, dz = (q[0] - p[0]) / L, (q[1] - p[1]) / L; nx, nz = -dz, dx
        over = (0.12 if abs(dx * d1[0] + dz * d1[1]) > 0.999 else 0.0) if segs is None else 0.12 * (k_ & 1); top = LEAD + over
        if segs is not None: p, q = (p[0] - dx * 0.5, p[1] - dz * 0.5), (q[0] + dx * 0.5, q[1] + dz * 0.5)    # a curve's segments run past each other: their outer corners gape at every bend otherwise
        s = lambda c, w, y: (c[0] + nx * w / 2, y, c[1] + nz * w / 2)
        A, B = CAME_BASE, CAME_TOP
        for g in ([s(p, -B, top), s(q, -B, top), s(q, B, top), s(p, B, top)],          # the face (left of p-q is +n)
                  [s(p, -A, 0), s(q, -A, 0), s(q, -B, top), s(p, -B, top)],            # the bevel on the -n side
                  [s(q, A, 0), s(p, A, 0), s(p, B, top), s(q, B, top)]):               # on the +n side
            faces.append((g, [(g[k][0] * dx / 32 + g[k][2] * dz / 32, 0.02 * k) for k in range(4)]))
    return faces


def bar(p, q, width, proud):
    """a timber or stone glazing bar: its face and two sides, grain along it. Its ends die into what it meets"""
    L = math.dist(p, q); dx, dz = (q[0] - p[0]) / L, (q[1] - p[1]) / L; nx, nz = -dz * width / 2, dx * width / 2
    a0, b0, a1, b1 = (p[0] - nx, p[1] - nz), (q[0] - nx, q[1] - nz), (p[0] + nx, p[1] + nz), (q[0] + nx, q[1] + nz)
    P = lambda c, y: (c[0], y, c[1]); u = L / S; v = width / S
    return [([P(a0, proud), P(b0, proud), P(b1, proud), P(a1, proud)], [(0, 0), (u, 0), (u, v), (0, v)]),
            ([P(a0, 0), P(b0, 0), P(b0, proud), P(a0, proud)], [(0, 0.4), (u, 0.4), (u, 0.4 + proud / S), (0, 0.4 + proud / S)]),
            ([P(b1, 0), P(a1, 0), P(a1, proud), P(b1, proud)], [(u, 0.5), (0, 0.5), (0, 0.5 + proud / S), (u, 0.5 + proud / S)])]


def inside(a, b, g):
    """the part of a-b within the outline, as a one-item list, or nothing"""
    s = clip(a, b, g); return [s] if s and math.dist(*s) > 0.5 else []


def arc(cx, cz, rx, rz, a0, a1, n):
    pts = [(cx + rx * math.cos(a0 + (a1 - a0) * i / n), cz + rz * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]
    return list(zip(pts, pts[1:]))


def grid_segs(g, step=13.0):
    """square quarries, level and plumb, from the opening's middle"""
    c = centre(g); xs = [p[0] for p in g]; zs = [p[1] for p in g]; R_ = max(xs) - min(xs) + max(zs) - min(zs); segs = []
    for k in range(-40, 41):
        segs += inside((c[0] + k * step, c[1] - R_), (c[0] + k * step, c[1] + R_), g) + inside((c[0] - R_, c[1] + k * step), (c[0] + R_, c[1] + k * step), g)
    return segs


def spokes(g, cx, cz, r0x, r0z, n, a0=0.0, a1=math.pi):
    """bars fanning out of a hub, from its rim to the outline"""
    out = []
    for i in range(1, n):
        a = a0 + (a1 - a0) * i / n; c_, s_ = math.cos(a), math.sin(a)
        out += inside((cx + r0x * c_, cz + r0z * s_), (cx + 900 * c_, cz + 900 * s_), g)
    return out


def knot_head(g, cx, z0, rx, rz):
    """the guild's sunburst, the door's fanlight and the great window's head alike: three petals knotted through a ring in a hub, a double band round it, rays to a scalloped rim, short rays past it"""
    P = lambda a, r: (cx + rx * r * math.cos(a), z0 + rz * r * math.sin(a))
    def line(pts): return [s_ for a_, b_ in zip(pts, pts[1:]) for s_ in inside(a_, b_, g)]
    R1, R2, RIM = 0.34, 0.39, 0.78; n = 12; segs = []
    for r_ in (R1, R2): segs += line([P(math.pi * i / 24, r_) for i in range(25)])
    segs += line([P(math.pi * i / 16, R1 * 0.56) for i in range(17)])                            # the ring the petals pass through
    for ac in (math.pi / 6, math.pi / 2, 5 * math.pi / 6):
        for sgn in (-1, 1):
            segs += line([P(ac + sgn * 0.46 * math.sin(math.pi * k / 10), R1 * 0.94 * k / 10) for k in range(11)])
    for i in range(n):
        a0, a1 = math.pi * i / n, math.pi * (i + 1) / n; mid = (a0 + a1) / 2
        segs += line([P(a0 + (a1 - a0) * k / 8, RIM + 0.07 * math.sin(math.pi * k / 8)) for k in range(9)])   # a scallop
        segs += line([P(mid, RIM + 0.07), P(mid, 1.2)])                                          # a short ray past it
        if i: segs += line([P(a0, R2), P(a0, RIM)])                                               # a long ray
    return segs


def wedges(g, cx, z0, n):
    """the glass cut into n wedges from a point on its foot, each convex: each takes its own tilt, as a quarry does"""
    out = []
    def cut(poly, nx, nz):
        o = []
        for i in range(len(poly)):
            a, b = poly[i], poly[(i + 1) % len(poly)]; da = (a[0] - cx) * nx + (a[1] - z0) * nz; db = (b[0] - cx) * nx + (b[1] - z0) * nz
            if da >= 0: o.append(a)
            if da * db < 0: t = da / (da - db); o.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
        return o
    for i in range(n):
        a0, a1 = math.pi * i / n, math.pi * (i + 1) / n
        p = cut(cut(list(g), -math.sin(a0), math.cos(a0)), math.sin(a1), -math.cos(a1))
        if len(p) >= 3: out.append(p)
    return out


def spring(h):
    return h * 0.63


def head_coat(polys, W_, y, seed):
    """the reflection over each piece of glass: a whole quarry of the normal map each, a different one, so each piece leans its own way"""
    out = []
    for i, p in enumerate(polys):
        cu, cv = ((i * 5 + seed) % TILE + 0.5) / TILE, ((i * 7 + (seed >> 3)) % TILE + 0.5) / TILE
        out.append(([(x, y, z) for x, z in p], [(cu + x / (W_ * TILE * 1.3), cv + z / (W_ * TILE * 1.3)) for x, z in p]))
    return out


def pattern_parts(name, g, w, h):
    """(lead segments, timber bars) of a pattern over the glass g. Sizes follow the opening, so a pattern fits whichever window it is given"""
    xs = [p[0] for p in g]; zs = [p[1] for p in g]; x0, x1, z0, z1 = min(xs), max(xs), min(zs), max(zs); W_, H_ = x1 - x0, z1 - z0; cx = (x0 + x1) / 2
    if name == "square": return grid_segs(g), []
    if name == "fan_knot": return knot_head(g, cx, z0, W_ / 2, H_), []
    if name == "lights_knot":    # three tall lights of square panes under the sunburst
        s = spring(h); b = bar((x0, s), (x1, s), 7.0, 5.0) + bar((cx - W_ / 6, z0), (cx - W_ / 6, s), 5.0, 5.0) + bar((cx + W_ / 6, z0), (cx + W_ / 6, s), 5.0, 5.0)
        return grid_segs([(x0, z0), (x1, z0), (x1, s), (x0, s)], LIGHT) + knot_head(g, cx, s, W_ / 2, z1 - s), b
    if name == "fan_radial":     # a sunburst: bars rising from a half round over the door's middle
        return arc(cx, z0, W_ * 0.17, H_ * 0.34, 0, math.pi, 10) + spokes(g, cx, z0, W_ * 0.17, H_ * 0.34, 10), []
    if name == "fan_web":        # a spider's web: fewer bars, crossed by two arcs
        return spokes(g, cx, z0, W_ * 0.12, H_ * 0.24, 6) + arc(cx, z0, W_ * 0.12, H_ * 0.24, 0, math.pi, 10) + arc(cx, z0, W_ * 0.29, H_ * 0.58, 0, math.pi, 16) + arc(cx, z0, W_ * 0.42, H_ * 0.84, 0, math.pi, 20), []
    if name == "tracery":        # two lancets under a rose, in timber, the diamond's lead in the lights
        s = z0 + H_ * 0.60; rc = (cx, s + H_ * 0.16); r = W_ * 0.19; b = []
        for p, q in [((cx, z0), (cx, s))] + arc(rc[0], rc[1], r, r, 0, 2 * math.pi, 16) + [((cx, s), (cx - r * 0.72, rc[1] - r * 0.72)), ((cx, s), (cx + r * 0.72, rc[1] - r * 0.72))] + \
                [((x0, s - H_ * 0.03), (cx - r * 0.98, rc[1] - r * 0.2)), ((x1, s - H_ * 0.03), (cx + r * 0.98, rc[1] - r * 0.2))]:
            b += bar(p, q, 5.0, 5.0)
        return segments(g), b
    if name == "lights":         # three tall lights of square panes under a sunburst head
        s = z0 + H_ * 0.60; b = bar((x0, s), (x1, s), 7.0, 5.0) + bar((cx - W_ / 6, z0), (cx - W_ / 6, s), 5.0, 5.0) + bar((cx + W_ / 6, z0), (cx + W_ / 6, s), 5.0, 5.0)
        low = grid_segs([(x0, z0), (x1, z0), (x1, s), (x0, s)], 15.0)
        return low + arc(cx, s, W_ * 0.16, W_ * 0.16, 0, math.pi, 10) + spokes(g, cx, s, W_ * 0.16, W_ * 0.16, 8), b
    if name in ("cross", "cross_diamond"):     # a casement's timber cross, with small plain panes or the diamond between
        tz = z0 + H_ * 0.62; b = bar((cx, z0), (cx, z1), 5.0, 4.5) + bar((x0, tz), (x1, tz), 5.0, 4.5)
        return (segments(g) if name == "cross_diamond" else grid_segs(g, 26.0)), b
    raise ValueError(name)


def atlas_uv(x, z, g, kind, w, h, flip):
    """picture_uv squeezed into the opening's cell; flip mirrors it, which the lattice allows: it is symmetric about the opening's axis"""
    u, v = picture_uv(x, z, g); a, b, c_, d = cell(kind, w, h)
    return (a + (1 - u if flip else u) * (c_ - a), b + v * (d - b))


def parts(kind, w, h, side, seed=0, pattern=None):
    frame, width, proud = STYLE[kind][0 if side == "out" else 1]
    o = outline(kind, w, h); g = inset(o, width); c = centre(g); flip = seed & 1; su, sv = (seed >> 1) % TILE / TILE, (seed >> 4) % TILE / TILE
    pts = lambda y: [(x, y, z) for x, z in g]
    lit = [(pts(0), [atlas_uv(x, z, g, kind, w, h, flip) for x, z in g])]
    out = {frame: ring(o, g, proud, frame == "sframe"), "gpane": lit, "gcoat": [(pts(COAT), [(window_uv(x, z, c)[0] + su, window_uv(x, z, c)[1] + sv) for x, z in g])], "glead": lead(g)}
    pattern = pattern or KIND_PATTERN.get(kind)
    if pattern and pattern != "diamond":
        segs, bars_ = pattern_parts(pattern, g, w, h); out["glead"] = lead(g, segs); out.setdefault("wframe", []).extend(bars_)
        xs = [p[0] for p in g]; x0, x1, z0 = min(xs), max(xs), min(p[1] for p in g); cx = (x0 + x1) / 2
        if pattern == "fan_knot": out["gcoat"] = head_coat(wedges(g, cx, z0, 12), x1 - x0, COAT, seed)
        elif pattern == "lights_knot":
            s = spring(h); low = [(x0, z0), (x1, z0), (x1, s), (x0, s)]
            out["gcoat"] = [([(x, COAT, z) for x, z in low], [((x - cx) / LIGHT / TILE + su, (z - z0) / LIGHT / TILE + sv) for x, z in low])] + head_coat(wedges(g, cx, s, 12), x1 - x0, COAT, seed)
        if pattern in ("fan_knot", "lights_knot"): pass
        elif pattern == "square":                                                               # the quarries' tilts square with the lead
            out["gcoat"] = [(pts(COAT), [((x - c[0]) / 13.0 / TILE + su, (z - c[1]) / 13.0 / TILE + sv) for x, z in g])]
        elif not pattern.endswith("diamond") and pattern != "tracery":                         # no lattice to fall in with: one quarry's tilt, the ripple alone
            out["gcoat"] = [(pts(COAT), [(x / (w * TILE) + su, z / (h * TILE) + sv) for x, z in g])]
    return out


def hood(kind, w, h, wide, proud):
    """the jamb carried round the head, outside the opening: a head with only the frame's ring reads thinner than sides with a jamb beside it. Ends on the jambs at the springing"""
    s = spring(h); pts = outline(kind, w, h)[2:]                                                   # the outline from the right springing, over the head, to the left
    out_ = [(w / 2 + wide) * math.cos(math.pi * i / (len(pts) - 1)) for i in range(len(pts))], [s + (h - s + wide) * math.sin(math.pi * i / (len(pts) - 1)) for i in range(len(pts))]
    outer = list(zip(*out_)); faces = []; run = 0.0
    for i in range(len(pts) - 1):
        a, b, c, d = outer[i], outer[i + 1], pts[i + 1], pts[i]; L = math.dist(a, b); u0, u1 = run / S, (run + L) / S
        P = lambda q, y: (q[0], y, q[1])
        f = [P(a, proud), P(b, proud), P(c, proud), P(d, proud)]; faces.append((f, [(u0, 0), (u1, 0), (u1, wide / S), (u0, wide / S)]))
        e = [P(a, 0), P(b, 0), P(b, proud), P(a, proud)]; faces.append((e, [(u0, 0.4), (u1, 0.4), (u1, 0.4 + proud / S), (u0, 0.4 + proud / S)]))
        run += L
    return faces


def pane(kind, x, z, g, h):
    """which piece of glass a point of the opening lies in, and how far toward its lead: the atlas's quarries, whichever pattern the kind has: (i, j, 0 at its middle .. 1 on a bar)"""
    if KIND_PATTERN.get(kind) == "lights_knot":
        s = spring(h); cx = centre(g)[0]
        if z < s:
            u, v = (x - cx) / LIGHT, z / LIGHT; return math.floor(u), math.floor(v), max(abs(u - math.floor(u) - 0.5), abs(v - math.floor(v) - 0.5)) * 2
        a = math.atan2(z - s, x - cx) / math.pi * 12; return math.floor(a), 40, abs(a - math.floor(a) - 0.5) * 2
    if KIND_PATTERN.get(kind) == "fan_knot":
        a = math.atan2(max(z, 0.01), x - centre(g)[0]) / math.pi * 12; return math.floor(a), 41, abs(a - math.floor(a) - 0.5) * 2
    return quarry(x, z, centre(g))


def quarry(x, z, c):
    """which quarry a point of the opening lies in, and how far toward its lead: (i, j, 0 at its middle .. 1 on a bar)"""
    u, v = window_uv(x, z, c); u, v = u * TILE, v * TILE
    return math.floor(u), math.floor(v), max(abs(u - math.floor(u) - 0.5), abs(v - math.floor(v) - 0.5)) * 2


def place(faces, W, uc, z0, d):
    o, r, n = W; up = r.__class__((0, 0, 1))
    return [([o + r * (uc + x) + up * (z0 + z) + n * (d + y) for x, y, z in pts], uvs) for pts, uvs in faces]


def newell(p):
    n = [0.0, 0.0, 0.0]
    for i in range(len(p)):
        a, b = p[i - 1], p[i]
        n[0] += (a[1] - b[1]) * (a[2] + b[2]); n[1] += (a[2] - b[2]) * (a[0] + b[0]); n[2] += (a[0] - b[0]) * (a[1] + b[1])
    return n


if __name__ == "__main__":
    # a wall facing +y in the world: right = -x, so right x up = +y. Faces are tested in the world, where poly() takes their winding from
    world = lambda p: (-p[0], p[1], p[2]); bad = tris = 0
    for kind, w, h in (("arched", 120, 186), ("arched", 110, 171), ("gothic", 190, 308), ("leaded", 96, 192), ("leaded", 80, 160), ("grid", 84, 111), ("small", 60, 81), ("small", 122, 128), ("panes", 65, 196), ("fan", 223, 112)):
        for side in ("out", "in"):
            P = parts(kind, w, h, side, 0, "diamond"); tris_w = 0                                # (the frame's own faces: patterns are tested below)
            for key, faces in P.items():
                for pts, uvs in faces:
                    tris_w += len(pts) - 2; W = [world(p) for p in pts]; n = newell(W); c = [sum(q[i] for q in W) / len(W) for i in range(3)]
                    if len(uvs) != len(pts): bad += 1; print("BAD uv count", kind, key)
                    for p in pts:
                        if abs(p[0]) > w / 2 + 1e-6 or p[2] < -1e-6 or p[2] > h + 1e-6: bad += 1; print("BAD leaves the opening", kind, key, p)
                    # every piece looks toward the viewer's half: nothing faces the wall. A side wall faces along x or z only
                    if n[1] < -1e-6: bad += 1; print("BAD faces the wall", kind, side, key, n)
                    if key in ("gpane", "gcoat") and n[1] <= 0: bad += 1; print("BAD glass", kind, key, n)
                    if key.endswith("frame") and abs(n[1]) < 1e-6 and n[1] == 0:           # reveal or outer side: outward from its own ring's solid
                        pass
            for key in ("wframe", "sframe"):                                                # a reveal looks at the opening's centre, an outer side away from it
                if key not in P: continue
                frames = P[key]; cx, cz = 0.0, h * 0.45
                for i, (pts, uvs) in enumerate(frames):
                    if i % 3 == 0: continue
                    W = [world(p) for p in pts]; n = newell(W); c = [sum(q[i_] for q in W) / len(W) for i_ in range(3)]
                    to = (-cx - c[0], 0, cz - c[2]); dot = n[0] * to[0] + n[2] * to[2]
                    if (i % 3 == 1 and dot < 0) or (i % 3 == 2 and dot > 0): bad += 1; print("BAD frame winding", kind, side, key, i)
            tris += tris_w; print(f"{kind} {w}x{h} {side}: {tris_w} triangles")
    for kind, w, h in SIZES:                                                                # the seeds' whole-quarry slide keeps the cell lines on the bars
        P = parts(kind, w, h, "in", 0b1010011); Q = parts(kind, w, h, "in", 0); a, b, c_, d = cell(kind, w, h)
        for (pt, uv), (_, uv0) in zip(P["gcoat"], Q["gcoat"]):
            for p, q in zip(uv, uv0):
                if abs((p[0] - q[0]) * TILE - round((p[0] - q[0]) * TILE)) > 1e-6: bad += 1; print("BAD seed slides off the lattice", kind)
        for u, v in P["gpane"][0][1]:
            if not (a - 1e-9 <= u <= c_ + 1e-9 and b - 1e-9 <= v <= d + 1e-9): bad += 1; print("BAD outside its cell", kind, w, h)
    for pat, kind, w, h in (("square", "grid", 84, 111), ("cross", "grid", 84, 111), ("cross_diamond", "grid", 84, 111), ("fan_radial", "fan", 223, 112), ("fan_web", "fan", 223, 112), ("tracery", "gothic", 190, 308), ("lights", "gothic", 190, 308), ("fan_knot", "fan", 223, 112), ("lights_knot", "gothic", 190, 308)):
        P = parts(kind, w, h, "out", 0, pat); n_ = 0
        for key, faces in P.items():
            for pts, uvs in faces:
                n_ += len(pts) - 2
                if len(uvs) != len(pts): bad += 1; print("BAD uv count", pat, key)
                if newell([world(p) for p in pts])[1] < -1e-6: bad += 1; print("BAD faces the wall", pat, key)
                for p in pts:
                    if abs(p[0]) > w / 2 + 1e-6 or p[2] < -1e-6 or p[2] > h + 1e-6: bad += 1; print("BAD leaves the opening", pat, key, p)
        if not P["glead"]: bad += 1; print("BAD no lead", pat)
        print(f"{pat} on {kind} {w}x{h}: {n_} triangles")
    H_ = hood("gothic", 190, 308, 18, 8)
    for pts, uvs in H_:
        if newell([world(p) for p in pts])[1] < -1e-6: bad += 1; print("BAD hood faces the wall")
        if abs(min(p[2] for p in pts)) < spring(308) - 1: bad += 1; print("BAD hood below the springing")
    if not H_: bad += 1; print("BAD no hood")
    print(f"PARTS {tris} triangles over the samples, {bad} bad")
    if not tris: print("FAIL PARTS read nothing")
    sys.exit(1 if bad or not tris else 0)
