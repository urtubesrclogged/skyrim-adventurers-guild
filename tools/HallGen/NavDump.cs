using System.Collections;
using System.Reflection;
using Mutagen.Bethesda.Skyrim;

// NavDump: a vanilla interior's navmesh as the game has it (2026-10-27, for generating the Guild Hall's own: the CK wiki
// blocks fetchers, so the conventions are measured from the masters): its header, a sample of its triangles (flags,
// cover, edge links), its door triangles, its grid, and the NAVI map entry that names it.
//   dotnet run -- navdump <cell editor ID> [triangles to print]
static class NavDump
{
    static string Show(object? o, int depth = 0)
    {
        if (o is null) return "null";
        var t = o.GetType();
        if (t.IsPrimitive || o is string || o is decimal || t.IsEnum) return o.ToString()!;
        if (o is Mutagen.Bethesda.Plugins.IFormLinkGetter fl) return fl.FormKey.ToString();
        if (t.Name.StartsWith("P3") || t.Name.StartsWith("P2")) return o.ToString()!;
        if (depth > 3) return t.Name;
        if (o is IEnumerable e && o is not string)
        {
            var items = e.Cast<object?>().ToList();
            return $"[{items.Count}: " + string.Join(", ", items.Take(6).Select(i => Show(i, depth + 1))) + (items.Count > 6 ? ", ..." : "") + "]";
        }
        var props = t.GetProperties(BindingFlags.Public | BindingFlags.Instance).Where(p => p.GetIndexParameters().Length == 0 && p.Name != "Registration" && !p.Name.StartsWith("Static"));
        return t.Name + "{" + string.Join("; ", props.Select(p => { object? v; try { v = p.GetValue(o); } catch { v = "?"; } return p.Name + "=" + Show(v, depth + 1); })) + "}";
    }

    public static void Run(List<ISkyrimModDisposableGetter> mods, string cellEd, int nTris)
    {
        if (cellEd == "--water")   // (the basement's bath: which vanilla interiors have water, at what height)
        {
            var seen = new Dictionary<Mutagen.Bethesda.Plugins.FormKey, ICellGetter>();
            foreach (var m in mods) foreach (var b in m.Cells) foreach (var sb in b.SubBlocks) foreach (var c in sb.Cells) seen[c.FormKey] = c;
            var wet = seen.Values.Where(c => c.Flags.HasFlag(Cell.Flag.HasWater) && c.WaterHeight is { } h && Math.Abs(h) < 100000).ToList();
            Console.WriteLine($"{wet.Count} interiors with water");
            foreach (var c in wet.Where(c => c.EditorID is { } e && System.Text.RegularExpressions.Regex.IsMatch(e, "Bath|Spring|Pool|Inn|House|Hall|Sanctuary|Cistern|Temple|Palace|Keep")).Take(40))
                Console.WriteLine($"  {c.EditorID} ({c.Name?.String}): water {c.WaterHeight} {c.Water.FormKeyNullable}");
            return;
        }
        if (cellEd == "--navi")
        {
            foreach (var m in mods)
                foreach (var navi in m.NavigationMeshInfoMaps)
                    Console.WriteLine($"NAVI {navi.FormKey} in {m.ModKey.FileName}: {navi.MapInfos.Count} map infos, version {navi.NavMeshVersion}, preferred pathing {(navi.PreferredPathing is null ? "none" : "present")}");
            return;
        }
        ICellGetter? cell = null; string? from = null;
        var navs = new Dictionary<Mutagen.Bethesda.Plugins.FormKey, INavigationMeshGetter>();   // (every copy's: an override
        foreach (var m in mods)                                                                   // of the cell may carry none)
            foreach (var b in m.Cells) foreach (var sb in b.SubBlocks) foreach (var c in sb.Cells)
                if (c.EditorID == cellEd || (cell is not null && c.FormKey == cell.FormKey))
                {
                    cell = c; from = m.ModKey.FileName;
                    foreach (var n0 in c.NavigationMeshes) navs[n0.FormKey] = n0;
                }
        if (cell is null) { Console.WriteLine("no cell " + cellEd); return; }
        Console.WriteLine($"cell {cellEd} {cell.FormKey} (winning copy in {from}), {navs.Count} navmesh(es)");
        foreach (var n in navs.Values)
        {
            Console.WriteLine($"NAVM {n.FormKey} flags {n.MajorRecordFlagsRaw:X8}");
            if (n.Data is not { } d) continue;
            Console.WriteLine($"  version/parent: {Show(d.NavmeshVersion)} / {Show(d.Parent)}");
            Console.WriteLine($"  vertices {d.Vertices.Count}, triangles {d.Triangles.Count}, edge links {d.EdgeLinks.Count}, door triangles {d.DoorTriangles.Count}");
            int ccw = 0, cw = 0;
            foreach (var t in d.Triangles)
            {
                var A = d.Vertices[t.Vertices.X]; var B = d.Vertices[t.Vertices.Y]; var C = d.Vertices[t.Vertices.Z];
                var cr = (B.X - A.X) * (C.Y - A.Y) - (B.Y - A.Y) * (C.X - A.X);
                if (cr > 0) ccw++; else if (cr < 0) cw++;
            }
            Console.WriteLine($"  winding seen from above: {ccw} counter-clockwise, {cw} clockwise");
            var flags = d.Triangles.GroupBy(t => t.Flags.ToString()).OrderByDescending(g => g.Count()).Take(12);
            Console.WriteLine("  triangle flags: " + string.Join(" | ", flags.Select(g => $"{g.Key} x{g.Count()}")));
            var covers = d.Triangles.GroupBy(t => Show(t.CoverFlags)).OrderByDescending(g => g.Count()).Take(6);
            Console.WriteLine("  cover: " + string.Join(" | ", covers.Select(g => $"{g.Key} x{g.Count()}")));
            foreach (var t in d.Triangles.Take(nTris)) Console.WriteLine("  tri " + Show(t));
            foreach (var l in d.EdgeLinks.Take(4)) Console.WriteLine("  edge link " + Show(l));
            foreach (var dt in d.DoorTriangles.Take(6)) Console.WriteLine("  door tri " + Show(dt));
            Console.WriteLine("  grid: " + Show(d.NavmeshGrid).Substring(0, Math.Min(1500, Show(d.NavmeshGrid).Length)));
            Console.WriteLine("  other: " + string.Join("; ", d.GetType().GetProperties().Where(p => !new[] { "Vertices", "Triangles", "EdgeLinks", "DoorTriangles", "NavmeshGrid" }.Contains(p.Name))
                .Select(p => { object? v; try { v = p.GetValue(d); } catch { v = "?"; } return p.Name + "=" + Show(v, 2); })));
            foreach (var m in mods)
                foreach (var navi in m.NavigationMeshInfoMaps)
                    foreach (var mi in navi.MapInfos.Where(x => x.NavigationMesh.FormKey == n.FormKey))
                        Console.WriteLine($"  NAVI ({m.ModKey.FileName} {navi.FormKey}): " + Show(mi));
        }
    }
}
