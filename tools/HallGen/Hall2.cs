using Mutagen.Bethesda;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Skyrim;
using Noggog;
using System.Text.Json;

// The modelled hall (blender/guildhall_gen.py -> hall_nif.py) at its site: statics of our own for the body, both roofs, the
// site's terrace and the door, placed by AG's DLL from hall2.json (WriteLayout below), and the hall's interior (AddInterior).
static partial class Build
{
    static void AddHall2(SkyrimMod mod, List<ISkyrimModDisposableGetter> mods, string dir, Func<FormKey> newKey, FormKey player, string outDir,
        FormKey travelQuest, Cell firstCell, PlacedObject inMarker)
    {
        static (short[] lo, short[] hi) BoundsOf(params string[] jsons)
        {
            var lo = new double[] { 1e9, 1e9, 1e9 }; var hi = new double[] { -1e9, -1e9, -1e9 };
            foreach (var j in jsons)
            {
                using var d = JsonDocument.Parse(File.ReadAllText(j));
                foreach (var sh in d.RootElement.GetProperty("shapes").EnumerateObject())
                    foreach (var v in sh.Value.GetProperty("v").EnumerateArray())
                        for (int k = 0; k < 3; k++) { var c = v[k].GetDouble(); lo[k] = Math.Min(lo[k], c); hi[k] = Math.Max(hi[k], c); }
            }
            return (lo.Select(x => (short)Math.Floor(x)).ToArray(), hi.Select(x => (short)Math.Ceiling(x)).ToArray());
        }
        Static Own(string ed, string model, (short[] lo, short[] hi) b)
        {
            var st = new Static(newKey(), SkyrimRelease.SkyrimSE)
            {
                EditorID = ed, Model = new Model { File = model },
                ObjectBounds = new ObjectBounds { First = new P3Int16(b.lo[0], b.lo[1], b.lo[2]), Second = new P3Int16(b.hi[0], b.hi[1], b.hi[2]) },
            };
            mod.Statics.Add(st); return st;
        }
        string J(string name) => Path.Combine(dir, name);
        var body = Own("AGHall2Body", @"AdventurersGuild\Hall2\AGHall2Body.nif", BoundsOf(J("hall2_body.json")));
        var roofB = BoundsOf(J("hall2_roof.json"));
        var slate = Own("AGHall2RoofSlate", @"AdventurersGuild\Hall2\AGHall2RoofSlate.nif", roofB);
        var tile = Own("AGHall2RoofTile", @"AdventurersGuild\Hall2\AGHall2RoofTile.nif", roofB);
        var door = Own("AGHall2Door", @"AdventurersGuild\Hall2\AGH2Csdoubledoorint01.nif", (new short[] { -91, -8, 0 }, new short[] { 91, 0, 175 }));

        var byModel = new Dictionary<string, FormKey>(StringComparer.OrdinalIgnoreCase);
        // statics first; then vanilla trees, for the beds' plants (lavender, mountain flowers, snowberry, ferns are TREE records)
        foreach (var r in mods.SelectMany(m => m.Statics).Cast<ISkyrimMajorRecordGetter>().Concat(mods.SelectMany(m => m.MoveableStatics)).Concat(mods.SelectMany(m => m.Trees)))
            if ((r as IModeledGetter)?.Model?.File.ToString() is { } f) byModel.TryAdd(Norm(f), r.FormKey);
        static string Norm(string m) { m = m.Replace('/', '\\'); return m.StartsWith(@"meshes\", StringComparison.OrdinalIgnoreCase) ? m[7..] : m; }
        byModel[Norm("meshes/architecture/solitude/doors/sdoubledoorint01.nif")] = door.FormKey;
        // the benches are the vanilla furniture, not its static copy (CommonBench01STATIC shares the mesh and came first): sittable
        var bench = new FormKey(ModKey.FromFileName("Skyrim.esm"), 0x02E6CF);
        if (mods.SelectMany(m => m.Furniture).FirstOrDefault(f => f.FormKey == bench)?.Model?.File.ToString() is { } bf) byModel[Norm(bf)] = bench;
        else throw new Exception("CommonBench01 (Skyrim.esm 02E6CF) not found");
        foreach (var st in mod.Statics)                       // the first builds' own pieces (the crest on the signpost)
            if (st.Model?.File.ToString() is { } f2) byModel.TryAdd(Norm(f2), st.FormKey);
        // a piece may name its record: one mesh is often shared by a plain record and its snow, ice or light-snow copies
        // (CommonTableSquare01 has four), or by furniture and its static (CommonChair01): the name settles it
        var byEd = new Dictionary<string, FormKey>(StringComparer.OrdinalIgnoreCase);
        foreach (var r in mods.SelectMany(m => m.Statics).Cast<ISkyrimMajorRecordGetter>().Concat(mods.SelectMany(m => m.Furniture))
                     .Concat(mods.SelectMany(m => m.Lights)).Concat(mods.SelectMany(m => m.MoveableStatics)).Concat(mods.SelectMany(m => m.Trees))
                     .Concat(mods.SelectMany(m => m.Containers)).Concat(mods.SelectMany(m => m.Doors))   // (2026-10-26: the interior's chests and doors;
                     .Concat(mods.SelectMany(m => m.Activators)).Concat(mods.SelectMany(m => m.MiscItems)).Concat(mods.SelectMany(m => m.Florae)).Concat(mods.SelectMany(m => m.Books)).Concat(mods.SelectMany(m => m.Ingestibles)).Concat(mods.SelectMany(m => m.Ingredients))   // the fit-out: the rack, baskets; a purse; books
                     .Concat(mods.SelectMany(m => m.Weapons)).Concat(mods.SelectMany(m => m.Armors))   // (2026-10-29: the basement's racks' weapons)
                     .Concat(mods.SelectMany(m => m.Ammunitions))   // (2026-10-29: the archery range's arrows and its prop quiver, DummyArrow)
                     .Concat(mods.SelectMany(m => m.IdleMarkers)))   // (2026-11-04: the readers' and Merila's markers at the boards)
            if (r.EditorID is { } e) byEd.TryAdd(e, r.FormKey);
        // (2026-10-29) the hall's own meshes that the outside's pieces place (the guild's banner): fixed IDs in a block of their
        // own, OwnFixed, so neither the records made in order above (whose IDs saves hold) nor the ledger's shift; created here,
        // before the sites' pieces look their records up by name
        foreach (var (ed_, id_, nif_, lo_, hi_) in OwnFixed)
        {
            var st_ = new Static(new FormKey(mod.ModKey, id_), SkyrimRelease.SkyrimSE)
            {
                EditorID = ed_, Model = new Model { File = @"AdventurersGuild\Hall2\" + nif_ },
                ObjectBounds = new ObjectBounds { First = new P3Int16(lo_[0], lo_[1], lo_[2]), Second = new P3Int16(hi_[0], hi_[1], hi_[2]) },
            };
            mod.Statics.Add(st_); byEd[ed_] = st_.FormKey;
        }
        // (the overmantel display: fixed, dragonbone) plaques, shield and swords as statics on vanilla's meshes, the
        // sword on our copy with its scabbard hidden (blender/own_copies.py, hide_shapes.py): a static draws what a weapon's world reference hides
        foreach (var (ed_, id_, nif_, lo_, hi_) in OwnDisplay)
        {
            var st_ = new Static(new FormKey(mod.ModKey, id_), SkyrimRelease.SkyrimSE)
            {
                EditorID = ed_, Model = new Model { File = nif_ },
                ObjectBounds = new ObjectBounds { First = new P3Int16(lo_[0], lo_[1], lo_[2]), Second = new P3Int16(hi_[0], hi_[1], hi_[2]) },
            };
            mod.Statics.Add(st_); byEd[ed_] = st_.FormKey;
        }
        // (the grand stair had no small details to break it up: one satchel, openable, with a little
        // loot) a satchel left on the stair's wall at its landing: vanilla's, its contents fixed and never respawning (TreasSatchel respawns its list)
        {
            var sa_ = mods.SelectMany(m => m.Containers).Last(c => c.EditorID == "TreasSatchel").Duplicate(new FormKey(mod.ModKey, 0x7F20));
            sa_.EditorID = "AGHall2StairSatchel"; sa_.Flags &= ~Container.Flag.Respawns;
            IItemGetter It(IEnumerable<IItemGetter> rs, string ed) => rs.Last(r => r.EditorID == ed);
            sa_.Items = new()
            {
                new ContainerEntry { Item = new ContainerItem { Item = It(mods.SelectMany(m => m.MiscItems), "Gold001").ToLink<IItemGetter>(), Count = 23 } },
                new ContainerEntry { Item = new ContainerItem { Item = It(mods.SelectMany(m => m.MiscItems), "Lockpick").ToLink<IItemGetter>(), Count = 2 } },
                new ContainerEntry { Item = new ContainerItem { Item = It(mods.SelectMany(m => m.Ingestibles), "RestoreHealth01").ToLink<IItemGetter>(), Count = 1 } },
            };
            mod.Containers.Add(sa_); byEd["AGHall2StairSatchel"] = sa_.FormKey;
        }
        // (2026-11-02) the same for what moves: vanilla's moving banner's record, on our rigged mesh
        foreach (var (ed_, id_, nif_, lo_, hi_) in OwnMoving)
        {
            var mv_ = mods.SelectMany(m => m.MoveableStatics).Last(m => m.EditorID == "CityBannerRiften01").Duplicate(new FormKey(mod.ModKey, id_));
            mv_.EditorID = ed_; mv_.Model = new Model { File = @"AdventurersGuild\Hall2\" + nif_ };
            mv_.ObjectBounds = new ObjectBounds { First = new P3Int16(lo_[0], lo_[1], lo_[2]), Second = new P3Int16(hi_[0], hi_[1], hi_[2]) };
            mod.MoveableStatics.Add(mv_); byEd[ed_] = mv_.FormKey;
        }
        foreach (var (ed_, id_, nif_, lo_, hi_) in OwnHinged)
        {
            var mv_ = mods.SelectMany(m => m.MoveableStatics).Last(m => m.EditorID == "SignGeneralGoods01").Duplicate(new FormKey(mod.ModKey, id_));
            mv_.EditorID = ed_; mv_.Model = new Model { File = @"AdventurersGuild\Hall2\" + nif_ };
            mv_.ObjectBounds = new ObjectBounds { First = new P3Int16(lo_[0], lo_[1], lo_[2]), Second = new P3Int16(hi_[0], hi_[1], hi_[2]) };
            mod.MoveableStatics.Add(mv_); byEd[ed_] = mv_.FormKey;
        }
        // (the built-in pieces stop changing per install: blender/own_copies.py) each a copy of vanilla's record, its behaviour its own, on our copy of its mesh; the
        // placed references keep their IDs: the ledger reads a copy as the piece it was (OwnCopyOf)
        foreach (var (ed_, id_) in OwnCopies)
        {
            var k_ = new FormKey(mod.ModKey, id_); var nif_ = @"AdventurersGuild\Hall2\AGH2C" + ed_.ToLowerInvariant() + ".nif";
            if (ed_.StartsWith("Imp") && mods.SelectMany(m => m.MoveableStatics).LastOrDefault(r => r.EditorID == ed_) is { } ms0_)
            {
                var c_ = ms0_.Duplicate(k_); c_.EditorID = "AGHall2C" + ed_; c_.Model!.File = nif_; c_.Model.Data = null; mod.MoveableStatics.Add(c_); OwnCopyOf[ms0_.FormKey] = k_;
            }
            else if (mods.SelectMany(m => m.Statics).LastOrDefault(r => r.EditorID == ed_) is { } st0_)
            {
                var c_ = st0_.Duplicate(k_); c_.EditorID = "AGHall2C" + ed_; c_.Model!.File = nif_; c_.Model.Data = null; mod.Statics.Add(c_); OwnCopyOf[st0_.FormKey] = k_;
            }
            else
            {
                var d0_ = mods.SelectMany(m => m.Doors).Last(r => r.EditorID == ed_);
                var c_ = d0_.Duplicate(k_); c_.EditorID = "AGHall2C" + ed_; c_.Model!.File = nif_; c_.Model.Data = null; mod.Doors.Add(c_); OwnCopyOf[d0_.FormKey] = k_;
            }
            byEd[ed_] = k_;
        }
        // (lit iron torches at the front door, the higher-resolution ones) vanilla's lit torch, its flame in the mesh, on our copy: blender/own_copies.py
        { var t_ = mods.SelectMany(m => m.MoveableStatics).Last(r => r.EditorID == "TorchPermanantOn").Duplicate(new FormKey(mod.ModKey, 0x7F19)); t_.EditorID = "AGHall2CTorchPermanantOn";
          t_.Model!.File = @"AdventurersGuild\Hall2\AGH2Ctorchpermanent01.nif"; t_.Model.Data = null; mod.MoveableStatics.Add(t_); byEd["TorchPermanantOn"] = t_.FormKey; }

        var P = new List<(FormKey b, float x, float y, float z, float a, float s, int site)>();
        var sx = new List<float>(); var sy = new List<float>(); var syaw = new List<float>();
        var vx = new List<float>(); var vy = new List<float>(); var vz = new List<float>(); var va = new List<float>();
        var clear = new List<(float x0, float x1, float y0, float y1, int site, int kind)>();
        // five site slots, always: the quest keeps its ID (0x901) however many sites a build has, so a save carries it
        for (int k = 1; k <= 5; k++)
        {
            var sj = J($"hall2_site_{k}.json");
            if (!File.Exists(sj)) { newKey(); continue; }
            var site = Own($"AGHall2Site{k}", $@"AdventurersGuild\Hall2\AGHall2Site{k}.nif", BoundsOf(sj));
            using var d = JsonDocument.Parse(File.ReadAllText(sj));
            var o = d.RootElement.GetProperty("site").EnumerateArray().Select(v => v.GetDouble()).ToArray();   // x, y, floor, yaw
            double a = o[3] * Math.PI / 180, c = Math.Cos(a), s = Math.Sin(a);
            (double wx, double wy) W(double lx, double ly) => (o[0] + lx * c + ly * s, o[1] - lx * s + ly * c);
            void Add(FormKey b, double lx, double ly, double lz, double yaw, double sc)
            {
                var (wx, wy) = W(lx, ly);
                P.Add((b, (float)wx, (float)wy, (float)(o[2] + lz), (float)(((o[3] + yaw) % 360 + 360) % 360), (float)sc, k));
            }
            Add(body.FormKey, 0, 0, 0, 0, 1); Add(slate.FormKey, 0, 0, 0, 0, 1); Add(site.FormKey, 0, 0, 0, 0, 1);
            foreach (var p in d.RootElement.GetProperty("pieces").EnumerateArray())
            {
                var model = Norm(p.GetProperty("model").GetString()!);
                FormKey b;
                if (p.TryGetProperty("ed", out var edp)) { if (!byEd.TryGetValue(edp.GetString()!, out b)) throw new Exception("no record named " + edp.GetString()); }
                else if (!byModel.TryGetValue(model, out b)) throw new Exception("no base record for " + model);
                var pos = p.GetProperty("pos").EnumerateArray().Select(v => v.GetDouble()).ToArray();
                Add(b, pos[0], pos[1], pos[2], p.GetProperty("yaw").GetDouble(), p.GetProperty("scale").GetDouble());
            }
            sx.Add((float)o[0]); sy.Add((float)o[1]); syaw.Add((float)o[3]);
            var foot = d.RootElement.GetProperty("stair_foot").EnumerateArray().Select(v => v.GetDouble()).ToArray();
            var (fx, fy) = W(foot[0], foot[1]);
            vx.Add((float)fx); vy.Add((float)fy); vz.Add((float)(o[2] + foot[2] + 60));
            va.Add((float)((Math.Atan2(o[0] - fx, o[1] - fy) * 180 / Math.PI + 360) % 360));   // facing the hall
            foreach (var b in d.RootElement.GetProperty("clear").EnumerateArray())
            {
                var q = b.EnumerateArray().Select(v => (float)v.GetDouble()).ToArray();
                clear.Add((q[0], q[1], q[2], q[3], k, q.Length > 4 ? (int)q[4] : 0));
            }
            Console.WriteLine($"hall2 site {k}: origin {o[0]:F0},{o[1]:F0} floor {o[2]:F0} yaw {o[3]}; view {fx:F0},{fy:F0},{o[2] + foot[2] + 60:F0}");
        }

        ScriptObjectProperty Obj(string name, FormKey k) => new() { Name = name, Object = k.ToLink<ISkyrimMajorRecordGetter>(), Flags = ScriptProperty.Flag.Edited };
        ScriptObjectListProperty Objs(string name, IEnumerable<FormKey> ks)
        {
            var p = new ScriptObjectListProperty { Name = name, Flags = ScriptProperty.Flag.Edited };
            foreach (var k in ks) p.Objects.Add(new ScriptObjectProperty { Object = k.ToLink<ISkyrimMajorRecordGetter>() });
            return p;
        }
        ScriptFloatListProperty Floats(string name, IEnumerable<float> vs) { var p = new ScriptFloatListProperty { Name = name, Flags = ScriptProperty.Flag.Edited }; p.Data.AddRange(vs); return p; }
        ScriptIntListProperty Ints(string name, IEnumerable<int> vs) { var p = new ScriptIntListProperty { Name = name, Flags = ScriptProperty.Flag.Edited }; p.Data.AddRange(vs); return p; }
        if (P.Count > 256) throw new Exception($"{P.Count} pieces: AGHall2 holds 256 (two arrays of 128)");
        var P1 = P.Take(128).ToList(); var P2 = P.Skip(128).ToList();
        if (clear.Count > 128) throw new Exception($"{clear.Count} hide boxes: a Papyrus array holds 128");
        var q2 = new Quest(newKey(), SkyrimRelease.SkyrimSE)
        {
            EditorID = "AGHall2Quest", Name = "Guild Hall study",
            Flags = Quest.Flag.StartGameEnabled, Priority = 0,
            VirtualMachineAdapter = new QuestAdapter { Scripts = { new ScriptEntry { Name = "AGHall2", Properties = {
                Obj("PlayerRef", player),
                // a Papyrus array holds 128 values: the pieces go in two halves (AGHall2 reads them as one list of up to 256)
                Objs("Bases", P1.Select(p => p.b)), Floats("PX", P1.Select(p => p.x)), Floats("PY", P1.Select(p => p.y)), Floats("PZ", P1.Select(p => p.z)),
                Floats("PA", P1.Select(p => p.a)), Floats("PS", P1.Select(p => p.s)), Ints("PSite", P1.Select(p => p.site)),
                Objs("Bases2", P2.Select(p => p.b)), Floats("PX2", P2.Select(p => p.x)), Floats("PY2", P2.Select(p => p.y)), Floats("PZ2", P2.Select(p => p.z)),
                Floats("PA2", P2.Select(p => p.a)), Floats("PS2", P2.Select(p => p.s)), Ints("PSite2", P2.Select(p => p.site)),
                Objs("RoofBases", new[] { slate.FormKey, tile.FormKey }),
                Floats("SiteX", sx), Floats("SiteY", sy), Floats("SiteYaw", syaw),
                Floats("ViewX", vx), Floats("ViewY", vy), Floats("ViewZ", vz), Floats("ViewA", va),
                Floats("CX0", clear.Select(c => c.x0)), Floats("CX1", clear.Select(c => c.x1)), Floats("CY0", clear.Select(c => c.y0)), Floats("CY1", clear.Select(c => c.y1)),
                Ints("CSite", clear.Select(c => c.site)), Ints("CKind", clear.Select(c => c.kind)) } } } },
        };
        // the study quest AGHall2Quest is no longer written: the DLL places the hall from hall2.json. Its
        // record is still made, unused, so its ID (0x901) and every one after it stay as they were
        Console.WriteLine($"hall2: {P.Count} pieces over {sx.Count} sites, quest {q2.FormKey}");
        var doorsOrNull = AddInterior(mod, mods, dir, newKey, travelQuest, firstCell, inMarker, byEd);
        // (2026-10-27) the owner groups the NPC session's merge step gives to people (npcs/merge_npcs.sh reads it beside the
        // plugin): each group's references, local IDs, all in the hall's cell
        if (OwnerGroups.Count > 0)
        {
            File.WriteAllText(Path.Combine(outDir, "hall-owners.json"), JsonSerializer.Serialize(new { groups = OwnerGroups.ToDictionary(kv => kv.Key, kv => kv.Value.OrderBy(x => x).Select(x => $"0x{x:X6}").ToList()) },
                new JsonSerializerOptions { WriteIndented = true }));
            Console.WriteLine("hall2: owner groups " + string.Join(", ", OwnerGroups.OrderBy(kv => kv.Key).Select(kv => $"{kv.Key} {kv.Value.Count}")) + " -> hall-owners.json");
        }
        if (doorsOrNull is { } doors)   // the front door now opens: the
            for (int i = 0; i < P.Count; i++)                                    // layout places the activator there; the back
            {                                                                    // door too, since hall2t
                var o_ = P.First(q => q.b == body.FormKey && q.site == P[i].site);   // the site's origin: its body piece
                if (P[i].b != door.FormKey) continue;
                bool front = Math.Abs(P[i].x - o_.x) < 50 && Math.Abs(P[i].y - o_.y) < 50;
                if (front) P[i] = (doors.front, P[i].x, P[i].y, P[i].z, P[i].a, P[i].s, P[i].site);
                else if (doors.patio is { } pk) P[i] = (pk, P[i].x, P[i].y, P[i].z, P[i].a, P[i].s, P[i].site);
            }
        WriteLayout(outDir, P, sx, sy, syaw, clear, slate.FormKey);
    }

    // The walkable interior: the front door opens - an activator running
    // AGHallDoor instead of the static - into a cell of its own: the whole shell in one static (blender/interior_gen.py
    // exported with AG_INTERIOR as hall2_interior.json -> AGHall2Interior.nif), its lamps, a landing point of its own and a
    // door back out. Its ambient light is bright and even: one mesh takes only a few point lights. Records after every
    // existing ID; the door in, or null without an exported interior.
    // The first build (hall2p) landed the player on AGHallTravel's InMarker, moved into this cell; the SE test install's save kept that
    // marker where an earlier build had it (the copied farmhouse), and a save's change wins over the plugin. So the front
    // door names its own landing point (AGHall2InMarker, new) and is a new record: a new layout, so the DLL re-places it.
    // W (after the first in-game test): the records that build had keep their IDs (0x902-0x918: a save may hold the
    // landing point 0x917 moved), with twelve lamp slots as before; all that is new comes after. New: the hearth's fire, its
    // skull, the tower's sconces, a vanilla lighting template, and the lookout as a cell of its own behind two real load
    // doors (vanilla's TrapdoorLadder02 at the top landing, Winterhold's floor trapdoor in the lookout), each sending the
    // player to where the other's "arrive" says (exported by interior_gen.py).
    // The working rooms (after hall2r): the last build's records keep their IDs through 0x927 (fifteen
    // lamps, then its pieces and the lookout), so every lamp after the fifteenth and every piece that names its record
    // ("ed": doors, beds, chests, the library's ladder and hatch) is made after all of those, in the order the interior
    // lists them. Append only: a piece's ID follows from its place in that list (a chest's contents live in the save).
    const int LampsBefore = 15;
    static (FormKey front, FormKey? patio)? AddInterior(SkyrimMod mod, List<ISkyrimModDisposableGetter> mods, string dir, Func<FormKey> newKey, FormKey travelQuest, Cell firstCell, PlacedObject inMarker,
        Dictionary<string, FormKey> byEd)
    {
        var path = Path.Combine(dir, "hall2_interior.json");
        if (!File.Exists(path)) return null;
        var skyrim = ModKey.FromNameAndExtension("Skyrim.esm");
        FormKey V(uint id) => new FormKey(skyrim, id);
        Mutagen.Bethesda.Skyrim.Activator Door(string ed, bool inside, FormKey? target = null, FormKey? key = null)
        {
            var a = new Mutagen.Bethesda.Skyrim.Activator(key ?? newKey(), SkyrimRelease.SkyrimSE)
            {
                // (an inside door names where it leads, as vanilla's do: Riverwood, to match the front door)
                EditorID = ed, Name = inside ? "Riverwood" : "Adventurers Guild Hall", ActivateTextOverride = "Open",
                ObjectBounds = new ObjectBounds { First = new P3Int16(-91, -8, 0), Second = new P3Int16(91, 0, 175) },
                Model = new Model { File = @"AdventurersGuild\Hall2\AGH2Csdoubledoorint01.nif" },
                VirtualMachineAdapter = new VirtualMachineAdapter { Scripts = { new ScriptEntry { Name = "AGHallDoor", Properties = {
                    new ScriptObjectProperty { Name = "Travel", Object = travelQuest.ToLink<ISkyrimMajorRecordGetter>(), Flags = ScriptProperty.Flag.Edited },
                    new ScriptBoolProperty { Name = "Inside", Data = inside, Flags = ScriptProperty.Flag.Edited } } } } },
            };
            if (target is { } t)
                a.VirtualMachineAdapter.Scripts[0].Properties.Add(new ScriptObjectProperty { Name = "Target", Object = t.ToLink<ISkyrimMajorRecordGetter>(), Flags = ScriptProperty.Flag.Edited });
            mod.Activators.Add(a); return a;
        }
        Door("AGHall2DoorIn", false); var doorOut = Door("AGHall2DoorOut", true);   // (the first door in: unused since)

        using var d = JsonDocument.Parse(File.ReadAllText(path));
        // (2026-10-28, the performance pass) the shell comes by room (blender/split_rooms.py: hall2_interior_room_<Room>.json, each
        // pivoted inside its room, listed in rooms_parts.json with its origin), so the room bounds can leave a room undrawn;
        // a room's mesh's bounds from its own points
        using var parts = JsonDocument.Parse(File.ReadAllText(Path.Combine(dir, "rooms_parts.json")));
        ObjectBounds BoundsOf(string file)
        {
            using var rd = JsonDocument.Parse(File.ReadAllText(Path.Combine(dir, file)));
            double[] lo = { 1e9, 1e9, 1e9 }, hi = { -1e9, -1e9, -1e9 };
            foreach (var sh in rd.RootElement.GetProperty("shapes").EnumerateObject())
                foreach (var v in sh.Value.GetProperty("v").EnumerateArray())
                    for (int k = 0; k < 3; k++) { var c = v[k].GetDouble(); lo[k] = Math.Min(lo[k], c); hi[k] = Math.Max(hi[k], c); }
            return new ObjectBounds { First = new P3Int16((short)Math.Floor(lo[0]), (short)Math.Floor(lo[1]), (short)Math.Floor(lo[2])),
                                      Second = new P3Int16((short)Math.Ceiling(hi[0]), (short)Math.Ceiling(hi[1]), (short)Math.Ceiling(hi[2])) };
        }
        // the record that was the whole shell keeps its ID (it is made in this fixed order) and is now the great hall's room
        var gh_ = parts.RootElement.GetProperty("GreatHall");
        var shell = new Static(newKey(), SkyrimRelease.SkyrimSE)
        {
            EditorID = "AGHall2Interior", Model = new Model { File = @"AdventurersGuild\Hall2\" + gh_.GetProperty("nif").GetString() },
            ObjectBounds = BoundsOf(gh_.GetProperty("file").GetString()!),
        };
        mod.Statics.Add(shell);
        Light Lamp(string ed, uint radius, int r, int g, int b)
        {
            var l = new Light(newKey(), SkyrimRelease.SkyrimSE)
            {
                EditorID = ed, Radius = radius, Color = System.Drawing.Color.FromArgb(r, g, b), Time = -1,
                FalloffExponent = 1f, FOV = 90f, FadeValue = 1f,
                ObjectBounds = new ObjectBounds { First = new P3Int16(-8, -8, -8), Second = new P3Int16(8, 8, 8) },
            };
            mod.Lights.Add(l); return l;
        }
        var lampHall = Lamp("AGHall2LampHall", 1100, 255, 196, 140);     // a chandelier's
        var lampRoom = Lamp("AGHall2LampRoom", 700, 255, 200, 150);      // a room's
        var lampSmall = Lamp("AGHall2LampSconce", 380, 255, 190, 120);   // a sconce's

        var cellKey = newKey();
        FormKey imageSpaceByEd(string e) => mods.SelectMany(m => m.ImageSpaces).Last(i => i.EditorID == e).FormKey;
        FormKey templateByEd(string e) => mods.SelectMany(m => m.LightingTemplates).Last(t => t.EditorID == e).FormKey;
        var jorrvaskr = mods.SelectMany(m => m.Cells.SelectMany(b => b.SubBlocks).SelectMany(sb => sb.Cells)).Last(c => c.EditorID == "WhiterunJorrvaskr");
        Cell NewCell(FormKey key, string ed, string name)
        {
            var c = new Cell(key, SkyrimRelease.SkyrimSE)
            {
                EditorID = ed, Name = name, Flags = Cell.Flag.IsInteriorCell,
                Lighting = firstCell.Lighting?.DeepCopy() ?? new CellLighting(),
            };
            c.AcousticSpace.SetTo(firstCell.AcousticSpace.FormKeyNullable);
            // (the lighting: as Proudspire, a hall of many windows, bright and cheerful during the day, dimmer, warmer and
            // cozy after sundown; as bright as Jorrvaskr;
            // our own ambient, with an optional Lux patch for Lux's users.) Proudspire's imagespace and template (until now a
            // farmhouse's imagespace, FarmInteriorIS, from the first test build's cell, and Whiterun's template); the ambient and the
            // directional ambient Jorrvaskr's own (its cell overrides its template's, as ours does), copied from the masters'
            // record; everything else from the template (plans/LIGHTING.md)
            c.ImageSpace.SetTo(imageSpaceByEd("SolitudeInteriorLgIS"));
            c.LightingTemplate.SetTo(templateByEd("SolitudeInteriors"));
            var li = c.Lighting!;
            var jl_ = jorrvaskr.Lighting!;
            li.AmbientColor = jl_.AmbientColor;
            li.AmbientColors = jl_.AmbientColors?.DeepCopy() ?? new AmbientColors();
            li.Inherits = (CellLighting.Inherit)(0x7FF & ~0x1);   // everything from the template but the ambient colours
            return c;
        }
        var cell = NewCell(cellKey, "AGHall2InteriorCell", "Adventurers Guild Hall");
        // the IDs the first walkable build gave out, in its order: the shell's ref, twelve lamps, the way out, the landing
        // point, the front door (kept so the records above and the cell keep their IDs; the refs themselves are matched below)
        var shellRefKey = newKey(); var lampKeys = Enumerable.Range(0, 12).Select(_ => newKey()).ToList();
        var outRefKey = newKey(); var landKey = newKey(); var frontKey = newKey();
        double[] Arr(JsonElement e) => e.EnumerateArray().Select(v => v.GetDouble()).ToArray();
        var pieces = d.RootElement.GetProperty("pieces").EnumerateArray().ToList();
        var dp = pieces.First(p => p.GetProperty("model").GetString()!.Contains("sdoubledoorint01", StringComparison.OrdinalIgnoreCase) && !p.TryGetProperty("ed", out _));
        var dpos = Arr(dp.GetProperty("pos"));
        var doorIn = Door("AGHall2FrontDoor", false, landKey, frontKey);   // its landing point, AGHall2InMarker, keeps landKey (below)

        // The fit-out (2026-10-26): the last build's plugin is the ledger (HALL2_PREV_ESP). Every reference it had in the hall's
        // cells keeps its ID for the piece of the same record (a light: for any light) that now stands nearest, a named piece
        // by its name first; one with no successor stays where it was, initially disabled; everything new takes an ID after
        // the last that plugin used. So a bed stays a bed and a chest keeps what a save put in it, whatever order the
        // generator lists things in (until hall2s an ID followed from a piece's place in that list: append only).
        var prevPath = Environment.GetEnvironmentVariable("HALL2_PREV_ESP");
        if (string.IsNullOrEmpty(prevPath) && Environment.GetEnvironmentVariable("HALL2_FRESH") != "1")
            throw new Exception("HALL2_PREV_ESP must name the last build's plugin, unmerged (or HALL2_FRESH=1 for a first build)");
        var prevByCell = new Dictionary<string, List<PrevRef>>(); var prevRec = new Dictionary<string, FormKey>(); uint prevMax = 0;
        var prevKind = new Dictionary<string, Type>();
        var prevNav = new Dictionary<string, FormKey>();   // (2026-10-27) each cell's navmesh keeps its ID between builds   // (a record by editor ID that changes kind takes a new ID: 2026-10-27, the board)
        // (2026-10-27) the ledger may be the plugin under its first name (AGHallSpike.esp): its IDs carry over by number. The
        // NPC session's block (0x8000-0x97FF, merged in after this build; 0x9000 on is its second block, 2026-11-05; 0x9800-0x99FF the promotion trials' block, AG Detail Work, 2026-11-05) is never the ledger's
        ModKey prevKey = mod.ModKey; bool renamed = false;
        FormKey Tr(FormKey k) => k.ModKey == prevKey ? new FormKey(mod.ModKey, k.ID) : k;
        static bool Npc(uint id) => id >= 0x8000 && id <= 0x99FF;
        var lightBases = new HashSet<FormKey>(mods.SelectMany(m => m.Lights).Select(l => l.FormKey));
        if (!string.IsNullOrEmpty(prevPath))
        {
            using var pm = SkyrimMod.CreateFromBinaryOverlay(prevPath, SkyrimRelease.SkyrimSE);
            prevKey = pm.ModKey; renamed = prevKey != mod.ModKey;
            foreach (var r in pm.EnumerateMajorRecords())
            {
                if (r.FormKey.ModKey == prevKey && (Npc(r.FormKey.ID) || Fixed(r.FormKey.ID))) continue;
                if (r.FormKey.ModKey == prevKey) prevMax = Math.Max(prevMax, r.FormKey.ID);
                if (r.EditorID is { } e && r.FormKey.ModKey == prevKey) { prevRec.TryAdd(e, Tr(r.FormKey)); prevKind.TryAdd(e, r.GetType()); }
                if (r is ILightGetter) lightBases.Add(Tr(r.FormKey));
            }
            foreach (var c in pm.Cells.SelectMany(b => b.SubBlocks).SelectMany(sb => sb.Cells))
            {
                if (c.EditorID is not ("AGHall2InteriorCell" or "AGHall2LookoutCell" or "AGHall2BasementCell")) continue;
                if (c.NavigationMeshes.FirstOrDefault() is { } pn) prevNav[c.EditorID] = Tr(pn.FormKey);
                prevByCell[c.EditorID] = c.Persistent.Concat(c.Temporary).OfType<IPlacedObjectGetter>().Where(r => r.Placement is not null && !Npc(r.FormKey.ID))
                    .Select(r => new PrevRef(Tr(r.FormKey), Tr(r.Base.FormKey), r.Placement!.Position, r.Placement.Rotation, r.Scale ?? 1f,
                                             (r.MajorRecordFlagsRaw & 0x400) != 0, r.EditorID)).ToList();
            }
            Console.WriteLine($"interior: ledger {Path.GetFileName(prevPath)}: IDs to 0x{prevMax:X}, " +
                              string.Join(", ", prevByCell.Select(kv => $"{kv.Key} {kv.Value.Count} refs")));
        }
        FormKey Fresh() { FormKey k; do k = newKey(); while (k.ID <= prevMax); return k; }
        if (renamed) Console.WriteLine($"interior: renamed from {prevKey.FileName}: the ledger's IDs carry over by number, its retired refs are dropped (no save holds the new plugin)");
        FormKey Rec(string ed) => prevRec.TryGetValue(ed, out var k) ? k : Fresh();   // a record the last build had, by editor ID
        FormKey RecAs<T>(string ed) => prevKind.TryGetValue(ed, out var t) && !typeof(T).IsAssignableFrom(t) ? Fresh() : Rec(ed);

        // W's own statics: Hearthfire's skull (its mesh is in every install's archives, its record would make HearthFires.esm a
        // master; retired by the fit-out, kept for the disabled ref), the lookout's shell
        var skull = new Static(Rec("AGHall2DragonSkull"), SkyrimRelease.SkyrimSE)
        {
            EditorID = "AGHall2DragonSkull", Model = new Model { File = @"_BYOH\Architecture\BYOHHouse\Trophy\BYOHHouseTrophyDragon01.nif" },
            ObjectBounds = new ObjectBounds { First = new P3Int16(-105, -44, -4), Second = new P3Int16(66, 42, 83) },
        };
        mod.Statics.Add(skull);
        // Hearthfire's standing bear for the great hall, as our own static for the same
        // reason (its record is HearthFires.esm's)
        var bear = new Static(Rec("AGHall2Bear"), SkyrimRelease.SkyrimSE)
        {
            EditorID = "AGHall2Bear", Model = new Model { File = @"_BYOH\Architecture\BYOHHouse\Trophy\BYOHHouseTrophyBear2ft01.nif" },
            ObjectBounds = new ObjectBounds { First = new P3Int16(-50, -36, -2), Second = new P3Int16(64, 77, 180) },
        };
        mod.Statics.Add(bear);
        byEd["AGHall2Bear"] = bear.FormKey;
        // (2026-11-01) the guild's banner as the holds' are: vanilla's animated cloth with its own picture, by a texture set on the mesh's one shape
        var bannerTx_ = new TextureSet(Rec("AGHall2BannerClothTX"), SkyrimRelease.SkyrimSE) { EditorID = "AGHall2BannerClothTX", ObjectBounds = new ObjectBounds(), Diffuse = @"AdventurersGuild\Hall2\AGH2BannerCloth.dds", NormalOrGloss = @"AdventurersGuild\Hall2\AGH2BannerCloth_n.dds" };
        mod.TextureSets.Add(bannerTx_);
        var bannerCloth_ = mods.SelectMany(m => m.MoveableStatics).Last(m => m.EditorID == "CityBannerRiften01").Duplicate(Rec("AGHall2BannerCloth"));
        bannerCloth_.EditorID = "AGHall2BannerCloth"; bannerCloth_.Model!.AlternateTextures![0].NewTexture.SetTo(bannerTx_.FormKey);
        mod.MoveableStatics.Add(bannerCloth_); byEd["AGHall2BannerCloth"] = bannerCloth_.FormKey;
        // the counter's paperwork (clutter for the counter shelves): vanilla's book, note and
        // journal meshes as our own statics, so they are dressing, not readable or takeable books (many of vanilla's notes
        // belong to quests); replacers of the meshes still apply
        foreach (var (ced, cmodel, clo, chi) in new[] {
            ("AGHall2Note01", @"Clutter\Books\Note01.nif", (-8, -5, 0), (8, 5, 1)), ("AGHall2Note02", @"Clutter\Books\Note02.nif", (-8, -5, 0), (8, 5, 1)),
            ("AGHall2Note03", @"Clutter\Books\Note03.nif", (-8, -5, 0), (8, 5, 1)), ("AGHall2Note04", @"Clutter\Books\Note04.nif", (-8, -5, 0), (8, 5, 1)),
            ("AGHall2Book01", @"Clutter\Books\BasicBook01.nif", (-9, -12, -2), (9, 12, 2)), ("AGHall2Book03", @"Clutter\Books\BasicBook03.nif", (-9, -12, -2), (9, 12, 2)),
            ("AGHall2Book06", @"Clutter\Books\BasicBook06.nif", (-9, -12, -2), (9, 12, 2)), ("AGHall2BookLarge", @"Clutter\Books\Book02LowPoly02.nif", (-12, -15, -3), (12, 15, 3)),
            ("AGHall2Journal", @"Clutter\Books\JournalLowPoly01.nif", (-6, -9, -1), (7, 9, 1)),
            // the strongroom's ledger (2026-10-27): the mesh of TGR's business ledger, vanilla's one open ledger, as dressing (the record
            // itself is a Thieves Guild quest item)
            ("AGHall2Ledger", @"Clutter\Quest\TGRBusinessLedger.nif", (-31, -19, -3), (31, 19, 3)),
            // the library's shelves (2026-10-27): the other covers of the same book, not to be taken from the shelves
            ("AGHall2Book03a", @"Clutter\Books\BasicBook03a.nif", (-9, -12, -2), (9, 12, 2)), ("AGHall2Book04", @"Clutter\Books\BasicBook04.nif", (-9, -12, -2), (9, 12, 2)),
            ("AGHall2Book04a", @"Clutter\Books\BasicBook04a.nif", (-9, -12, -2), (9, 12, 2)), ("AGHall2Book05", @"Clutter\Books\BasicBook05.nif", (-9, -12, -2), (9, 12, 2)),
            ("AGHall2Book05a", @"Clutter\Books\BasicBook05a.nif", (-9, -12, -2), (9, 12, 2)), ("AGHall2BookLarge2", @"Clutter\Books\Book02LowPoly.nif", (-12, -15, -3), (12, 15, 3)) })
        {
            var cs = new Static(Rec(ced), SkyrimRelease.SkyrimSE)
            {
                EditorID = ced, Model = new Model { File = cmodel },
                ObjectBounds = new ObjectBounds { First = new P3Int16((short)clo.Item1, (short)clo.Item2, (short)clo.Item3), Second = new P3Int16((short)chi.Item1, (short)chi.Item2, (short)chi.Item3) },
            };
            mod.Statics.Add(cs);
            byEd[ced] = cs.FormKey;
        }
        // the guild board (v1: the planned size on the tower foot's face, a stand-off
        // frame round the arch's stub). Since then the working board:
        // an activator, "Guild Board", activated to "Read"; AG's DLL opens the board page for any activator whose model is
        // under AdventurersGuild\Board\AGGuildBoard, so it needs no script
        var board = new Mutagen.Bethesda.Skyrim.Activator(RecAs<IActivatorGetter>("AGHall2GuildBoard"), SkyrimRelease.SkyrimSE)
        {
            EditorID = "AGHall2GuildBoard", Name = "Guild Board", ActivateTextOverride = "Read",
            Model = new Model { File = @"AdventurersGuild\Board\AGGuildBoard.nif" },
            ObjectBounds = new ObjectBounds { First = new P3Int16(-125, -21, -1), Second = new P3Int16(125, 1, 140) },
        };
        mod.Activators.Add(board);
        byEd["AGHall2GuildBoard"] = board.FormKey;
        foreach (var v_ in new[] { "B", "C" })                  // its other postings (the board session's v4 variants), rotated
        {                                                       // by AGHallBoardRotate on a marker beside it
            var bv = new Mutagen.Bethesda.Skyrim.Activator(RecAs<IActivatorGetter>("AGHall2GuildBoard" + v_), SkyrimRelease.SkyrimSE)
            {
                EditorID = "AGHall2GuildBoard" + v_, Name = "Guild Board", ActivateTextOverride = "Read",
                Model = new Model { File = $@"AdventurersGuild\Board\AGGuildBoard_{v_}.nif" },
                ObjectBounds = new ObjectBounds { First = new P3Int16(-125, -21, -3), Second = new P3Int16(125, 1, 140) },
            };
            mod.Activators.Add(bv);
            byEd["AGHall2GuildBoard" + v_] = bv.FormKey;
        }
        // (the party leader board, on wall G) the same as the
        // guild board: AG's LeaderBoard.cpp opens its page for this model, so it needs no script. Its name is a placeholder.
        // At the fixed ID promised to it; its bounds measured from the mesh (x -64.2..64.4, y -4.9..-0.4, z -0.2..120.3)
        {
            var lb_ = new Mutagen.Bethesda.Skyrim.Activator(new FormKey(mod.ModKey, 0x7F21), SkyrimRelease.SkyrimSE)
            {
                EditorID = "AGHall2LeaderBoard", Name = "Party Standings", ActivateTextOverride = "Read",
                Model = new Model { File = @"AdventurersGuild\LeaderBoard\AGLeaderBoard.nif" },
                ObjectBounds = new ObjectBounds { First = new P3Int16(-65, -5, -1), Second = new P3Int16(65, 0, 121) },
            };
            mod.Activators.Add(lb_);
            byEd["AGHall2LeaderBoard"] = lb_.FormKey;
            // (2026-11-04, the detail session's story pieces: leaderboard/lb_build.py LB_PART) the fresh slip and the Golden Hand's strike, statics on the
            // board's own spot; LeaderBoard.cpp finds them by model in the board's cell and shows or hides each as the story stands. Bounds measured from the meshes
            foreach (var (ed_, id_, nif_, lo_, hi_) in new (string, uint, string, short[], short[])[] {
                         ("AGHall2LeaderSlip", 0x7F22, "AGLeaderSlip.nif", new short[] { 42, -6, 27 }, new short[] { 57, -4, 41 }),
                         ("AGHall2LeaderStrike", 0x7F23, "AGLeaderStrike.nif", new short[] { -28, -5, 30 }, new short[] { 40, -3, 33 }) })
            {
                var st_ = new Static(new FormKey(mod.ModKey, id_), SkyrimRelease.SkyrimSE)
                {
                    EditorID = ed_, Model = new Model { File = @"AdventurersGuild\LeaderBoard\" + nif_ },
                    ObjectBounds = new ObjectBounds { First = new P3Int16(lo_[0], lo_[1], lo_[2]), Second = new P3Int16(hi_[0], hi_[1], hi_[2]) },
                };
                mod.Statics.Add(st_); byEd[ed_] = st_.FormKey;
            }
        }
        // the guild, as an owner: what it owns (the rack's shield, the strongroom's contents) is stolen if taken
        // (the guild owns the hall, as the Companions own Jorrvaskr; vanilla's, measured: the Companions
        // faction tracks its own crime, does not report crimes against its members, can own, and is allied to itself; the
        // Harbinger's rooms belong to a hidden faction of his own) the guild owns the hall and handles theft in it itself;
        // the guild master's office, bedroom and strongroom belong to his own faction, so a registered member (in the guild's)
        // still steals if he takes from them
        var guild = new Faction(Rec("AGHall2GuildFaction"), SkyrimRelease.SkyrimSE)
        {
            EditorID = "AGHall2GuildFaction", Name = "Adventurers Guild",
            Flags = Faction.FactionFlag.HiddenFromPC | Faction.FactionFlag.TrackCrime | Faction.FactionFlag.DoNotReportCrimesAgainstMembers | Faction.FactionFlag.CanBeOwner,
        };
        guild.Relations.Add(new Relation { Target = guild.FormKey.ToLink<IRelatableGetter>(), Reaction = CombatReaction.Ally });
        // (2026-10-27) AG's DLL finds the guild's faction by its ID: it must never move
        if (guild.FormKey.ID != 0x995) throw new Exception($"AGHall2GuildFaction is 0x{guild.FormKey.ID:X}, not 0x995: AG's DLL finds it by that ID");
        mod.Factions.Add(guild);
        var gmFaction = new Faction(Rec("AGHall2GuildMasterFaction"), SkyrimRelease.SkyrimSE)
        {
            EditorID = "AGHall2GuildMasterFaction", Name = "Guild Master", Flags = Faction.FactionFlag.HiddenFromPC | Faction.FactionFlag.CanBeOwner,
        };
        mod.Factions.Add(gmFaction);
        cell.Owner.SetTo(guild.FormKey); cell.Flags |= Cell.Flag.PublicArea;   // (the hall: the guild's, and open to all)
        // the hall's own chest: vanilla's upper-class chest mesh, but
        // vanilla's empty one (TreasUpperChestEMPTY) respawns, which would empty a recruit's chest; this one never does and
        // holds nothing to start with
        var upperChest = mods.SelectMany(m => m.Containers).Last(c => c.EditorID == "TreasUpperChestEMPTY");
        var hallChest = upperChest.Duplicate(Rec("AGHall2Chest"));
        hallChest.EditorID = "AGHall2Chest"; hallChest.Name = "Chest";
        hallChest.Flags &= ~Container.Flag.Respawns; hallChest.Items = null;
        mod.Containers.Add(hallChest);
        byEd["AGHall2Chest"] = hallChest.FormKey;
        // the loft's chest (a chest with a valuable item, owned by the general guild faction so players can take it: a
        // decent enchanted piece of armor, with a letter explaining it, written as a former adventurer who left it; the
        // armor a tier higher than the leveled lists give at the time; until hall2bd a leveled roll from vanilla's enchanted cuirass lists, each entry 6 levels sooner) and a
        // retired member's letter. The guild's (the cell), so a member takes them freely; it never respawns
        // (the tier-up roll gave Leather Armor of the Minor Squire at level 10, too weak an enchantment; so
        // Stone-Arm's own piece) one fixed cuirass for everyone in place of the roll:
        // vanilla's Steel Plate Knight cuirass (its template, mesh and keywords) as Stone-Arm's Cuirass, its enchantment two
        // constant effects on vanilla's own magic effects, Fortify Heavy Armor 30 and Fortify Healing Rate 15
        var enchSrc_ = mods.SelectMany(m => m.ObjectEffects).Last(e => e.EditorID == "EnchArmorFortifyHeavyArmor05");
        var healSrc_ = mods.SelectMany(m => m.ObjectEffects).Last(e => e.EditorID == "EnchArmorFortifyHealRate04");
        var stoneEnch = enchSrc_.Duplicate(Rec("AGHall2StoneArmEnch"));
        stoneEnch.EditorID = "AGHall2StoneArmEnch"; stoneEnch.Name = "Stone-Arm's Luck";
        var heavyFx_ = enchSrc_.Effects[0].DeepCopy(); heavyFx_.Data!.Magnitude = 30;
        var healFx_ = healSrc_.Effects[0].DeepCopy(); healFx_.Data!.Magnitude = 15;
        stoneEnch.Effects.Clear(); stoneEnch.Effects.Add(heavyFx_); stoneEnch.Effects.Add(healFx_);
        mod.ObjectEffects.Add(stoneEnch);
        var cuirassSrc_ = mods.SelectMany(m => m.Armors).Last(a => a.EditorID == "EnchArmorSteelPlateCuirassHeavyArmor03");
        var legacyArmor = cuirassSrc_.Duplicate(Rec("AGHall2StoneArmCuirass"));
        legacyArmor.EditorID = "AGHall2StoneArmCuirass"; legacyArmor.Name = "Stone-Arm's Cuirass";
        legacyArmor.ObjectEffect.SetTo(stoneEnch); legacyArmor.Value = 1200;
        mod.Armors.Add(legacyArmor);
        var noteSrc_ = mods.SelectMany(m => m.Books).Last(b => b.EditorID == "MS07JareeRaNote");
        var legacyLetter = new Book(Rec("AGHall2LegacyLetter"), SkyrimRelease.SkyrimSE)
        {
            EditorID = "AGHall2LegacyLetter", Name = LegacyLetter.Title, Model = noteSrc_.Model?.DeepCopy(), ObjectBounds = noteSrc_.ObjectBounds.DeepCopy(),
            PickUpSound = noteSrc_.PickUpSound.FormKeyNullable is { } pu_ ? new FormLinkNullable<ISoundDescriptorGetter>(pu_) : new FormLinkNullable<ISoundDescriptorGetter>(),
            PutDownSound = noteSrc_.PutDownSound.FormKeyNullable is { } pd_ ? new FormLinkNullable<ISoundDescriptorGetter>(pd_) : new FormLinkNullable<ISoundDescriptorGetter>(),
            InventoryArt = noteSrc_.InventoryArt.FormKeyNullable is { } ia_ ? new FormLinkNullable<IStaticGetter>(ia_) : new FormLinkNullable<IStaticGetter>(),
            Flags = noteSrc_.Flags, Type = noteSrc_.Type, Value = 0, Weight = 0, Description = "", BookText = LegacyLetter.Text,
        };
        mod.Books.Add(legacyLetter);
        var legacyChest = hallChest.Duplicate(Rec("AGHall2LegacyChest"));
        legacyChest.EditorID = "AGHall2LegacyChest";
        legacyChest.Items = new() { new ContainerEntry { Item = new ContainerItem { Item = legacyArmor.ToLink<IItemGetter>(), Count = 1 } },
                                    new ContainerEntry { Item = new ContainerItem { Item = legacyLetter.ToLink<IItemGetter>(), Count = 1 } } };
        mod.Containers.Add(legacyChest);
        byEd["AGHall2LegacyChest"] = legacyChest.FormKey;
        // (vanilla's writing chair at the library's desk, so whoever sits
        // there writes) its copy with a name: vanilla's CommonWritingChair01LR has none, and the player can only use what is named
        var writingChair_ = mods.SelectMany(m => m.Furniture).Last(f => f.EditorID == "CommonWritingChair01LR").Duplicate(Rec("AGHall2WritingChair"));
        writingChair_.EditorID = "AGHall2WritingChair"; writingChair_.Name = "Chair";
        mod.Furniture.Add(writingChair_); byEd["AGHall2WritingChair"] = writingChair_.FormKey;
        var armors =mods.SelectMany(m => m.Armors).GroupBy(a => a.FormKey).Select(g => g.Last()).Where(a => a.EditorID is not null)
                         .GroupBy(a => a.EditorID!).ToDictionary(g => g.Key, g => g.Last().FormKey, StringComparer.OrdinalIgnoreCase);
        var keywords = mods.SelectMany(m => m.Keywords).Where(k => k.EditorID is not null).GroupBy(k => k.EditorID!)
                           .ToDictionary(g => g.Key, g => g.Last().FormKey, StringComparer.OrdinalIgnoreCase);
        // the lights by kind: vanilla's own Solitude inn and Whiterun records (2026-10-26: our three lamps reached 380..1100 at
        // full strength and washed every room out; vanilla's inns light small pools)
        // (2026-10-28, the lighting plan: vanilla lights its halls with a few large soft lights, a fire at 768 with shadows,
        // fills at 512, window fills at 200, candles as accents at 128 (lightsurvey: Jorrvaskr 13 lights, Dragonsreach 28;
        // the hall had 63, nearly all small). Each kind now Jorrvaskr's or Dragonsreach's own record, found by editor ID)
        FormKey lightByEd(string e) => mods.SelectMany(m => m.Lights).Last(l => l.EditorID == e).FormKey;
        // (2026-10-28, the performance pass) each one portal-strict, the hall's own copy where vanilla's is not: with the room
        // bounds a portal-strict light lights only its own room (and what its portals show), so a lamp no longer lights the
        // rooms through its walls (measured on the shell: 3 lights on a piece at the median and 12 at the 90th from its own
        // room's, 5 and 11 counting every light whose reach crosses a wall); vanilla's halls mark theirs so too (Dragonsreach
        // 11 of 28, the Bannered Mare 9 of 18), and a shadow light must be (the CK's Light page)
        FormKey strict(string ed, ILightGetter src, System.Drawing.Color? colour = null)
        {
            if (src.Flags.HasFlag(Light.Flag.PortalStrict)) return src.FormKey;
            var c_ = src.Duplicate(Rec(ed)); c_.EditorID = ed; c_.Flags |= Light.Flag.PortalStrict;
            if (colour is { } k_) c_.Color = k_;
            mod.Lights.Add(c_); return c_.FormKey;
        }
        var fireColour_ = System.Drawing.Color.FromArgb(0, 255, 160, 64);   // (2026-10-30: a fire's orange, where vanilla's 216,170,101 goes yellow-white on plaster)
        ILightGetter lightRec(string e) => mods.SelectMany(m => m.Lights).Last(l => l.EditorID == e);
        var lightOf = new Dictionary<string, FormKey>
        {
            ["candle"] = lightByEd("WRCandleFlickerNS"),       // 128, fade 1.7, flicker (was SolitudeInnCandleDefault 256): portal-strict already
            ["candle_small"] = lightByEd("WRCandleFlickerNS"), // 128, 1.7
            ["candle_night"] = lightByEd("WRCandleFlickerNS"), // (a candle by a window: on when the daylight is off)
            ["window"] = strict("AGHall2LightWindow", lightRec("WRWindowFill")),         // 200, 1.5, cool daylight (Jorrvaskr's nine); on the region
            ["fire"] = strict("AGHall2LightFire", lightRec("WRFireLightShadow01"), fireColour_),      // 768, 3.0, shadows (Jorrvaskr's and the Bannered Mare's hearth)
            ["fire_small"] = strict("AGHall2LightFireSmall", mods.SelectMany(m => m.Lights).Last(l => l.FormKey == V(0x05D948)), fireColour_),   // WRLightFire01: 512, 1.0
            ["lamp"] = strict("AGHall2LightLamp", lightRec("WRInteriorLightYellow")),    // 512, 1.25 (Jorrvaskr's fill)
        };

        // (in game, from 8am the walls by the windows washed out to glare: 2.0 at 60 off the wall put about 1.4 on pale plaster. Now Lux_SolitudeFakeWindowColdNS's recipe, 250, 0.75, a grey that the region's colour multiplies. They burn by day only)
        { var w_ = mod.Lights.First(l => l.EditorID == "AGHall2LightWindow"); w_.Radius = 250; w_.FadeValue = 0.75f; w_.Color = System.Drawing.Color.FromArgb(0, 158, 158, 158); }
        // (2026-11-02, the same plan) a chandelier's reach, modelled on Lux_FarmChandelierFlickerNS: wide and low in a deep orange, where WRCandleFlickerNS's pale 1.7 clips red and green together on plaster; no shadow, flicker, portal-strict (its flags); fixed ID
        { var c_ = lightRec("WRCandleFlickerNS").Duplicate(new FormKey(mod.ModKey, 0x7F1A)); c_.EditorID = "AGHall2LightChandelier"; c_.Radius = 360; c_.FadeValue = 1.0f;
          c_.Color = System.Drawing.Color.FromArgb(0, 255, 173, 100); mod.Lights.Add(c_); lightOf["chandelier"] = c_.FormKey; }
        // (2026-11-02) the big rooms' soft daylight, modelled on Lux_DefaultSunBounceNS: 500, fade 1.0, a grey that the region's colour multiplies; portal-strict, as the fill it copies; fixed ID
        { var b_ = mod.Lights.First(l => l.EditorID == "AGHall2LightWindow").Duplicate(new FormKey(mod.ModKey, 0x7F14)); b_.EditorID = "AGHall2LightBounce"; b_.Radius = 500; b_.FadeValue = 1.0f;
          b_.Color = System.Drawing.Color.FromArgb(0, 197, 197, 197); mod.Lights.Add(b_); lightOf["bounce"] = b_.FormKey; }
        // everything the two cells hold, then matched to the ledger
        var plans = new List<Plan>();
        // (2026-11-02) a mesh with the inside's panes on it: its reference carries the region (blender/window_emit_check.py gates it)
        var paneBases = new HashSet<FormKey>(); bool Glazed(string f_) => File.ReadAllText(Path.IsPathRooted(f_) ? f_ : Path.Combine(dir, Path.GetFileName(f_))).Contains("\"gpane");
        Plan Add(Plan p) { plans.Add(p); return p; }
        FormKey BaseOf(JsonElement p)
        {
            var m = p.GetProperty("model").GetString()!.ToLowerInvariant();
            if (p.TryGetProperty("ed", out var edp))
            {
                var e = edp.GetString()!;
                if (byEd.TryGetValue(e, out var b)) return b;
                if (armors.TryGetValue(e, out var ab)) return ab;
                throw new Exception("interior: no record named " + e);
            }
            if (m.Contains("impwallsconce02candleon01")) return V(0x05D6EA);   // ImpWallSconce02CandleOn01
            if (m.Contains("fireplacewood01burning")) return V(0x035F4A);      // FireplaceWood01Burning
            if (m.Contains("byohhousetrophydragon01")) return skull.FormKey;
            if (m.Contains("trapdoorladder02")) return V(0x05AD3B);            // TrapdoorLadder02
            if (m.Contains("winterholdtrapdoor01")) return V(0x10DE06);        // WinterholdTrapdoor01
            throw new Exception("interior: no record for " + m);
        }
        void Pieces(string cellEd, IEnumerable<JsonElement> ps, string? skipModel = null)
        {
            foreach (var p in ps)
            {
                var m = p.GetProperty("model").GetString()!;
                if (skipModel is not null && m.Contains(skipModel, StringComparison.OrdinalIgnoreCase) && !p.TryGetProperty("ed", out _)) continue;
                var pos = Arr(p.GetProperty("pos"));
                var pl = new Plan(cellEd, BaseOf(p), pos[0], pos[1], pos[2], p.GetProperty("yaw").GetDouble(), p.GetProperty("scale").GetDouble(), false) { J = p };
                if (p.TryGetProperty("name", out var nm)) pl.Name = nm.GetString();
                if (p.TryGetProperty("rx", out var rx_)) pl.RX = rx_.GetDouble();   // a tilt about its own x (a map on a wall)
                if (p.TryGetProperty("ga", out var ga_)) { var g_ = Arr(ga_); pl.GA = new P3Float((float)(g_[0] * Math.PI / 180), (float)(g_[1] * Math.PI / 180), (float)(g_[2] * Math.PI / 180)); }   // (2026-11-03) the game's own angles, as given
                if (p.TryGetProperty("role", out var ro)) pl.Role = ro.GetString();
                if (p.TryGetProperty("pair", out var pr)) pl.Pair = pr.GetString();
                if (pl.Role == "ladder") { pl.Pair ??= "hatch"; pl.Name ??= "AGHall2LadderDoor"; }        // (W's tower ladder and the
                if (pl.Role == "hatch") { pl.Pair ??= "ladder"; pl.Name ??= "AGHall2LookoutHatch"; }      // lookout's hatch: their names)
                pl.Persistent = pl.Pair is not null || (p.TryGetProperty("persistent", out var pe) && pe.GetBoolean());
                Add(pl);
            }
        }
        // each light's level by Lux's measure, its peak on visible plaster 0.45 or less (fires 0.84), by position: blender/plaster_check.py
        // gates the result on the plugin. The list's own values are the final radius and fade; an entry that meets no light stops the build, for a moved light has to be measured again
        var levels_ = JsonDocument.Parse(File.ReadAllText("textures/light_levels.json")).RootElement.EnumerateArray().ToList(); var levelsUsed_ = new HashSet<int>();
        void Lights(string cellEd, JsonElement lights)
        {
            foreach (var l in lights.EnumerateArray())
            {
                var p = Arr(l[0]); var w = l[1].GetDouble();
                string? kind = l.GetArrayLength() > 3 ? l[3].GetString() : null;
                if (kind is null && w < 5e5) continue;                 // the renders' window glows: no light of their own in a cell
                if (kind == "glow") continue;
                var b = kind is not null ? lightOf[kind] : (w >= 5e6 ? lampHall : w >= 1.5e6 ? lampRoom : lampSmall).FormKey;
                var lv_ = levels_.FindIndex(e_ => { var q_ = Arr(e_.GetProperty("pos")); return Math.Abs(q_[0] - p[0]) <= 1 && Math.Abs(q_[1] - p[1]) <= 1 && Math.Abs(q_[2] - p[2]) <= 1; });
                if (lv_ >= 0 && levels_[lv_].GetProperty("kind").GetString() == "chandelier") b = lightOf["chandelier"];
                var pl_ = Add(new Plan(cellEd, b, p[0], p[1], p[2], 0, 1, true) { Kind = kind });
                // (the kitchen was far too bright) a light trimmed in place as vanilla trims its own:
                // the reference's radius offset (XRDS) and fade offset (XLIG), e.g. Breezehome's hearth, WRFireLightShadow01
                // at -322 and -0.51; the export's fifth and sixth entries
                if (l.GetArrayLength() > 4) pl_.LightRadius = (float)l[4].GetDouble();
                if (l.GetArrayLength() > 5) pl_.LightFade = (float)l[5].GetDouble();
                if (lv_ >= 0)
                {
                    if (!levelsUsed_.Add(lv_)) throw new Exception("light_levels.json: two lights at one entry, " + levels_[lv_].GetProperty("id").GetString());
                    var nw_ = levels_[lv_].GetProperty("new"); ILightGetter rec_ = mod.Lights.FirstOrDefault(x_ => x_.FormKey == b) ?? mods.SelectMany(m_ => m_.Lights).Last(x_ => x_.FormKey == b);
                    var dr_ = nw_.GetProperty("r").GetDouble() - rec_.Radius; var df_ = nw_.GetProperty("fade").GetDouble() - rec_.FadeValue;
                    pl_.LightRadius = Math.Abs(dr_) > 0.5 ? (float)dr_ : null; pl_.LightFade = Math.Abs(df_) > 0.001 ? (float)df_ : null;
                }
            }
        }
        // the back door (working since hall2t): an outside door in the layout's place
        // for it, which brings one in to a landing point by the lobby's back wall, and the inside door, which takes one out in
        // front of the outside one (AGHallNative.HallRef finds it); the front door's inside one now leads out in front of its
        // own outside door too, whichever door one came in by
        doorOut.VirtualMachineAdapter!.Scripts[0].Properties.Add(new ScriptObjectProperty { Name = "Outside", Object = doorIn.FormKey.ToLink<ISkyrimMajorRecordGetter>(), Flags = ScriptProperty.Flag.Edited });
        Mutagen.Bethesda.Skyrim.Activator? patioDoor = null; FormKey patioLandKey = default; Plan? patioLand = null;
        if (d.RootElement.TryGetProperty("patio_land", out var pl_))
        {
            patioLandKey = prevByCell.GetValueOrDefault("AGHall2InteriorCell")?.FirstOrDefault(r => r.Ed == "AGHall2PatioInMarker")?.Key ?? Fresh();
            patioDoor = Door("AGHall2PatioDoor", false, patioLandKey, Rec("AGHall2PatioDoor"));
            var patioOut = Door("AGHall2PatioDoorOut", true, null, Rec("AGHall2PatioDoorOut"));
            patioOut.VirtualMachineAdapter!.Scripts[0].Properties.Add(new ScriptObjectProperty { Name = "Outside", Object = patioDoor.FormKey.ToLink<ISkyrimMajorRecordGetter>(), Flags = ScriptProperty.Flag.Edited });
            byEd["AGHall2PatioDoorOut"] = patioOut.FormKey;
            var lp = Arr(pl_[0]);
            patioLand = Add(new Plan("AGHall2InteriorCell", inMarker.Base.FormKey, lp[0], lp[1], lp[2], pl_[1].GetDouble(), 1, false) { Name = "AGHall2PatioInMarker", Persistent = true, FixedKey = patioLandKey });
        }
        var gho_ = Arr(gh_.GetProperty("origin"));
        Add(new Plan("AGHall2InteriorCell", shell.FormKey, gho_[0], gho_[1], gho_[2], 0, 1, false) { FixedKey = shellRefKey });
        if (Glazed(gh_.GetProperty("file").GetString()!)) paneBases.Add(shell.FormKey);
        foreach (var rp in parts.RootElement.EnumerateObject().Where(rp => rp.Name != "GreatHall"))
        {
            var ro = Arr(rp.Value.GetProperty("origin")); var rn = "AGHall2Room" + rp.Name;
            var rs = new Static(Rec(rn), SkyrimRelease.SkyrimSE)
            {
                EditorID = rn, Model = new Model { File = @"AdventurersGuild\Hall2\" + rp.Value.GetProperty("nif").GetString() },
                ObjectBounds = BoundsOf(rp.Value.GetProperty("file").GetString()!),
            };
            mod.Statics.Add(rs);
            if (Glazed(rp.Value.GetProperty("file").GetString()!)) paneBases.Add(rs.FormKey);
            Add(new Plan("AGHall2InteriorCell", rs.FormKey, ro[0], ro[1], ro[2], 0, 1, false));
        }
        Console.WriteLine($"interior: the shell in {parts.RootElement.EnumerateObject().Count()} rooms");
        // (2026-10-27, the clutter pass) the baked clutter, merged into statics by blender/bake_clutter.py as vanilla's bookcases
        // carry their books; (2026-10-28, the performance pass) one per room, AGHall2Bake<Room>.nif pivoted at the room's origin
        // like its shell (rooms_bakes.json, blender/split_rooms.py's); its bounds round the pieces' origins (none is 35 across)
        if (File.Exists(Path.Combine(dir, "rooms_bakes.json")))
        {
            using var bk_ = JsonDocument.Parse(File.ReadAllText(Path.Combine(dir, "rooms_bakes.json")));
            foreach (var g in bk_.RootElement.EnumerateObject())
            {
                var lo_ = Arr(g.Value.GetProperty("lo")); var hi_ = Arr(g.Value.GetProperty("hi")); var bo_ = Arr(g.Value.GetProperty("origin"));
                var bn = "AGHall2Bake" + g.Name;
                var bs = new Static(Rec(bn), SkyrimRelease.SkyrimSE)
                {
                    EditorID = bn, Model = new Model { File = $@"AdventurersGuild\Hall2\{bn}.nif" },
                    ObjectBounds = new ObjectBounds { First = new P3Int16((short)Math.Floor(lo_[0]), (short)Math.Floor(lo_[1]), (short)Math.Floor(lo_[2])),
                                                      Second = new P3Int16((short)Math.Ceiling(hi_[0]), (short)Math.Ceiling(hi_[1]), (short)Math.Ceiling(hi_[2])) },
                };
                mod.Statics.Add(bs);
                Add(new Plan("AGHall2InteriorCell", bs.FormKey, bo_[0], bo_[1], bo_[2], 0, 1, false));
                Console.WriteLine($"interior: {bn} carries {g.Value.GetProperty("pieces").GetInt32()} baked pieces");
            }
        }
        // the room bounds and their portals (blender/rooms_check.py's rooms.json, vanilla's way: Dragonsreach, the Blue Palace):
        // each room's boxes as RoomMarkers, a PortalMarker in each opening between two rooms; their primitives, links and
        // portals are set once the references exist (below)
        // (culling dropped altogether after hall2bl: walls and ceilings
        // missing through open doors into Room5, the common room and the kitchen. No room bounds or portals are written; the
        // ledger's old markers are dropped, not kept disabled (below). The shell stays split by room: one mesh per room)
        const bool UseRooms = false;
        var roomPlans = new Dictionary<(string room, int box), Plan>(); var roomBoxes = new Dictionary<(string room, int box), double[]>();
        var portalPlans = new List<(Plan p, JsonElement j)>();
        using var roomsDoc_ = JsonDocument.Parse(File.ReadAllText(Path.Combine(dir, "rooms.json")));
        if (UseRooms)
        foreach (var rm in roomsDoc_.RootElement.GetProperty("rooms").EnumerateObject())
        {
            int i_ = 0;
            foreach (var bx in rm.Value.EnumerateArray())
            {
                var b_ = Arr(bx);
                roomPlans[(rm.Name, i_)] = Add(new Plan("AGHall2InteriorCell", V(0x00001F), (b_[0] + b_[1]) / 2, (b_[2] + b_[3]) / 2, (b_[4] + b_[5]) / 2, 0, 1, false)
                    { Name = $"AGHall2Room{rm.Name}{i_}" });
                roomBoxes[(rm.Name, i_)] = b_;
                i_++;
            }
        }
        int pi_ = 0;
        if (UseRooms)
        foreach (var pt in roomsDoc_.RootElement.GetProperty("portals").EnumerateArray())
        {
            int ax = pt.GetProperty("axis").GetInt32(); var o_ = pt.GetProperty("o"); double pl = pt.GetProperty("plane").GetDouble();
            var u = Arr(pt.GetProperty("u")); var v = Arr(pt.GetProperty("v"));
            var c = new double[3]; c[ax] = pl; c[o_[0].GetInt32()] = (u[0] + u[1]) / 2; c[o_[1].GetInt32()] = (v[0] + v[1]) / 2;
            // its thin box's local y along the side's normal: a turn of 90 for a side across x, none across y, a tilt for a floor's
            var pp = Add(new Plan("AGHall2InteriorCell", V(0x000020), c[0], c[1], c[2], ax == 0 ? 90 : 0, 1, false) { Name = $"AGHall2Portal{pi_++}" });
            if (ax == 2) pp.RX = 90;
            portalPlans.Add((pp, pt));
        }
        Lights("AGHall2InteriorCell", d.RootElement.GetProperty("lights"));
        Add(new Plan("AGHall2InteriorCell", doorOut.FormKey, dpos[0], dpos[1], dpos[2], dp.GetProperty("yaw").GetDouble(), dp.GetProperty("scale").GetDouble(), false) { FixedKey = outRefKey });
        var landPlan = Add(new Plan("AGHall2InteriorCell", inMarker.Base.FormKey, dpos[0] - 90, dpos[1], dpos[2], 270, 1, false) { Name = "AGHall2InMarker", Persistent = true, FixedKey = landKey });
        Pieces("AGHall2InteriorCell", pieces, "sdoubledoorint01");
        // named, persistent markers for the NPC plugin (COORDINATION.md: the clerks' spots, the barkeep's lean marker)
        if (d.RootElement.TryGetProperty("markers", out var mk_))
            foreach (var m in mk_.EnumerateArray())
            {
                var e = m[1].GetString()!; var mp = Arr(m[2]);
                if (!byEd.TryGetValue(e, out var mb)) throw new Exception("interior: no record named " + e);
                Add(new Plan("AGHall2InteriorCell", mb, mp[0], mp[1], mp[2], m[3].GetDouble(), 1, false) { Name = m[0].GetString(), Persistent = true, J = m.GetArrayLength() > 4 ? m[4] : null });   // (a fifth item: its settings, "disabled")
            }
        var lpath = Path.Combine(dir, "hall2_lookout.json");
        JsonDocument? ld = File.Exists(lpath) ? JsonDocument.Parse(File.ReadAllText(lpath)) : null;
        Static? look = null;
        if (ld is not null)
        {
            double[] llo = { 1e9, 1e9, 1e9 }, lhi = { -1e9, -1e9, -1e9 };
            foreach (var sh in ld.RootElement.GetProperty("shapes").EnumerateObject())
                foreach (var v in sh.Value.GetProperty("v").EnumerateArray())
                    for (int k = 0; k < 3; k++) { var c = v[k].GetDouble(); llo[k] = Math.Min(llo[k], c); lhi[k] = Math.Max(lhi[k], c); }
            look = new Static(Rec("AGHall2Lookout"), SkyrimRelease.SkyrimSE)
            {
                EditorID = "AGHall2Lookout", Model = new Model { File = @"AdventurersGuild\Hall2\AGHall2Lookout.nif" },
                ObjectBounds = new ObjectBounds { First = new P3Int16((short)Math.Floor(llo[0]), (short)Math.Floor(llo[1]), (short)Math.Floor(llo[2])),
                                                  Second = new P3Int16((short)Math.Ceiling(lhi[0]), (short)Math.Ceiling(lhi[1]), (short)Math.Ceiling(lhi[2])) },
            };
            mod.Statics.Add(look);
            if (Glazed("hall2_lookout.json")) paneBases.Add(look.FormKey);
            Add(new Plan("AGHall2LookoutCell", look.FormKey, 0, 0, 0, 0, 1, false));
            Lights("AGHall2LookoutCell", ld.RootElement.GetProperty("lights"));
            Pieces("AGHall2LookoutCell", ld.RootElement.GetProperty("pieces").EnumerateArray());
            if (ld.RootElement.TryGetProperty("markers", out var lmk_))   // (2026-10-28: the routines' Strongroom spot)
                foreach (var m in lmk_.EnumerateArray())
                {
                    var e = m[1].GetString()!; var mp = Arr(m[2]);
                    if (!byEd.TryGetValue(e, out var mb)) throw new Exception("interior: no record named " + e);
                    Add(new Plan("AGHall2LookoutCell", mb, mp[0], mp[1], mp[2], m[3].GetDouble(), 1, false) { Name = m[0].GetString(), Persistent = true });
                }
        }

        // (2026-10-28) the basement, a cell of its own (plans/BASEMENT.md; blender/basement_gen.py, exported as hall2_basement.json):
        // its shell, lights, pieces and markers, as the lookout's
        var bpath = Path.Combine(dir, "hall2_basement.json");
        JsonDocument? bd = File.Exists(bpath) ? JsonDocument.Parse(File.ReadAllText(bpath)) : null;
        Static? basement = null;
        if (bd is not null)
        {
            double[] blo = { 1e9, 1e9, 1e9 }, bhi = { -1e9, -1e9, -1e9 };
            foreach (var sh in bd.RootElement.GetProperty("shapes").EnumerateObject())
                foreach (var v in sh.Value.GetProperty("v").EnumerateArray())
                    for (int k = 0; k < 3; k++) { var c = v[k].GetDouble(); blo[k] = Math.Min(blo[k], c); bhi[k] = Math.Max(bhi[k], c); }
            basement = new Static(Rec("AGHall2Basement"), SkyrimRelease.SkyrimSE)
            {
                EditorID = "AGHall2Basement", Model = new Model { File = @"AdventurersGuild\Hall2\AGHall2Basement.nif" },
                ObjectBounds = new ObjectBounds { First = new P3Int16((short)Math.Floor(blo[0]), (short)Math.Floor(blo[1]), (short)Math.Floor(blo[2])),
                                                  Second = new P3Int16((short)Math.Ceiling(bhi[0]), (short)Math.Ceiling(bhi[1]), (short)Math.Ceiling(bhi[2])) },
            };
            mod.Statics.Add(basement);
            // (a single note in the secret room, reading "This room is TBD") a note of the
            // hall's own, vanilla's note (dunIrkngthandNote01's form and model) with its text; no script, no quest keywords
            var secretNoteSrc_ = mods.SelectMany(m => m.Books).Last(b => b.EditorID == "dunIrkngthandNote01");
            var secretNote_ = secretNoteSrc_.Duplicate(Rec("AGHall2SecretRoomNote"));
            secretNote_.EditorID = "AGHall2SecretRoomNote"; secretNote_.Name = "Note"; secretNote_.BookText = "This room is TBD";
            secretNote_.VirtualMachineAdapter = null; secretNote_.Keywords = null;
            mod.Books.Add(secretNote_); byEd["AGHall2SecretRoomNote"] = secretNote_.FormKey;
            // (the player sits in the water, as other mods' baths allow) the pool ledge's seat:
            // vanilla's InvisibleChairPlayerTriple has no collision, so the crosshair can never find it; its form with our
            // mesh (blender/pool_seat_nif.py: its markers and a collision slab on the seat line) and a name, as a player can
            // only activate what is named
            var poolSeat_ = mods.SelectMany(m => m.Furniture).Last(f => f.EditorID == "InvisibleChairPlayerTriple").Duplicate(Rec("AGHall2PoolSeat"));
            poolSeat_.EditorID = "AGHall2PoolSeat"; poolSeat_.Name = "Bath Ledge";
            poolSeat_.Model = new Model { File = @"AdventurersGuild\Hall2\AGHall2PoolSeat.nif" };
            poolSeat_.ObjectBounds = new ObjectBounds { First = new P3Int16(-75, -16, 33), Second = new P3Int16(75, 16, 38) };   // (its slab, on
            // the seat's line; its origin is 33.8 under it, inside the ledge, as vanilla's chair's)
            mod.Furniture.Add(poolSeat_); byEd["AGHall2PoolSeat"] = poolSeat_.FormKey;
            // (the upstairs display case is locked, and the GM has a key) its key, a copy of vanilla's plain
            // house key; the Guildmaster carries it (the NPC session adds it to the GM's inventory by this editor ID). It
            // opens the strongroom's ladder too, as "Guild Hall Key" (one key
            // to several locks as vanilla's: MarkarthTreasuryHouseKey opens three); the assistant carries one as well
            var caseKey_ = mods.SelectMany(m => m.Keys).Last(k => k.EditorID == "RiftenSnowShodHouseKey").Duplicate(Rec("AGHall2DisplayCaseKey"));
            caseKey_.EditorID = "AGHall2DisplayCaseKey"; caseKey_.Name = "Guild Hall Key"; caseKey_.VirtualMachineAdapter = null;
            mod.Keys.Add(caseKey_); byEd["AGHall2DisplayCaseKey"] = caseKey_.FormKey;
            // (the counter's back office door had a key of its own, AGHall2BackOfficeKey, until the door was
            // unlocked and its key removed: a follower walked through it locked)
            Add(new Plan("AGHall2BasementCell", basement.FormKey, 0, 0, 0, 0, 1, false));
            Lights("AGHall2BasementCell", bd.RootElement.GetProperty("lights"));
            Pieces("AGHall2BasementCell", bd.RootElement.GetProperty("pieces").EnumerateArray());
            if (bd.RootElement.TryGetProperty("markers", out var bmk_))
                foreach (var m in bmk_.EnumerateArray())
                {
                    var e = m[1].GetString()!; var mp = Arr(m[2]);
                    if (!byEd.TryGetValue(e, out var mb)) throw new Exception("interior: no record named " + e);
                    Add(new Plan("AGHall2BasementCell", mb, mp[0], mp[1], mp[2], m[3].GetDouble(), 1, false) { Name = m[0].GetString(), Persistent = true });
                }
        }

        // the match, cell by cell: every (plan, ledger ref) pair of the same kind, nearest first, a shared name before all
        foreach (var (cellEd, prevs) in prevByCell)
        {
            var cand = new List<(double cost, Plan p, PrevRef r)>();
            foreach (var p in plans.Where(p => p.Cell == cellEd))
                foreach (var r in prevs)
                {
                    bool same = p.IsLight ? lightBases.Contains(r.Base) : r.Base == p.Base || (OwnCopyOf.TryGetValue(r.Base, out var nb_) && nb_ == p.Base);
                    if (!same) continue;
                    if (p.J is { } jf && jf.TryGetProperty("fresh", out _) && r.Ed != p.Name) continue;   // fresh: only its own name
                    if (p.Name is not null && r.Ed is not null && r.Ed != p.Name) continue;   // (a name is an identity: 2026-10-28, the
                                                                             // day/night markers took the retired board rotator's ref)
                    double cost = Math.Sqrt(Math.Pow(r.Pos.X - p.X, 2) + Math.Pow(r.Pos.Y - p.Y, 2) + Math.Pow(r.Pos.Z - p.Z, 2));
                    if (p.Name is not null && r.Ed == p.Name) cost = -1;                   // its own name
                    else if ((p.Name is null) != (r.Ed is null)) cost += 1e7;              // a named ref only for a named piece
                    cand.Add((cost, p, r));
                }
            var taken = new HashSet<FormKey>();
            foreach (var (cost, p, r) in cand.OrderBy(c => c.cost))
            {
                if (p.Prev is not null || taken.Contains(r.Key)) continue;
                p.Prev = r; taken.Add(r.Key);
            }
        }

        var cells = new Dictionary<string, Cell> { ["AGHall2InteriorCell"] = cell };
        Cell? lcell = null;
        if (look is not null)
        {
            lcell = NewCell(Rec("AGHall2LookoutCell"), "AGHall2LookoutCell", "Guild Strongroom");   // (the fit-out: not a lookout, a
            lcell.Owner.SetTo(gmFaction.FormKey);                                               // strongroom; the guild master's,
            lcell.Flags |= Cell.Flag.PublicArea;                                                // as the Harbinger's rooms are)
            // (hall2bf: the strongroom's lights were too bright) a back room keeps its template's ambient,
            // as vanilla's do (lightsurvey: Markarth's Treasury House and Dragonsreach's basement inherit theirs; SolitudeInteriors'
            // is 44,33,27), not the great hall's Jorrvaskr-bright one: everything from the template
            lcell.Lighting!.Inherits = (CellLighting.Inherit)0x7FF;
            cells["AGHall2LookoutCell"] = lcell;
        }
        Cell? bcell = null;
        if (basement is not null)
        {
            // the basement: the guild's and open to all, as the hall; its light from its template (a back room's, as the
            // Strongroom's: lit by room, the rooms' own lamps and braziers). Its water as vanilla's interior pools': the
            // cell flagged for water with no height of its own (-2147483648, as PurewaterRun01's, ClearspringTarn01's), the pool's
            // water a placed plane (basement_gen.py); hall2bi's cell water at the pool's height showed nothing
            bcell = NewCell(Rec("AGHall2BasementCell"), "AGHall2BasementCell", "Adventurers Guild Hall Basement");
            bcell.Owner.SetTo(guild.FormKey);
            bcell.Flags |= Cell.Flag.PublicArea | Cell.Flag.HasWater;
            bcell.WaterHeight = -2147483648f;
            bcell.Lighting!.Inherits = (CellLighting.Inherit)0x7FF;
            cells["AGHall2BasementCell"] = bcell;
        }
        // a piece tilted about its own x (rx) and turned (yaw), as the renders draw it: Rz(-yaw) Rx(-rx), the tilt first. The game
        // builds a reference's rotation as Rx(-X) Ry(-Y) Rz(-Z) (Gamebryo's Euler XYZ: the turn first, the tilt after it about
        // the world's x; the office map at X 270 and Z -90 stood on its side, out of its wall), so
        // the wanted matrix is taken apart in that order
        static P3Float GameAngles(double rxDeg, double yawDeg)
        {
            if (Math.Abs(rxDeg) < 1e-9) return new P3Float(0, 0, (float)(yawDeg * Math.PI / 180));
            double a = -rxDeg * Math.PI / 180, c = -yawDeg * Math.PI / 180;
            double sa = Math.Sin(a), ca = Math.Cos(a), sc = Math.Sin(c), cc = Math.Cos(c);
            // D = Rz(c) Rx(a) = [[cc, -sc ca, sc sa], [sc, cc ca, -cc sa], [0, sa, ca]]; game: Rx(A) Ry(B) Rz(C) with A=-X ...
            double d02 = sc * sa, d12 = -cc * sa, d22 = ca, d01 = -sc * ca, d00 = cc, d10 = sc, d11 = cc * ca;
            double B = Math.Asin(Math.Clamp(d02, -1, 1)), A, C;
            if (Math.Abs(Math.Cos(B)) > 1e-6) { A = Math.Atan2(-d12, d22); C = Math.Atan2(-d01, d00); }
            else { C = 0; A = B > 0 ? Math.Atan2(d10, d11) : Math.Atan2(-d10, d11); }   // (gimbal at B = +-90: only A +- C is fixed)
            return new P3Float((float)-A, (float)-B, (float)-C);
        }
        PlacedObject Ref(Cell into, FormKey key, FormKey b, double x, double y, double z, double yawDeg, double scale, bool persistent, double rxDeg = 0)
        {
            var r = new PlacedObject(key, SkyrimRelease.SkyrimSE)
            {
                Placement = new Placement { Position = new P3Float((float)x, (float)y, (float)z), Rotation = GameAngles(rxDeg, yawDeg) },
            };
            r.Base.SetTo(b);
            if (Math.Abs(scale - 1) > 1e-6) r.Scale = (float)scale;
            if (persistent) { r.MajorRecordFlagsRaw |= 0x400; into.Persistent.Add(r); } else into.Temporary.Add(r);
            return r;
        }
        if (levelsUsed_.Count != levels_.Count) throw new Exception($"light_levels.json: {levels_.Count - levelsUsed_.Count} of {levels_.Count} entries met no light: " + string.Join(" ", levels_.Where((e_, i_) => !levelsUsed_.Contains(i_)).Select(e_ => e_.GetProperty("id").GetString())));
        int kept = 0, fresh = 0;
        foreach (var p in plans)
        {
            var key = p.Prev?.Key ?? p.FixedKey ?? Fresh();
            if (p.Prev is null) fresh++; else kept++;
            p.Ref = Ref(cells[p.Cell], key, p.Base, p.X, p.Y, p.Z, p.Yaw, p.Scale, p.Persistent || (p.Prev?.Persistent ?? false), p.RX);
            if (p.GA is { } ga2_) p.Ref.Placement!.Rotation = ga2_;
            if (p.LightRadius is { } lr_) p.Ref.Radius = lr_;
            if (p.LightFade is { } lf_) p.Ref.LightData = new LightData { FadeOffset = lf_ };
            if (p.Name is not null) p.Ref.EditorID = p.Name;
            else if (p.Prev?.Ed is not null) p.Ref.EditorID = p.Prev.Ed;
        }
        // the room bounds' data, as vanilla's (Dragonsreach's raw records): a room's primitive a box of its full size (Mutagen
        // writes half, as the game stores it), coloured 0,0.5,1 at 0.2, its half sizes again as a multibound (XMBO) and the
        // room's other boxes linked (XLRM: drawn together, no portal between); a portal's a thin box 2 deep, black at 0.25, its
        // two rooms (XPOD) the boxes either side of it
        foreach (var ((rm, bi), p) in roomPlans)
        {
            var b_ = roomBoxes[(rm, bi)];
            var size = new P3Float((float)(b_[1] - b_[0]), (float)(b_[3] - b_[2]), (float)(b_[5] - b_[4]));
            p.Ref!.Primitive = new PlacedPrimitive { Type = PlacedPrimitive.TypeEnum.Box, Bounds = size, Color = System.Drawing.Color.FromArgb(0, 128, 255), Unknown = 0.2f };
            p.Ref.BoundHalfExtents = new P3Float(size.X / 2, size.Y / 2, size.Z / 2);
            var linked = roomPlans.Where(kv => kv.Key.room == rm && kv.Key.box != bi).Select(kv => kv.Value.Ref!.FormKey).ToList();
            foreach (var k_ in linked) p.Ref.LinkedRooms.Add(k_.ToLink<IPlacedObjectGetter>());
        }
        foreach (var (p, pt) in portalPlans)
        {
            var u = Arr(pt.GetProperty("u")); var v = Arr(pt.GetProperty("v")); var bxs = pt.GetProperty("boxes");
            var a_ = roomPlans[(bxs[0][0].GetString()!, bxs[0][1].GetInt32())].Ref!; var b2_ = roomPlans[(bxs[1][0].GetString()!, bxs[1][1].GetInt32())].Ref!;
            p.Ref!.Primitive = new PlacedPrimitive { Type = PlacedPrimitive.TypeEnum.PortalBox, Bounds = new P3Float((float)(u[1] - u[0]), 2, (float)(v[1] - v[0])),
                                                     Color = System.Drawing.Color.FromArgb(0, 0, 0), Unknown = 0.25f };
            p.Ref.Portals = new ExtendedList<Portal> { new Portal { Origin = a_.FormKey.ToLink<IPlacedObjectGetter>(), Destination = b2_.FormKey.ToLink<IPlacedObjectGetter>() } };
        }
        Console.WriteLine($"interior: {roomPlans.Count} room bounds, {portalPlans.Count} portals");
        // what the ledger had that nothing replaced: kept, where it was, initially disabled (a save's changes to it still
        // land on the same kind of thing)
        int retired = 0, dropped = 0;
        // (2026-10-27: hall2au-hall2ax crashed the game on loading the cell, the board session's find: the board's three old refs
        // were kept on the STATs that became ACTIs under new IDs, and those STATs were no longer written; a disabled ref whose
        // base is missing still crashes the engine. A retired ref whose base was this plugin's and is gone is dropped)
        var emitted = new HashSet<FormKey>(mod.EnumerateMajorRecords().Select(m_ => m_.FormKey));
        foreach (var (cellEd, prevs) in renamed ? new Dictionary<string, List<PrevRef>>() : prevByCell)
            foreach (var r in prevs.Where(r => !plans.Any(p => p.Prev == r)))
            {
                if (!cells.TryGetValue(cellEd, out var into)) continue;
                if (r.Base.ModKey == mod.ModKey && !emitted.Contains(r.Base)) { dropped++; Console.WriteLine($"interior: retired ref {r.Key.ID:X6} dropped: its base {r.Base.ID:X6} is no longer written"); continue; }
                // (a room or portal marker no longer written goes: kept disabled without its box it is nothing anyone can see, and
                // what the engine makes of a disabled room bound is unknown; markers hold nothing a save needs)
                if (r.Base == V(0x00001F) || r.Base == V(0x000020)) { dropped++; continue; }
                if (r.Ed is "AGHall2DaylightMarker" or "AGHall2DayNightControl") { dropped++; continue; }   // (2026-11-02: the old switch, nothing a save needs)
                // (its name only if no live reference took it: 2026-10-27, the board's ref A retired as its base changed kind,
                // and two refs of one name broke the NPC merge's lookup by name)
                var ed_ = r.Ed is { } e0 && plans.Any(p => p.Name == e0) ? null : r.Ed;
                var o = new PlacedObject(r.Key, SkyrimRelease.SkyrimSE) { Placement = new Placement { Position = r.Pos, Rotation = r.Rot }, EditorID = ed_ };
                o.Base.SetTo(r.Base);
                if (Math.Abs(r.Scale - 1) > 1e-6) o.Scale = r.Scale;
                o.MajorRecordFlagsRaw |= 0x800;                                              // initially disabled
                if (r.Persistent) { o.MajorRecordFlagsRaw |= 0x400; into.Persistent.Add(o); } else into.Temporary.Add(o);
                retired++;
            }

        void File_(Cell c)
        {
            uint cid = c.FormKey.ID; int bn = (int)(cid % 10), sbn = (int)(cid / 10 % 10);
            var block = mod.Cells.Records.FirstOrDefault(b => b.BlockNumber == bn);
            if (block is null) { block = new CellBlock { BlockNumber = bn, GroupType = GroupTypeEnum.InteriorCellBlock }; mod.Cells.Records.Add(block); }
            var sub = block.SubBlocks.FirstOrDefault(s => s.BlockNumber == sbn);
            if (sub is null) { sub = new CellSubBlock { BlockNumber = sbn, GroupType = GroupTypeEnum.InteriorCellSubBlock }; block.SubBlocks.Add(sub); }
            sub.Cells.Add(c);
        }
        // the cells' navmeshes: blender/navgen.py's, from the export's collision
        // (nav_interior.json, nav_lookout.json beside it), written as vanilla writes its interiors' (measured, `navdump`):
        // version 12, the format's constant CRC, every triangle "Found", a door triangle (and its "Door" flag) under each
        // load door's landing, no cover, no edge links (one navmesh a cell), the search grid as counts and triangle indices;
        // and an entry in the NAVI map (Skyrim.esm's 012FB4, which the game merges across plugins: Update.esm's override
        // holds 31 entries, HearthFires' 132) naming the cell, a point on the mesh and the load doors
        var navInfos = new List<NavigationMapInfo>();
        var placedAll = cell.Persistent.Concat(cell.Temporary).Concat(lcell is null ? Enumerable.Empty<IPlaced>() : lcell.Persistent.Concat(lcell.Temporary))
            .Concat(bcell is null ? Enumerable.Empty<IPlaced>() : bcell.Persistent.Concat(bcell.Temporary))
            .OfType<PlacedObject>().ToList();
        void AddNav(Cell c_, string json_)
        {
            if (!File.Exists(json_)) { Console.WriteLine($"navmesh: none for {c_.EditorID} ({Path.GetFileName(json_)} not exported)"); return; }
            using var nd_ = JsonDocument.Parse(File.ReadAllText(json_)); var nr_ = nd_.RootElement;
            var nk_ = prevNav.TryGetValue(c_.EditorID!, out var pk_) ? pk_ : Fresh();
            var data_ = new NavigationMeshData { NavmeshVersion = 12, CrcHash = 2783551548, Parent = new CellNavmeshParent { Parent = c_.ToLink<ICellGetter>() } };
            foreach (var v_ in nr_.GetProperty("verts").EnumerateArray())
                data_.Vertices.Add(new P3Float(v_[0].GetSingle(), v_[1].GetSingle(), v_[2].GetSingle()));
            var doorTri_ = new Dictionary<int, FormKey>();
            foreach (var d_ in nr_.GetProperty("doors").EnumerateArray())
            {
                if (d_.GetProperty("tri").ValueKind != JsonValueKind.Number) { Console.WriteLine($"navmesh: {d_.GetProperty("name").GetString()} has no triangle under its landing"); continue; }
                var nm_ = d_.GetProperty("name").GetString();
                var ref_ = placedAll.FirstOrDefault(r => r.EditorID == nm_);
                if (ref_ is null) { Console.WriteLine($"navmesh: no reference named {nm_} for a door triangle"); continue; }
                doorTri_[d_.GetProperty("tri").GetInt32()] = ref_.FormKey;
            }
            int ti_ = 0;
            foreach (var t_ in nr_.GetProperty("tris").EnumerateArray())
            {
                var vv_ = t_.GetProperty("v"); var ll_ = t_.GetProperty("links");
                data_.Triangles.Add(new NavmeshTriangle
                {
                    Vertices = new P3Int16((short)vv_[0].GetInt32(), (short)vv_[1].GetInt32(), (short)vv_[2].GetInt32()),
                    EdgeLink_0_1 = (short)ll_[0].GetInt32(), EdgeLink_1_2 = (short)ll_[1].GetInt32(), EdgeLink_2_0 = (short)ll_[2].GetInt32(),
                    Flags = NavmeshTriangle.Flag.Found | (doorTri_.ContainsKey(ti_) ? NavmeshTriangle.Flag.Door : 0), CoverFlags = 0,
                });
                ti_++;
            }
            foreach (var (tri_, door_) in doorTri_)
                data_.DoorTriangles.Add(new DoorTriangle { TriangleBeforeDoor = (short)tri_, Unknown = -460622861, Door = new FormLink<IPlacedObjectGetter>(door_) });
            var g_ = nr_.GetProperty("grid"); int div_ = g_.GetProperty("div").GetInt32();
            data_.NavmeshGridDivisor = (uint)div_; data_.MaxDistanceX = g_.GetProperty("maxdx").GetSingle(); data_.MaxDistanceY = g_.GetProperty("maxdy").GetSingle();
            var mn_ = g_.GetProperty("min"); var mx_ = g_.GetProperty("max");
            data_.Min = new P3Float(mn_[0].GetSingle(), mn_[1].GetSingle(), mn_[2].GetSingle()); data_.Max = new P3Float(mx_[0].GetSingle(), mx_[1].GetSingle(), mx_[2].GetSingle());
            var gb_ = new List<byte>();
            foreach (var cell_ in g_.GetProperty("cells").EnumerateArray())
            {
                var ids_ = cell_.EnumerateArray().Select(x => (ushort)x.GetInt32()).ToList();
                // (2026-10-28, hall2be's CTD at the main menu: each cell's count is a uint32, as all 3000 of Skyrim.esm's first
                // navmeshes parse; it was a uint16 since hall2ba, so the game read each count with the next index as one
                // huge number and read on past the record: hall2ba-bd loaded by luck, hall2be's smaller record crashed)
                gb_.AddRange(BitConverter.GetBytes((uint)ids_.Count));
                foreach (var id_ in ids_) gb_.AddRange(BitConverter.GetBytes(id_));
            }
            data_.NavmeshGrid = new MemorySlice<byte>(gb_.ToArray());
            var nav_ = new NavigationMesh(nk_, SkyrimRelease.SkyrimSE) { Data = data_ };
            c_.NavigationMeshes.Add(nav_);
            var pt_ = nr_.GetProperty("point");
            var info_ = new NavigationMapInfo
            {
                NavigationMesh = nav_.ToLink<INavigationMeshGetter>(), Unknown = 0, Point = new P3Float(pt_[0].GetSingle(), pt_[1].GetSingle(), pt_[2].GetSingle()),
                PreferredMergesFlag = 0, Unknown2 = unchecked((int)2783551548u),
                Parent = new NavigationMapInfoCellParent { Unused = 0, ParentCell = c_.ToLink<ICellGetter>() },
            };
            foreach (var door_ in doorTri_.Values.Distinct()) info_.LinkedDoors.Add(new LinkedDoor { Unknown = -460622861, Door = new FormLink<IPlacedObjectGetter>(door_) });
            // (2026-10-30, the NPC session: none of ours had it, nearly all of vanilla's load doors do) each load door names its own cell's navmesh and
            // the triangle before it (XNDP: 1212 of vanilla's 1218 are a door triangle of the navmesh they name, 1215 their own cell's)
            foreach (var (tri_, door_) in doorTri_)
                placedAll.First(r => r.FormKey == door_).NavigationDoorLink = new NavigationDoorLink { NavMesh = nav_.ToLink<INavigationMeshGetter>(), TeleportMarkerTriangle = (short)tri_ };
            navInfos.Add(info_);
            Console.WriteLine($"navmesh: {c_.EditorID} {nk_}: {data_.Vertices.Count} vertices, {data_.Triangles.Count} triangles, {data_.DoorTriangles.Count} door triangles ({string.Join(", ", doorTri_.Values.Select(k => placedAll.First(r => r.FormKey == k).EditorID))}), grid {div_} x {div_}");
        }
        AddNav(cell, Path.Combine(dir, "nav_interior.json"));
        if (lcell is not null) AddNav(lcell, Path.Combine(dir, "nav_lookout.json"));
        if (bcell is not null) AddNav(bcell, Path.Combine(dir, "nav_basement.json"));
        if (navInfos.Count > 0)
        {
            var navi_ = new NavigationMeshInfoMap(new FormKey(ModKey.FromFileName("Skyrim.esm"), 0x012FB4), SkyrimRelease.SkyrimSE) { NavMeshVersion = 12, PreferredPathing = new PreferredPathing() };
            navi_.MapInfos.AddRange(navInfos);
            mod.NavigationMeshInfoMaps.Add(navi_);
        }
        // (how an interior is properly lit, from the Bannered Mare under ELE:
        // ELE adds no light there: the same 18 as vanilla, a dark fill and a calm image space, and the fires and windows do the work. The hall's fill was three times
        // that, its directional light up, its image space at brightness 1.20 with strong slow eye adaptation. ELE and Lux edit cells by name, so neither reaches
        // this one: its own records, to those measured values, every cell inheriting all of it. KNOWLEDGEBASE.local.md, "What makes an interior look lit")
        System.Drawing.Color Rgb(int r_, int g_, int b_) => System.Drawing.Color.FromArgb(0, r_, g_, b_);
        var hallLt_ = mods.SelectMany(m => m.LightingTemplates).Last(t => t.EditorID == "SolitudeInteriors").Duplicate(Rec("AGHall2LightingTemplate"));
        hallLt_.EditorID = "AGHall2LightingTemplate";
        hallLt_.AmbientColor = Rgb(51, 51, 51);   /* (the fixed fill, as dim at midday as at midnight: down to ELE's 1ELE_Bright_LT, the level Community Shaders' SSGI was already tuned at (AG::GuildHall::TuneLighting), so the windows' daylight carries the day. Was 92, x/y 41, z+ 85, z- 92) */ hallLt_.DirectionalColor = Rgb(10, 12, 15); hallLt_.DirectionalRotationXY = 0; hallLt_.DirectionalRotationZ = 90; hallLt_.DirectionalFade = 1;
        hallLt_.FogNearColor = Rgb(88, 83, 71); hallLt_.FogFarColor = Rgb(88, 83, 71); hallLt_.FogNear = 0; hallLt_.FogFar = 8000; hallLt_.FogClipDistance = 8000; hallLt_.FogPower = 1; hallLt_.FogMax = 1;
        hallLt_.LightFadeStartDistance = 8999; hallLt_.LightFadeEndDistance = 9000;
        hallLt_.DirectionalAmbientColors = new AmbientColors { DirectionalXPlus = Rgb(23, 21, 19), DirectionalXMinus = Rgb(23, 21, 19), DirectionalYPlus = Rgb(23, 21, 19), DirectionalYMinus = Rgb(23, 21, 19),
            DirectionalZPlus = Rgb(47, 46, 45), DirectionalZMinus = Rgb(51, 51, 51), Specular = Rgb(0, 0, 0), Scale = 1 };
        mod.LightingTemplates.Add(hallLt_);
        var hallIs_ = mods.SelectMany(m => m.ImageSpaces).Last(i => i.EditorID == "WhiteRunIntIS").Duplicate(Rec("AGHall2InteriorIS"));
        hallIs_.EditorID = "AGHall2InteriorIS";
        hallIs_.Hdr = new ImageSpaceHdr { EyeAdaptSpeed = 100, EyeAdaptStrength = 0.7f, BloomBlurRadius = 7, BloomThreshold = 0.35f, BloomScale = 0.5f, ReceiveBloomThreshold = 100, White = 1, SunlightScale = 1, SkyScale = 0 };
        hallIs_.Cinematic = new ImageSpaceCinematic { Saturation = 1, Brightness = 1, Contrast = 1 };
        hallIs_.Tint = new ImageSpaceTint { Amount = 0, Color = Rgb(0, 0, 0) };
        mod.ImageSpaces.Add(hallIs_);
        foreach (var c_ in new[] { cell, lcell, bcell })
        {
            if (c_ is null) continue;
            c_.LightingTemplate.SetTo(hallLt_.FormKey); c_.ImageSpace.SetTo(hallIs_.FormKey); c_.Lighting!.Inherits = (CellLighting.Inherit)0x7FF;
        }
        File_(cell);
        if (lcell is not null) File_(lcell);
        if (bcell is not null) File_(bcell);

        // load doors: each sends one to where its pair's "arrive" says; linked refs by name (a rack to its activator, the
        // activator to its rack and its starting item); owners; scripts a reference carries itself (vanilla's racks do)
        TeleportDestination To(Plan other)
        {
            var a = Arr(other.J!.Value.GetProperty("arrive"));
            var t = new TeleportDestination { Position = new P3Float((float)a[0], (float)a[1], (float)a[2]),
                                              Rotation = new P3Float(0, 0, (float)(other.J.Value.GetProperty("arrive_yaw").GetDouble() * Math.PI / 180)) };
            t.Door.SetTo(other.Ref!.FormKey); return t;
        }
        var byRole = plans.Where(p => p.Role is not null).ToDictionary(p => p.Role!);
        int doors = 0;
        foreach (var p in plans.Where(p => p.Pair is not null))
        {
            if (!byRole.TryGetValue(p.Pair!, out var other)) throw new Exception($"interior: {p.Role} pairs with {p.Pair}, not placed");
            p.Ref!.TeleportDestination = To(other); doors++;
        }
        var byName = plans.Where(p => p.Name is not null).GroupBy(p => p.Name!).ToDictionary(g => g.Key, g => g.First());
        int links = 0;
        foreach (var p in plans.Where(p => p.J is { } j && j.TryGetProperty("links", out _)))
        {
            foreach (var l in p.J!.Value.GetProperty("links").EnumerateObject())
            {
                if (!byName.TryGetValue(l.Value.GetString()!, out var t)) throw new Exception($"interior: {p.Name} links to {l.Value.GetString()}, not placed");
                var lr = new LinkedReferences();
                if (l.Name.Length > 0) lr.KeywordOrReference.SetTo(keywords[l.Name]);
                lr.Reference.SetTo(t.Ref!.FormKey);
                p.Ref!.LinkedReferences.Add(lr); links++;
            }
        }
        foreach (var p in plans.Where(p => p.Cell is "AGHall2InteriorCell" or "AGHall2BasementCell" && p.J is { } j && j.TryGetProperty("group", out _)))   // (2026-11-06: the basement for Henriette's room)
        {
            var g_ = p.J!.Value.GetProperty("group").GetString()!;
            if (!OwnerGroups.TryGetValue(g_, out var l_)) OwnerGroups[g_] = l_ = new();
            l_.Add(p.Ref!.FormKey.ID);
        }
        // (2026-11-03, room 5 as the player's home) "playerbed": vanilla's PlayerBedOwnership, which owns every player home's bed and which a spouse joins on marrying
        var playerBed_ = mods.SelectMany(m => m.Factions).Last(f => f.EditorID == "PlayerBedOwnership").FormKey;
        foreach (var p in plans.Where(p => p.J is { } j && j.TryGetProperty("owner", out _)))   // "guild" or "gm" (the guild master's)
        {
            var o_ = p.J!.Value.GetProperty("owner").GetString();
            p.Ref!.Owner.SetTo(o_ == "gm" ? gmFaction.FormKey : o_ == "playerbed" ? playerBed_ : guild.FormKey);
        }
        // (2026-11-03) an enable parent, as vanilla's homes swap their furniture ("parent": the named marker; "opposite": shown while the marker is disabled):
        // (room 5's two beds used it until 2026-11-04, when the room got one bed whose owner changes instead; kept for the next swap)
        foreach (var p in plans.Where(p => p.J is { } j && j.TryGetProperty("parent", out _)))
        {
            var pn_ = p.J!.Value.GetProperty("parent").GetString();
            var par_ = plans.FirstOrDefault(q => q.Name == pn_)?.Ref ?? throw new Exception("enable parent not placed: " + pn_);
            var ep_ = new EnableParent(); ep_.Reference.SetTo(par_.FormKey);
            if (p.J.Value.TryGetProperty("opposite", out var op_) && op_.GetBoolean()) ep_.Flags = EnableParent.Flag.SetEnableStateToOppositeOfParent;
            p.Ref!.EnableParent = ep_;
        }
        // (2026-10-28) a locked door: "key" is the basement's secret room (big, obvious and locked: the secret is what lies
        // behind that door): it needs its key, which no one has until the quest that gives it
        // (the upstairs display case, locked at Expert as Jorrvaskr's cases; the GM has its key) any level
        // by name, and "lock_key" names the key record that opens it
        foreach (var p in plans.Where(p => p.J is { } j && j.TryGetProperty("lock", out _)))
        {
            var lv_ = p.J!.Value.GetProperty("lock").GetString();
            p.Ref!.Lock = new LockData { Level = lv_ == "key" ? LockLevel.RequiresKey : Enum.Parse<LockLevel>(lv_ ?? "Apprentice") };
            if (p.J.Value.TryGetProperty("lock_key", out var k_)) p.Ref.Lock.Key.SetTo(byEd[k_.GetString()!]);
        }
        // items hung for show (the rack's shield): vanilla's "Don't Havok Settle" (0x20000000) keeps them where they are placed
        // until someone takes them, as vanilla's wall displays do
        foreach (var p in plans.Where(p => p.J is { } j && j.TryGetProperty("settled", out _))) p.Ref!.MajorRecordFlagsRaw |= 0x20000000;
        foreach (var p in plans.Where(p => p.J is { } j && j.TryGetProperty("disabled", out _))) p.Ref!.MajorRecordFlagsRaw |= 0x800;   // initially disabled
        // day and night (the daylight plan, measured in a throwaway build: panes and walls follow the region through Wait inside the cell, and the region multiplies a
        // light's colour): as vanilla's and Lux's halls, no script: the panes, the window fills and the bounce lights on vanilla's FXLightRegionSunlightWhite, the candles by the windows on its inverse
        foreach (var p in plans.Where(p => p.Ref is not null && (p.Kind is "window" or "bounce" || paneBases.Contains(p.Base)))) p.Ref!.Emittance.SetTo(V(0x075492));
        foreach (var p in plans.Where(p => p.Kind == "candle_night" && p.Ref is not null)) p.Ref!.Emittance.SetTo(V(0x06ED59));
        // (with the fixed fill) the windows' glow cards (interior_gen's "region"), as Erikur's House's FXGlowFillRoundBrt: on the region with the fills
        foreach (var p in plans.Where(p => p.Ref is not null && p.J is { } j && j.TryGetProperty("region", out _))) p.Ref!.Emittance.SetTo(V(0x075492));
        Console.WriteLine($"interior: daylight: {plans.Count(p => p.Kind == "window")} fills, {plans.Count(p => p.Kind == "bounce")} bounce, {plans.Count(p => paneBases.Contains(p.Base))} meshes with panes on the region, {plans.Count(p => p.Kind == "candle_night")} candles on its inverse, {plans.Count(p => p.J is { } j && j.TryGetProperty("region", out _))} glow cards on the region");
        // the back office door closes behind the hall's folk: the game never closes a door itself (AGHallBackOfficeDoor); a door the player
        // opened stays open. (The bedroom doors close only when their sleeper goes to bed, npcgen's
        // AGHallBedroomDoor with each door's sleeper; the guild master's suite door and the attic's are left as they are left)
        foreach (var dn_ in new[] { "AGHall2BackroomDoor" })
        {
            var d_ = plans.FirstOrDefault(p => p.Name == dn_);
            if (d_?.Ref is null) throw new InvalidOperationException($"door closer: no door named {dn_} in the interior");
            d_.Ref.VirtualMachineAdapter = new VirtualMachineAdapter { Scripts = { new ScriptEntry { Name = "AGHallBackOfficeDoor" } } };
        }
        // the guild's cloth banner (a moveable static, as vanilla's city banners) locked where it hangs: a bump knocked it off its
        // bracket into the kitchen (2026-11-07); AGHallBannerLock keyframes it as it loads, its sway its own animation
        foreach (var p in plans.Where(p => p.Ref is not null && byEd.TryGetValue("AGHall2BannerCloth", out var bc_) && p.Ref.Base.FormKey == bc_))
            p.Ref!.VirtualMachineAdapter = new VirtualMachineAdapter { Scripts = { new ScriptEntry { Name = "AGHallBannerLock" } } };
        // the guild board's rotation: its marker carries AGHallBoardRotate, pointed at the three boards
        if (plans.FirstOrDefault(p => p.Name == "AGHall2BoardRotator") is { } rot_)
        {
            var se_ = new ScriptEntry { Name = "AGHallBoardRotate" };
            foreach (var (prop_, nm_) in new[] { ("BoardA", "AGHall2GuildBoardRefA"), ("BoardB", "AGHall2GuildBoardRefB"), ("BoardC", "AGHall2GuildBoardRefC") })
            {
                var tgt_ = plans.First(p => p.Name == nm_).Ref!;
                se_.Properties.Add(new ScriptObjectProperty { Name = prop_, Object = tgt_.FormKey.ToLink<ISkyrimMajorRecordGetter>(), Flags = ScriptProperty.Flag.Edited });
            }
            rot_.Ref!.VirtualMachineAdapter = new VirtualMachineAdapter { Scripts = { se_ } };
        }
        // a reference's own script with vanilla's own property values: copied whole from a vanilla reference of the same base
        // that carries it (the rack could not be activated: the bare script had no properties, so
        // WeaponRackActivateSCRIPT's RackType was 0 and its OnActivate did nothing)
        var scripted = plans.Where(p => p.J is { } j && j.TryGetProperty("ref_script", out _)).ToList();
        var wantBases = scripted.Select(p => p.Base).ToHashSet();
        var vmadOf = new Dictionary<FormKey, IVirtualMachineAdapterGetter>();
        if (wantBases.Count > 0)
            foreach (var m in mods)
                foreach (var r in m.EnumerateMajorRecords<IPlacedObjectGetter>())
                    if (wantBases.Contains(r.Base.FormKey) && r.VirtualMachineAdapter is { } v && v.Scripts.Count > 0 && !vmadOf.ContainsKey(r.Base.FormKey))
                        vmadOf[r.Base.FormKey] = v;
        foreach (var p in scripted)
        {
            var name = p.J!.Value.GetProperty("ref_script").GetString()!;
            if (vmadOf.TryGetValue(p.Base, out var v) && v.Scripts.Any(sc => sc.Name.Equals(name, StringComparison.OrdinalIgnoreCase)))
            {
                p.Ref!.VirtualMachineAdapter = v.DeepCopy();
                var bs_ = mods.SelectMany(m => m.Activators).LastOrDefault(a => a.FormKey == p.Base)?.VirtualMachineAdapter;
                Console.WriteLine($"interior: {p.Name ?? p.Base.ToString()} carries {name} with vanilla's ref properties [" +
                    string.Join(", ", v.Scripts.SelectMany(sc => sc.Properties).Select(pp => pp.Name + "=" + (pp is IScriptIntPropertyGetter ip ? ip.Data.ToString() : pp is IScriptBoolPropertyGetter bp ? bp.Data.ToString() : pp is IScriptObjectPropertyGetter op ? op.Object.FormKey.ToString() : "?"))) +
                    "]; its base's scripts: " + (bs_ is null ? "none" : string.Join("; ", bs_.Scripts.Select(sc => sc.Name + " (" + sc.Properties.Count + " props: " + string.Join(",", sc.Properties.Select(pp => pp.Name)) + ")"))));
            }
            else throw new Exception($"interior: no vanilla reference of {p.Base} carries {name}");
        }
        var land = landPlan.Ref!;
        Console.WriteLine($"interior: {plans.Count} refs ({kept} keep the ledger's IDs, {fresh} new), {retired} retired (disabled), {dropped} retired dropped (base gone), {doors} load doors, {links} links");
        Console.WriteLine($"interior: cell {cell.EditorID} {cellKey}, shell {shell.FormKey}, door in {doorIn.FormKey} out {doorOut.FormKey}, landing {land.FormKey} at {land.Placement!.Position}");
        if (land.FormKey != landKey) throw new Exception($"interior: the landing point moved off its ID ({land.FormKey}, was {landKey}): a save holds it");
        if (patioLand is not null && patioLand.Ref!.FormKey != patioLandKey) throw new Exception($"interior: the back door's landing point is {patioLand.Ref.FormKey}, its door says {patioLandKey}");
        if (patioDoor is not null) Console.WriteLine($"interior: back door out {patioDoor.FormKey}, landing {patioLandKey} at {patioLand!.Ref!.Placement!.Position}");
        ld?.Dispose();
        return (doorIn.FormKey, patioDoor?.FormKey);
    }

    // the fit-out's ledger (2026-10-26): a reference of the last build, and a reference this build places
    sealed record PrevRef(FormKey Key, FormKey Base, P3Float Pos, P3Float Rot, float Scale, bool Persistent, string? Ed);
    static readonly Dictionary<string, List<uint>> OwnerGroups = new();
    // (2026-10-29) the hall's own statics placed by the outside's layout, at fixed IDs in 0x7F00..0x7FFF (below the NPC session's
    // 0x8000 block; the ledger's highest ID leaves the block out, as it leaves the NPCs'): editor ID, ID, mesh, bounds. A new
    // one takes the next ID; an ID is never reused
    static readonly (string ed, uint id, string nif, short[] lo, short[] hi)[] OwnFixed =
    {
        ("AGHall2Banner330", 0x7F00, "AGHall2Banner330.nif", new short[] { -57, -26, -343 }, new short[] { 57, 1, 13 }),   // the wings' four, 330 x 90, still (2026-11-02: placed no more, OwnMoving; kept for what the ledger's retired references name)
        ("AGHall2Chain805", 0x7F02, "AGHall2Chain805.nif", new short[] { -2, -2, 0 }, new short[] { 2, 2, 805 }),   // the chandeliers' chains: chain_nif.py
        ("AGHall2Chain421", 0x7F03, "AGHall2Chain421.nif", new short[] { -2, -2, 0 }, new short[] { 2, 2, 421 }),
        ("AGHall2Chain308", 0x7F04, "AGHall2Chain308.nif", new short[] { -2, -2, 0 }, new short[] { 2, 2, 308 }),
        ("AGHall2Chain248", 0x7F24, "AGHall2Chain248.nif", new short[] { -2, -2, 0 }, new short[] { 2, 2, 248 }),   // (2026-11-06: the strongroom's ring 60 higher)
    };
    static readonly (string ed, uint id, string nif, short[] lo, short[] hi)[] OwnMoving =
    {
        ("AGHall2Banner330A", 0x7F0E, "AGHall2Banner330A.nif", new short[] { -60, -66, -343 }, new short[] { 60, 1, 13 }),   // the wings' four, moving, each on its own loop: banner_nif.py
        ("AGHall2Banner330B", 0x7F0F, "AGHall2Banner330B.nif", new short[] { -60, -66, -343 }, new short[] { 60, 1, 13 }),
        ("AGHall2Banner330C", 0x7F10, "AGHall2Banner330C.nif", new short[] { -60, -66, -343 }, new short[] { 60, 1, 13 }),
        ("AGHall2Banner330D", 0x7F11, "AGHall2Banner330D.nif", new short[] { -60, -66, -343 }, new short[] { 60, 1, 13 }),
        ("AGHall2Banner160E", 0x7F12, "AGHall2Banner160E.nif", new short[] { -30, -36, -173 }, new short[] { 30, 1, 13 }),   // the gallery's two
        ("AGHall2Banner160F", 0x7F13, "AGHall2Banner160F.nif", new short[] { -30, -36, -173 }, new short[] { 30, 1, 13 }),
    };
    // (2026-11-02) the Guild's sign, on vanilla's hinge: an MSTT as vanilla's hanging signs are (blender/sign_nif.py). 0x7F01 was AGHall2WindowsDay, gone the same day; 0x7F14 the bounce light
    static readonly (string ed, uint id, string nif, short[] lo, short[] hi)[] OwnHinged =
    {
        ("AGHall2Sign", 0x7F15, "AGHall2Sign.nif", new short[] { -16, 0, -72 }, new short[] { 9, 98, 8 }),
    };
    // (2026-11-03) the overmantel's display: the bounds measured from each mesh (scratchpad nif_bounds.py)
    static readonly (string ed, uint id, string nif, short[] lo, short[] hi)[] OwnDisplay =
    {
        ("AGHall2PlaqueShield", 0x7F1B, @"Clutter\WeaponRack\WRPlaqueShield01.nif", new short[] { -4, 2, -4 }, new short[] { 4, 3, 4 }),
        ("AGHall2PlaqueLeft", 0x7F1C, @"Clutter\WeaponRack\WRPlaqueLeft01.nif", new short[] { -1, -1, -21 }, new short[] { 44, 3, 21 }),
        ("AGHall2PlaqueRight", 0x7F1D, @"Clutter\WeaponRack\WRPlaqueRight01.nif", new short[] { -44, -1, -21 }, new short[] { 0, 3, 21 }),
        ("AGHall2DisplayShield", 0x7F1E, @"Armor\Dragonbone\DragonboneShield.nif", new short[] { -23, -45, -14 }, new short[] { 24, 21, 4 }),
        ("AGHall2DisplaySword", 0x7F1F, @"AdventurersGuild\Hall2\AGH2DisplaySword.nif", new short[] { -12, -20, -3 }, new short[] { 12, 72, 4 }),
        ("AGHall2UrnStatic", 0x7F25, @"Clutter\Glazed02PotteryUrn01.nif", new short[] { -15, -15, 0 }, new short[] { 15, 15, 33 }),   // (the fern's urn by the counter was loose clutter, so both are placed: vanilla's urn as a static, as Barrel02Static is the barrel's)
    };
    static readonly (string ed, uint id)[] OwnCopies =
    {
        ("BarStraight01", 0x7F05), ("BarLeft01", 0x7F06), ("BarRight01", 0x7F07), ("SSingleDoorInt01L", 0x7F08), ("SHouseIntDoor02Load", 0x7F09), ("SMdCFirePlace01", 0x7F0A),
        ("FarmBTrapdoor01", 0x7F0B), ("FarmBTrapdoor02", 0x7F0C), ("SSingleDoorInt01R", 0x7F0D),
        ("ImpWallSconceCandle01", 0x7F16), ("ImpWallSconce02CandleOn01", 0x7F17), ("ImpChandellierCandle01", 0x7F18),   // (2026-11-02: the wall iron, the higher-resolution rule for what is part of the building)
    };
    static readonly Dictionary<FormKey, FormKey> OwnCopyOf = new();
    static bool Fixed(uint id) => id >= 0x7F00 && id <= 0x7FFF;
    sealed class Plan
    {
        public Plan(string cell, FormKey b, double x, double y, double z, double yaw, double scale, bool isLight)
        { Cell = cell; Base = b; X = x; Y = y; Z = z; Yaw = yaw; Scale = scale; IsLight = isLight; }
        public string Cell; public FormKey Base; public double X, Y, Z, Yaw, Scale, RX; public bool IsLight, Persistent; public P3Float? GA;
        public float? LightRadius, LightFade;
        public string? Name, Role, Pair, Kind; public JsonElement? J; public PrevRef? Prev; public PlacedObject? Ref; public FormKey? FixedKey;
    }

    // The same hall as the quest's properties, for AG's DLL (src/plugin/src/hall), which places and keeps it itself: every piece by its
    // record ("plugin|local ID"), world position, angle (degrees) and scale; each site's origin and turn; the hide boxes
    // in a site's layout frame. "version" changes whenever anything placed changes, so a save holding an older hall is
    // rebuilt on load. Written next to the plugin, as SKSE/Plugins/AdventurersGuild/Hall/hall2.json.
    static void WriteLayout(string outDir, List<(FormKey b, float x, float y, float z, float a, float s, int site)> P,
        List<float> sx, List<float> sy, List<float> syaw, List<(float x0, float x1, float y0, float y1, int site, int kind)> clear, FormKey slate)
    {
        static string Rec(FormKey k) => $"{k.ModKey.FileName}|0x{k.ID:X6}";
        static double R(float v) => Math.Round(v, 2);
        var body = new
        {
            sites = sx.Select((x, i) => new { site = i + 1, x = R(x), y = R(sy[i]), yaw = R(syaw[i]) }),
            pieces = P.Select(p => new { b = Rec(p.b), x = R(p.x), y = R(p.y), z = R(p.z), a = R(p.a), s = R(p.s), site = p.site }),
            clear = clear.Select(c => new { x0 = R(c.x0), x1 = R(c.x1), y0 = R(c.y0), y1 = R(c.y1), site = c.site, kind = c.kind }),
            roof = Rec(slate),
        };
        var canon = JsonSerializer.Serialize(body);
        var version = Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(System.Text.Encoding.UTF8.GetBytes(canon)))[..16];
        var dirOut = Path.Combine(outDir, "SKSE", "Plugins", "AdventurersGuild", "Hall");
        Directory.CreateDirectory(dirOut);
        var json = JsonSerializer.Serialize(new { version, body.sites, body.pieces, body.clear, body.roof });
        File.WriteAllText(Path.Combine(dirOut, "hall2.json"), json);
        Console.WriteLine($"hall2: layout {version} written ({P.Count} pieces, {clear.Count} hide boxes) -> {Path.Combine(dirOut, "hall2.json")}");
    }
}
