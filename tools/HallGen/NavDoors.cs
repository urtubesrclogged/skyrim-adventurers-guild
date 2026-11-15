using System.Text.RegularExpressions;
using Mutagen.Bethesda.Skyrim;
// NavDoors: how vanilla's navmeshes treat a cell's doors (Willem was blocked by the door to his bedroom;
// our load doors had no XNDP). For every door reference in the cells: load door or inner door, its XNDP, whether its navmesh's
// door triangles name it, and the flags of the triangle nearest it.
//   dotnet run -- navdoors ["<cell editor ID regex>"] [--list]    (EXTRA_PLUGINS=<the hall's plugin> for ours)
public static class NavDoors
{
    public static void Run(List<ISkyrimModDisposableGetter> mods, string rx, bool list)
    {
        var r = new Regex(rx);
        var doors = new HashSet<Mutagen.Bethesda.Plugins.FormKey>();
        foreach (var m in mods) foreach (var d in m.Doors) doors.Add(d.FormKey);
        var tally = new SortedDictionary<string, int>();
        foreach (var m in mods) foreach (var b in m.Cells) foreach (var sb in b.SubBlocks) foreach (var c in sb.Cells)
        {
            if (c.EditorID is not { } e || !r.IsMatch(e) || !c.Flags.HasFlag(Cell.Flag.IsInteriorCell)) continue;
            var nav = c.NavigationMeshes.Select(n => n.Data).Where(d => d is not null && d.Triangles.Count > 0).ToList();
            if (nav.Count == 0) continue;
            var inTri = new HashSet<Mutagen.Bethesda.Plugins.FormKey>();
            foreach (var d in nav) foreach (var dt in d!.DoorTriangles) inTri.Add(dt.Door.FormKey);
            foreach (var o in c.Persistent.Concat(c.Temporary).OfType<IPlacedObjectGetter>())
            {
                if (!doors.Contains(o.Base.FormKey) || o.Placement is not { } pl) continue;
                var p = pl.Position; string kind = o.TeleportDestination is null ? "inner" : "load";
                double best = 1e9; string fl = "none";
                foreach (var d in nav) foreach (var t in d!.Triangles)
                {
                    var A = d.Vertices[t.Vertices.X]; var B = d.Vertices[t.Vertices.Y]; var C = d.Vertices[t.Vertices.Z];
                    double cx = (A.X + B.X + C.X) / 3, cy = (A.Y + B.Y + C.Y) / 3, cz = (A.Z + B.Z + C.Z) / 3;
                    double g = Math.Sqrt((cx - p.X) * (cx - p.X) + (cy - p.Y) * (cy - p.Y)) + Math.Abs(cz - p.Z) * 0.5;
                    if (g < best) { best = g; fl = t.Flags.ToString(); }
                }
                var key = $"{kind,-5} XNDP {(o.NavigationDoorLink is null ? "no " : "yes")} door-triangle {(inTri.Contains(o.FormKey) ? "yes" : "no ")} nearest tri {fl}";
                tally[key] = tally.GetValueOrDefault(key) + 1;
                if (list) Console.WriteLine($"{e,-30} {kind,-5} at ({p.X:F0}, {p.Y:F0}, {p.Z:F0}) XNDP {(o.NavigationDoorLink is null ? "no" : "yes")} tri-list {(inTri.Contains(o.FormKey) ? "yes" : "no")} nearest {best:F0} {fl}");
            }
        }
        foreach (var kv in tally.OrderByDescending(k => k.Value)) Console.WriteLine($"{kv.Value,6}  {kv.Key}");
    }
}
// (2026-10-30: the engine keeps an actor's radius off a navmesh's edge itself, fNavmeshBoundsActorRadiusMultiplier, and the hall's mesh is
// eroded by a radius first.) The navmesh's width through each inner door, along the door's plane from the middle of its leaf, against the door's.
//   dotnet run -- navdoorw ["<cell editor ID regex>"] [--list]
public static class NavDoorW
{
    public static void Run(List<ISkyrimModDisposableGetter> mods, string rx, bool list)
    {
        var r = new Regex(rx);
        var doors = new Dictionary<Mutagen.Bethesda.Plugins.FormKey, IDoorGetter>();
        foreach (var m in mods) foreach (var d in m.Doors) doors[d.FormKey] = d;
        var w = new List<double>(); var fr = new List<double>(); int off = 0;
        foreach (var m in mods) foreach (var b in m.Cells) foreach (var sb in b.SubBlocks) foreach (var c in sb.Cells)
        {
            if (c.EditorID is not { } e || !r.IsMatch(e) || !c.Flags.HasFlag(Cell.Flag.IsInteriorCell)) continue;
            var nav = c.NavigationMeshes.Select(n => n.Data).Where(d => d is not null && d.Triangles.Count > 0).ToList();
            if (nav.Count == 0) continue;
            foreach (var o in c.Persistent.Concat(c.Temporary).OfType<IPlacedObjectGetter>())
            {
                if (!doors.TryGetValue(o.Base.FormKey, out var bd) || o.TeleportDestination is not null || o.Placement is not { } pl || bd.ObjectBounds is not { } ob) continue;
                double a = pl.Rotation.Z, ca = Math.Cos(a), sa = Math.Sin(a); double L(double lx, double ly, out double wy) { wy = pl.Position.Y - lx * sa + ly * ca; return pl.Position.X + lx * ca + ly * sa; }
                double wx = ob.Second.X - ob.First.X, wy_ = ob.Second.Y - ob.First.Y; bool alongX = wx >= wy_;   // (a door's leaf runs along whichever is longer: a Solitude door's along its local y, hinge at the origin)
                double dw = Math.Max(wx, wy_), mx = (ob.First.X + ob.Second.X) / 2.0, my = (ob.First.Y + ob.Second.Y) / 2.0;
                if (dw < 30 || dw > 220) continue;
                var tris = new List<(Noggog.P3Float A, Noggog.P3Float B, Noggog.P3Float C)>();
                foreach (var d in nav) foreach (var t in d!.Triangles)
                {
                    var A = d.Vertices[t.Vertices.X]; var B = d.Vertices[t.Vertices.Y]; var C = d.Vertices[t.Vertices.Z];
                    if (Math.Abs((A.Z + B.Z + C.Z) / 3 - pl.Position.Z) > 50) continue;
                    if (Math.Min(A.X, Math.Min(B.X, C.X)) > pl.Position.X + 300 || Math.Max(A.X, Math.Max(B.X, C.X)) < pl.Position.X - 300 || Math.Min(A.Y, Math.Min(B.Y, C.Y)) > pl.Position.Y + 300 || Math.Max(A.Y, Math.Max(B.Y, C.Y)) < pl.Position.Y - 300) continue;
                    tris.Add((A, B, C));
                }
                bool On(double x, double y)
                {
                    foreach (var (A, B, C) in tris)
                    {
                        double D = (B.Y - C.Y) * (A.X - C.X) + (C.X - B.X) * (A.Y - C.Y); if (Math.Abs(D) < 1e-9) continue;
                        double u = ((B.Y - C.Y) * (x - C.X) + (C.X - B.X) * (y - C.Y)) / D, v = ((C.Y - A.Y) * (x - C.X) + (A.X - C.X) * (y - C.Y)) / D;
                        if (u >= -1e-6 && v >= -1e-6 && u + v <= 1 + 1e-6) return true;
                    }
                    return false;
                }
                // the run through the door's middle along its plane, the narrowest of the plane and just either side of it
                double best = 1e9;
                foreach (var dy in new[] { 0.0, -6, 6 })
                {
                    double P_(double t, out double y_) => alongX ? L(mx + t, my + dy, out y_) : L(mx + dy, my + t, out y_);
                    var x0_ = P_(0, out var y0_); if (!On(x0_, y0_)) { best = 0; continue; }
                    double run = 0;
                    foreach (var sgn in new[] { -1.0, 1.0 })
                        for (double s = 2; s <= dw + 60; s += 2) { var x = P_(sgn * s, out var y); if (!On(x, y)) break; run += 2; }
                    best = Math.Min(best, run);
                }
                if (best <= 0) { off++; continue; }
                w.Add(best); fr.Add(best / dw);
                if (list) Console.WriteLine($"{e,-30} door {bd.EditorID,-32} at ({pl.Position.X:F0}, {pl.Position.Y:F0}, {pl.Position.Z:F0}) width {dw:F0} navmesh {best:F0} ({100 * best / dw:F0}%)");
            }
        }
        w.Sort(); fr.Sort(); double P(List<double> l, double f) => l.Count == 0 ? 0 : l[(int)(f * (l.Count - 1))];
        Console.WriteLine($"inner doors measured {w.Count}, no navmesh on the plane {off}; navmesh across them 5/25/50/75%: {P(w, .05):F0} {P(w, .25):F0} {P(w, .5):F0} {P(w, .75):F0}; of the door's width 5/25/50/75%: {100 * P(fr, .05):F0} {100 * P(fr, .25):F0} {100 * P(fr, .5):F0} {100 * P(fr, .75):F0}%");
    }
}
// DoorRefs: a load door's reference, field by field (2026-10-30, the basement door stuck in state 4 after each use): where it is filed, its flags, teleport flags, lock, scale, location ref types, owner.
//   dotnet run -- doorrefs "<base editor ID regex>" "<cell regex>" [n]
public static class DoorRefs
{
    public static void Run(List<ISkyrimModDisposableGetter> mods, string baseRx, string cellRx, int n)
    {
        var rb = new Regex(baseRx); var rc = new Regex(cellRx); var doors = new Dictionary<Mutagen.Bethesda.Plugins.FormKey, IDoorGetter>();
        foreach (var m in mods) foreach (var d in m.Doors) if (d.EditorID is { } e && rb.IsMatch(e)) doors[d.FormKey] = d;
        foreach (var d in doors.Values) Console.WriteLine($"base {d.EditorID}: flags {d.Flags} open sound {d.OpenSound.FormKeyNullable} close {d.CloseSound.FormKeyNullable} loop {d.LoopSound.FormKeyNullable} script {d.VirtualMachineAdapter is not null}");
        int k = 0;
        foreach (var m in mods) foreach (var b in m.Cells) foreach (var sb in b.SubBlocks) foreach (var c in sb.Cells)
        {
            if (c.EditorID is not { } e || !rc.IsMatch(e)) continue;
            foreach (var (grp, list) in new[] { ("persistent", c.Persistent), ("temporary", c.Temporary) })
                foreach (var o in list.OfType<IPlacedObjectGetter>())
                {
                    if (!doors.ContainsKey(o.Base.FormKey) || k++ >= n) continue;
                    var t = o.TeleportDestination;
                    Console.WriteLine($"{e,-26} {o.FormKey} {grp} flags 0x{o.MajorRecordFlagsRaw:X} scale {o.Scale} tel {(t is null ? "none" : $"-> {t.Door.FormKey} flags {t.Flags}")} loctypes {o.LocationRefTypes?.Count} lock {o.Lock?.Level} owner {o.Owner.FormKeyNullable} xndp {(o.NavigationDoorLink is null ? "no" : "yes")} radius {o.Radius} primitive {o.Primitive is not null} encounter {o.EncounterZone.FormKeyNullable} water {o.WaterVelocity is not null} parent {o.EnableParent is not null}");
                }
        }
    }
}
// LoadDoorUse: which door bases vanilla's load doors are, and how many of each stand unlocked (2026-10-30: SSingleDoorInt01Load stands once, locked to a key).
//   dotnet run -- loaddooruse "<cell regex>"
public static class LoadDoorUse
{
    public static void Run(List<ISkyrimModDisposableGetter> mods, string rx)
    {
        var r = new Regex(rx); var doors = new Dictionary<Mutagen.Bethesda.Plugins.FormKey, IDoorGetter>();
        foreach (var m in mods) foreach (var d in m.Doors) doors[d.FormKey] = d;
        var n = new Dictionary<string, (int all, int open, string model)>();
        foreach (var m in mods) foreach (var b in m.Cells) foreach (var sb in b.SubBlocks) foreach (var c in sb.Cells)
        {
            if (c.EditorID is not { } e || !r.IsMatch(e) || !c.Flags.HasFlag(Cell.Flag.IsInteriorCell)) continue;
            foreach (var o in c.Persistent.Concat(c.Temporary).OfType<IPlacedObjectGetter>())
            {
                if (o.TeleportDestination is null || !doors.TryGetValue(o.Base.FormKey, out var d)) continue;
                var k = d.EditorID ?? "?"; var v = n.GetValueOrDefault(k, (0, 0, d.Model?.File.ToString() ?? "")); n[k] = (v.Item1 + 1, v.Item2 + (o.Lock is null ? 1 : 0), v.Item3);
            }
        }
        foreach (var kv in n.OrderByDescending(k => k.Value.all).Take(24)) Console.WriteLine($"{kv.Value.all,5} refs, {kv.Value.open,5} unlocked  {kv.Key,-34} {kv.Value.model}");
    }
}
