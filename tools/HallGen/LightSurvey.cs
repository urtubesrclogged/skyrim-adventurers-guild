using System.Text.RegularExpressions;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Skyrim;
// LightSurvey: how bright vanilla keeps its inns and halls (Guild Hall interior, 2026-10-26: the walk of hall2s was washed out).
// For every interior cell whose editor ID matches: its lighting template and own lighting (ambient, directional, what it
// inherits), and its lights grouped by base: count, radius (the ref's own where it has one), fade, colour, flags.
//   dotnet run -c Release -- lightsurvey "^(WhiterunBanneredMare|RiverwoodSleepingGiantInn)$"
static class LightSurvey
{
    static Func<FormKey, string> m_ImageSpaceEd = _ => "?";
    public static void Run(List<ISkyrimModDisposableGetter> mods, string pattern)
    {
        var re = new Regex(pattern, RegexOptions.IgnoreCase);
        var lights = mods.SelectMany(m => m.Lights).GroupBy(l => l.FormKey).ToDictionary(g => g.Key, g => g.Last());
        var templates = mods.SelectMany(m => m.LightingTemplates).GroupBy(l => l.FormKey).ToDictionary(g => g.Key, g => g.Last());
        string Rgb(System.Drawing.Color c) => $"{c.R},{c.G},{c.B}";
        var copies = new Dictionary<FormKey, List<ICellGetter>>();
        foreach (var m in mods)
            foreach (var c in m.Cells.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells))
                if (re.IsMatch(c.EditorID ?? "")) { if (!copies.TryGetValue(c.FormKey, out var l)) copies[c.FormKey] = l = new(); l.Add(c); }
        var isEd_ = mods.SelectMany(mm => mm.ImageSpaces).GroupBy(i => i.FormKey).ToDictionary(g => g.Key, g => g.Last().EditorID ?? "");
        m_ImageSpaceEd = k => isEd_.TryGetValue(k, out var e) ? e : "?";
        foreach (var all in copies.Values.OrderBy(l => l.Last().EditorID))
        {
            var c = all.Last();
            var merged = new Dictionary<FormKey, IPlacedGetter>();
            foreach (var cc in all) foreach (var r in cc.Persistent.Concat(cc.Temporary)) merged[r.FormKey] = r;
            var objs = merged.Values.Where(r => !r.IsDeleted).OfType<IPlacedObjectGetter>().Where(r => r.Placement != null).ToList();
            Console.WriteLine($"== {c.EditorID} ({c.Name?.String})");
            { var isk_ = c.ImageSpace.FormKeyNullable; var ism_ = isk_ is { } ik_ ? m_ImageSpaceEd(ik_) : "none"; Console.WriteLine($"  imagespace {ism_} ({isk_}), water {c.Water.FormKeyNullable}, location {c.Location.FormKeyNullable}"); }
            if (c.LightingTemplate.FormKeyNullable is { } tk && templates.TryGetValue(tk, out var t))
                Console.WriteLine($"  template {t.EditorID}: ambient {Rgb(t.AmbientColor)} directional {Rgb(t.DirectionalColor)} fade {t.LightFadeStartDistance}..{t.LightFadeEndDistance}"
                    + (t.DirectionalAmbientColors is { } da ? $" dirAmb x+{Rgb(da.DirectionalXPlus)} x-{Rgb(da.DirectionalXMinus)} y+{Rgb(da.DirectionalYPlus)} y-{Rgb(da.DirectionalYMinus)} z+{Rgb(da.DirectionalZPlus)} z-{Rgb(da.DirectionalZMinus)}" : ""));
            if (c.Lighting is { } li)
                Console.WriteLine($"  own: ambient {Rgb(li.AmbientColor)} directional {Rgb(li.DirectionalColor)} fade {li.LightFadeBegin}..{li.LightFadeEnd} inherits [{li.Inherits}]"
                    + (li.AmbientColors is { } a ? $" dirAmb x+{Rgb(a.DirectionalXPlus)} z+{Rgb(a.DirectionalZPlus)} z-{Rgb(a.DirectionalZMinus)}" : ""));
            float x0 = float.MaxValue, y0 = float.MaxValue, x1 = float.MinValue, y1 = float.MinValue;
            var rows = new Dictionary<string, (int n, List<string> radii, string desc)>();
            foreach (var r in objs)
            {
                var p = r.Placement!.Position;
                x0 = Math.Min(x0, p.X); y0 = Math.Min(y0, p.Y); x1 = Math.Max(x1, p.X); y1 = Math.Max(y1, p.Y);
                if (!lights.TryGetValue(r.Base.FormKey, out var l)) continue;
                var f = l.Flags;
                string kind = f.HasFlag(Light.Flag.ShadowSpotlight) ? "shadow-spot" : f.HasFlag(Light.Flag.ShadowHemisphere) ? "shadow-hemi" : f.HasFlag(Light.Flag.ShadowOmnidirectional) ? "shadow-omni" : "";
                string fl = string.Join(" ", new[] { kind, f.HasFlag(Light.Flag.Flicker) ? "flicker" : "", f.HasFlag(Light.Flag.FlickerSlow) ? "flickerslow" : "", f.HasFlag(Light.Flag.Pulse) ? "pulse" : "", f.HasFlag(Light.Flag.PortalStrict) ? "portal" : "" }.Where(s => s.Length > 0));
                var desc = $"r {l.Radius} fade {l.FadeValue:F2} falloff {l.FalloffExponent:F2} col {Rgb(l.Color)} {fl}".Trim();
                var key = l.EditorID ?? l.FormKey.ToString();
                if (!rows.TryGetValue(key, out var row)) row = (0, new List<string>(), desc);
                var rr = r.Radius is { } rad ? $"{rad}" : "";
                var fo = r.LightData is { } ld && Math.Abs(ld.FadeOffset) > 1e-3 ? $"f{ld.FadeOffset:+0.00;-0.00}" : "";
                if (rr.Length + fo.Length > 0) row.radii.Add(rr + fo);
                rows[key] = (row.n + 1, row.radii, row.desc);
            }
            int total = rows.Values.Sum(v => v.n);
            Console.WriteLine($"  extent {Math.Round(x1 - x0)} x {Math.Round(y1 - y0)}, lights {total}");
            foreach (var (k, v) in rows.OrderByDescending(kv => kv.Value.n))
                Console.WriteLine($"  {v.n,3} {k,-40} {v.desc}" + (v.radii.Count > 0 ? $"  refs: {string.Join(" ", v.radii.Take(12))}" : ""));
        }
    }
}
// IsInfo: an image space's numbers (2026-10-30, the Bannered Mare under ELE against the hall): HDR, cinematic, tint.
//   dotnet run -- isinfo "<editor ID regex>"
static class IsInfo
{
    public static void Run(List<ISkyrimModDisposableGetter> mods, string pattern)
    {
        var re = new Regex(pattern, RegexOptions.IgnoreCase);
        foreach (var s in mods.SelectMany(m => m.ImageSpaces).GroupBy(i => i.FormKey).Select(g => g.Last()).Where(i => re.IsMatch(i.EditorID ?? "")))
        {
            var h = s.Hdr; var c = s.Cinematic; var t = s.Tint;
            if (s.DepthOfField is { } dof_) Console.WriteLine($"{s.EditorID}: dof strength {dof_.Strength} distance {dof_.Distance} range {dof_.Range}");
            Console.WriteLine($"{s.EditorID,-28} hdr adapt speed {h?.EyeAdaptSpeed:F2} strength {h?.EyeAdaptStrength:F2} bloom blur {h?.BloomBlurRadius:F1} thr {h?.BloomThreshold:F2} scale {h?.BloomScale:F2} recv {h?.ReceiveBloomThreshold:F2} white {h?.White:F2} sun {h?.SunlightScale:F2} sky {h?.SkyScale:F2} | sat {c?.Saturation:F2} bright {c?.Brightness:F2} contrast {c?.Contrast:F2} | tint {t?.Amount:F2} {t?.Color}");
        }
    }
}
// PluginLights: what a lighting mod changes (2026-10-30: do ELE and Lux reach a new cell by themselves?): its plugin's cells, lights, templates and image spaces,
// new records apart from overrides of the masters', and which of the vanilla records the hall uses it overrides.
//   EXTRA_PLUGINS=<plugin> dotnet run -- pluginlights
static class LtInfo
{
    public static void Run(List<ISkyrimModDisposableGetter> mods, string pattern)
    {
        var re = new Regex(pattern, RegexOptions.IgnoreCase);
        foreach (var t in mods.SelectMany(m => m.LightingTemplates).GroupBy(i => i.FormKey).Select(g => g.Last()).Where(i => re.IsMatch(i.EditorID ?? "")))
        {
            Console.WriteLine($"{t.EditorID}: ambient {t.AmbientColor} directional {t.DirectionalColor} rot {t.DirectionalRotationXY}/{t.DirectionalRotationZ} dirfade {t.DirectionalFade} fog near {t.FogNearColor} {t.FogNear} far {t.FogFarColor} {t.FogFar} clip {t.FogClipDistance} power {t.FogPower} max {t.FogMax} light fade {t.LightFadeStartDistance}..{t.LightFadeEndDistance}");
            foreach (var (n, a) in new[] { ("ambientcolors", t.AmbientColors), ("directionalambient", t.DirectionalAmbientColors) })
                if (a is not null) Console.WriteLine($"   {n}: x+ {a.DirectionalXPlus} x- {a.DirectionalXMinus} y+ {a.DirectionalYPlus} y- {a.DirectionalYMinus} z+ {a.DirectionalZPlus} z- {a.DirectionalZMinus} spec {a.Specular} scale {a.Scale}");
        }
    }
}
static class PluginLights
{
    public static void Run(List<ISkyrimModDisposableGetter> mods)
    {
        var m = mods.Last(); int nm = mods.Count - 1; bool Own(Mutagen.Bethesda.Plugins.FormKey k) => k.ModKey == m.ModKey;
        string C<T>(IEnumerable<T> r, Func<T, Mutagen.Bethesda.Plugins.FormKey> k) { var l = r.ToList(); return $"{l.Count(x => Own(k(x)))} new, {l.Count(x => !Own(k(x)))} overrides"; }
        int cells = 0, interior = 0; foreach (var b in m.Cells) foreach (var sb in b.SubBlocks) foreach (var c in sb.Cells) { cells++; if (c.Flags.HasFlag(Cell.Flag.IsInteriorCell)) interior++; }
        Console.WriteLine($"{m.ModKey.FileName}: interior cells edited {interior}; lights {C(m.Lights, x => x.FormKey)}; templates {C(m.LightingTemplates, x => x.FormKey)}; image spaces {C(m.ImageSpaces, x => x.FormKey)}");
        foreach (var e in new[] { "WRFireLightShadow01", "WRInteriorLightYellow", "WRCandleFlickerNS", "WRWindowFill", "WRChandlierFlickerShadow", "SolitudeInnFirePlacesShadowDefault", "SolitudeInnSunlightShadow" })
        {
            var ov = m.Lights.FirstOrDefault(x => x.EditorID == e); var b = mods.Take(nm).SelectMany(x => x.Lights).LastOrDefault(x => x.EditorID == e);
            Console.WriteLine($"  LIGH {e,-36} {(ov is null ? "not touched" : $"overridden: radius {b?.Radius} -> {ov.Radius}, fade {b?.FadeValue} -> {ov.FadeValue}, colour {b?.Color} -> {ov.Color}")}");
        }
        foreach (var e in new[] { "SolitudeInteriors", "WhiteRunIntLightingTemplate" }) Console.WriteLine($"  LGTM {e,-36} {(m.LightingTemplates.Any(x => x.EditorID == e) ? "overridden" : "not touched")}");
        foreach (var e in new[] { "SolitudeInteriorLgIS", "SolitudeInteriorIS", "WhiteRunIntIS" }) Console.WriteLine($"  IMGS {e,-36} {(m.ImageSpaces.Any(x => x.EditorID == e) ? "overridden" : "not touched")}");
    }
}
