"""Who is behind a locked door? (the back office door was locked on four people.) A routine that puts someone behind a lock they cannot open reads in game as a stuck NPC and
in no other gate, and the key is added in another session's file, so both ends are read here, from the merged plugin: for each door the export gives a "lock_key", the door's lock in the plugin,
the key on each of its "keyholders", and every marker of every routine against its "behind" rectangles. Read-only.
    python lock_check.py <merged plugin.esp> <export dir> <schedules.json>       exit 1 on any FAIL, and when it read no pieces (no locked door with keyholders is a pass since 2026-11-11)"""
import json, struct, sys, zlib


def subs(b):
    i, big = 0, None
    while i + 6 <= len(b):
        t = b[i:i + 4].decode("latin-1"); n = struct.unpack_from("<H", b, i + 4)[0]; i += 6
        if t == "XXXX": big = struct.unpack_from("<I", b, i)[0]; i += n; continue
        if big is not None: n, big = big, None
        yield t, b[i:i + n]; i += n


def walk(data, a, z, recs):
    while a < z:
        t = data[a:a + 4].decode("latin-1"); size = struct.unpack_from("<I", data, a + 4)[0]
        if t == "GRUP":
            walk(data, a + 24, a + size, recs); a += size; continue
        flags, fid = struct.unpack_from("<II", data, a + 8)
        body = data[a + 24:a + 24 + size]
        if flags & 0x40000: body = zlib.decompress(body[4:])
        recs.append((t, fid, body)); a += 24 + size


esp, E, sched = sys.argv[1:4]
data = open(esp, "rb").read(); hsize = struct.unpack_from("<I", data, 4)[0]; recs = []
walk(data, 24 + hsize, len(data), recs)
edid = lambda body: next((sd[:-1].decode("latin-1") for st, sd in subs(body) if st == "EDID"), "")
keys = {edid(b): f for t, f, b in recs if t == "KEYM"}
npcs = {edid(b): {struct.unpack("<I", sd[:4])[0] for st, sd in subs(b) if st == "CNTO"} for t, f, b in recs if t == "NPC_"}
locks = {edid(b): next((sd for st, sd in subs(b) if st == "XLOC"), None) for t, f, b in recs if t == "REFR" and edid(b)}
LEVEL = {1: "Novice", 25: "Apprentice", 50: "Adept", 75: "Expert", 100: "Master", 255: "Key"}
H = lambda p: (p[1], -p[0], p[2])
parts = [json.load(open(f"{E}/hall2_{c}.json")) for c in ("interior", "basement", "lookout")]
marks = {}
for d in parts:
    for m in d.get("markers", []): marks[m[0] or m[1]] = H(m[2])             # [name, base, position, yaw]
    for p in d["pieces"]:
        if p.get("name"): marks.setdefault(p["name"], H(p["pos"]))
S = json.load(open(sched, encoding="utf-8"))["npcs"]; bad = 0; n = 0
for d in parts:
    for p in d["pieces"]:
        if "lock_key" not in p or "keyholders" not in p: continue
        nm, kname, n = p.get("name"), p["lock_key"], n + 1
        if kname not in keys: print(f"FAIL LOCK {nm}: no key record {kname} in the plugin"); bad += 1; continue
        x = locks.get(nm)
        if x is None: print(f"FAIL LOCK {nm}: no lock on the reference in the plugin"); bad += 1; continue
        lv, key = x[0], struct.unpack_from("<I", x, 4)[0]
        if LEVEL.get(lv) != p["lock"] or key != keys[kname]: print(f"FAIL LOCK {nm}: the plugin has level {lv}, key {key:08X}; wanted {p['lock']}, {keys[kname]:08X}"); bad += 1
        have = {e for e, c in npcs.items() if keys[kname] in c}
        for e in p["keyholders"]:
            if e not in have: print(f"FAIL LOCK {nm}: {e} does not carry {kname}"); bad += 1
        for e in sorted(have - set(p["keyholders"])): print(f"FAIL LOCK {nm}: {e} carries {kname}, and is not one of the people it is for"); bad += 1
        # (the door's own floor only: 150 under it to 300 over it; 2026-11-07, Ylva's archery lane in the basement, under the backroom,
        # was counted behind the backroom's door, the NPC session's catch)
        behind = lambda q: p["pos"][2] - 150 < q[2] < p["pos"][2] + 300 and any(r[0] <= q[0] <= r[2] and r[1] <= q[1] <= r[3] for r in p["behind"])
        for e, v in S.items():
            for w in sorted(({v.get("default")} | {b.get("where") for b in v.get("blocks", [])}) - {None, "bed"}):
                q = marks.get(w)
                if q is None: print(f"FAIL LOCK {nm}: {e}'s {w} is on no plan"); bad += 1
                elif behind(q) and e not in have: print(f"FAIL LOCK {nm}: {e} works at {w}, behind it, with no key"); bad += 1
        print(f"lock {nm}: {p['lock']}, {kname}, carried by {len(have)}: " + ", ".join(sorted(have)))
# (the back office door, the one door with keyholders, no longer has a lock or key; the display case and
# the strongroom name none. None is a pass, said so; what must never pass is reading no pieces at all)
if not any(d["pieces"] for d in parts): print("FAIL LOCK read no pieces"); bad = 1
elif not n: print("lock: no locked door names its keyholders (nothing to check)")
print(f"LOCKS {n} doors, {bad} failures"); sys.exit(1 if bad else 0)
