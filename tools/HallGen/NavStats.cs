using System.Text.RegularExpressions;
using Mutagen.Bethesda;
using Mutagen.Bethesda.Plugins.Order;
using Mutagen.Bethesda.Skyrim;
// NavStats: the shape of an interior's navmesh triangles (2026-10-30, the NPCs stalling on the hall's floors: the stair's slivers had
// stopped the follower): counts, inradius and smallest angle, for vanilla's cells beside ours.
//   dotnet run -- navstats "<cell editor ID regex>"    (EXTRA_PLUGINS=<the hall's plugin> for ours)
public static class NavStats
{
    public static void Run(List<ISkyrimModDisposableGetter> mods, string rx)
    {
        var r = new Regex(rx);
        foreach (var m in mods) foreach (var b in m.Cells) foreach (var sb in b.SubBlocks) foreach (var c in sb.Cells)
        {
            if (c.EditorID is not { } e || !r.IsMatch(e)) continue;
            foreach (var n in c.NavigationMeshes)
            {
                if (n.Data is not { } d || d.Triangles.Count == 0) continue;
                var inr = new List<double>(); var ang = new List<double>();
                foreach (var t in d.Triangles)
                {
                    var A = d.Vertices[t.Vertices.X]; var B = d.Vertices[t.Vertices.Y]; var C = d.Vertices[t.Vertices.Z];
                    double D(Noggog.P3Float p, Noggog.P3Float q) => Math.Sqrt((p.X - q.X) * (p.X - q.X) + (p.Y - q.Y) * (p.Y - q.Y) + (p.Z - q.Z) * (p.Z - q.Z));
                    double a = D(B, C), bb = D(A, C), cc = D(A, B), s = (a + bb + cc) / 2, area = Math.Sqrt(Math.Max(0, s * (s - a) * (s - bb) * (s - cc)));
                    inr.Add(s > 0 ? area / s : 0);
                    var cs = new[] { (bb * bb + cc * cc - a * a) / (2 * bb * cc + 1e-9), (a * a + cc * cc - bb * bb) / (2 * a * cc + 1e-9), (a * a + bb * bb - cc * cc) / (2 * a * bb + 1e-9) };
                    ang.Add(cs.Min(x => Math.Acos(Math.Clamp(x, -1, 1)) * 180 / Math.PI));
                }
                inr.Sort(); ang.Sort(); double P(List<double> l, double f) => l[(int)(f * (l.Count - 1))];
                Console.WriteLine($"{e,-30} {m.ModKey.FileName,-34} tris {inr.Count,5}  inradius 5/50/95% {P(inr, .05),5:F1} {P(inr, .5),5:F1} {P(inr, .95),5:F1}  under 4: {100.0 * inr.Count(x => x < 4) / inr.Count,3:F0}%  angle 5/50% {P(ang, .05),4:F1} {P(ang, .5),4:F1}  under 5deg: {100.0 * ang.Count(x => x < 5) / ang.Count,3:F0}%");
            }
        }
    }
}
