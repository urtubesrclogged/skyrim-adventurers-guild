using Mutagen.Bethesda.Skyrim;

// Navmesh: the triangles of every navmesh in a block of Tamriel's cells (the winning copy of each), as JSON lines:
// {"cell":[x,y],"nav":"formkey","tris":[[x1,y1,z1,x2,y2,z2,x3,y3,z3],...]}  -- to see where NPCs can walk
static class Navmesh
{
    public static void Run(List<ISkyrimModDisposableGetter> mods, int cx0, int cy0, int cx1, int cy1)
    {
        var tamKey = new Mutagen.Bethesda.Plugins.FormKey(Mutagen.Bethesda.Plugins.ModKey.FromFileName("Skyrim.esm"), 0x00003C);
        var navs = new Dictionary<Mutagen.Bethesda.Plugins.FormKey, (int, int, INavigationMeshGetter)>();
        foreach (var m in mods)
            foreach (var w in m.Worldspaces.Where(w => w.FormKey == tamKey))
                foreach (var b in w.SubCells) foreach (var sb in b.Items) foreach (var c in sb.Items)
                {
                    if (c.Grid is not { } gr || gr.Point.X < cx0 || gr.Point.X > cx1 || gr.Point.Y < cy0 || gr.Point.Y > cy1) continue;
                    foreach (var n in c.NavigationMeshes) navs[n.FormKey] = (gr.Point.X, gr.Point.Y, n);
                }
        foreach (var (key, (x, y, n)) in navs)
        {
            if (n.Data is not { } d) continue;
            var v = d.Vertices;
            var tris = d.Triangles.Select(t => new[] { v[t.Vertices.X], v[t.Vertices.Y], v[t.Vertices.Z] }
                .SelectMany(p => new[] { Math.Round(p.X), Math.Round(p.Y), Math.Round(p.Z) }));
            Console.WriteLine(System.Text.Json.JsonSerializer.Serialize(new { cell = new[] { x, y }, nav = key.ToString(), tris }));
        }
    }
}
