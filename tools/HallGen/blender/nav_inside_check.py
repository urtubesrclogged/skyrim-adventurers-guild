"""Does the navmesh run inside a piece? (2026-11-04: Henriette found standing on the dining table; navgen had skipped every piece missing
from furniture_check.py's footprint table, so the basement's navmesh ran under its tables, targets, dummies, workbench and casks. An actor
put on navmesh inside a piece stands inside it, and the game lifts it out on top.) Every solid piece the export places, by its measured
footprint (furniture_check.py's) or else its record's bounds (records.json beside the export), shrunk by EDGE (a table's unused sides grown by an actor's radius instead); the navmesh sampled every
S inside each triangle; a sample inside a footprint at the piece's floor fails. Fails also when it read no piece or no triangle.
    python nav_inside_check.py <nav_*.json> <hall2_*.json>     exit 1 on navmesh inside a piece"""
import re, sys, os, json, math
nav, src = json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))
EDGE, S, HEIGHT, RADIUS = 6.0, 6.0, 90.0, 14.0
H = lambda p: (p[1], -p[0], p[2])
fc = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "furniture_check.py"), encoding="utf-8").read(); ns = {}
exec(fc[fc.index("FP = {"):fc.index("def rot(yaw):")], ns); FP, EXTRA = ns["FP"], ns["EXTRA"]
rp = os.path.join(os.path.dirname(os.path.abspath(sys.argv[2])), "records.json")
REC = json.load(open(rp)) if os.path.exists(rp) else {}
NOBLOCK_T = {"Door", "Weapon", "Ammunition", "MiscItem", "Book", "Flora", "Ingestible", "Ingredient", "Key", "SoulGem", "Scroll", "Armor", "Light"}
NOBLOCK_M = re.compile(r"(?i)^meshes[\\/]effects[\\/]")    # (effects: glows, fog, light shafts; no collision in game)
boxes = []                                    # (name, cx, cy, ex, ey, scale, a0, b0, a1, b1, z0, z1)
for p in src["pieces"]:
    ed = p.get("ed") or os.path.basename(p["model"]); x, y, z = H(p["pos"]); s = p.get("scale", 1.0)
    a = math.radians(p["yaw"] + 90); ex, ey = (math.cos(a), -math.sin(a)), (math.sin(a), math.cos(a))
    if ed in FP:
        if not FP[ed] or not FP[ed][0]: continue
        ents = FP[ed][1]
        for bx in [FP[ed][0]] + EXTRA.get(ed, []):
            a0, b0, a1, b1 = bx
            if min(a1 - a0, b1 - b0) * s >= 70:      # (a table, big enough to stand on: on its unused sides, no navmesh within an actor's
                m = RADIUS + EDGE                     # radius of it, so an actor stood there never overlaps it: Henriette's table end)
                a0 -= 0 if any(e < bx[0] for e, _ in ents) else m / s; a1 += 0 if any(e > bx[2] for e, _ in ents) else m / s
                b0 -= 0 if any(e < bx[1] for _, e in ents) else m / s; b1 += 0 if any(e > bx[3] for _, e in ents) else m / s
            boxes.append((ed, x, y, ex, ey, s, a0, b0, a1, b1, z - 10, z + HEIGHT))
    elif ed in REC:
        r = REC[ed]
        if r.get("type") in NOBLOCK_T or (r.get("type") == "Activator" and "Water" in ed) or NOBLOCK_M.match(p["model"]): continue
        x0, y0, z0, x1, y1, z1 = r["obnd"]
        if (z1 - z0) * s <= 26 or x1 <= x0 or y1 <= y0: continue   # (no more than a step, navgen's STEP: walked over, as a flat sack;
                                                                 # what hangs high: its heights are its own, over no floor sample)
        boxes.append((ed, x, y, ex, ey, s, x0, y0, x1, y1, z + z0 * s - 10, z + z1 * s))
V = [H(v) for v in nav["verts"]]; T = nav["tris"]
if not boxes or not T: print(f"NAV INSIDE FAIL: read {len(boxes)} pieces and {len(T)} triangles"); sys.exit(1)
def local(b, px, py):                         # a point in the piece's own frame (the inverse of navgen's placement)
    _, x, y, ex, ey, s = b[:6]; dx, dy = (px - x) / s, (py - y) / s
    det = ex[0] * ey[1] - ey[0] * ex[1]
    return ((dx * ey[1] - ey[0] * dy) / det, (ex[0] * dy - dx * ex[1]) / det)
hits = {}
for t in T:
    A, B, C = (V[v] for v in t["v"])
    xs, ys = [A[0], B[0], C[0]], [A[1], B[1], C[1]]
    d = (B[1] - C[1]) * (A[0] - C[0]) + (C[0] - B[0]) * (A[1] - C[1])
    if abs(d) < 1e-9: continue
    near = [b for b in boxes if abs(b[1] - sum(xs) / 3) < 400 and abs(b[2] - sum(ys) / 3) < 400]
    if not near: continue
    gx = min(xs)
    while gx <= max(xs):
        gy = min(ys)
        while gy <= max(ys):
            l1 = ((B[1] - C[1]) * (gx - C[0]) + (C[0] - B[0]) * (gy - C[1])) / d; l2 = ((C[1] - A[1]) * (gx - C[0]) + (A[0] - C[0]) * (gy - C[1])) / d; l3 = 1 - l1 - l2
            if min(l1, l2, l3) >= 0:
                gz = l1 * A[2] + l2 * B[2] + l3 * C[2]
                for b in near:
                    if not (b[10] <= gz <= b[11]): continue
                    la, lb = local(b, gx, gy)
                    if b[6] + EDGE < la < b[8] - EDGE and b[7] + EDGE < lb < b[9] - EDGE:
                        k = (b[0], round(b[1]), round(b[2])); hits.setdefault(k, [0, (gx, gy, gz)]); hits[k][0] += 1
            gy += S
        gx += S
Lf = lambda p: (-p[1], p[0], p[2])
print(f"NAV INSIDE {os.path.basename(sys.argv[1])}: {len(boxes)} piece footprints, {len(T)} triangles; {len(hits)} pieces with navmesh inside")
for (ed, x, y), (n, pt) in sorted(hits.items(), key=lambda kv: -kv[1][0]):
    c = Lf((x, y, 0)); q = Lf(pt); print(f"  FAIL {ed} at ({c[0]:.0f}, {c[1]:.0f}): {n} samples inside, e.g. ({q[0]:.0f}, {q[1]:.0f}, {q[2]:.0f})")
sys.exit(1 if hits else 0)
