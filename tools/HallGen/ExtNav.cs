using Mutagen.Bethesda.Skyrim;
using Mutagen.Bethesda.Plugins;

// ExtNav: how vanilla writes an EXTERIOR navmesh and blocks navmesh with collision (2026-11-13, the hall's own outdoor NAVM
// records, option 2 of the outdoor navmesh plan): the navmeshes of the Tamriel cells round a point (parent, vertices, grid,
// flags, edge links to other navmeshes, their NAVI entries), the collision layers flagged Navmesh Obstacle, the base objects
// flagged Obstacle, and placed collision primitives (XPRM with a collision layer) by layer.
//   dotnet run -- extnav <cx> <cy> [radius in cells]
static class ExtNav
{
    public static void Run(List<ISkyrimModDisposableGetter> mods, int cx, int cy, int rad)
    {
        var tamriel = new FormKey(ModKey.FromFileName("Skyrim.esm"), 0x00003C);
        // the winning copy of each navmesh in the cells round (cx, cy), with the plugin it comes from
        var navs = new Dictionary<FormKey, (INavigationMeshGetter n, string from, int x, int y)>();
        foreach (var m in mods)
            foreach (var ws in m.Worldspaces)
            {
                if (ws.FormKey != tamriel) continue;
                foreach (var b in ws.SubCells) foreach (var sb in b.Items) foreach (var c in sb.Items)
                {
                    if (c.Grid is not { } g) continue;
                    if (Math.Abs(g.Point.X - cx) > rad || Math.Abs(g.Point.Y - cy) > rad) continue;
                    foreach (var n in c.NavigationMeshes) navs[n.FormKey] = (n, m.ModKey.FileName, g.Point.X, g.Point.Y);
                }
            }
        var infos = new Dictionary<FormKey, (INavigationMapInfoGetter i, string from)>();
        foreach (var m in mods) foreach (var navi in m.NavigationMeshInfoMaps) foreach (var i in navi.MapInfos) infos[i.NavigationMesh.FormKey] = (i, m.ModKey.FileName);
        Console.WriteLine($"{navs.Count} navmesh(es) in cells ({cx - rad}..{cx + rad}, {cy - rad}..{cy + rad})");
        var flagCount = new Dictionary<string, int>(); var crc = new Dictionary<uint, int>(); var ver = new Dictionary<uint, int>();
        var areas = new List<double>();
        foreach (var (key, (n, from, x, y)) in navs.OrderBy(k => k.Value.y).ThenBy(k => k.Value.x))
        {
            if (n.Data is not { } d) continue;
            crc[d.CrcHash] = crc.GetValueOrDefault(d.CrcHash) + 1; ver[d.NavmeshVersion] = ver.GetValueOrDefault(d.NavmeshVersion) + 1;
            var par = d.Parent is IWorldspaceNavmeshParentGetter wp ? $"world {wp.Parent.FormKey} ({wp.Coordinates.X},{wp.Coordinates.Y})" : d.Parent?.GetType().Name ?? "none";
            int ext = 0, inner = 0, open = 0, pref = 0;
            var V = d.Vertices;
            double zmin = 1e9, zmax = -1e9, xmin = 1e9, xmax = -1e9, ymin = 1e9, ymax = -1e9;
            foreach (var v in V) { zmin = Math.Min(zmin, v.Z); zmax = Math.Max(zmax, v.Z); xmin = Math.Min(xmin, v.X); xmax = Math.Max(xmax, v.X); ymin = Math.Min(ymin, v.Y); ymax = Math.Max(ymax, v.Y); }
            foreach (var t in d.Triangles)
            {
                foreach (NavmeshTriangle.Flag f in Enum.GetValues(typeof(NavmeshTriangle.Flag)))
                    if (f != 0 && t.Flags.HasFlag(f)) flagCount[f.ToString()] = flagCount.GetValueOrDefault(f.ToString()) + 1;
                if (t.Flags.HasFlag(NavmeshTriangle.Flag.Preferred)) pref++;
                var ls = new[] { t.EdgeLink_0_1, t.EdgeLink_1_2, t.EdgeLink_2_0 };
                var lf = new[] { NavmeshTriangle.Flag.EdgeLink_0_1, NavmeshTriangle.Flag.EdgeLink_1_2, NavmeshTriangle.Flag.EdgeLink_2_0 };
                for (int k = 0; k < 3; k++) { if (t.Flags.HasFlag(lf[k])) ext++; else if (ls[k] < 0) open++; else inner++; }
                var a = V[t.Vertices.X]; var b = V[t.Vertices.Y]; var c = V[t.Vertices.Z];
                areas.Add(Math.Abs((b.X - a.X) * (c.Y - a.Y) - (b.Y - a.Y) * (c.X - a.X)) / 2);
            }
            var others = d.EdgeLinks.GroupBy(e => e.Mesh.FormKey).Select(g => $"{g.Key.ID:X6}x{g.Count()}(unk {string.Join("/", g.Select(e => e.Unknown).Distinct())})");
            Console.WriteLine($"NAVM {key} [{from}] cell ({x},{y}) {par}; v{V.Count} t{d.Triangles.Count}; x {xmin:F0}..{xmax:F0} y {ymin:F0}..{ymax:F0} z {zmin:F0}..{zmax:F0}");
            Console.WriteLine($"   edges: {inner} inner, {open} open, {ext} to other navmeshes [{string.Join(" ", others)}]; preferred {pref}; door tris {d.DoorTriangles.Count}");
            Console.WriteLine($"   grid div {d.NavmeshGridDivisor} maxd {d.MaxDistanceX:F1}/{d.MaxDistanceY:F1} min {d.Min} max {d.Max}; grid bytes {d.NavmeshGrid.Length}");
            if (infos.TryGetValue(key, out var inf))
            {
                var i = inf.i;
                var ip = i.Parent is INavigationMapInfoWorldParentGetter iw ? $"world {iw.ParentWorldspace.FormKey} ({iw.ParentWorldspaceCoord.X},{iw.ParentWorldspaceCoord.Y})" : i.Parent?.GetType().Name;
                Console.WriteLine($"   NAVI [{inf.from}]: point {i.Point}; unk {i.Unknown} unk2 {i.Unknown2:X}; prefMergesFlag {i.PreferredMergesFlag}; mergedTo {i.MergedTo.Count} [{string.Join(" ", i.MergedTo.Select(z => z.FormKey.ID.ToString("X6")))}]; prefMerges {i.PreferredMerges.Count}; doors {i.LinkedDoors.Count}; island {(i.Island is null ? "none" : "yes")}; parent {ip}");
            }
            else Console.WriteLine("   NAVI: none");
        }
        areas.Sort();
        if (areas.Count > 0) Console.WriteLine($"triangle area: median {areas[areas.Count / 2]:F0}, 10% {areas[areas.Count / 10]:F0}, 90% {areas[areas.Count * 9 / 10]:F0}; {areas.Count} triangles");
        Console.WriteLine("flags: " + string.Join(", ", flagCount.OrderByDescending(k => k.Value).Select(k => $"{k.Key} {k.Value}")));
        Console.WriteLine("crc: " + string.Join(", ", crc.Select(k => $"{k.Key} x{k.Value}")) + "; version: " + string.Join(", ", ver.Select(k => $"{k.Key} x{k.Value}")));

        // collision layers flagged Navmesh Obstacle
        Console.WriteLine("\nCOLL layers:");
        var layers = new Dictionary<uint, string>();
        foreach (var m in mods) foreach (var l in m.CollisionLayers)
        {
            layers[l.Index] = l.EditorID ?? "?";
            if (l.Flags.ToString() != "0") Console.WriteLine($"  {l.Index} {l.EditorID}: flags {l.Flags}");
        }
        // base objects flagged Obstacle (record flag 1<<25) by type
        Console.WriteLine("\nbase objects with the Obstacle flag (1<<25):");
        void Ob<T>(IEnumerable<T> recs, string tag) where T : ISkyrimMajorRecordGetter
        {
            var hit = recs.Where(r => (r.MajorRecordFlagsRaw & (1 << 25)) != 0).ToList();
            Console.WriteLine($"  {tag}: {hit.Count} [{string.Join(", ", hit.Take(14).Select(r => r.EditorID))}]");
        }
        foreach (var m in mods.Take(1)) { Ob(m.Statics, "STAT"); Ob(m.Activators, "ACTI"); Ob(m.MoveableStatics, "MSTT"); Ob(m.Containers, "CONT"); Ob(m.Furniture, "FURN"); Ob(m.Doors, "DOOR"); }
        // placed collision primitives: XPRM refs with a layer (XTRI), by layer and base
        Console.WriteLine("\nplaced primitives (XPRM) by collision layer / base (all plugins loaded):");
        var prim = new Dictionary<string, int>(); var ex = new Dictionary<string, string>();
        foreach (var m in mods)
        {
            void Scan(IEnumerable<IPlacedGetter> refs, string where)
            {
                foreach (var r in refs.OfType<IPlacedObjectGetter>())
                {
                    if (r.Primitive is null) continue;
                    var lay = r.CollisionLayer is { } li ? (layers.TryGetValue((uint)li, out var ln) ? ln : li.ToString()) : "none";
                    var k = $"{lay} / base {r.Base.FormKey.ID:X6} / {r.Primitive.Type}";
                    prim[k] = prim.GetValueOrDefault(k) + 1;
                    if (!ex.ContainsKey(k)) ex[k] = $"{r.FormKey} in {where} bounds {r.Primitive.Bounds} flags {r.MajorRecordFlagsRaw:X}";
                }
            }
            foreach (var b in m.Cells) foreach (var sb in b.SubBlocks) foreach (var c in sb.Cells) Scan(c.Temporary.Concat(c.Persistent), c.EditorID ?? "?");
            foreach (var ws in m.Worldspaces)
            {
                if (ws.TopCell is { } tc) Scan(tc.Temporary.Concat(tc.Persistent), "world top");
                foreach (var b in ws.SubCells) foreach (var sb in b.Items) foreach (var c in sb.Items) Scan(c.Temporary.Concat(c.Persistent), c.EditorID ?? $"{ws.EditorID} {c.Grid?.Point}");
            }
        }
        foreach (var (k, n) in prim.OrderByDescending(p => p.Value).Take(30)) Console.WriteLine($"  {n,6}  {k}   e.g. {ex[k]}");
    }

