using Mutagen.Bethesda;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Skyrim;
using Noggog;

// The Creation Kit starter: AGHallCK.esp, the composed hall (a layout JSON) as plain references in its exterior cell,
// for arranging by eye in the CK. It overrides that vanilla cell (a full ESP, not light), so it is a CK workspace,
// not something to ship. The marker AGHallCKOrigin is the building's origin: positions are read back relative to it.
static class Ck
{
    static readonly ModKey Own = ModKey.FromFileName("AGHallCK.esp");
    static uint next = 0x800;
    static FormKey New() => new FormKey(Own, next++);

    public static void Run(List<ISkyrimModDisposableGetter> mods, string layoutPath, string outDir)
    {
        var mod = new SkyrimMod(Own, SkyrimRelease.SkyrimSE);
        using var doc = System.Text.Json.JsonDocument.Parse(File.ReadAllText(layoutPath));
        var root = doc.RootElement;
        var o = root.GetProperty("origin").EnumerateArray().Select(v => v.GetDouble()).ToArray();
        double yaw = root.GetProperty("yaw").GetDouble(), a = yaw * Math.PI / 180, ca = Math.Cos(a), sa = Math.Sin(a);

        // our own meshes become our own statics; every other model is found among the vanilla statics and doors
        Static OwnStatic(string ed, string model, short x0, short y0, short z0, short x1, short y1, short z1)
        {
            var st = new Static(New(), SkyrimRelease.SkyrimSE)
            {
                EditorID = ed, Model = new Model { File = model },
                ObjectBounds = new ObjectBounds { First = new P3Int16(x0, y0, z0), Second = new P3Int16(x1, y1, z1) },
            };
            mod.Statics.Add(st); return st;
        }
        string Key(string f) => f.StartsWith("Meshes\\", StringComparison.OrdinalIgnoreCase) ? f : "Meshes\\" + f;
        var byModel = new Dictionary<string, FormKey>(StringComparer.OrdinalIgnoreCase);
        int own = 0;   // every custom mesh of ours the layout uses becomes a static of our own (as Build.cs)
        foreach (var p in root.GetProperty("pieces").EnumerateArray())
        {
            var m = p.GetProperty("model").GetString()!;
            if (byModel.ContainsKey(m) || !m.StartsWith(@"Meshes\AdventurersGuild\", StringComparison.OrdinalIgnoreCase)) continue;
            byModel[m] = OwnStatic($"AGHallCKPiece{own++:D2}", m[7..], -2000, -2000, -500, 2000, 2000, 1600).FormKey;
        }
        foreach (var r in mods.SelectMany(m => m.Statics).Cast<ISkyrimMajorRecordGetter>().Concat(mods.SelectMany(m => m.MoveableStatics)).Concat(mods.SelectMany(m => m.Doors)))
            if ((r as IModeledGetter)?.Model?.File.ToString() is { } f) byModel.TryAdd(Key(f), r.FormKey);

        // the cell: the winning vanilla record for the grid square holding the origin, without its contents
        int gx = (int)Math.Floor(o[0] / 4096), gy = (int)Math.Floor(o[1] / 4096);
        var tamKey = new FormKey(ModKey.FromFileName("Skyrim.esm"), 0x00003C);
        IWorldspaceGetter? tam = null; ICellGetter? src = null; IWorldspaceBlockGetter? blk = null; IWorldspaceSubBlockGetter? sub = null;
        foreach (var m in mods)
            foreach (var w in m.Worldspaces.Where(w => w.FormKey == tamKey))
            {
                tam = w;
                foreach (var b in w.SubCells) foreach (var sb in b.Items) foreach (var c in sb.Items)
                    if (c.Grid?.Point.X == gx && c.Grid?.Point.Y == gy) { src = c; blk = b; sub = sb; }
            }
        if (tam is null || src is null) throw new Exception($"no cell {gx},{gy} in Tamriel");
        var ws = tam.DeepCopy(new Worldspace.TranslationMask(true) { SubCells = false, TopCell = false });
        var cell = src.DeepCopy(new Cell.TranslationMask(true) { Temporary = false, Persistent = false, Landscape = false, NavigationMeshes = false });
        ws.SubCells.Add(new WorldspaceBlock
        {
            BlockNumberX = blk!.BlockNumberX, BlockNumberY = blk.BlockNumberY, GroupType = GroupTypeEnum.ExteriorCellBlock,
            Items = { new WorldspaceSubBlock { BlockNumberX = sub!.BlockNumberX, BlockNumberY = sub.BlockNumberY, GroupType = GroupTypeEnum.ExteriorCellSubBlock, Items = { cell } } }
        });
        mod.Worldspaces.Add(ws);

        PlacedObject Ref(FormKey b, string ed, double lx, double ly, double lz, double pyaw, double scale)
        {
            var r = new PlacedObject(New(), SkyrimRelease.SkyrimSE)
            {
                EditorID = ed,
                Placement = new Placement
                {
                    Position = new P3Float((float)(o[0] + lx * ca + ly * sa), (float)(o[1] - lx * sa + ly * ca), (float)(o[2] + lz)),
                    Rotation = new P3Float(0, 0, (float)(((yaw + pyaw) % 360 + 360) % 360 * Math.PI / 180)),
                },
            };
            if (Math.Abs(scale - 1) > 1e-4) r.Scale = (float)scale;
            r.Base.SetTo(b);
            cell.Temporary.Add(r);
            return r;
        }
        var marker = mods.SelectMany(m => m.Statics).Last(s => s.EditorID == "XMarkerHeading");
        Ref(marker.FormKey, "AGHallCKOrigin", 0, 0, 0, 0, 1);
        int i = 0;
        foreach (var p in root.GetProperty("pieces").EnumerateArray())
        {
            if (p.TryGetProperty("only_textures", out _)) continue;
            var model = p.GetProperty("model").GetString()!;
            var pos = p.GetProperty("pos").EnumerateArray().Select(v => v.GetDouble()).ToArray();
            double py = p.TryGetProperty("yaw", out var y) ? y.GetDouble() : 0, sc = p.TryGetProperty("scale", out var s) ? s.GetDouble() : 1;
            if (!byModel.TryGetValue(model, out var b)) throw new Exception("no base record for " + model);
            Ref(b, $"AGHallCK{i++:D2}", pos[0], pos[1], pos[2], py, sc);
        }

        Directory.CreateDirectory(outDir);
        var path = Path.Combine(outDir, "AGHallCK.esp");
        mod.WriteToBinary(path, new BinaryWriteParameters
        {
            MastersListOrdering = new MastersListOrderingByLoadOrder(new[] { "Skyrim.esm", "Update.esm", "Dawnguard.esm", "HearthFires.esm", "Dragonborn.esm" }.Select(x => ModKey.FromFileName(x)).ToList())
        });
        Console.WriteLine($"wrote {path}: cell {gx},{gy} ({src.FormKey}), {i} pieces + origin marker, IDs 0x800-0x{next - 1:X}");
    }
}
