using System.Text.RegularExpressions;
using Mutagen.Bethesda.Skyrim;
// OnRefs: what vanilla sets on a piece of furniture (the office's cupboard was empty;
// its shelves dressed from vanilla's own, not guessed). For every reference of the matching bases, the references whose
// origin lies within its footprint (its local x, y half extents, turned with it) and between z0 and z1 over its origin,
// with their height over it.
//   dotnet run -- onrefs <editor ID regex> <half x> <half y> <z0> <z1> [max]
static class OnRefs
{
    public static void Run(List<ISkyrimModDisposableGetter> mods, string pattern, double hx, double hy, double z0, double z1, int max)
    {
        var re = new Regex(pattern, RegexOptions.IgnoreCase);
        var eds = new Dictionary<Mutagen.Bethesda.Plugins.FormKey, string>();
        foreach (var m in mods) foreach (var r in m.EnumerateMajorRecords()) if (r.EditorID is { } e) eds[r.FormKey] = e;
        var counts = new Dictionary<string, int>(); int n = 0;
        foreach (var m in mods) foreach (var b in m.Cells) foreach (var sb in b.SubBlocks) foreach (var c in sb.Cells)
        {
            var refs = c.Persistent.Concat(c.Temporary).OfType<IPlacedObjectGetter>().Where(r => r.Placement != null).ToList();
            foreach (var r in refs.Where(r => eds.TryGetValue(r.Base.FormKey, out var e) && re.IsMatch(e)))
            {
                var p = r.Placement!; double cz = Math.Cos(p.Rotation.Z), sz = Math.Sin(p.Rotation.Z);   // (2026-11-13: was -Z, which turned every rotated piece's items the wrong way; tested on 165 items on vanilla's corner shelves: 127 land on the shelf this way, 80 the other)
                var on = new List<string>();
                foreach (var o in refs)
                {
                    if (o == r) continue;
                    var q = o.Placement!; double dx = q.Position.X - p.Position.X, dy = q.Position.Y - p.Position.Y, dz = q.Position.Z - p.Position.Z;
                    double lx = dx * cz - dy * sz, ly = dx * sz + dy * cz;   // (into the piece's own frame)
                    if (Math.Abs(lx) > hx || Math.Abs(ly) > hy || dz < z0 || dz > z1) continue;
                    var ed = eds.GetValueOrDefault(o.Base.FormKey, "?");
                    on.Add(Environment.GetEnvironmentVariable("ONREFS_XY") == "1" ? $"{ed}@({lx:0},{ly:0},{dz:0}) yaw {(q.Rotation.Z - p.Rotation.Z) * 180 / Math.PI:0} d({dx:0},{dy:0}) rz {p.Rotation.Z * 180 / Math.PI:0}" : $"{ed}@{dz:0}");   // (ONREFS_XY=1: where on the piece, in its own frame, 2026-11-13) counts[ed] = counts.GetValueOrDefault(ed) + 1;
                }
                Console.WriteLine($"{c.EditorID}\t{on.Count}\t{string.Join(" ", on)}");
                if (++n >= max) goto done;
            }
        }
        done:
        Console.WriteLine("ONREFS most common: " + string.Join(", ", counts.OrderByDescending(kv => kv.Value).Take(30).Select(kv => $"{kv.Key} x{kv.Value}")));
    }
}
