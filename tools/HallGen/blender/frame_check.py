"""Is every arch's dressed surround all there? (the kitchen arch's frame clipped: it stood 6 from the back wall and its frame is 14
wide, so 8 of it lay inside that wall on one side, the whole frame showing on the other.) The placement gates test a piece against the shell; a surround is part of the shell. So: from each point of
each surround's outer edge, 3 proud of the face, to the opening's edge inside it, nothing of the cell may stand in the way by more than TOL: the great hall's arches lose 2 of their 14 to the wall
at y 732, which no one can see, and are counted, not failed.
    python frame_check.py <hall2_part.json>        exit 1 on any FAIL, and when the export names no arch"""
import json, sys
import numpy as np
d = json.load(open(sys.argv[1])); pairs = np.array(d.get("arches", []), float)
if not len(pairs): print("FAIL FRAME read no arch"); sys.exit(1)
# (the drawn faces: what the player sees, a piece of it having no collision of its own)
T = []
for sh in d["shapes"].values():
    v = sh["v"]
    for f in sh["f"]:
        for i in range(1, len(f) - 1): T.append((v[f[0]], v[f[i]], v[f[i + 1]]))
T = np.array(T, float)[:, :, :3]
H = lambda p: (p[1], -p[0], p[2]); TOL = 3.0
def hit(a, b):
    v0, e1, e2 = T[:, 0], T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]; s_ = b - a
    p = np.cross(s_, e2); det = (e1 * p).sum(1); ok = abs(det) > 1e-9; inv = np.where(ok, 1 / np.where(ok, det, 1), 0)
    t = a - v0; u = (t * p).sum(1) * inv; q = np.cross(t, e1); v = (q * s_).sum(1) * inv; w = (e2 * q).sum(1) * inv
    w_ = w[ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (w > 1e-4) & (w < 1 - 1e-4)]
    return (w_.max() * np.linalg.norm(s_)) if len(w_) else 0.0                     # (how far in from its outer edge the last thing in the way stands)
bad = 0; shaved = 0; seen = {}
for a, b in pairs:
    deep = hit(a, b)
    if deep <= 0: continue
    if deep <= TOL: shaved += 1; continue
    bad += 1
    q = H(a); seen.setdefault((round(q[0]), round(q[1] / 30)), []).append((q, deep))
for ps in seen.values():
    z = [p[2] for p, _ in ps]; p = ps[0][0]
    print(f"FAIL FRAME the surround at ({p[0]:.0f}, {p[1]:.0f}) is buried up to {max(d_ for _, d_ in ps):.0f} deep over {len(ps)} points, z {min(z):.0f}..{max(z):.0f}")
print(f"FRAMES {len(pairs)} points, {bad} buried, {shaved} shaved by {TOL:.0f} or less"); sys.exit(1 if bad else 0)
