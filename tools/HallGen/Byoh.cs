using Mutagen.Bethesda.Skyrim;

// Every static of HearthFires.esm (the Build Your Own Home kit), with its size and model, grouped by model folder.
static class Byoh
{
    public static void Run(List<ISkyrimModDisposableGetter> mods)
    {
        var hf = mods.First(m => m.ModKey.FileName == "HearthFires.esm");
        foreach (var s in hf.Statics)
        {
            var model = s.Model?.File.ToString() ?? "";
            if (s.ObjectBounds is not { } b) continue;
            var parts = model.Split('\\');
            var folder = parts.Length > 1 ? parts[^2] : "";
            Console.WriteLine($"{folder}\t{s.EditorID}\t{b.Second.X - b.First.X}x{b.Second.Y - b.First.Y}x{b.Second.Z - b.First.Z}\t{s.FormKey}\t{model}");
        }
    }
}
