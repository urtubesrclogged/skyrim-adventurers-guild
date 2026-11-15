"""The settle test: do the hall's loose items stay where the plugin puts them? (the tavern's curio lay
on the floor and most of the clutter was thrown about. Measured: 48 of 125 loose items moved; brand-new ones flew up to 560. The
engine ejects an item that starts inside collision; vanilla's stay put because the Creation Kit's Havok settle baked them onto the
real collision, and our placement measures the visual meshes.) The game's own physics is the authority, so this asks it, through
DevBench, with the player in the cell (unloaded items have no physics):
    python settle_check.py read   <plugin.esp> [--port 8920] [--radius 6000]     where each loose item is now, against the plugin
    python settle_check.py settle <plugin.esp> [--port 8920] [--wait 8]          each one back to the plugin's place, wait, read
    python settle_check.py restore <plugin.esp> [--port 8920]                    each moved one back (MoveToMyEditorLocation), no report
settle and restore MOVE THINGS IN THE RUNNING GAME: warn the player first. Writes settle_<cell or 'loaded'>.json beside this script's
logs (--out) with every item's plugin and resting place; exits 1 when any item moved more than SETTLE_TOL after settling."""
import json, math, struct, sys, time, urllib.request, zlib, os, collections

MOV = {"MISC", "ALCH", "INGR", "BOOK", "WEAP", "ARMO", "AMMO", "SLGM", "SCRL", "KEYM"}
SETTLE_TOL, THROWN = 1.5, 6.0          # resting within 1.5 of the plugin's place passes; past 6 it was thrown, not settled

def plugin_refs(path):
    """{local id: (base, (x, y, z), (rx, ry, rz))} for every REFR in the plugin"""
    b = open(path, "rb").read(); out = {}
    def walk(o, end):
        while o < end:
            t = b[o:o + 4]; sz = struct.unpack_from("<I", b, o + 4)[0]
            if t == b"GRUP": walk(o + 24, o + sz); o += sz; continue
            fl, fid = struct.unpack_from("<II", b, o + 8); data = b[o + 24:o + 24 + sz]
            if t == b"REFR":
                if fl & 0x40000: data = zlib.decompress(data[4:])
                p = 0; base = pos = None
                while p < len(data):
                    st = data[p:p + 4]; ss = struct.unpack_from("<H", data, p + 4)[0]; v = data[p + 6:p + 6 + ss]
                    if st == b"NAME": base = struct.unpack_from("<I", v)[0]
                    if st == b"DATA": pos = struct.unpack_from("<6f", v)
                    p += 6 + ss
                if pos: out[fid & 0xFFFFFF] = (base, pos[:3], pos[3:])
            o += 24 + sz
    walk(24 + struct.unpack_from("<I", b, 4)[0], len(b)); return out

def api(port, tool, payload, timeout=20):
    rq = urllib.request.Request(f"http://127.0.0.1:{port}/api/tool/{tool}", json.dumps(payload).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(rq, timeout=timeout) as r: return json.loads(r.read())

def live(port, radius):
    return api(port, "inspect", {"kind": "refs", "radius": radius, "limit": 5000}, 30)["refs"]

def ours(port, radius, P):
    """the loaded loose items that are the plugin's: the high byte is the one under which the most live refs match the plugin exactly"""
    L = [r for r in live(port, radius) if r["base"]["formType"] in MOV]
    votes = collections.Counter()
    for r in L:
        fid = int(r["formId"], 16); e = P.get(fid & 0xFFFFFF)
        if e and math.dist(e[1], r["position"]) < 0.5: votes[fid >> 24] += 1
    if not votes: sys.exit("no loaded loose item matches the plugin: wrong plugin, or the player is not in the hall")
    hi = votes.most_common(1)[0][0]
    return [r for r in L if int(r["formId"], 16) >> 24 == hi and (int(r["formId"], 16) & 0xFFFFFF) in P], hi

def report(items, P, out):
    rows = []
    for r in items:
        e = P[int(r["formId"], 16) & 0xFFFFFF]; d = math.dist(e[1], r["position"]); dz = r["position"][2] - e[1][2]
        v = "ok" if d <= SETTLE_TOL else ("THROWN" if d > THROWN else "SETTLED")
        rows.append(dict(id=r["formId"], name=r["base"].get("name"), base=r["base"]["formId"], plugin=[round(x, 2) for x in e[1]],
                         rest=[round(x, 2) for x in r["position"]], moved=round(d, 1), dz=round(dz, 1), verdict=v))
    rows.sort(key=lambda x: -x["moved"])
    json.dump(rows, open(out, "w"), indent=1)
    c = collections.Counter(x["verdict"] for x in rows)
    print(f"SETTLE {len(rows)} loose items: ok {c['ok']}, settled 1.5-6 {c['SETTLED']}, thrown over 6 {c['THROWN']} (report {out})")
    for x in rows:
        if x["verdict"] != "ok": print(f"  {x['verdict']:7} {x['name']!s:28} {x['id']} moved {x['moved']:6} dz {x['dz']:6}  plugin {x['plugin']}  rest {x['rest']}")
    return c["SETTLED"] + c["THROWN"]

if __name__ == "__main__":
    a = sys.argv[1:]; mode, esp = a[0], a[1]
    opt = lambda k, d: type(d)(a[a.index(k) + 1]) if k in a else d
    port, radius, wait = opt("--port", 8920), opt("--radius", 6000.0), opt("--wait", 8.0)
    out = opt("--out", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "build", "hall-work", "settle.json"))
    P = plugin_refs(esp); items, hi = ours(port, radius, P)
    print(f"plugin index 0x{hi:02X}: {len(items)} of its loose items loaded")
    if mode in ("settle", "restore"):
        moved = [r for r in items if mode == "settle" or math.dist(P[int(r["formId"], 16) & 0xFFFFFF][1], r["position"]) > 0.5]
        for r in moved:
            api(port, "papyrus", {"action": "call", "script": "ObjectReference", "function": "MoveToMyEditorLocation", "args": [], "self": {"form": r["formId"]}})
        print(f"{len(moved)} put back where the plugin places them")
        if mode == "restore": sys.exit(0)
        time.sleep(wait); items, _ = ours(port, radius, P)
    sys.exit(1 if report(items, P, out) else 0)
