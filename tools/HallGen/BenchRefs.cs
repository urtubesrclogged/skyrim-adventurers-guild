using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Skyrim;
// BenchRefs: research for placing furniture as vanilla does. Every placed reference of one base record (default
// CommonBench01, Skyrim.esm 02E6CF) in Skyrim.esm's cells, with everything modelled within 400 units of it, as JSON lines:
// {"cell":..,"ref":[x,y,z,rx,ry,rz,scale],"near":[[model,x,y,z,rx,ry,rz,scale],...]}  (rotations in radians)
static class BenchRefs
{
    public static void Run(List<ISkyrimModDisposableGetter> mods, string baseId, int max)
    {
        var target = FormKey.Factory(baseId);
        var model = new Dictionary<FormKey, string>();
        foreach (var r in mods.SelectMany(m => m.Statics).Cast<ISkyrimMajorRecordGetter>().Concat(mods.SelectMany(m => m.Furniture)).Concat(mods.SelectMany(m => m.MoveableStatics))
                     .Concat(mods.SelectMany(m => m.Activators)).Concat(mods.SelectMany(m => m.Containers)).Concat(mods.SelectMany(m => m.Doors)))
            if ((r as IModeledGetter)?.Model?.File.ToString() is { } f) model[r.FormKey] = f;
        var sk = mods.First(m => m.ModKey.FileName == "Skyrim.esm");
        var cells = sk.Cells.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells).Select(c => ((ICellGetter)c, c.EditorID ?? "interior"))
            .Concat(sk.Worldspaces.SelectMany(w => w.SubCells.SelectMany(b => b.Items).SelectMany(s => s.Items).Select(c => ((ICellGetter)c, (w.EditorID ?? "") + " exterior"))));
        int n = 0;
        foreach (var (c, name) in cells)
        {
            var refs = c.Persistent.Concat(c.Temporary).OfType<IPlacedObjectGetter>().Where(r => r.Placement != null).ToList();
            foreach (var b in refs.Where(r => r.Base.FormKey == target))
            {
                var p = b.Placement!;
                var near = refs.Where(r => r != b && model.ContainsKey(r.Base.FormKey) && Math.Abs(r.Placement!.Position.X - p.Position.X) < 400 && Math.Abs(r.Placement.Position.Y - p.Position.Y) < 400 && Math.Abs(r.Placement.Position.Z - p.Position.Z) < 300)
                    .Select(r => new object[] { model[r.Base.FormKey], r.Placement!.Position.X, r.Placement.Position.Y, r.Placement.Position.Z, r.Placement.Rotation.X, r.Placement.Rotation.Y, r.Placement.Rotation.Z, r.Scale ?? 1f }).ToList();
                Console.WriteLine(System.Text.Json.JsonSerializer.Serialize(new { cell = name, @ref = new object[] { p.Position.X, p.Position.Y, p.Position.Z, p.Rotation.X, p.Rotation.Y, p.Rotation.Z, b.Scale ?? 1f }, near }));
                if (++n >= max) return;
            }
        }
    }
}
