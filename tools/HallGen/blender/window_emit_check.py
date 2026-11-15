"""The hall's daylight, as vanilla's, from the plugin (the daylight plan): every reference of a mesh holding the inside's panes, every window fill and bounce light carries
vanilla's FXLightRegionSunlightWhite; nothing is left of the old switch. It fails if it finds no pane mesh or no fill: a gate that read nothing has passed nothing.
    python window_emit_check.py <plugin.esp> <meshes dir>        FAIL lines, exit 1"""
import glob, os, struct, sys, zlib
REGION = 0x075492
data = open(sys.argv[1], "rb").read(); MD = sys.argv[2]
panes = {os.path.basename(f).lower() for f in glob.glob(os.path.join(MD, "*.nif")) if b"AGH2GlassDay_g" in open(f, "rb").read()}
def subs(b):
    i = 0; o = {}
    while i + 6 <= len(b):
        t = b[i:i + 4]; n = struct.unpack_from("<H", b, i + 4)[0]; o[t] = b[i + 6:i + 6 + n]; i += 6 + n
    return o
rec = {}; hs = struct.unpack_from("<I", data, 4)[0]
def walk(a, z):
    while a < z:
        t = data[a:a + 4]; size = struct.unpack_from("<I", data, a + 4)[0]
        if t == b"GRUP": walk(a + 24, a + size); a += size; continue
        fl, fid = struct.unpack_from("<II", data, a + 8); body = data[a + 24:a + 24 + size]; a += 24 + size
        if fl & 0x40000: body = zlib.decompress(body[4:])
        rec[fid] = (t, fl, subs(body))
walk(24 + hs, len(data))
ed = lambda f: rec[f][2].get(b"EDID", b"")[:-1].decode("latin1") if f in rec else ""
bad = 0
def fail(m):
    global bad; bad += 1; print("FAIL DAYLIGHT", m)
glazed = {f for f, (t, _, s) in rec.items() if t == b"STAT" and b"MODL" in s and os.path.basename(s[b"MODL"][:-1].decode("latin1").replace(chr(92), "/")).lower() in panes}
fills = {f for f in rec if ed(f) in ("AGHall2LightWindow", "AGHall2LightBounce")}
n_pane = n_fill = 0
for f, (t, fl, s) in rec.items():
    if t != b"REFR" or b"NAME" not in s: continue
    b_ = struct.unpack("<I", s[b"NAME"][:4])[0]; xe = struct.unpack("<I", s[b"XEMI"])[0] if b"XEMI" in s else None
    if fl & 0x800 and b_ in glazed | fills: continue         # (a retired reference, initially disabled)
    if b_ in glazed:
        n_pane += 1
        if xe != REGION: fail(f"reference {f:#x} of {ed(b_)} holds panes and has no region: {xe}")
    if b_ in fills:
        n_fill += 1
        if xe != REGION: fail(f"{ed(b_)} reference {f:#x} has no region: {xe}")
        if b"XESP" in s: fail(f"{ed(b_)} reference {f:#x} still has an enable parent")
for f, (t, fl, s) in rec.items():
    if ed(f) in ("AGHall2DaylightMarker", "AGHall2DayNightControl", "AGHall2WindowsDay", "AGHall2LightWindowTestRed"): fail(f"{ed(f)} is still in the plugin")
if b"AGHallDayNight" in data: fail("AGHallDayNight is still named in the plugin")
if not n_pane or not n_fill or not panes: fail(f"read {len(panes)} pane meshes, {n_pane} references of them, {n_fill} fills")
print(f"DAYLIGHT {len(panes)} meshes with panes, {n_pane} references, {n_fill} fills and bounce lights, {bad} failures"); sys.exit(1 if bad else 0)
