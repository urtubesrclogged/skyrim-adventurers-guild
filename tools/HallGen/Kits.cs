using Mutagen.Bethesda.Skyrim;
using System.Text.RegularExpressions;

// Kits: vanilla statics whose model lives under Architecture or Dungeons\*\Exterior and whose name says what the
// piece is (wall, gate, arch, tower, stair, door frame, facade...), grouped by kit folder, with sizes.
static class Kits
{
    public static void Run(List<ISkyrimModDisposableGetter> mods)
    {
        var role = new Regex("wall|gate|arch|tower|stair|step|entr|facade|front|portal|pillar|column|buttress|roof|gable|porch|balcon|awning|frame|trim|banner|brazier", RegexOptions.IgnoreCase);
        var skip = new Regex("lod|snow|destroyed|ruined|broken|rubble|debris|_?ice|frost|collapsed|dirtcliff|rock", RegexOptions.IgnoreCase);
        var where = new Regex(@"^(Meshes\\)?(Architecture|Dungeons\\[^\\]+\\Exterior|DLC0\d\\Architecture)", RegexOptions.IgnoreCase);
        foreach (var s in mods.SelectMany(m => m.Statics).GroupBy(s => s.FormKey).Select(g => g.Last()))
        {
            var model = s.Model?.File.ToString() ?? "";
            if (!where.IsMatch(model)) continue;
            var ed = s.EditorID ?? "";
            if (!role.IsMatch(ed) || skip.IsMatch(ed) || s.ObjectBounds is not { } b) continue;
            var parts = model.Split('\\').ToList();
            if (parts[0].Equals("Meshes", StringComparison.OrdinalIgnoreCase)) parts.RemoveAt(0);
            var kit = string.Join("/", parts.Take(parts.Count - 1));
            Console.WriteLine($"{kit}\t{ed}\t{b.Second.X - b.First.X}x{b.Second.Y - b.First.Y}x{b.Second.Z - b.First.Z}\t{s.FormKey}\t{model}");
        }
    }
}
