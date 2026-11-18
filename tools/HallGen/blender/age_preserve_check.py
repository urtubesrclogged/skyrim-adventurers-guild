"""The age pass may cut faces into cells and colour them, never move them: every face of the final export must lie on a
face of the same part and material in an export made without the cuts (guildhall_gen.py with AGE_CELL all 0). A face
that does not is out of place (a floating panel).
    python age_preserve_check.py <final export dir> <uncut export dir>
Prints hall-frame positions (x across the front, y negative in front, z from the floor). Exit 1 on any stray face."""
import sys, os, json, math

def load(d):
    out = {}
    for fn in ("hall2_body.json", "hall2_roof.json", "hall2_site_1.json"):
        j = json.load(open(os.path.join(d, fn)))
        for key, sh in j["shapes"].items():
            if key in ("moss", "mosswall", "wearcrack", "wearstain", "spill"): continue                       # decals: checked by decal_support_check.py
            out[(fn, key)] = [[sh["v"][i] for i in f] for f in sh["f"]]
    return out

def plane(P):
    n = [0.0, 0.0, 0.0]
    for i in range(1, len(P) - 1):                                         # area-weighted normal of the polygon
        a = [P[i][k] - P[0][k] for k in range(3)]; b = [P[i + 1][k] - P[0][k] for k in range(3)]
        n = [n[0] + a[1] * b[2] - a[2] * b[1], n[1] + a[2] * b[0] - a[0] * b[2], n[2] + a[0] * b[1] - a[1] * b[0]]
    L = math.sqrt(sum(c * c for c in n))
    if L < 1e-9: return None, None, 0.0
    n = [c / L for c in n]
    return n, sum(n[k] * P[0][k] for k in range(3)), L / 2

def inside(P, q, n, tol=0.5):
    """q (on P's plane) inside the convex or concave polygon P, within tol: winding test in the dominant projection"""
    ax = max(range(3), key=lambda k: abs(n[k])); i, j = [k for k in range(3) if k != ax]
    pts = [(p[i], p[j]) for p in P]; x, y = q[i], q[j]
    win = False
    for k in range(len(pts)):
        (x1, y1), (x2, y2) = pts[k], pts[(k + 1) % len(pts)]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1): win = not win
    if win: return True
    for k in range(len(pts)):                                              # on an edge, within tol
        (x1, y1), (x2, y2) = pts[k], pts[(k + 1) % len(pts)]
        dx, dy = x2 - x1, y2 - y1; L2 = dx * dx + dy * dy
        t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / L2))
        if math.hypot(x - (x1 + t * dx), y - (y1 + t * dy)) <= tol: return True
    return False

final, base = load(sys.argv[1]), load(sys.argv[2])
bad, total = [], 0
for k, faces in final.items():
    groups = {}
    for P in base.get(k, []):
        n, d, a = plane(P)
        if n is None: continue
        groups.setdefault((round(n[0], 2), round(n[1], 2), round(n[2], 2)), []).append((n, d, P))
    for P in faces:
        n, d, a = plane(P)
        if n is None or a < 0.5: continue
        total += 1
        c = [sum(p[m] for p in P) / len(P) for m in range(3)]
        ok = False
        for g in groups.get((round(n[0], 2), round(n[1], 2), round(n[2], 2)), []):
            if abs(g[1] - d) <= 0.5 and inside(g[2], c, g[0]):
                ok = True; break
        if not ok: bad.append((round(a), k[0].replace("hall2_", "").replace(".json", ""), k[1], [round(c[1]), round(-c[0]), round(c[2])], [round(-n[1], 2), round(n[0], 2), round(n[2], 2)]))
bad.sort(reverse=True)
print(total, "faces checked against the uncut geometry:", len(bad), "lie on no original face (area, part, material, hall x y z, hall normal)")
for b in bad[:40]: print("  ", b)
sys.exit(1 if bad else 0)