    // L_NAVCUT boxes: exterior or interior, enable-parented or initially disabled (a runtime switch), and one in full
    public static void NavCut(List<ISkyrimModDisposableGetter> mods)
    {
        int ext = 0, inte = 0, ep = 0, dis = 0, rot = 0; var shown = 0;
        foreach (var m in mods)
        {
            void Scan(IEnumerable<IPlacedGetter> refs, string where, bool isExt)
            {
                foreach (var r in refs.OfType<IPlacedObjectGetter>())
                {
                    if (r.Primitive is null || r.CollisionLayer != 49) continue;
                    if (isExt) ext++; else inte++;
                    if (r.EnableParent is not null) ep++;
                    if ((r.MajorRecordFlagsRaw & 0x800) != 0) dis++;
                    if (r.Placement is { } pl && (Math.Abs(pl.Rotation.X) > 1e-3 || Math.Abs(pl.Rotation.Y) > 1e-3)) rot++;
                    if ((isExt && shown < 6) || (r.EnableParent is not null && shown < 12))
                    {
                        shown++;
                        Console.WriteLine($"  {r.FormKey} [{m.ModKey.FileName}] {where}: base {r.Base.FormKey} prim {r.Primitive.Type} bounds {r.Primitive.Bounds} unk {r.Primitive.Unknown} color {r.Primitive.Color} pos {r.Placement?.Position} rot {r.Placement?.Rotation} scale {r.Scale} flags {r.MajorRecordFlagsRaw:X} ep {(r.EnableParent is { } e ? e.Reference.FormKey + " " + e.Flags : "-")}");
                    }
                }
            }
            foreach (var b in m.Cells) foreach (var sb in b.SubBlocks) foreach (var c in sb.Cells) Scan(c.Temporary.Concat(c.Persistent), c.EditorID ?? "?", false);
            foreach (var ws in m.Worldspaces)
            {
                if (ws.TopCell is { } tc) Scan(tc.Temporary.Concat(tc.Persistent), ws.EditorID + " top", true);
                foreach (var b in ws.SubCells) foreach (var sb in b.Items) foreach (var c in sb.Items) Scan(c.Temporary.Concat(c.Persistent), $"{ws.EditorID} {c.Grid?.Point}", true);
            }
        }
        Console.WriteLine($"L_NAVCUT boxes: {ext} exterior, {inte} interior; {ep} enable-parented, {dis} initially disabled, {rot} tilted");
    }

