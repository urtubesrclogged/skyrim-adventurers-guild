using System.Text.RegularExpressions;
using Mutagen.Bethesda.Skyrim;
// DoorTorch: how high vanilla mounts a torch beside a door (for the hall's front door torches: how high
// they sit on other vanilla sets and modded buildings). Every reference of the bases whose editor ID
// matches, with the nearest door in the same space (interior cell, or worldspace) within reach: its height over the door's
// bottom, its top over it, the door's height, the share of it, and how far out along the wall from the door's middle.
//   dotnet run -c Release -- doortorch "<torch editor ID regex>" [<reach>]    (EXTRA_PLUGINS=... for a mod's buildings)
static class DoorTorch
{
    public static void Run(List<ISkyrimModDisposableGetter> mods, string pattern, double reach)
    {
        var re = new Regex(pattern, RegexOptions.IgnoreCase);
        var torches = new Dictionary<Mutagen.Bethesda.Plugins.FormKey, (string ed, Mutagen.Bethesda.Skyrim.IObjectBoundsGetter? ob)>();
        foreach (var r in mods.SelectMany(m => m.Statics).Cast<IObjectBoundedGetter>().Concat(mods.SelectMany(m => m.MoveableStatics)).Concat(mods.SelectMany(m => m.Lights)))
            if (r is ISkyrimMajorRecordGetter mr && re.IsMatch(mr.EditorID ?? "")) torches[mr.FormKey] = (mr.EditorID!, r.ObjectBounds);
        var doors = new Dictionary<Mutagen.Bethesda.Plugins.FormKey, IDoorGetter>();
        foreach (var d in mods.SelectMany(m => m.Doors)) doors[d.FormKey] = d;
        // every space's references, the last plugin's copy of each; a worldspace's persistent and temporary cells pooled
        var spaces = new Dictionary<string, Dictionary<Mutagen.Bethesda.Plugins.FormKey, (string mod, IPlacedObjectGetter r)>>();
        void Add(string sp, string mod, ICellGetter c)
        {
            if (!spaces.TryGetValue(sp, out var d)) spaces[sp] = d = new();
            foreach (var r in c.Persistent.Concat(c.Temporary).OfType<IPlacedObjectGetter>()) d[r.FormKey] = (mod, r);
        }
        foreach (var m in mods)
        {
            foreach (var c in m.Cells.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells)) Add(c.EditorID ?? c.FormKey.ToString(), m.ModKey.FileName, c);
            foreach (var w in m.Worldspaces)
            {
                if (w.TopCell is { } t) Add(w.EditorID ?? "", m.ModKey.FileName, t);
                foreach (var c in w.SubCells.SelectMany(b => b.Items).SelectMany(s => s.Items)) Add(w.EditorID ?? "", m.ModKey.FileName, c);
            }
        }
        Console.WriteLine("space\tmod\ttorch\tscale\tdoor\tdoorH\tz over door bottom\ttop over bottom\tshare of door\tout from middle\tdepth\tdist");
        var tally = new List<(double z, double share, double dh)>(); int alone = 0;
        foreach (var (sp, refs) in spaces)
        {
            var ds = refs.Values.Where(v => doors.ContainsKey(v.r.Base.FormKey) && v.r.Placement is not null && (v.r.MajorRecordFlagsRaw & 0x20) == 0).ToList();
            foreach (var (mod, t) in refs.Values)
            {
                if (!torches.TryGetValue(t.Base.FormKey, out var tb) || t.Placement is not { } tp || (t.MajorRecordFlagsRaw & 0x20) != 0) continue;
                var p = tp.Position; double best = reach; (string mod, IPlacedObjectGetter r)? hit = null;
                foreach (var d in ds)
                {
                    var q = d.r.Placement!.Position; double g = Math.Sqrt((q.X - p.X) * (q.X - p.X) + (q.Y - p.Y) * (q.Y - p.Y));
                    if (g < best && Math.Abs(q.Z - p.Z) < 400) { best = g; hit = d; }
                }
                if (hit is not { } h) { alone++; continue; }
                var dp = h.r.Placement!; var db = doors[h.r.Base.FormKey]; double ds_ = h.r.Scale ?? 1, ts = t.Scale ?? 1;
                double bot = dp.Position.Z + db.ObjectBounds.First.Z * ds_, dh = (db.ObjectBounds.Second.Z - db.ObjectBounds.First.Z) * ds_;
                double top = p.Z + (tb.ob?.Second.Z ?? 0) * ts;
                // along the wall and into it, in the door's own frame (its yaw; the engine's rotations are clockwise)
                double a = dp.Rotation.Z, dx = p.X - dp.Position.X, dy = p.Y - dp.Position.Y;
                double u = dx * Math.Cos(a) - dy * Math.Sin(a), v = dx * Math.Sin(a) + dy * Math.Cos(a);
                Console.WriteLine($"{sp}\t{mod}\t{tb.ed}\t{ts:0.##}\t{db.EditorID}\t{dh:0}\t{p.Z - bot:0}\t{top - bot:0}\t{(p.Z - bot) / dh:0.00}\t{Math.Abs(u):0}\t{v:0}\t{best:0}");
                tally.Add((p.Z - bot, (p.Z - bot) / dh, dh));
            }
        }
        if (tally.Count == 0) { Console.WriteLine($"no torch within {reach} of a door ({alone} torches alone): read nothing"); Environment.Exit(1); }
        var zs = tally.Select(x => x.z).OrderBy(x => x).ToList(); var sh = tally.Select(x => x.share).OrderBy(x => x).ToList();
        double Q(List<double> l, double f) => l[(int)Math.Round(f * (l.Count - 1))];
        Console.WriteLine($"-- {tally.Count} torches by a door ({alone} with none within {reach}); origin over the door's bottom: min {zs[0]:0} q1 {Q(zs, .25):0} median {Q(zs, .5):0} q3 {Q(zs, .75):0} max {zs[^1]:0}; share of the door's height: q1 {Q(sh, .25):0.00} median {Q(sh, .5):0.00} q3 {Q(sh, .75):0.00}");
    }
}
