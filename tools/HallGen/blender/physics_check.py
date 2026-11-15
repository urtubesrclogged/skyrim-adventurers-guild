"""What hangs on hinges? (2026-10-30, the walk: a hanging rabbit and pheasant stretched from a kitchen shelf to the ceiling.) A piece whose mesh has
havok constraints has dynamic bodies under a fixed anchor: placed by anything solid, they are pushed out and its skin stretches. None may stand in a hall part.
    python physics_check.py <hall2_part.json> [...] --data <extracted Data>     exit 1 on any"""
import json, os, re, sys
a = sys.argv[1:]; i = a.index("--data"); data = a[i + 1]; del a[i:i + 2]; bad = 0; seen = {}
for f in a:
    for p in json.load(open(f))["pieces"]:
        m = p["model"].lower().replace(chr(92), "/"); k = os.path.join(data, m)
        if m not in seen:
            seen[m] = os.path.exists(k) and bool(re.search(rb"bhk\w*Constraint", open(k, "rb").read(6000)))
        if seen[m] and "book" not in m: print("FAIL HINGED", p.get("ed"), [round(v) for v in p["pos"]]); bad += 1
print("PHYSICS", len(seen), "meshes,", bad, "hinged pieces"); sys.exit(1 if bad else 0)
