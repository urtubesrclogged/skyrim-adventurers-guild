"""Every hanging thing in a cell against the floor and the ceiling it hangs between (the
services' chandeliers went from head height at 151 to flat against the 400 ceiling). The rule: look at the offset from
the floor AND from the ceiling. Unless a chandelier is over a piece of furniture the player has to walk around, it MUST
hang higher than the characters, and no chandelier in a medium or high room sits right up against the ceiling.

The floor and the ceiling are read from the cell's own collision at the thing's x, y (the highest face below it, the
lowest above it); its bottom and top from its mesh's measured extents (module_bounds.py); furniture under it from the
placed pieces whose models are furniture, within its reach. Rules:
  CLEAR  over walkable floor, its bottom at least CLEAR_MIN over the floor (the tallest playable race, 1.1 x 128, with a
         helmet's and the first-person camera's margin: 151 was hit)
  DROP   in a room at least ROOM_MID high, its bottom at least a third of the room's height below the ceiling, and the
         chain or rope it hangs by at least DROP_MIN long (not right up against the ceiling)
    python hang_check.py <hall2_interior.json> [more cells' json...]"""
import json, sys, re

CLEAR_MIN, ROOM_MID, DROP_MIN = 200.0, 300.0, 60.0
# the hanging meshes: bottom below the origin, the body's top above it, the hanger's top (chain, rope, rod) above it
HANGING = {
    "candlehornchandelier01": (-29, 0, 220), "candlehornchandelier02": (-29, 0, 50),
    "hanginggarlicbraid01": (-47, 0, 0), "hangingfrostmirriam01": (-15, 20, 20), "hangingelvesear01": (-16, 5, 5),
    "hanginganimalsring02": (-51, 49, 49),
}
FURNITURE = re.compile(r"table|bench|bed|desk|counter|bar|chest|shelf|barrel|crate|chair|cupboard|drawers|wardrobe|sideboard|lectern|stool|pen|forge|anvil", re.I)


RADIUS = {"candlehornchandelier01": 37, "candlehornchandelier02": 37, "impchandelliercandle01": 66}; WALL_MIN = 60.0
def inside(p, a, b, c):
    """p in the triangle abc, all 2D"""
    d_ = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
    if abs(d_) < 1e-9: return False
    u = ((b[1] - c[1]) * (p[0] - c[0]) + (c[0] - b[0]) * (p[1] - c[1])) / d_
    v = ((c[1] - a[1]) * (p[0] - c[0]) + (a[0] - c[0]) * (p[1] - c[1])) / d_
    return min(u, v, 1 - u - v) >= -1e-6


def wall_gap(coll, x, y, z, far):
    """the nearest upright face, along the four axes: the face itself at that height, not its box (a rafter's side is a tall box and only a slant of it is anywhere near)"""
    best = None
    for a, b, c in coll:
        lo = [min(a[i], b[i], c[i]) for i in range(3)]; hi = [max(a[i], b[i], c[i]) for i in range(3)]
        if not lo[2] <= z <= hi[2] or hi[2] - lo[2] < 100: continue   # (a wall, not a beam it hangs among)
        if lo[1] <= y <= hi[1] and hi[0] - lo[0] < 2 and inside((y, z), *[(q[1], q[2]) for q in (a, b, c)]):
            d_ = abs((lo[0] + hi[0]) / 2 - x)
            if d_ < far and (best is None or d_ < best): best = d_
        if lo[0] <= x <= hi[0] and hi[1] - lo[1] < 2 and inside((x, z), *[(q[0], q[2]) for q in (a, b, c)]):
            d_ = abs((lo[1] + hi[1]) / 2 - y)
            if d_ < far and (best is None or d_ < best): best = d_
    return best


def faces_at(coll, x, y):
    out = []
    for a, b, c in coll:
        den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(den) < 1e-9: continue
        u = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / den
        v = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / den
        w = 1 - u - v
        if min(u, v, w) < -1e-6: continue
        out.append(u * a[2] + v * b[2] + w * c[2])
    return out


def check(path):
    j = json.load(open(path)); coll = j["coll"]; pieces = j["pieces"]; bad = 0; rows = []
    hanging = []
    for p in pieces:
        k = p["model"].split("/")[-1].replace(".nif", "").lower()
        if k in HANGING: hanging.append((p, HANGING[k]))
        elif k == "candlelanternwithcandle01":
            hanging.append((p, (-2, 42, None)))           # (a lantern hangs only where a rod over it is the hall's: checked below)
    for p, (lo, hi, top) in hanging:
        x, y, z = p["pos"]; s = p.get("scale", 1.0)
        bottom, body = z + lo * s, z + hi * s
        zs = faces_at(coll, x, y)
        below = [f for f in zs if f < bottom - 5]; above = [f for f in zs if f > body + 1]
        if not below: continue
        floor = max(below); ceil = min(above) if above else None
        if top is None:                                    # a lantern standing on something is not hanging
            if bottom - floor < 100: continue
            top = (ceil - z) / s if ceil else hi
        hanger = top * s - hi * s                          # the chain's or rope's length over the body
        under = sorted({q["ed"] if "ed" in q else q["model"].split("/")[-1] for q in pieces
                        if q is not p and FURNITURE.search(q["model"]) and abs(q["pos"][0] - x) < 55 and abs(q["pos"][1] - y) < 55
                        and floor - 5 <= q["pos"][2] <= floor + 120})
        room = (ceil - floor) if ceil else None
        msgs = []
        if not under and bottom - floor < CLEAR_MIN: msgs.append(f"CLEAR bottom {bottom - floor:.0f} over walkable floor (< {CLEAR_MIN:.0f})")
        if room and room >= ROOM_MID and "chandelier" in p["model"]:
            if ceil - bottom < room / 3: msgs.append(f"DROP bottom {ceil - bottom:.0f} under the ceiling (< a third of {room:.0f})")
            if hanger < DROP_MIN: msgs.append(f"DROP hung by {hanger:.0f} (< {DROP_MIN:.0f})")
        wall = wall_gap(coll, x, y, bottom + 20, 300)
        reach = (RADIUS.get(p["model"].split("/")[-1].replace(".nif", "").lower(), 0)) * s
        if reach and wall is not None and wall < reach + WALL_MIN and not under:
            msgs.append(f"WALL {wall - reach:.0f} from a wall (< {WALL_MIN:.0f}: hanging pieces need both height and distance from the walls)")
        hx, hy = y, -x                                     # (layout to the hall's frame, for reading)
        rows.append((p.get("ed", p["model"]), hx, hy, floor, bottom - floor, room, (ceil - bottom) if ceil else None, under, msgs))
        bad += bool(msgs)
    print(f"HANG {path.split('/')[-1]}: {len(rows)} hanging things, {bad} breaking the rules (clear {CLEAR_MIN:.0f} over walkable "
          f"floor; in rooms over {ROOM_MID:.0f}, a third of the room below the ceiling, hung by at least {DROP_MIN:.0f})")
    for ed, hx, hy, fl, clr, room, gap, under, msgs in rows:
        print(f"  {'BAD ' if msgs else 'ok  '}{ed:28s} hall ({hx:6.0f},{hy:5.0f}) floor {fl:4.0f}: bottom +{clr:4.0f}"
              f"{'' if room is None else f', room {room:4.0f}, under the ceiling {gap:4.0f}'}"
              f"{', over ' + '/'.join(under) if under else ', walkway'}{'  <- ' + '; '.join(msgs) if msgs else ''}")
    return bad


if __name__ == "__main__":
    sys.exit(1 if sum(check(a) for a in sys.argv[1:]) else 0)
