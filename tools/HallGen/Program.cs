using Mutagen.Bethesda;
using Mutagen.Bethesda.Skyrim;

var data = Environment.GetEnvironmentVariable("SKYRIM_DATA") ?? throw new InvalidOperationException("SKYRIM_DATA not set");
string[] masters = { "Skyrim.esm", "Update.esm", "Dawnguard.esm", "HearthFires.esm", "Dragonborn.esm" };
var mods = masters.Select(m => SkyrimMod.CreateFromBinaryOverlay(Path.Combine(data, m), SkyrimRelease.SkyrimSE)).ToList();
// more plugins after the masters, in load order (a later one wins): EXTRA_PLUGINS=<path>;<path>
foreach (var p in (Environment.GetEnvironmentVariable("EXTRA_PLUGINS") ?? "").Split(';', StringSplitOptions.RemoveEmptyEntries))
    mods.Add(SkyrimMod.CreateFromBinaryOverlay(p, SkyrimRelease.SkyrimSE));
switch (args.FirstOrDefault())
{
    case "survey": Survey.Run(mods, args.Length > 1 ? args[1] : "."); break;
    case "props": Props.Run(); break;
    case "shells": Shells.Run(mods, args.Length > 1 ? int.Parse(args[1]) : 1200); break;
    case "bounds": Bounds.Run(mods, args.Skip(1).ToArray()); break;
    case "kits": Kits.Run(mods); break;
    case "interiors": Interiors.Run(mods, args[1]); break;
    case "lightsurvey": LightSurvey.Run(mods, args[1]); break;
    case "links": Links.Run(mods, args[1], args[2]); break;
    case "refdiff": RefDiff.Run(mods, args[1], args[2], args.Contains("--all")); break;
    case "reflect":   // the properties of Mutagen getter interfaces, to see what a record exposes
        foreach (var tn in args.Skip(1))
        {
            var t = typeof(ISkyrimMod).Assembly.GetType("Mutagen.Bethesda.Skyrim." + tn);
            Console.WriteLine($"-- {tn}: " + (t is null ? "not found" : string.Join(", ", t.GetProperties().Concat(t.GetInterfaces().SelectMany(i => i.GetProperties())).Select(p => $"{p.Name}:{p.PropertyType.Name}").Distinct())));
        }
        break;
    case "byoh": Byoh.Run(mods); break;
    case "manor": Manor.Run(mods); break;
    case "doors": Doors.Run(mods); break;
    case "find": Find.Run(mods, args[1]); break;
    case "perf": Perf.Run(mods, args[1]); break;
    case "roomsurvey": RoomSurvey.Run(mods, args[1]); break;
    case "vmad": Vmad.Run(mods, args[1]); break;
    case "cases": Cases.Run(mods, args[1], args[2]); break;
    case "pairs": Pairs.Run(mods, args[1], args[2], args.Length > 3 ? double.Parse(args[3]) : 40); break;
    case "navflags": NavFlags.Run(mods, args[1], args.Skip(2).Select(double.Parse).ToArray()); break;
    case "watersurvey": WaterSurvey.Run(mods, args.Skip(1).ToArray()); break;
    case "refs": Refs.Run(mods, args[1]); break;
    case "cellloc": Refs.CellLoc(mods, int.Parse(args[1]), int.Parse(args[2])); break;
    case "cellrefs": Refs.CellRefs(mods, args[1]); break;
    case "stairnav": StairNav.Run(mods, args[1], double.Parse(args[2]), double.Parse(args[3]), args.Length > 4 ? int.Parse(args[4]) : 20); break;
    case "onrefs": OnRefs.Run(mods, args[1], double.Parse(args[2]), double.Parse(args[3]), double.Parse(args[4]), double.Parse(args[5]), args.Length > 6 ? int.Parse(args[6]) : 200); break;
    case "doortorch": DoorTorch.Run(mods, args[1], args.Length > 2 ? double.Parse(args[2]) : 300); break;
    case "hangrefs": HangRefs.Run(mods, args[1], double.Parse(args[2]), double.Parse(args[3])); break;
    case "benchrefs": BenchRefs.Run(mods, args.Length > 1 ? args[1] : "02E6CF:Skyrim.esm", args.Length > 2 ? int.Parse(args[2]) : 60); break;
    case "land": Land.Run(mods, args.Skip(1).ToArray()); break;
    case "landgrid": LandGrid.Run(args[1], args[2], args[3], args[4], args[5]); break;
    case "grassof": GrassOf.Run(args[1], args[2], args[3]); break;
    case "landowners": LandOwners.Run(args[1], args[2], args[3], args[4]); break;
    case "navdump": NavDump.Run(mods, args[1], args.Length > 2 ? int.Parse(args[2]) : 4); break;
    case "navstats": NavStats.Run(mods, args[1]); break;
    case "navislands": NavIslands.Run(mods, args.Length > 1 && !args[1].StartsWith("--") ? args[1] : ".", args.Contains("--list")); break;
    case "navdoors": NavDoors.Run(mods, args.Length > 1 && !args[1].StartsWith("--") ? args[1] : ".", args.Contains("--list")); break;
    case "navdoorw": NavDoorW.Run(mods, args.Length > 1 && !args[1].StartsWith("--") ? args[1] : ".", args.Contains("--list")); break;
    case "isinfo": IsInfo.Run(mods, args[1]); break;
    case "pluginlights": PluginLights.Run(mods); break;
    case "navflagbits": foreach (var v in Enum.GetValues(typeof(NavmeshTriangle.Flag))) Console.WriteLine($"{v} = 0x{(int)v:X}"); break;
    case "furnmarkers":   // a furniture record's markers (entry points, disabled ones), and how many of vanilla's disable any
        { int dis = 0, all = 0;
          foreach (var m in mods) foreach (var f in m.Furniture) { all++; if (f.Markers?.Any(k => (int)(k.DisabledEntryPoints?.Points ?? 0) != 0) == true) dis++;
            if (f.EditorID == args[1] || (args.Length > 2 && f.Model?.File.ToString().Contains(args[2], StringComparison.OrdinalIgnoreCase) == true)) foreach (var k in f.Markers ?? (IReadOnlyList<IFurnitureMarkerGetter>)Array.Empty<IFurnitureMarkerGetter>()) Console.WriteLine($"{m.ModKey.FileName} {f.EditorID}: enabled {k.Enabled}, entry {k.EntryPoints?.Type} {k.EntryPoints?.Points}, disabled {k.DisabledEntryPoints?.Type} {k.DisabledEntryPoints?.Points}"); }
          Console.WriteLine($"{dis} of {all} furniture records disable an entry point"); Console.WriteLine("Entry: " + string.Join(", ", Enum.GetValues(typeof(Furniture.Entry)).Cast<object>().Select(v => $"{v}={(int)v}"))); }
        break;
    case "navcut": ExtNav.NavCut(mods); break;
    case "navcutsize": ExtNav.NavCutSize(mods); break;
    case "extnav": ExtNav.Run(mods, int.Parse(args[1]), int.Parse(args[2]), args.Length > 3 ? int.Parse(args[3]) : 1); break;
    case "ltinfo": LtInfo.Run(mods, args[1]); break;
    case "navdoublebeds": NavDoubleBeds.Run(mods, args[1]); break;
    case "tavernaisles": TavernAisles.Run(mods, args.Contains("--list")); break;
    case "cellplan": CellPlan.Run(mods, args[1], args[2]); break;
    case "navtables": NavTables.Run(mods, args.Length > 1 && !args[1].StartsWith("--") ? args[1] : ".", args.Contains("--list")); break;
    case "navbedsides": NavBedSides.Run(mods, args.Length > 1 && !args[1].StartsWith("--") ? args[1] : ".", args.Contains("--list")); break;
    case "doorrefs": DoorRefs.Run(mods, args[1], args[2], args.Length > 3 ? int.Parse(args[3]) : 12); break;
    case "loaddooruse": LoadDoorUse.Run(mods, args[1]); break;
    case "navbeds": NavBeds.Run(mods, args.Length > 1 ? args[1] : "."); break;
    case "pkgloc": PkgLoc.Run(mods, args[1]); break;
    case "navmesh": Navmesh.Run(mods, int.Parse(args[1]), int.Parse(args[2]), int.Parse(args[3]), int.Parse(args[4])); break;
    case "ck": Ck.Run(mods, args[1], args[2]); break;
    case "build": Build.Run(mods, args[1], args.Length > 2 ? args[2] : null); break;
    case "verify": Verify.Run(mods, args[1]); break;
    default: Console.WriteLine("usage: survey <interior cell regex> | build <out dir>"); break;
}
