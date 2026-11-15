"""Does the sculpted crest sit on its roundel? crest_low.json (crest_game.py) is in the crest's own frame: x right, y up,
z out from the roundel's face. The roundel (guildhall_gen.py roundel()) has a face of radius 130, 8 proud of the wall,
and a rim from 130 to 150, 14 proud: the crest's back lies on the face (z 0).
  - nothing behind the face (z below -0.5): it would show through the stone
  - over the rim (radius 130-150) everything at least 1 clear of the rim's top (z above 6 + 1)
  - nothing past the roundel's edge (radius over 150): it would hang in the air off the wall
    python crest_fit_check.py <crest_low.json>        exit 1 on any fault"""
import sys, json, math
C = json.load(open(sys.argv[1]))
RF, RR, D_FACE, D_RIM = 130.0, 150.0, 8.0, 14.0
bad = []
over_rim = [(x, y, z) for x, y, z in C["v"] if RF < math.hypot(x, y) <= RR]
for x, y, z in C["v"]:
    r = math.hypot(x, y)
    if z < -0.5: bad.append(("behind the face", round(x), round(y), round(z, 1)))
    elif r > RR: bad.append(("past the roundel's edge", round(x), round(y), round(r, 1)))
    elif r > RF and z < D_RIM - D_FACE + 1.0: bad.append(("on the rim", round(x), round(y), round(z, 1)))
print(f"{len(C['f'])} triangles, {len(C['v'])} vertices | extent x {min(v[0] for v in C['v']):.1f}..{max(v[0] for v in C['v']):.1f}"
      f" y {min(v[1] for v in C['v']):.1f}..{max(v[1] for v in C['v']):.1f} z {min(v[2] for v in C['v']):.1f}..{max(v[2] for v in C['v']):.1f}")
print(f"{len(over_rim)} vertices over the rim, lowest at z {min((v[2] for v in over_rim), default=float('nan')):.1f} (the rim's top is z {D_RIM - D_FACE:.0f})")
for b in bad[:20]: print("  FAULT", *b)
print("FAULTS", len(bad))
sys.exit(1 if bad else 0)
