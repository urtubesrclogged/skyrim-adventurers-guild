"""Was every mesh made from this export built after it? (2026-11-01: the window test bay's outside: AGHall2Body.nif comes from hall2_body.json, the build chain had stopped rebuilding it, and the
10:06 mesh passed every gate, because a stale file exists, reads clean and has every texture it names.) Every mesh that comes from an export, against the export's own time.
    python fresh_check.py <export dir> <meshes dir>       FAIL STALE per mesh, exit 1; exit 1 too when it read no mesh"""
import glob, os, re, sys
E, O = sys.argv[1:3]
t0 = max(os.path.getmtime(p) for p in glob.glob(os.path.join(E, "hall2_*.json")))
FROM = re.compile(r"(?i)^AGHall2(Body|Roof(Slate|Tile)|Site\d+|Room\w+|Bake\w+|Basement|Lookout)\.nif$")
ns = [p for p in glob.glob(os.path.join(O, "*.nif")) if FROM.match(os.path.basename(p))]; bad = 0
for p in sorted(ns):
    late = t0 - os.path.getmtime(p)
    if late > 0: print(f"FAIL STALE {os.path.basename(p)}: built {late / 60:.0f} minutes before the export"); bad += 1
if not ns: print("FAIL STALE read no mesh"); bad = 1
print(f"FRESH {len(ns)} meshes from the export, {bad} stale"); sys.exit(1 if bad else 0)
