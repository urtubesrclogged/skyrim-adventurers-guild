using Mutagen.Bethesda;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Skyrim;
using Noggog;

// Writes the Guild Hall's plugin: first the records of the hall's first test builds, in their order, so every later record
// keeps its ID (a copy of Hod and Gerdur's house as a test interior, test doors and pieces), the travel quest AGHallTravelQuest
// whose script moves the player through the hall's doors; then the hall itself (Hall2.cs). Nothing of vanilla is overridden.
static partial class Build
{
    // (the hall ships as its own full plugin, "AdventurersGuild - Guild Hall.esp"; until then the
    // light AGHallSpike.esp) the NPC session's records are merged in afterwards (npcs/merge_npcs.sh) in 0x8000-0x99FF (0x9800 on: the promotion trials),
    // which this build never allocates
    public const string PluginName = "AdventurersGuild - Guild Hall.esp";
    static readonly ModKey Own = ModKey.FromFileName(PluginName);
    static uint next = 0x800;
    static FormKey New() { var k = new FormKey(Own, next++); if (next >= 0x8000) throw new Exception("IDs reached 0x8000: the NPCs' reserved block"); return k; }

    public static void Run(List<ISkyrimModDisposableGetter> mods, string outDir, string? layoutPath = null)
    {
        var mod = new SkyrimMod(Own, SkyrimRelease.SkyrimSE);
        var sk = ModKey.FromFileName("Skyrim.esm");
        FormKey V(uint id) => new FormKey(sk, id);
        var srcCellKey = V(0x0133C7);               // RiverwoodGerdursHouse
        var copies = mods.SelectMany(m => m.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(sb => sb.Cells)).Where(c => c.FormKey == srcCellKey).ToList();
        var src = copies.Last();
        var doorBase = mods.SelectMany(m => m.Doors).Last(d => d.EditorID == "FarmhouseLDoor01");
        var shell = mods.SelectMany(m => m.Statics).Last(s => s.EditorID == "Farmhouse04");
        var marker = mods.SelectMany(m => m.Statics).Last(s => s.EditorID == "XMarkerHeading");

        var questKey = New(); var extDoorKey = New(); var intDoorKey = New(); var cellKey = New(); var inMarkerKey = New();

        ScriptEntry DoorScript(bool inside) => new ScriptEntry
        {
            Name = "AGHallDoor",
            Properties = {
                new ScriptObjectProperty { Name = "Travel", Object = questKey.ToLink<ISkyrimMajorRecordGetter>(), Flags = ScriptProperty.Flag.Edited },
                new ScriptBoolProperty { Name = "Inside", Data = inside, Flags = ScriptProperty.Flag.Edited } }
        };
        Mutagen.Bethesda.Skyrim.Activator Door(FormKey k, string ed, string name, bool inside) => new Mutagen.Bethesda.Skyrim.Activator(k, SkyrimRelease.SkyrimSE)
        {
            EditorID = ed, Name = name,
            ObjectBounds = doorBase.ObjectBounds.DeepCopy(),
            Model = doorBase.Model?.DeepCopy(),
            VirtualMachineAdapter = new VirtualMachineAdapter { Scripts = { DoorScript(inside) } },
        };
        mod.Activators.Add(Door(extDoorKey, "AGHallTestExteriorDoor", "Adventurers Guild Hall", false));
        mod.Activators.Add(Door(intDoorKey, "AGHallTestInteriorDoor", "Riverwood", true));

        // the interior: every ref of every copy of the cell (HearthFires adds some), people and the load door left out
        var cell = new Cell(cellKey, SkyrimRelease.SkyrimSE)
        {
            EditorID = "AGHallTestInterior", Name = "Adventurers Guild Hall (test)",
            Flags = Cell.Flag.IsInteriorCell,
            Lighting = src.Lighting?.DeepCopy(),
        };
        cell.LightingTemplate.SetTo(src.LightingTemplate.FormKey);
        cell.Music.SetTo(src.Music.FormKeyNullable);
        cell.AcousticSpace.SetTo(src.AcousticSpace.FormKeyNullable);
        cell.ImageSpace.SetTo(src.ImageSpace.FormKeyNullable);

        var map = new Dictionary<FormKey, FormKey>();
        var refs = copies.SelectMany(c => c.Persistent.Concat(c.Temporary)).GroupBy(r => r.FormKey).Select(g => g.Last()).ToList();
        IPlacedObjectGetter? loadDoor = null;
        var keep = new List<IPlacedObjectGetter>();
        foreach (var r in refs)
        {
            if (r is not IPlacedObjectGetter po) continue;             // Hod, Gerdur and Frodnar stay home
            if (po.TeleportDestination is not null) { loadDoor = po; continue; }
            map[r.FormKey] = New(); keep.Add(po);
        }
        foreach (var r in keep)
        {
            var n = (PlacedObject)r.Duplicate(map[r.FormKey]);
            n.RemapLinks(map);
            // anything still pointing at a vanilla ref outside the copy (enable parents, linked refs, owners) is dropped
            if (n.EnableParent is { } ep && ep.Reference.FormKey.ModKey != Own) n.EnableParent = null;
            n.LinkedReferences.RemoveWhere(l => l.Reference.FormKey.ModKey != Own);
            n.LocationReference.Clear();
            n.LocationRefTypes = null;
            n.Owner.Clear(); n.FactionRank = null; n.PersistentLocation.Clear();
            n.MajorRecordFlagsRaw &= ~0x400;   // temporary, like the rest of a house's clutter
            cell.Temporary.Add(n);
        }
        // the way out: the interior door, now an activator; and where the player lands coming in
        if (loadDoor is null) throw new Exception("no load door in the source cell");
        var outDoor = new PlacedObject(New(), SkyrimRelease.SkyrimSE) { Placement = loadDoor.Placement!.DeepCopy() };
        outDoor.Base.SetTo(intDoorKey);
        cell.Temporary.Add(outDoor);
        var ext = mods[0].Worldspaces.SelectMany(w => w.EnumerateMajorRecords<IPlacedObjectGetter>()).First(d => d.TeleportDestination?.Door.FormKey == loadDoor.FormKey);
        var land = ext.TeleportDestination!;   // the outside door's destination = where vanilla puts you inside
        var inMarker = new PlacedObject(inMarkerKey, SkyrimRelease.SkyrimSE)
        {
            EditorID = "AGHallTestInMarker",
            Placement = new Placement { Position = land.Position, Rotation = land.Rotation },
        };
        inMarker.Base.SetTo(marker.FormKey);
        inMarker.MajorRecordFlagsRaw |= 0x400;   // persistent: the quest script holds it
        cell.Persistent.Add(inMarker);
        // navmesh: copied as new records into the new cell; door triangles (they named the vanilla load door) removed
        int navs = 0;
        foreach (var nv in copies.SelectMany(c => c.NavigationMeshes).GroupBy(n => n.FormKey).Select(g => g.Last()))
        {
            var k = New(); map[nv.FormKey] = k;
            var n = (NavigationMesh)nv.Duplicate(k);
            n.RemapLinks(map);
            if (n.Data is { } d)
            {
                d.Parent = new CellNavmeshParent { Parent = cellKey.ToLink<ICellGetter>() };
                d.DoorTriangles.Clear();
            }
            cell.NavigationMeshes.Add(n); navs++;
        }
        uint id = cellKey.ID;
        mod.Cells.Records.Add(new CellBlock
        {
            BlockNumber = (int)(id % 10), GroupType = GroupTypeEnum.InteriorCellBlock,
            SubBlocks = { new CellSubBlock { BlockNumber = (int)(id / 10 % 10), GroupType = GroupTypeEnum.InteriorCellSubBlock, Cells = { cell } } }
        });

        // test 2: more shells, each with its own door model. New records go AFTER every existing ID: a save made with the
        // first build holds refs to 0x800-0x8DC.
        Mutagen.Bethesda.Skyrim.Activator DoorOf(string doorEd, string ed)
        {
            var db = mods.SelectMany(m => m.Doors).Last(d => d.EditorID == doorEd);
            return new Mutagen.Bethesda.Skyrim.Activator(New(), SkyrimRelease.SkyrimSE)
            {
                EditorID = ed, Name = "Adventurers Guild Hall",
                ObjectBounds = db.ObjectBounds.DeepCopy(), Model = db.Model?.DeepCopy(),
                VirtualMachineAdapter = new VirtualMachineAdapter { Scripts = { DoorScript(false) } },
            };
        }
        var dragonDoor = DoorOf("WRDragonDoor01", "AGHallDoorWhiterun");
        var templeDoor = DoorOf("NorLargeDoor", "AGHallDoorTemple");
        var havenDoor = DoorOf("SkyHavenDoor01", "AGHallDoorSkyHaven");
        mod.Activators.Add(dragonDoor); mod.Activators.Add(templeDoor); mod.Activators.Add(havenDoor);
        FormKey St(string ed) => mods.SelectMany(m => m.Statics).Last(s => s.EditorID == ed).FormKey;
        // shell, door, door offset (x, y, z) and turn in the shell's frame - measured from vanilla's own use (Shells.cs)
        var presets = new (FormKey shell, FormKey door, float lx, float ly, float lz, float rot)[]
        {
            (St("Farmhouse04"), extDoorKey, -256, -250, 0, 0),                    // 0 Hod and Gerdur's, Rorik's Manor
            (St("FarmLonghouse01"), extDoorKey, 0, -896, 224, 0),                // 1 Highmoon Hall, Falkreath's longhouse
            (St("FarmInn01"), extDoorKey, 384, -385, 224, 0),                    // 2 Sleeping Giant and six more inns
            (St("WRJorvaskr01"), dragonDoor.FormKey, 291, -97, -322, 180),       // 3 Jorrvaskr
            (St("NorTempleExterior01"), templeDoor.FormKey, 0, 743, 0, 180),     // 4 Bleak Falls / Ragnvald temple front
            (St("SkyHavenExteriorFacade01"), havenDoor.FormKey, 656, 113, 216, 181), // 5 Sky Haven, carved into the mountain
        };

        // test 3: the composed hall (a Blender layout: vanilla pieces in the building's frame) placed piece by piece at
        // run time, its Dragonsreach door an activator; the custom meshes (blender/*.py) are statics of our own
        var hallDoor = DoorOf("WRCastleDoor01", "AGHallDoorHall");
        mod.Activators.Add(hallDoor);
        Static OwnStatic(string ed, string model, short x0, short y0, short z0, short x1, short y1, short z1)
        {
            var st = new Static(New(), SkyrimRelease.SkyrimSE)
            {
                EditorID = ed, Model = new Model { File = model },
                ObjectBounds = new ObjectBounds { First = new P3Int16(x0, y0, z0), Second = new P3Int16(x1, y1, z1) },
            };
            mod.Statics.Add(st); return st;
        }
        var skirt = OwnStatic("AGHallSkirt", @"AdventurersGuild\Hall\AGHallSkirt.nif", -421, -1195, -265, 760, 1195, 700);  // 0x8E1
        var crest = OwnStatic("AGHallCrest", @"AdventurersGuild\Hall\AGHallCrest.nif", 0, -91, -110, 1, 91, 110);           // 0x8E2
        var hall = new List<(FormKey b, float x, float y, float z, float yaw, float scale)>();
        var clear = new List<double[]>();   // where trees are hidden: boxes in the building's frame (x0, x1, y0, y1)
        double size = 1;                    // the whole hall's scale (layout "scale")
        var oldBases = new HashSet<FormKey>();
        if (layoutPath is not null)
        {
            var byModel = new Dictionary<string, FormKey>(StringComparer.OrdinalIgnoreCase);
            foreach (var st in new[] { skirt, crest })
                byModel[st.Model!.File.ToString() is var f0 && f0.StartsWith("Meshes\\", StringComparison.OrdinalIgnoreCase) ? f0 : "Meshes\\" + f0] = st.FormKey;
            foreach (var r in mods.SelectMany(m => m.Statics).Cast<ISkyrimMajorRecordGetter>().Concat(mods.SelectMany(m => m.MoveableStatics)))
                if ((r as IModeledGetter)?.Model?.File.ToString() is { } f) byModel.TryAdd(f.StartsWith("Meshes\\", StringComparison.OrdinalIgnoreCase) ? f : "Meshes\\" + f, r.FormKey);
            // every base any earlier layout placed: CleanupStray deletes leftovers of those (created refs only)
            // (2026-11-04: both are required: skipped when missing, they shortened the list by 7 bases with nothing said, found only by
            // comparing a build against the deployed one)
            foreach (var old in new[] { "B4_flush.json", "B5_dressed.json" }.Select(f => Path.Combine(Path.GetDirectoryName(layoutPath)!, "..", f))
                         .Select(f => File.Exists(f) ? f : throw new FileNotFoundException("an earlier layout CleanupStray needs is missing", f)))
            {
                using var od = System.Text.Json.JsonDocument.Parse(File.ReadAllText(old));
                foreach (var p in od.RootElement.GetProperty("pieces").EnumerateArray())
                    if (byModel.TryGetValue(p.GetProperty("model").GetString()!, out var k)) oldBases.Add(k);
            }
            oldBases.Add(skirt.FormKey); oldBases.Add(crest.FormKey); oldBases.Add(hallDoor.FormKey);
            using var doc = System.Text.Json.JsonDocument.Parse(File.ReadAllText(layoutPath));
            if (doc.RootElement.TryGetProperty("scale", out var sz)) size = sz.GetDouble();
            if (doc.RootElement.TryGetProperty("clear_boxes", out var cb))
                foreach (var bx in cb.EnumerateArray()) clear.Add(bx.EnumerateArray().Select(v => v.GetDouble()).ToArray());
            int own = 0;
            foreach (var p in doc.RootElement.GetProperty("pieces").EnumerateArray())
            {
                if (p.TryGetProperty("only_textures", out _)) continue;   // a part of a mesh: custom piece later
                var model = p.GetProperty("model").GetString()!;
                var pos = p.GetProperty("pos").EnumerateArray().Select(v => (float)v.GetDouble()).ToArray();
                float yaw = p.TryGetProperty("yaw", out var y) ? (float)y.GetDouble() : 0, sc = p.TryGetProperty("scale", out var s) ? (float)s.GetDouble() : 1;
                // any other custom mesh of ours becomes a static of its own, after every existing ID
                if (!byModel.ContainsKey(model) && model.StartsWith(@"Meshes\AdventurersGuild\", StringComparison.OrdinalIgnoreCase))
                    byModel[model] = OwnStatic($"AGHallPiece{own++:D2}", model[7..], -2000, -2000, -500, 2000, 2000, 1600).FormKey;
                FormKey b = model.Contains("WRCastleDoor01", StringComparison.OrdinalIgnoreCase) ? hallDoor.FormKey
                    : byModel.TryGetValue(model, out var k) ? k : throw new Exception("no base record for " + model);
                hall.Add((b, (float)(pos[0] * size), (float)(pos[1] * size), (float)(pos[2] * size), yaw, (float)(sc * size)));
            }
        }

        ScriptObjectProperty Obj(string name, FormKey k) => new ScriptObjectProperty { Name = name, Object = k.ToLink<ISkyrimMajorRecordGetter>(), Flags = ScriptProperty.Flag.Edited };
        // (the first test build's records go, with the test functions that used them) the travel quest keeps what
        // the doors need; the test records below were made only so every later record keeps its ID, and are taken out again
        var testRecords = new HashSet<FormKey>(mod.EnumerateMajorRecords().Select(r => r.FormKey));
        var q = new Quest(questKey, SkyrimRelease.SkyrimSE)
        {
            EditorID = "AGHallTravelQuest", Name = "Guild Hall travel",
            Flags = Quest.Flag.StartGameEnabled, Priority = 0,
            VirtualMachineAdapter = new QuestAdapter { Scripts = { new ScriptEntry { Name = "AGHallTravel", Properties = {
                Obj("MarkerBase", marker.FormKey), Obj("PlayerRef", V(0x14)) } } } },
        };
        mod.Quests.Add(q);
        int dropped = 0;
        foreach (var k in testRecords)
        {
            if (mod.Activators.ContainsKey(k)) { mod.Activators.Remove(k); dropped++; }
            if (mod.Statics.ContainsKey(k)) { mod.Statics.Remove(k); dropped++; }
        }
        mod.Cells.Records.Clear();   // the test interior's block: its cell, refs and navmesh (the hall's own cells come after, in Hall2.cs)
        Console.WriteLine($"the first test build's records: {dropped} top-level records and the test interior left out, their IDs kept unused");

        // test 10: the modelled Solitude-style hall at its candidate sites (Hall2.cs), after every earlier record
        if (Environment.GetEnvironmentVariable("HALL2_DIR") is { Length: > 0 } h2) AddHall2(mod, mods, h2, New, V(0x14), outDir, questKey, cell, inMarker);

        Directory.CreateDirectory(outDir);
        var path = Path.Combine(outDir, PluginName);
        mod.WriteToBinary(path, new BinaryWriteParameters
        {
            MastersListOrdering = new MastersListOrderingByLoadOrder(new[] { "Skyrim.esm", "Update.esm", "Dawnguard.esm", "HearthFires.esm", "Dragonborn.esm" }.Select(x => ModKey.FromFileName(x)).ToList())
        });
        Console.WriteLine($"wrote {path}: {keep.Count} copied refs, {navs} navmesh, {hall.Count} hall pieces, IDs 0x800-0x{next - 1:X}, landing at {land.Position} rot {land.Rotation}");
    }
}
