using System.Text.RegularExpressions;
using Mutagen.Bethesda.Skyrim;
// TavernAisles: how wide the walkways are beside the long tables of Skyrim's taverns and the mods' (for the Guild
// Hall's tavern layout, compared with how other taverns, mods' inns especially, lay theirs out).
// A tavern is an interior cell with a bar counter or a bar stool in it, or "Inn"/"Tavern" in its name. For every long table (a static
// table at least 150 long) and each side: rays out from the side's middle part; the seats against it (a bench or chair starting within
// 60 of the edge) are stepped over, and the walkway is measured from the seats' outer edge to the next piece of furniture, or to where
// the floor's navmesh ends (a wall: the navmesh stops short of a wall, so that figure is the navmesh's width, a little under the floor's).
// Pieces by their records' bounds (a furniture record's bounds often include its sitters' room: such a neighbour reads a little close).
//   dotnet run -- tavernaisles [--list]      (EXTRA_PLUGINS=<mods' plugins>; a cell overridden by a later plugin is read as that plugin has it)
public static class TavernAisles
{
    record Box(string Ed, double X, double Y, double Ca, double Sa, double X0, double Y0, double X1, double Y1, bool Seat, double Z0, double Z1);
    public static void Run(List<ISkyrimModDisposableGetter> mods, bool list)
    {
        var bases = new Dictionary<Mutagen.Bethesda.Plugins.FormKey, (string ed, IObjectBoundsGetter b, bool seat, bool furn)>();
        void Add<T>(IEnumerable<T> recs, bool furn) where T : ISkyrimMajorRecordGetter, IObjectBoundedGetter
        { foreach (var r in recs) if (r.EditorID is { } e && r.ObjectBounds is { } b) bases[r.FormKey] = (e, b, furn || Regex.IsMatch(e, "Bench|Chair|Stool", RegexOptions.IgnoreCase), furn); }
        foreach (var m in mods) { Add(m.Statics, false); Add(m.Furniture, true); Add(m.Containers, false); Add(m.MoveableStatics, false); Add(m.Activators, false); }
        var cells = new Dictionary<Mutagen.Bethesda.Plugins.FormKey, (ICellGetter c, string mod)>();
        foreach (var m in mods) foreach (var bl in m.Cells) foreach (var sb in bl.SubBlocks) foreach (var c in sb.Cells) cells[c.FormKey] = (c, m.ModKey.FileName);
        var side = new List<(double w, string kind, string cell, string mod, string tbl, string seat, string what)>();
        foreach (var (c, mod) in cells.Values)
        {
            var refs = c.Persistent.Concat(c.Temporary).OfType<IPlacedObjectGetter>().Where(o => o.Placement is not null && bases.ContainsKey(o.Base.FormKey)).ToList();
            bool tavern = Regex.IsMatch(c.EditorID ?? "", "Inn|Tavern|Meadery", RegexOptions.IgnoreCase)
                          || refs.Any(o => Regex.IsMatch(bases[o.Base.FormKey].ed, "^(BarStraight|WoodenBarStool|BarLeft|BarRight)", RegexOptions.IgnoreCase));
            if (!tavern) continue;
            var boxes = new List<Box>();
            foreach (var o in refs)
            {
                var (ed, b, seat, furn) = bases[o.Base.FormKey]; var pl = o.Placement!; double s = o.Scale ?? 1;
                double w = (b.Second.X - b.First.X) * s, d = (b.Second.Y - b.First.Y) * s, h = (b.Second.Z - b.First.Z) * s;
                if (h < 20 || w > 700 || d > 700 || w < 4 || d < 4) continue;            // (rugs, markers, room shells)
                // furniture only (walls are where the floor's navmesh ends): what stands on a tavern's floor
                if (!furn && !Regex.IsMatch(ed, "Table|Chair|Bench|Stool|^Bar|Barrel|Keg|Crate|Cupboard|Wardrobe|Dresser|Chest|Counter|FirePit|Hearth|Column|Pillar|Post|Endtable|Sack|Basket|Rack|Loom|Anvil|Grindstone", RegexOptions.IgnoreCase)) continue;
                if (Regex.IsMatch(ed, "Marker|Rug|Carpet", RegexOptions.IgnoreCase)) continue;
                double z0 = pl.Position.Z + b.First.Z * s, z1 = pl.Position.Z + b.Second.Z * s;
                boxes.Add(new Box(ed, pl.Position.X, pl.Position.Y, Math.Cos(pl.Rotation.Z), Math.Sin(pl.Rotation.Z), b.First.X * s, b.First.Y * s, b.Second.X * s, b.Second.Y * s, seat, z0, z1));
            }
            var nav = c.NavigationMeshes.Select(n => n.Data).Where(d => d is not null).SelectMany(d => d!.Triangles.Select(t => (d.Vertices[t.Vertices.X], d.Vertices[t.Vertices.Y], d.Vertices[t.Vertices.Z]))).ToList();
            bool In(Box bx, double x, double y)
            {   // (world -> the box's own frame: the inverse of x = X + lx*ca + ly*sa, y = Y - lx*sa + ly*ca)
                double dx = x - bx.X, dy = y - bx.Y, lx = dx * bx.Ca - dy * bx.Sa, ly = dx * bx.Sa + dy * bx.Ca;
                return lx >= bx.X0 && lx <= bx.X1 && ly >= bx.Y0 && ly <= bx.Y1;
            }
            bool OnNav(double x, double y, double z)
            {
                foreach (var (A, B, C) in nav)
                {
                    if (Math.Abs((A.Z + B.Z + C.Z) / 3 - z) > 40) continue;
                    if (Math.Max(A.X, Math.Max(B.X, C.X)) < x || Math.Min(A.X, Math.Min(B.X, C.X)) > x || Math.Max(A.Y, Math.Max(B.Y, C.Y)) < y || Math.Min(A.Y, Math.Min(B.Y, C.Y)) > y) continue;
                    double D = (B.Y - C.Y) * (A.X - C.X) + (C.X - B.X) * (A.Y - C.Y); if (Math.Abs(D) < 1e-9) continue;
                    double u = ((B.Y - C.Y) * (x - C.X) + (C.X - B.X) * (y - C.Y)) / D, v = ((C.Y - A.Y) * (x - C.X) + (A.X - C.X) * (y - C.Y)) / D;
                    if (u >= -1e-6 && v >= -1e-6 && u + v <= 1 + 1e-6) return true;
                }
                return false;
            }
            foreach (var t in boxes.Where(b => !b.Seat && Regex.IsMatch(b.Ed, "Table", RegexOptions.IgnoreCase) && !Regex.IsMatch(b.Ed, "Round|End|Night|Small|Alch|Ench|Smith|Map|Cloth", RegexOptions.IgnoreCase)))
            {
                double L = Math.Max(t.X1 - t.X0, t.Y1 - t.Y0); if (L < 150) continue;
                bool longX = t.X1 - t.X0 >= t.Y1 - t.Y0; double floorZ = t.Z0;
                // the 4 sides: (outward normal in the table's frame, the side's half-length); "long" = the sides along its length
                foreach (var (nx, ny) in new[] { (0.0, 1.0), (0.0, -1.0), (1.0, 0.0), (-1.0, 0.0) })
                {
                    bool isLong = longX ? nx == 0 : ny == 0;
                    double cx = (t.X0 + t.X1) / 2, cy = (t.Y0 + t.Y1) / 2, hx = (t.X1 - t.X0) / 2, hy = (t.Y1 - t.Y0) / 2;
                    double best = double.MaxValue; string seatEd = "-", what = "-", kind = "-";
                    foreach (var f in new[] { -0.3, 0.0, 0.3 })
                    {
                        double lx0 = cx + nx * hx + (nx == 0 ? f * 2 * hx : 0), ly0 = cy + ny * hy + (ny == 0 ? f * 2 * hy : 0);
                        double start = 0; string sEd = "-"; Box? inSeat = null; double? hit = null; string hw = "-", hk = "-"; bool seenNav = false;
                        double sx0 = t.X + lx0 * t.Ca + ly0 * t.Sa, sy0 = t.Y - lx0 * t.Sa + ly0 * t.Ca;
                        var ignore = boxes.Where(o => !o.Seat && In(o, sx0, sy0)).ToHashSet();       // (what the table stands in or against: a shell, a dais)
                        for (double s = 1; s <= 420; s += 2)
                        {
                            double lx = lx0 + nx * s, ly = ly0 + ny * s, x = t.X + lx * t.Ca + ly * t.Sa, y = t.Y - lx * t.Sa + ly * t.Ca;
                            var b = boxes.FirstOrDefault(o => !ReferenceEquals(o, t) && !ignore.Contains(o) && o.Z1 > floorZ + 15 && o.Z0 < floorZ + 120 && In(o, x, y));
                            if (inSeat is not null) { if (b is null || !ReferenceEquals(b, inSeat)) { start = s; inSeat = null; if (b is null) continue; } else continue; }
                            if (b is not null)
                            {
                                if (b.Seat && s - start < 60 && sEd == "-") { inSeat = b; sEd = b.Ed; continue; }
                                hit = s - start; hw = b.Ed; hk = "furniture"; break;
                            }
                            if (nav.Count > 0) { bool on = OnNav(x, y, floorZ); if (on) seenNav = true; else if (seenNav) { hit = s - start; hw = "navmesh end"; hk = "wall/edge"; break; } }
                        }
                        if (hit is { } h && h < best) { best = h; seatEd = sEd; what = hw; kind = hk; }
                    }
                    if (best < 400) side.Add((best, (isLong ? "long" : "end") + (seatEd != "-" ? "+seats" : "") + " -> " + kind, c.EditorID ?? c.FormKey.ToString(), mod, t.Ed, seatEd, what));
                }
            }
        }
        string Q(List<double> l) { l.Sort(); return l.Count == 0 ? "-" : $"n {l.Count,4}, 10% {l[l.Count / 10],4:F0}, 25% {l[l.Count / 4],4:F0}, median {l[l.Count / 2],4:F0}, 75% {l[l.Count * 3 / 4],4:F0}"; }
        foreach (var grp in side.GroupBy(s => s.mod.StartsWith("Skyrim.esm") || s.mod.StartsWith("Dawnguard") || s.mod.StartsWith("Dragonborn") || s.mod.StartsWith("HearthFires") || s.mod.StartsWith("Update") ? "vanilla" : s.mod.Contains("Guild") ? "ours" : "mods"))
        {
            Console.WriteLine($"== {grp.Key}: {grp.Select(s => s.cell).Distinct().Count()} tavern cells");
            foreach (var k in grp.GroupBy(s => s.kind).OrderBy(k => k.Key)) Console.WriteLine($"  {k.Key,-34} {Q(k.Select(s => s.w).ToList())}");
        }
        if (list) foreach (var s in side.OrderBy(s => s.mod).ThenBy(s => s.cell)) Console.WriteLine($"  {s.mod,-28} {s.cell,-32} {s.tbl,-22} {s.kind,-30} {s.w,4:F0}  seat {s.seat}, then {s.what}");
    }
}
