using System.Text.RegularExpressions;
using Mutagen.Bethesda.Skyrim;
// Pairs: how vanilla sets one piece with another (a quill floated by its inkwell): every reference
// of base B within r of a reference of base A in the same cell, its offset in A's frame, its rotation (degrees) and flags.
//   dotnet run -- pairs "<A editor ID regex>" "<B editor ID regex>" [r]
static class Pairs
{
    public static void Run(List<ISkyrimModDisposableGetter> mods, string aPat, string bPat, double r)
    {
        var ra = new Regex(aPat, RegexOptions.IgnoreCase); var rb = new Regex(bPat, RegexOptions.IgnoreCase);
        var ed = new Dictionary<Mutagen.Bethesda.Plugins.FormKey, string>();
        foreach (var m in mods) foreach (var x in m.EnumerateMajorRecords()) if (x.EditorID is { } e) ed[x.FormKey] = e;
        const double D = 180 / Math.PI;
        // (2026-10-29) the interiors' cells, and the worldspaces' (each exterior cell with its world's persistent refs: an
        // exterior building's doors and statics are often persistent while its clutter is not)
        var groups = new List<(string name, List<IPlacedObjectGetter> refs)>();
        foreach (var m in mods) foreach (var bl in m.Cells) foreach (var sb in bl.SubBlocks) foreach (var c in sb.Cells)
            groups.Add((c.EditorID ?? "?", c.Persistent.Concat(c.Temporary).OfType<IPlacedObjectGetter>().Where(x => x.Placement is not null).ToList()));
        foreach (var m in mods) foreach (var w in m.Worldspaces)
        {
            var pers = w.TopCell is { } tc ? tc.Persistent.Concat(tc.Temporary).OfType<IPlacedObjectGetter>().Where(x => x.Placement is not null).ToList() : new();
            foreach (var c in w.SubCells.SelectMany(b => b.Items).SelectMany(s => s.Items))
            {
                var rs = c.Persistent.Concat(c.Temporary).OfType<IPlacedObjectGetter>().Where(x => x.Placement is not null).ToList();
                if (rs.Count == 0) continue;
                var p0 = rs[0].Placement!.Position;
                rs.AddRange(pers.Where(x => Math.Abs(x.Placement!.Position.X - p0.X) < 6000 && Math.Abs(x.Placement.Position.Y - p0.Y) < 6000));
                groups.Add(($"{w.EditorID} {(c.Grid is { } g ? $"{g.Point.X},{g.Point.Y}" : "")}", rs));
            }
        }
        foreach (var (cname, refs) in groups)
        {
            var c = new { EditorID = cname };
            foreach (var a in refs.Where(x => ra.IsMatch(ed.GetValueOrDefault(x.Base.FormKey, ""))))
                foreach (var b in refs.Where(x => rb.IsMatch(ed.GetValueOrDefault(x.Base.FormKey, ""))))
                {
                    var pa = a.Placement!.Position; var pb = b.Placement!.Position;
                    double dx = pb.X - pa.X, dy = pb.Y - pa.Y, dz = pb.Z - pa.Z;
                    if (Math.Sqrt(dx * dx + dy * dy + dz * dz) > r) continue;
                    double z = a.Placement.Rotation.Z, c_ = Math.Cos(z), s_ = Math.Sin(z);
                    double lx = dx * c_ - dy * s_, ly = dx * s_ + dy * c_;      // (the game turns clockwise: back into A's frame)
                    var rb_ = b.Placement.Rotation;
                    Console.WriteLine($"{c.EditorID}\t{ed[a.Base.FormKey]}->{ed[b.Base.FormKey]}\tlocal {lx:0.0} {ly:0.0} {dz:0.0}\tB rot {rb_.X * D:0.0} {rb_.Y * D:0.0} {rb_.Z * D:0.0}\tA rot z {z * D:0.0}\tB flags 0x{b.MajorRecordFlagsRaw:X}{(b.Radius is { } rr ? $"\tradius {rr}" : "")}{(b.LightData is { } ld ? $"\tfade offset {ld.FadeOffset}" : "")}");
                }
        }
    }
}
