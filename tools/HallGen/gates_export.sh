#!/bin/bash
# The export's own checks, before any mesh is built (build_hall.sh runs it): placement on the basement, the lookout and the
# interior; the basement's seal and its coplanar faces; and (the same checks for anything added
# outside) the site's pieces, reported for review (the terrain is not in the site's collision,
# so a yard piece reads "nothing under it"), plants' overlaps with plants left out.
#   bash gates_export.sh <export dir>      exits 1 if it could not make the records or measures the gates read
E="${1:?export dir}"; HG="$(cd "$(dirname "$0")" && { pwd -W 2>/dev/null || pwd; })"; source "$HG/env.sh"; B="$HG/blender"; C="$HALL_WORK/data-root"; fail=0
cd "$HG"; unset EXTRA_PLUGINS
records() {   # records <eds file> <out json> <export json ...>: every placed record's bounds, the hall's own records added
  python -c "
import json, sys; eds = sorted({p.get('ed') for f in sys.argv[2:] for p in json.load(open(f))['pieces'] if p.get('ed')}); open(sys.argv[1], 'w').write(chr(10).join(eds))" "$1" "${@:3}"
  dotnet run -c Release --no-build -- bounds --json "$1" 2>/dev/null | grep "^{" > "$2"
  python -c "
import json, sys; r = json.load(open(sys.argv[1])); o = json.load(open('blender/own_records.json')); o.pop('_doc', None); r.update(o); json.dump(r, open(sys.argv[1], 'w'))" "$2"
}
records "$E/eds.txt" "$E/records.json" "$E/hall2_basement.json" "$E/hall2_interior.json" "$E/hall2_lookout.json"
cd "$B"; python mesh_info.py "$E/hall2_basement.json" "$E/hall2_interior.json" "$E/hall2_lookout.json" --data "$C" --out "$E/mesh_info.json" | tail -1
# (2026-11-05: this used to judge the basement's placement, seal and flicker and the site's pieces itself, and set an exit code the
# build ignored: the basement's 6 flicker pairs and the site's reports shipped unread. Each is now a gate in gates_all.sh, every
# failure held to gates/accepted.tsv. Here: the records and meshes' measures those gates read, and a first look at each part)
for p in basement lookout interior; do
  python placement_check.py "$E/hall2_$p.json" --mesh "$E/mesh_info.json" --records "$E/records.json" > "$E/place_$p.log"
  echo "$p: $(head -1 "$E/place_$p.log")"
done
cd "$HG"; records "$E/eds_site.txt" "$E/records_site.json" "$E/hall2_site_1.json"
cd "$B"; python mesh_info.py "$E/hall2_site_1.json" --data "$C" --out "$E/mesh_info_site.json" | tail -1
for f in records.json mesh_info.json records_site.json mesh_info_site.json; do [ -s "$E/$f" ] || { echo "FAILED: no $f"; fail=1; }; done
exit $fail
