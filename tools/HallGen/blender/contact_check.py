"""How many collision triangles meet where a character can touch them (2026-10-30, a CTD in Havok's character code with hits past its list of 32, Ylva against the front window: the
windows' glass had collision by mistake, each pane a fan from one corner, in two layers 0.8 apart, so 43 triangles lay within 8 of the contact points, the stack's positions, where
the wall has 1). From each collision vertex a character can reach (over the navmesh, up to its height), the triangles within TIGHT of it.
    python contact_check.py <export .json> <its nav .json> [--limit 28] [--tight 3] [--extra <json of triangles>]       FAIL CONTACT per place over the limit"""
import json, sys
import numpy as np
from scipy.spatial import cKDTree
A = sys.argv[1:]; LIMIT = 28; TIGHT = 3.0; EXTRA = None
if "--limit" in A: i = A.index("--limit"); LIMIT = int(A[i + 1]); del A[i:i + 2]
if "--tight" in A: i = A.index("--tight"); TIGHT = float(A[i + 1]); del A[i:i + 2]
if "--extra" in A: i = A.index("--extra"); EXTRA = A[i + 1]; del A[i:i + 2]
REACH = 34.0; HEIGHT = 134.0

def closest(p, T):
    """the closest point of each triangle to p (Ericson's), vectorised"""
    a, b, c = T[:, 0], T[:, 1], T[:, 2]; ab, ac = b - a, c - a; ap = p - a
    d1 = (ab * ap).sum(1); d2 = (ac * ap).sum(1); bp = p - b; d3 = (ab * bp).sum(1); d4 = (ac * bp).sum(1)
    cp = p - c; d5 = (ab * cp).sum(1); d6 = (ac * cp).sum(1)
    vc = d1 * d4 - d3 * d2; vb = d5 * d2 - d1 * d6; va = d3 * d6 - d5 * d4
    den = va + vb + vc; den[np.abs(den) < 1e-12] = 1e-12
    q = a + ab * (vb / den)[:, None] + ac * (vc / den)[:, None]
    m = (d1 <= 0) & (d2 <= 0); q[m] = a[m]
    m = (d3 >= 0) & (d4 <= d3); q[m] = b[m]
    m = (d6 >= 0) & (d5 <= d6); q[m] = c[m]
    m = (vc <= 0) & (d1 >= 0) & (d3 <= 0); t_ = d1 / np.where(d1 - d3 == 0, 1, d1 - d3); q[m] = (a + ab * t_[:, None])[m]
    m = (vb <= 0) & (d2 >= 0) & (d6 <= 0); t_ = d2 / np.where(d2 - d6 == 0, 1, d2 - d6); q[m] = (a + ac * t_[:, None])[m]
    m = (va <= 0) & (d4 >= d3) & (d5 >= d6); t_ = (d4 - d3) / np.where(d4 - d3 + d5 - d6 == 0, 1, d4 - d3 + d5 - d6); q[m] = (b + (c - b) * t_[:, None])[m]
    return q

path, nav = A[:2]
T = np.array(json.load(open(path))["coll"], float).reshape(-1, 3, 3); N = json.load(open(nav))
if EXTRA: T = np.vstack([T, np.array(json.load(open(EXTRA)), float)])
assert len(T), "no collision read"
V = np.array(N["verts"], float); F = np.array([t["v"] for t in N["tris"]], int); assert len(F), "no navmesh read"
spots = []
for t in F:
    a, b, c = V[t]; n = int(max(np.linalg.norm(b - a), np.linalg.norm(c - a), np.linalg.norm(c - b)) / 12) + 1
    for i in range(n + 1):
        for j in range(n + 1 - i):
            spots.append(a + (b - a) * i / n + (c - a) * j / n)
spots = np.unique(np.round(np.array(spots)), axis=0); tree = cKDTree(spots[:, :2])
lo, hi = T.min(1), T.max(1); pts = np.unique(np.round(T.reshape(-1, 3), 1), axis=0); res = []; reached = 0
for p in pts:
    s = spots[tree.query_ball_point(p[:2], REACH)]
    if not len(s) or not ((p[2] - s[:, 2] >= -2) & (p[2] - s[:, 2] <= HEIGHT)).any(): continue
    reached += 1
    m = np.all(lo <= p + TIGHT, 1) & np.all(hi >= p - TIGHT, 1)
    n = int(m.sum())
    if n > 8: q = closest(p, T[m]); n = int((((q - p) ** 2).sum(1) <= TIGHT * TIGHT).sum())
    res.append((n, p))
res.sort(key=lambda r: -r[0]); seen = []
for n, p in res:
    if n <= LIMIT: break
    if any(((p - s) ** 2).sum() < 900 for s in seen): continue
    seen.append(p)
    if len(seen) <= 10: print(f"  FAIL CONTACT {n} triangles meet at hall ({p[1]:.0f}, {-p[0]:.0f}, {p[2]:.0f})")
print(f"CONTACT {path.split('/')[-1]}: {len(T)} triangles, {reached} of {len(pts)} points in a character's reach; most meeting at one {res[0][0] if res else 0}; {len(seen)} places over {LIMIT}")
if not reached: print("  FAIL CONTACT no point in reach: this gate read nothing")
sys.exit(1 if seen or not reached else 0)