    // the box size convention: for always-on exterior L_NAVCUT boxes, navmesh triangle centres within the box's footprint read as
    // half extents (+-b) and as full sizes (+-b/2), surfaces within the box's height; a box the generator cut leaves none inside
    public static void NavCutSize(List<ISkyrimModDisposableGetter> mods)
    {
        var tamriel = new FormKey(ModKey.FromFileName("Skyrim.esm"), 0x00003C);
        var cells = new Dictionary<(int, int), (List<IPlacedObjectGetter> boxes, List<INavigationMeshGetter> navs)>();
        foreach (var m in mods) foreach (var ws in m.Worldspaces)
        {
            if (ws.FormKey != tamriel) continue;
            foreach (var b in ws.SubCells) foreach (var sb in b.Items) foreach (var c in sb.Items)
            {
                if (c.Grid is not { } g) continue;
                var k = (g.Point.X, g.Point.Y);
                if (!cells.TryGetValue(k, out var e)) cells[k] = e = (new(), new());
                foreach (var r in c.Temporary.Concat(c.Persistent).OfType<IPlacedObjectGetter>())
                    if (r.Primitive is not null && r.CollisionLayer == 49 && r.EnableParent is null && (r.MajorRecordFlagsRaw & 0x800) == 0) e.boxes.Add(r);
                e.navs.AddRange(c.NavigationMeshes);
            }
        }
        int ic = 0;   // interiors too, each its own key
        foreach (var m in mods) foreach (var b in m.Cells) foreach (var sb in b.SubBlocks) foreach (var c in sb.Cells)
        {
            var k = (100000 + (int)(c.FormKey.ID & 0xFFFFFF), m.ModKey.FileName.GetHashCode());
            var bx = c.Temporary.Concat(c.Persistent).OfType<IPlacedObjectGetter>().Where(r => r.Primitive is not null && r.CollisionLayer == 49 && r.EnableParent is null && (r.MajorRecordFlagsRaw & 0x800) == 0).ToList();
            if (bx.Count == 0 || c.NavigationMeshes.Count == 0) continue;
            cells[k] = (bx, c.NavigationMeshes.ToList()); ic++;
        }
        int nb = 0, inHalf = 0, inFull = 0, boxesHalfClean = 0, boxesFullClean = 0, near = 0;
        foreach (var (k, (boxes, navs)) in cells)
            foreach (var r in boxes)
            {
                var p = r.Placement!.Position; var rz = r.Placement.Rotation.Z; var bd = r.Primitive!.Bounds;
                double c = Math.Cos(-rz), s = Math.Sin(-rz);
                int h = 0, f = 0, n = 0;
                foreach (var nv in navs) if (nv.Data is { } d)
                    foreach (var t in d.Triangles)
                    {
                        var a = d.Vertices[t.Vertices.X]; var b = d.Vertices[t.Vertices.Y]; var w = d.Vertices[t.Vertices.Z];
                        double x = (a.X + b.X + w.X) / 3 - p.X, y = (a.Y + b.Y + w.Y) / 3 - p.Y, z = (a.Z + b.Z + w.Z) / 3 - p.Z;
                        double lx = x * c - y * s, ly = x * s + y * c;
                        if (Math.Abs(lx) < bd.X * 2 && Math.Abs(ly) < bd.Y * 2 && Math.Abs(z) < bd.Z * 2) n++;
                        if (Math.Abs(z) > bd.Z) continue;
                        if (Math.Abs(lx) < bd.X * 0.8 && Math.Abs(ly) < bd.Y * 0.8) h++;
                        if (Math.Abs(lx) < bd.X * 0.4 && Math.Abs(ly) < bd.Y * 0.4) f++;
                    }
                if (n == 0) continue;   // no navmesh round it at all: says nothing
                nb++; near += n; inHalf += h; inFull += f; if (h == 0) boxesHalfClean++; if (f == 0) boxesFullClean++;
            }
        Console.WriteLine($"{nb} always-on exterior L_NAVCUT boxes with navmesh round them ({near} triangle centres within twice their bounds)");
        Console.WriteLine($"  centres inside 0.8 x bounds (half extents): {inHalf}, boxes clean {boxesHalfClean}");
        Console.WriteLine($"  centres inside 0.4 x bounds (full sizes):  {inFull}, boxes clean {boxesFullClean}");
    }
}
