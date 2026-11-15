using Mutagen.Bethesda.Skyrim;
// Every DOOR base wider than 150 units with a model: the candidates for a grand front door.
static class Doors
{
    public static void Run(List<ISkyrimModDisposableGetter> mods)
    {
        foreach (var d in mods.SelectMany(m => m.Doors).GroupBy(d => d.FormKey).Select(g => g.Last()))
        {
            if (d.ObjectBounds is not { } b || d.Model is null) continue;
            int w = Math.Max(b.Second.X - b.First.X, b.Second.Y - b.First.Y), h = b.Second.Z - b.First.Z;
            if (w < (Environment.GetEnvironmentVariable("DOOR_MINW") is { } mw ? int.Parse(mw) : 150) || h < 150) continue;
            Console.WriteLine($"{d.EditorID}\t{w}x{h}\t{d.FormKey}\t{d.Model.File}");
        }
    }
}
