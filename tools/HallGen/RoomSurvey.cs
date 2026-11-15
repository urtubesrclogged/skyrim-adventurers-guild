using System.Text.RegularExpressions;
using Mutagen.Bethesda.Skyrim;
// RoomSurvey: how vanilla builds a cell's room bounds and portals (2026-10-28, the performance pass: "do them now"). For the
// interior cells whose editor ID matches, every room marker, portal, occlusion plane and multibound: position, rotation,
// its primitive's bounds, a portal's rooms (XPOD) and size (XPTL), a room's linked rooms (XLRM); then for every other
// reference with a model, how many room boxes hold its origin when the primitive's bounds are read as half extents and as
// full sizes (which reading makes everything land in a room tells what the numbers mean).
//   dotnet run -c Release -- roomsurvey "<cell regex>"
static class RoomSurvey
{
    public static void Run(List<ISkyrimModDisposableGetter> mods, string pattern)
    {
        var re = new Regex(pattern, RegexOptions.IgnoreCase);
        var eds = new Dictionary<Mutagen.Bethesda.Plugins.FormKey, string>();
        foreach (var m in mods) foreach (var r in m.EnumerateMajorRecords()) if (r.EditorID is { } e) eds[r.FormKey] = e;
        var cells = new Dictionary<Mutagen.Bethesda.Plugins.FormKey, (string ed, Dictionary<Mutagen.Bethesda.Plugins.FormKey, IPlacedObjectGetter> refs)>();
        foreach (var m in mods)
            foreach (var c in m.Cells.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells).Where(c => re.IsMatch(c.EditorID ?? "")))
            {
                if (!cells.TryGetValue(c.FormKey, out var e)) cells[c.FormKey] = e = (c.EditorID!, new());
                foreach (var r in c.Persistent.Concat(c.Temporary).OfType<IPlacedObjectGetter>()) e.refs[r.FormKey] = r;
            }
        string F(float v) => v.ToString("0.#");
        foreach (var (ced, refs) in cells.Values)
        {
            var all = refs.Values.Where(r => !r.IsDeleted && r.Placement != null).ToList();
            var rooms = all.Where(r => eds.GetValueOrDefault(r.Base.FormKey, "") == "RoomMarker").ToList();
            Console.WriteLine($"== {ced}: {all.Count} refs");
            foreach (var r in all)
            {
                var ed = eds.GetValueOrDefault(r.Base.FormKey, "?");
                if (r.Primitive == null && r.RoomPortal == null && r.OcclusionPlane == null && r.Portals == null && r.LinkedRooms is not { Count: > 0 } && r.BoundHalfExtents == null) continue;
                var p = r.Placement!;
                var s = $"{ed}\t{r.FormKey.ID:X6}\tpos {F(p.Position.X)},{F(p.Position.Y)},{F(p.Position.Z)}\trot {p.Rotation.X:0.###},{p.Rotation.Y:0.###},{p.Rotation.Z:0.###}\tscale {r.Scale ?? 1}";
                if (r.Primitive is { } pr) s += $"\tprim {pr.Type} {F(pr.Bounds.X)}x{F(pr.Bounds.Y)}x{F(pr.Bounds.Z)}";
                if (r.RoomPortal is { } rp) s += $"\tXPTL w {F(rp.Width)} h {F(rp.Height)} at {F(rp.Position.X)},{F(rp.Position.Y)},{F(rp.Position.Z)} q {rp.RotationQ1:0.###},{rp.RotationQ2:0.###},{rp.RotationQ3:0.###},{rp.RotationQ4:0.###}";
                if (r.OcclusionPlane is { } op) s += $"\tXOCP w {F(op.Width)} h {F(op.Height)}";
                if (r.Portals is { } po) s += "\tXPOD " + string.Join(" ", po.Select(x => $"{x.Origin.FormKey.ID:X6}->{x.Destination.FormKey.ID:X6}"));
                if (r.LinkedRooms is { Count: > 0 } lr) s += "\tXLRM " + string.Join(" ", lr.Select(x => $"{x.FormKey.ID:X6}"));
                if (r.BoundHalfExtents is { } bh) s += $"\tXMBO {F(bh.X)},{F(bh.Y)},{F(bh.Z)}";
                if (r.MultiBoundReference.FormKeyNullable is { } mb) s += $"\tXMBR {mb.ID:X6}";
                Console.WriteLine(s);
            }
            foreach (var half in new[] { true, false })
            {
                int none = 0, one = 0, many = 0; var outside = new List<string>();
                foreach (var r in all)
                {
                    var ed = eds.GetValueOrDefault(r.Base.FormKey, "?");
                    if (ed is "RoomMarker" or "PortalMarker" or "PlaneMarker" or "CollisionMarker") continue;
                    int n = rooms.Count(rm => Inside(rm, r.Placement!.Position, half));
                    if (n == 0) { none++; if (outside.Count < 12) outside.Add(ed); } else if (n == 1) one++; else many++;
                }
                Console.WriteLine($"  bounds as {(half ? "half extents" : "full sizes")}: in no room {none}, in one {one}, in several {many}; outside e.g. {string.Join(" ", outside)}");
            }
        }
    }

    static bool Inside(IPlacedObjectGetter room, Noggog.P3Float q, bool half)
    {
        var p = room.Placement!; var b = room.Primitive!.Bounds; float k = half ? 1f : 0.5f;
        double dx = q.X - p.Position.X, dy = q.Y - p.Position.Y, dz = q.Z - p.Position.Z;
        // into the box's frame: Skyrim's rotations are applied Z, then Y, then X (inverse here)
        double cz = Math.Cos(p.Rotation.Z), sz = Math.Sin(p.Rotation.Z);   // (2026-11-13: Z was turned the wrong way, as OnRefs' was; X and Y not yet tested)
        double x1 = dx * cz - dy * sz, y1 = dx * sz + dy * cz, z1 = dz;
        double cy = Math.Cos(-p.Rotation.Y), sy = Math.Sin(-p.Rotation.Y);
        double x2 = x1 * cy + z1 * sy, z2 = -x1 * sy + z1 * cy;
        double cx = Math.Cos(-p.Rotation.X), sx = Math.Sin(-p.Rotation.X);
        double y3 = y1 * cx - z2 * sx, z3 = y1 * sx + z2 * cx;
        float sc = room.Scale ?? 1f;
        return Math.Abs(x2) <= b.X * k * sc && Math.Abs(y3) <= b.Y * k * sc && Math.Abs(z3) <= b.Z * k * sc;
    }
}
