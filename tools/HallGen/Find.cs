using Mutagen.Bethesda.Skyrim;
using System.Text.RegularExpressions;
// Find: statics (and furniture, activators, containers, trees, flora, doors, misc items) whose editor ID matches a regex, with size,
// model and record type; lighting templates too (no model: their ambient and directional colours instead).
static class Find
{
    public static void Run(List<ISkyrimModDisposableGetter> mods, string pattern)
    {
        var re = new Regex(pattern, RegexOptions.IgnoreCase);
        foreach (var s in mods.SelectMany(m => m.Statics).Concat<ISkyrimMajorRecordGetter>(mods.SelectMany(m => m.MoveableStatics)).Concat(mods.SelectMany(m => m.Lights)).Concat(mods.SelectMany(m => m.Furniture)).Concat(mods.SelectMany(m => m.Activators)).Concat(mods.SelectMany(m => m.Containers)).Concat(mods.SelectMany(m => m.Trees)).Concat(mods.SelectMany(m => m.Florae)).Concat(mods.SelectMany(m => m.Doors)).Concat(mods.SelectMany(m => m.MiscItems)).Concat(mods.SelectMany(m => m.Books)).Concat(mods.SelectMany(m => m.Ingestibles)).Concat(mods.SelectMany(m => m.Ingredients)).GroupBy(s => s.FormKey).Select(g => g.Last()))
        {
            if (!re.IsMatch(s.EditorID ?? "")) continue;
            var ob = (s as IObjectBoundedGetter)?.ObjectBounds; var model = (s as IModeledGetter)?.Model?.File.ToString() ?? "";
            var type = s switch { IStaticGetter => "STAT", IMoveableStaticGetter => "MSTT", ILightGetter => "LIGH", IFurnitureGetter => "FURN",
                                  IActivatorGetter => "ACTI", IContainerGetter => "CONT", ITreeGetter => "TREE", IFloraGetter => "FLOR", IDoorGetter => "DOOR", IMiscItemGetter => "MISC", IBookGetter => "BOOK", IIngestibleGetter => "ALCH", IIngredientGetter => "INGR", _ => "?" };
            Console.WriteLine($"{s.EditorID}\t{(ob is null ? "?" : $"{ob.Second.X - ob.First.X}x{ob.Second.Y - ob.First.Y}x{ob.Second.Z - ob.First.Z}")}\t{s.FormKey}\t{model}\t{type}{(s is IContainerGetter cg ? $"\tflags {cg.Flags} items {cg.Items?.Count ?? 0}" : "")}");
        }
        foreach (var a in mods.SelectMany(m => m.Armors).GroupBy(a => a.FormKey).Select(g => g.Last()))   // armour: its world model
            if (re.IsMatch(a.EditorID ?? ""))
                Console.WriteLine($"{a.EditorID}	{a.Name?.String}	{a.FormKey}	{a.WorldModel?.Male?.Model?.File}	ARMO	value {a.Value} enchant {a.ObjectEffect.FormKeyNullable} amount {a.EnchantmentAmount} template {a.TemplateArmor.FormKeyNullable}");
        foreach (var e in mods.SelectMany(m => m.ObjectEffects).GroupBy(e => e.FormKey).Select(g => g.Last()))   // enchantments: their effects
            if (re.IsMatch(e.EditorID ?? ""))
                Console.WriteLine($"{e.EditorID}\t{e.Name?.String}\t{e.FormKey}\t{e.EnchantType} {e.CastType} {e.TargetType}\t" +
                                  string.Join("; ", e.Effects.Select(f => $"{f.BaseEffect.FormKey} mag {f.Data?.Magnitude} dur {f.Data?.Duration}")) + "\tENCH");
        foreach (var t in mods.SelectMany(m => m.LightingTemplates).GroupBy(t => t.FormKey).Select(g => g.Last()))
            if (re.IsMatch(t.EditorID ?? ""))
                Console.WriteLine($"{t.EditorID}\tambient {t.AmbientColor.R},{t.AmbientColor.G},{t.AmbientColor.B}\t{t.FormKey}\tdirectional {t.DirectionalColor.R},{t.DirectionalColor.G},{t.DirectionalColor.B} fade {t.DirectionalFade} fog {t.FogNearColor.R},{t.FogNearColor.G},{t.FogNearColor.B}\tLGTM");
    }
}
