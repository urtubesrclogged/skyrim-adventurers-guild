"""Read built NIFs back with PyNifly's own reader (not Blender's import): per shape, the shader flags, the alpha property,
and what the vertex colours and alphas actually hold (luminance range and mean, alpha range).
    python -I check_nif_colours.py <nif> [...]
Compare the ranges with the export JSON: the first hall build stored them gamma-decoded (0.3 as 0.07) and only this
read-back showed it."""
import sys, os
D = os.path.join(os.environ["APPDATA"], "Blender Foundation", "Blender", "5.2", "scripts", "addons", "io_scene_nifly")
sys.path.insert(0, D)
from pyn.pynifly import NifFile
from pyn.nifdefs import ShaderFlags1, ShaderFlags2
NifFile.Load(os.path.join(D, "pyn", "NiflyDLL.dll"))
lum = lambda c: 0.3 * c[0] + 0.59 * c[1] + 0.11 * c[2]
for p in sys.argv[1:]:
    f = NifFile(p); print("##", os.path.basename(p))
    for s in f.shapes:
        sh = s.shader.properties
        f1 = ShaderFlags1(sh.Shader_Flags_1).fullname if hasattr(ShaderFlags1(sh.Shader_Flags_1), "fullname") else sh.Shader_Flags_1
        f2 = ShaderFlags2(sh.Shader_Flags_2).fullname if hasattr(ShaderFlags2(sh.Shader_Flags_2), "fullname") else sh.Shader_Flags_2
        cols = s.colors or []
        L = [lum(c) for c in cols]; A = [c[3] for c in cols]
        al = s.alpha_property
        ap = None
        if al is not None:
            pr = al.properties; ap = {k: getattr(pr, k) for k in ("flags", "threshold") if hasattr(pr, k)}
            if not ap: ap = {k: getattr(pr, k) for k, _ in pr._fields_}
        line = f"   {s.name:18s} colours {len(cols):6d}"
        if cols: line += f" lum {min(L):.2f}..{max(L):.2f} mean {sum(L)/len(L):.2f} | alpha {min(A):.2f}..{max(A):.2f}"
        print(line, "| alphaprop", ap)
        print("      flags1:", f1); print("      flags2:", f2)
