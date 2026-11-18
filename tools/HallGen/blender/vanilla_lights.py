"""The hall's lights for a game without Community Shaders' Light Limit Fix: which stay on.

The vanilla renderer lights a shape with only a few lights (rooms.LIMIT); where more reach a shape, the ones it draws change
from frame to frame and the light flickers. With Light Limit Fix every light burns. Without it, AG's DLL switches off the
lights this script lists: each hangs off its cell's enable-parent marker (Hall2.cs), which the DLL disables at every load
when Light Limit Fix is missing, and raises the hall's ambient instead.

Only the chandeliers stay on; every other light (lamps, fires, candles, window fills, bounce lights) is switched off, so
lights that look alike behave alike, and the ambient lights the rest. The check: no shape may be reached by more than
rooms.LIMIT chandeliers. A shape is a shell shape (the interior's room parts, the lookout's and the basement's shell) or a
placed piece, reached when the light's sphere meets the shape's bounding sphere (rooms.lights_on, the engine's test), from
any room: the ground floor is open, and a room's shell shapes are large enough to meet its neighbours' lights.

    python vanilla_lights.py <export dir> <light_levels.json>
Writes <export dir>/vanilla_lights.json: {"cells": {cell: {"off": [[x, y, z], ...], "on": n}}} and fails when a shape
would still be over the limit, or when a piece has no mesh_info.json entry (it could not be counted)."""
import sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rooms as R

# each kind's record radius: Hall2.cs's lightOf after its own edits (the window fill 250, the bounce 500, the chandelier 360)
BASE = {"lamp": 512, "fire": 768, "fire_small": 512, "candle": 128, "candle_small": 128, "candle_night": 128,
        "window": 250, "bounce": 500, "chandelier": 360}
KEPT = {"chandelier"}
CELLS = (("AGHall2InteriorCell", "hall2_interior.json", True), ("AGHall2BasementCell", "hall2_basement.json", False),
         ("AGHall2LookoutCell", "hall2_lookout.json", False))


def level_of(levels, p):
    return next((e for e in levels if all(abs(e["pos"][k] - p[k]) <= 1 for k in range(3))), None)


def lights(D, levels):
    """the lights Hall2.cs places from an export: position, reach, kind (a level entry's radius is the final one)"""
    out = []
    for l in D["lights"]:
        kind = l[3] if len(l) > 3 else None
        if kind is None and l[1] < 5e5: continue          # (the renders' window glows: no light in a cell)
        if kind == "glow": continue
        kind = kind or "lamp"
        e = level_of(levels, l[0])
        if e and e.get("kind") == "chandelier": kind = "chandelier"
        r = e["new"]["r"] if e else BASE[kind] + (l[4] if len(l) > 4 else 0)
        out.append({"p": l[0], "r": max(16.0, r), "kind": kind})
    return out


def kept_kind(kind): return kind in KEPT


def sphere(lo, hi):
    return [(lo[k] + hi[k]) / 2 for k in range(3)], math.dist(lo, hi) / 2


def shell_shapes(E, f, interior):
    """(name, centre, radius) of each shell shape the cell draws"""
    if interior:
        parts = json.load(open(os.path.join(E, "rooms_parts.json")))
        for room, rp in parts.items():
            o = rp["origin"]
            for n, s in json.load(open(os.path.join(E, rp["file"])))["shapes"].items():
                lo = [min(v[k] for v in s["v"]) + o[k] for k in range(3)]; hi = [max(v[k] for v in s["v"]) + o[k] for k in range(3)]
                yield (n,) + tuple(sphere(lo, hi))
    else:
        for n, s in json.load(open(os.path.join(E, f)))["shapes"].items():
            lo = [min(v[k] for v in s["v"]) for k in range(3)]; hi = [max(v[k] for v in s["v"]) for k in range(3)]
            yield (n,) + tuple(sphere(lo, hi))


def piece_shapes(D, mi, missing):
    for p in D["pieces"]:
        m = mi.get(p["model"].lower().replace("\\", "/"))
        if m is None: missing.append(p["model"]); continue
        if not m.get("box"): continue                       # (nothing drawn: a marker's model)
        (x0, y0, z0), (x1, y1, z1) = m["box"]; s = p.get("scale", 1)
        a = math.radians(p.get("yaw", 0)); c, sn = math.cos(a), math.sin(a)
        xs, ys = [], []
        for x in (x0, x1):
            for y in (y0, y1):
                xs.append(p["pos"][0] + s * (x * c + y * sn)); ys.append(p["pos"][1] + s * (-x * sn + y * c))
        lo = [min(xs), min(ys), p["pos"][2] + s * min(z0, z1)]; hi = [max(xs), max(ys), p["pos"][2] + s * max(z0, z1)]
        yield (p["model"].replace("\\", "/").split("/")[-1],) + tuple(sphere(lo, hi))


def pick(L, G):
    """indices of the lights that stay on, and how many of them reach each shape"""
    on = [i for i in range(len(L)) if kept_kind(L[i]["kind"])]
    n = [sum(1 for i in on if math.dist(c, L[i]["p"]) < r + L[i]["r"]) for _, c, r in G]
    return on, n


def main():
    E, levels_path = sys.argv[1], sys.argv[2]
    levels = json.load(open(levels_path))
    mi = {k.lower().replace("\\", "/"): v for k, v in json.load(open(os.path.join(E, "mesh_info.json"))).items()}
    out, bad = {"cells": {}}, 0
    for cell, f, interior in CELLS:
        D = json.load(open(os.path.join(E, f)))
        L = lights(D, levels)
        missing = []
        G = list(shell_shapes(E, f, interior)) + list(piece_shapes(D, mi, missing))
        if missing:
            print(f"FAIL {cell}: {len(missing)} pieces have no mesh_info.json entry, so their lights cannot be counted: {sorted(set(missing))[:5]}"); bad += 1
        on, n = pick(L, G)
        over = [G[g][0] for g in range(len(G)) if n[g] > R.LIMIT]
        if over: print(f"FAIL {cell}: {len(over)} shapes over {R.LIMIT} lights with the kept lights: {over[:5]}"); bad += 1
        off = [L[i] for i in range(len(L)) if i not in set(on)]
        by = lambda xs: {k: sum(1 for x in xs if x["kind"] == k) for k in sorted({x["kind"] for x in xs})}
        print(f"{cell}: {len(G)} shapes; on {len(on)} {by([L[i] for i in on])}; off {len(off)} {by(off)}; most lights on a shape {max(n) if n else 0}")
        out["cells"][cell] = {"on": len(on), "off": [x["p"] for x in off]}
    json.dump(out, open(os.path.join(E, "vanilla_lights.json"), "w"), indent=1)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
