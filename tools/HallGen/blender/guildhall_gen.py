"""Parametric guild hall, built from Skyrim's own Solitude textures (study, not shipped).
   blender --background --python guildhall_gen.py -- <extracted data root> <out dir> [clay]
Units are game units (1 = ~1.43 cm). x = along the front (right), y = depth (back), z = up. Front faces -y."""
import sys, os, math, time, random, bpy, bmesh, addon_utils
from mathutils import Vector, Matrix

root, out = sys.argv[sys.argv.index("--") + 1], sys.argv[sys.argv.index("--") + 2]
CLAY = "clay" in sys.argv
# a real site: the hall's origin (pavilion front, floor level) in the world, its floor height and game yaw
SITE = [float(v) for v in os.environ["AG_SITE"].split(",")] if os.environ.get("AG_SITE") else None
TAG = os.environ.get("AG_TAG", "")
if SITE:
    import json as _json, base64 as _b64, struct as _struct
    _M = _json.load(open(os.environ["AG_MAP"]))
    _X0, _Y0 = _M["box"][0] * 4096, _M["box"][1] * 4096; _NX, _NY = _M["nx"], _M["ny"]
    _H = _struct.unpack("<%dh" % (_NX * _NY), _b64.b64decode(_M["heights"]))
    _A = math.radians(SITE[3]); _C, _S = math.cos(_A), math.sin(_A)
    def hall_to_world(hx, hy):
        lx, ly = -hy, hx                                  # layout frame: front +x
        return SITE[0] + lx * _C + ly * _S, SITE[1] - lx * _S + ly * _C
    def world_to_hall(wx, wy):
        dx, dy = wx - SITE[0], wy - SITE[1]
        lx, ly = dx * _C - dy * _S, dx * _S + dy * _C
        return ly, -lx
    def ground_under(x0, x1, y0, y1):
        """the lowest ground under a rectangle of the hall frame (corners, edges' middles, centre)"""
        return min(ground(x, y) for x in (x0, (x0 + x1) / 2, x1) for y in (y0, (y0 + y1) / 2, y1))
    def ground(hx, hy):
        """terrain height under a point of the hall frame, relative to the floor"""
        wx, wy = hall_to_world(hx, hy)
        fx, fy = (wx - _X0) / 128, (wy - _Y0) / 128; i, j = int(fx), int(fy); u, v = fx - i, fy - j
        i = min(max(i, 0), _NX - 2); j = min(max(j, 0), _NY - 2)
        h = lambda a, b: _H[b * _NX + a]
        return h(i, j) * (1 - u) * (1 - v) + h(i + 1, j) * u * (1 - v) + h(i, j + 1) * (1 - u) * v + h(i + 1, j + 1) * u * v - SITE[2]
os.makedirs(out, exist_ok=True)
TEX = os.path.join(root, "textures", "architecture", "solitude")
S = 256.0  # vanilla Solitude texel scale: one texture tile per 256 game units (measured on SBrylingHouse)
UP = Vector((0, 0, 1))

for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)
scene = bpy.context.scene

# ---------------------------------------------------------------- materials
MATS = {}
CLAYCOL = {"stone": (0.55, 0.55, 0.56), "base": (0.45, 0.45, 0.46), "trim": (0.6, 0.6, 0.6), "stucco": (0.86, 0.84, 0.8),
           "wood": (0.25, 0.2, 0.16), "roof": (0.3, 0.33, 0.38), "tile": (0.45, 0.28, 0.2), "win1": (0.2, 0.22, 0.25),
           "win3": (0.2, 0.22, 0.25), "door": (0.3, 0.24, 0.18), "steps": (0.5, 0.5, 0.5), "floor": (0.5, 0.5, 0.5),
           "grass": (0.3, 0.38, 0.22), "cloth": (0.5, 0.1, 0.08), "metal": (0.3, 0.3, 0.3), "dirt": (0.32, 0.26, 0.2),
           "planks": (0.3, 0.27, 0.22), "crest": (0.7, 0.6, 0.35), "moss": (0.3, 0.4, 0.2), "mosswall": (0.3, 0.4, 0.2), "wearcrack": (0.1, 0.1, 0.1), "wearstain": (0.12, 0.12, 0.1), "break": (0.6, 0.62, 0.62),
           "pipe": (0.3, 0.3, 0.3), "crest3d": (0.7, 0.6, 0.35), "wood2": (0.3, 0.22, 0.16), "planks2": (0.33, 0.27, 0.2)}
FILES = {"stone": "sstonewall02", "base": "sstonebase01", "trim": "strims01", "stucco": "sstuccowall", "wood": "swoodbeam01",
         "roof": "sroofslate01", "tile": "sdragontile01", "win1": "swindow01", "planks": "swoodplanks01", "crest": "../../adventurersguild/hall/AGHallCrest", "moss": "smoss01", "mosswall": "smoss02walls", "win3": "swindow03", "door": "sdoor02",
         "steps": "ssteps01", "floor": "sstonefloor01", "grass": "sgrass01", "metal": "smetaldet01", "dirt": "sdirt01",
         "pipe": "smetaldet01", "crest3d": "../../adventurersguild/hall2/agcrest"}
FILES.update({"painting1": "../../adventurersguild/hall2/AGH2Painting1", "painting2": "../../adventurersguild/hall2/AGH2Painting2"})
CLAYCOL.update({"painting1": (0.4, 0.4, 0.38), "painting2": (0.4, 0.4, 0.38)})
# (2026-10-26) the hall wears our own copies (textures/make_hall_textures.py; hall_nif.py's MAP): the renders show them too
_OWN = "../../adventurersguild/hall2/"
FILES.update({"stone": _OWN + "AGH2XStone", "base": _OWN + "AGH2XBase", "trim": _OWN + "AGH2XTrim", "stucco": _OWN + "AGH2XStucco",
              "wood": _OWN + "AGH2XWood", "tile": _OWN + "AGH2XTile", "win1": _OWN + "AGH2XWin1", "planks": _OWN + "AGH2XPlanks",
              "moss": _OWN + "AGH2XMoss", "mosswall": _OWN + "AGH2XMossWall", "wearcrack": _OWN + "AGH2XWearCrack", "wearstain": _OWN + "AGH2XWearStain", "break": _OWN + "AGH2XStoneBreak", "win3": _OWN + "AGH2XWin3", "door": _OWN + "AGH2XDoor",
              "steps": _OWN + "AGH2XSteps", "floor": _OWN + "AGH2XFloor", "metal": _OWN + "AGH2XMetal", "dirt": _OWN + "AGH2XDirt",
              "pipe": _OWN + "AGH2XMetal"})

TINT = {"roof": (0.55, 0.66, 0.85)}
def material(key):
    if key in MATS: return MATS[key]
    m = bpy.data.materials.new(key); m.use_nodes = True
    nt = m.node_tree; b = nt.nodes["Principled BSDF"]
    b.inputs["Roughness"].default_value = 0.85
    if CLAY or key not in FILES:
        b.inputs["Base Color"].default_value = (*CLAYCOL.get(key, (0.5, 0.5, 0.5)), 1)   # (a key with no clay colour, the windows' parts since 2026-11-01: grey, not a KeyError that stopped the clip check)
    else:
        t = nt.nodes.new("ShaderNodeTexImage"); t.image = bpy.data.images.load(os.path.join(TEX, FILES[key] + ".dds"))
        col = t.outputs["Color"]
        if key in TINT:
            mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = "RGBA"; mix.blend_type = "MULTIPLY"
            mix.inputs["Factor"].default_value = 1.0
            nt.links.new(col, [i for i in mix.inputs if i.identifier == "A_Color"][0])
            [i for i in mix.inputs if i.identifier == "B_Color"][0].default_value = (*TINT[key], 1)
            col = [o for o in mix.outputs if o.identifier == "Result_Color"][0]
        if key in AGE_CELL:                                  # the baked age, as the game multiplies it in
            va = nt.nodes.new("ShaderNodeAttribute"); va.attribute_name = "VERTEX_COLOR"
            mv = nt.nodes.new("ShaderNodeMix"); mv.data_type = "RGBA"; mv.blend_type = "MULTIPLY"; mv.inputs["Factor"].default_value = 1.0
            nt.links.new(col, [i for i in mv.inputs if i.identifier == "A_Color"][0]); nt.links.new(va.outputs["Color"], [i for i in mv.inputs if i.identifier == "B_Color"][0])
            col = [o for o in mv.outputs if o.identifier == "Result_Color"][0]
        nt.links.new(col, b.inputs["Base Color"])
        if key in ("moss", "mosswall", "wearcrack", "wearstain"):   # the decal: texture alpha x vertex alpha, alpha-tested at 19/255
            vaa = nt.nodes.new("ShaderNodeAttribute"); vaa.attribute_name = "VERTEX_ALPHA"
            mul = nt.nodes.new("ShaderNodeMath"); mul.operation = "MULTIPLY"
            nt.links.new(t.outputs["Alpha"], mul.inputs[0]); nt.links.new(vaa.outputs["Fac"], mul.inputs[1])
            gt = nt.nodes.new("ShaderNodeMath"); gt.operation = "GREATER_THAN"; gt.inputs[1].default_value = 19 / 255
            nt.links.new(mul.outputs[0], gt.inputs[0]); nt.links.new(gt.outputs[0], b.inputs["Alpha"])
            try: m.surface_render_method = "DITHERED"
            except Exception: pass
        npath = os.path.join(TEX, FILES[key] + "_n.dds")
        if os.path.exists(npath):
            tn = nt.nodes.new("ShaderNodeTexImage"); tn.image = bpy.data.images.load(npath); tn.image.colorspace_settings.name = "Non-Color"
            sep = nt.nodes.new("ShaderNodeSeparateColor"); comb = nt.nodes.new("ShaderNodeCombineColor")
            inv = nt.nodes.new("ShaderNodeMath"); inv.operation = "SUBTRACT"; inv.inputs[0].default_value = 1.0
            nt.links.new(tn.outputs["Color"], sep.inputs[0]); nt.links.new(sep.outputs[1], inv.inputs[1])
            nt.links.new(sep.outputs[0], comb.inputs[0]); nt.links.new(inv.outputs[0], comb.inputs[1]); nt.links.new(sep.outputs[2], comb.inputs[2])
            nm = nt.nodes.new("ShaderNodeNormalMap"); nm.inputs["Strength"].default_value = 0.8
            nt.links.new(comb.outputs[0], nm.inputs["Color"]); nt.links.new(nm.outputs["Normal"], b.inputs["Normal"])
    MATS[key] = m; return m

# Atlas rectangles (u0, v0, u1, v1) in image space (v down), measured from the textures (atlas.py)
ATLAS = {
    "leaded":  ("win1", (0.046, 0.016, 0.262, 0.447)),   # tall leaded window, octagonal head
    "grid":    ("win1", (0.711, 0.081, 0.989, 0.449)),   # timber grid casement, its square body (the cambered head cropped)
    "small":   ("win1", (0.795, 0.530, 0.971, 0.767)),   # small casement, its square body (the pediment cropped)
    "shutter": ("win1", (0.107, 0.500, 0.294, 0.767)),
    "arched":  ("win3", (0.230, 0.244, 0.462, 0.604)),   # stone-framed arched window
    "gothic":  ("win3", (0.550, 0.275, 0.994, 0.994)),   # the great window with a rose
    "archdoor": ("door", (0.598, 0.132, 0.947, 0.809)),  # arched plank door in a stone frame
    "dbldoor": ("door", (0.002, 0.002, 0.481, 0.804)),
    "fan":     ("win3", (0.230, 0.244, 0.462, 0.360)),   # the head of the arched window: a fanlight
    "panes":   ("win1", (0.602, 0.519, 0.758, 0.997)),   # tall two-column panes (the Blue Palace's): one leaf of a glazed door
}

# height / width of each atlas picture, so an opening keeps the picture's proportions
RATIO = {k: ((r[3] - r[1])) / ((r[2] - r[0])) for k, (_, r) in ATLAS.items()}
TRACED = {
    'leaded': [(0.0747, 0.0), (0.9299, 0.0), (0.9751, 0.0193), (0.9932, 0.06), (0.9932, 0.1008), (0.9932, 0.1416), (0.9932, 0.1823), (0.9932, 0.2231), (0.9932, 0.2639), (0.9932, 0.3046), (0.9932, 0.3454), (0.9932, 0.3862), (0.9932, 0.427), (0.9932, 0.4677), (0.9932, 0.5085), (0.9932, 0.5493), (0.9932, 0.59), (0.9932, 0.6308), (0.9932, 0.6716), (0.9932, 0.7123), (0.9932, 0.7531), (0.9932, 0.7939), (0.9932, 0.8347), (0.9661, 0.8754), (0.8846, 0.9162), (0.8032, 0.957), (0.5769, 0.9977), (0.3891, 0.9977), (0.1878, 0.957), (0.1176, 0.9162), (0.0362, 0.8754), (0.0045, 0.8347), (0.0068, 0.7939), (0.0045, 0.7531), (0.0045, 0.7123), (0.0045, 0.6716), (0.0045, 0.6308), (0.0045, 0.59), (0.0045, 0.5493), (0.0045, 0.5085), (0.0045, 0.4677), (0.0045, 0.427), (0.0045, 0.3862), (0.0045, 0.3454), (0.0068, 0.3046), (0.0045, 0.2639), (0.0045, 0.2231), (0.0045, 0.1823), (0.0045, 0.1416), (0.0045, 0.1008), (0.0045, 0.06), (0.0249, 0.0193)],
    'grid': [(0.1019, 0.0), (0.8946, 0.0), (0.9227, 0.0106), (0.9947, 0.0517), (0.9947, 0.0928), (0.9947, 0.134), (0.9947, 0.1751), (0.9947, 0.2162), (0.9947, 0.2573), (0.9947, 0.2984), (0.9947, 0.3395), (0.9947, 0.3806), (0.9947, 0.4218), (0.9947, 0.4629), (0.9947, 0.504), (0.9947, 0.5451), (0.9947, 0.5862), (0.9947, 0.6273), (0.9947, 0.6684), (0.9947, 0.7095), (0.9947, 0.7507), (0.9947, 0.7918), (0.9947, 0.8329), (0.9947, 0.874), (0.9947, 0.9151), (0.9947, 0.9562), (0.9947, 0.9973), (0.0035, 0.9973), (0.0035, 0.9562), (0.0035, 0.9151), (0.0035, 0.874), (0.0035, 0.8329), (0.0035, 0.7918), (0.0035, 0.7507), (0.0035, 0.7095), (0.0035, 0.6684), (0.0035, 0.6273), (0.0035, 0.5862), (0.0035, 0.5451), (0.0035, 0.504), (0.0035, 0.4629), (0.0035, 0.4218), (0.0035, 0.3806), (0.0035, 0.3395), (0.0035, 0.2984), (0.0035, 0.2573), (0.0035, 0.2162), (0.0035, 0.1751), (0.0035, 0.134), (0.0035, 0.0928), (0.0228, 0.0517), (0.0721, 0.0106)],
    'small': [(0.0056, 0.0), (0.9917, 0.0), (0.9917, 0.0062), (0.9917, 0.0474), (0.9917, 0.0887), (0.9917, 0.1299), (0.9917, 0.1711), (0.9917, 0.2124), (0.9917, 0.2536), (0.9917, 0.2948), (0.9917, 0.3361), (0.9917, 0.3773), (0.9917, 0.4186), (0.9917, 0.4598), (0.9917, 0.501), (0.9917, 0.5423), (0.9917, 0.5835), (0.9917, 0.6247), (0.9917, 0.666), (0.9917, 0.7072), (0.9917, 0.7485), (0.9917, 0.7897), (0.9917, 0.8309), (0.9917, 0.8722), (0.9917, 0.9134), (0.9917, 0.9546), (0.9917, 0.9959), (0.0056, 0.9959), (0.0056, 0.9546), (0.0056, 0.9134), (0.0056, 0.8722), (0.0056, 0.8309), (0.0056, 0.7897), (0.0056, 0.7485), (0.0056, 0.7072), (0.0056, 0.666), (0.0056, 0.6247), (0.0056, 0.5835), (0.0056, 0.5423), (0.0056, 0.501), (0.0056, 0.4598), (0.0056, 0.4186), (0.0056, 0.3773), (0.0056, 0.3361), (0.0056, 0.2948), (0.0056, 0.2536), (0.0056, 0.2124), (0.0056, 0.1711), (0.0056, 0.1299), (0.0056, 0.0887), (0.0056, 0.0474), (0.0056, 0.0062)],
    'shutter': [(0.0496, 0.0), (0.9922, 0.0), (0.9922, 0.0293), (0.9922, 0.0696), (0.9922, 0.1099), (0.9922, 0.1502), (0.9922, 0.1905), (0.9922, 0.2308), (0.9922, 0.2711), (0.9922, 0.3114), (0.9922, 0.3516), (0.9922, 0.3919), (0.9922, 0.4322), (0.9922, 0.4725), (0.9922, 0.5128), (0.9922, 0.5531), (0.9922, 0.5934), (0.9922, 0.6337), (0.9922, 0.674), (0.9922, 0.7143), (0.9922, 0.7546), (0.9922, 0.7949), (0.9922, 0.8352), (0.9922, 0.8755), (0.9478, 0.9158), (0.8225, 0.956), (0.6292, 0.9963), (0.4178, 0.9963), (0.2167, 0.956), (0.1123, 0.9158), (0.0496, 0.8755), (0.0496, 0.8352), (0.0052, 0.7949), (0.0052, 0.7546), (0.0496, 0.7143), (0.0496, 0.674), (0.0496, 0.6337), (0.0496, 0.5934), (0.0496, 0.5531), (0.0496, 0.5128), (0.0496, 0.4725), (0.0496, 0.4322), (0.0496, 0.3919), (0.0496, 0.3516), (0.0496, 0.3114), (0.0496, 0.2711), (0.0496, 0.2308), (0.0496, 0.1905), (0.0052, 0.1502), (0.0078, 0.1099), (0.0496, 0.0696), (0.0496, 0.0293)],
    'arched': [(0.0126, 0.0), (0.9895, 0.0), (0.9937, 0.0204), (0.9937, 0.0611), (0.9937, 0.1018), (0.9937, 0.1425), (0.9895, 0.1832), (0.9895, 0.2239), (0.9895, 0.2646), (0.9937, 0.3053), (0.9937, 0.346), (0.9937, 0.3867), (0.9937, 0.4274), (0.9937, 0.4681), (0.9937, 0.5088), (0.9937, 0.5495), (0.9937, 0.5902), (0.9937, 0.6309), (0.9853, 0.6716), (0.9726, 0.7123), (0.9579, 0.7531), (0.9179, 0.7938), (0.88, 0.8345), (0.8232, 0.8752), (0.7558, 0.9159), (0.6842, 0.9566), (0.5347, 0.9973), (0.4695, 0.9973), (0.3116, 0.9566), (0.24, 0.9159), (0.1726, 0.8752), (0.12, 0.8345), (0.0779, 0.7938), (0.0358, 0.7531), (0.0232, 0.7123), (0.0105, 0.6716), (0.0063, 0.6309), (0.0042, 0.5902), (0.0042, 0.5495), (0.0042, 0.5088), (0.0042, 0.4681), (0.0042, 0.4274), (0.0063, 0.3867), (0.0042, 0.346), (0.0042, 0.3053), (0.0063, 0.2646), (0.0063, 0.2239), (0.0042, 0.1832), (0.0042, 0.1425), (0.0063, 0.1018), (0.0042, 0.0611), (0.0042, 0.0204)],
    'gothic': [(0.0044, 0.0), (0.9967, 0.0), (0.9956, 0.0041), (0.9967, 0.0455), (0.9967, 0.087), (0.9967, 0.1284), (0.9967, 0.1698), (0.9967, 0.2113), (0.9967, 0.2527), (0.9967, 0.2942), (0.9967, 0.3356), (0.9967, 0.377), (0.9967, 0.4185), (0.9967, 0.4599), (0.9967, 0.5014), (0.9967, 0.5428), (0.9967, 0.5842), (0.9967, 0.6257), (0.9934, 0.6671), (0.9802, 0.7086), (0.9681, 0.75), (0.9362, 0.7914), (0.89, 0.8329), (0.8394, 0.8743), (0.7635, 0.9158), (0.6843, 0.9572), (0.5127, 0.9986), (0.0022, 0.9986), (0.0022, 0.9572), (0.2365, 0.9158), (0.1584, 0.8743), (0.11, 0.8329), (0.0649, 0.7914), (0.0319, 0.75), (0.0176, 0.7086), (0.0055, 0.6671), (0.0022, 0.6257), (0.0022, 0.5842), (0.0022, 0.5428), (0.0022, 0.5014), (0.0022, 0.4599), (0.0022, 0.4185), (0.0022, 0.377), (0.0022, 0.3356), (0.0022, 0.2942), (0.0022, 0.2527), (0.0022, 0.2113), (0.0022, 0.1698), (0.0022, 0.1284), (0.0022, 0.087), (0.0022, 0.0455), (0.0033, 0.0041)],
    'archdoor': [(0.007, 0.0), (0.9958, 0.0), (0.9958, 0.0115), (0.9958, 0.0527), (0.9958, 0.0938), (0.9958, 0.1349), (0.9958, 0.176), (0.9958, 0.2172), (0.9958, 0.2583), (0.9958, 0.2994), (0.9958, 0.3405), (0.9944, 0.3817), (0.9958, 0.4228), (0.9944, 0.4639), (0.9958, 0.5051), (0.9958, 0.5462), (0.9958, 0.5873), (0.9958, 0.6284), (0.9958, 0.6696), (0.9958, 0.7107), (0.9958, 0.7518), (0.9958, 0.7929), (0.9958, 0.8341), (0.9916, 0.8752), (0.986, 0.9163), (0.9958, 0.9574), (0.9902, 0.9986), (0.0028, 0.9986), (0.0042, 0.9574), (0.0028, 0.9163), (0.0098, 0.8752), (0.0042, 0.8341), (0.0028, 0.7929), (0.0042, 0.7518), (0.0042, 0.7107), (0.0028, 0.6696), (0.0028, 0.6284), (0.0028, 0.5873), (0.0056, 0.5462), (0.0028, 0.5051), (0.0042, 0.4639), (0.0028, 0.4228), (0.0056, 0.3817), (0.0042, 0.3405), (0.0028, 0.2994), (0.0056, 0.2583), (0.0056, 0.2172), (0.0028, 0.176), (0.0028, 0.1349), (0.0028, 0.0938), (0.0028, 0.0527), (0.0028, 0.0115)],
    'dbldoor': [(0.0031, 0.0), (0.9969, 0.0), (0.9969, 0.0049), (0.9969, 0.0463), (0.9969, 0.0877), (0.9969, 0.1291), (0.9969, 0.1705), (0.9969, 0.2119), (0.9969, 0.2533), (0.9969, 0.2948), (0.9959, 0.3362), (0.9969, 0.3776), (0.9969, 0.419), (0.9969, 0.4604), (0.9959, 0.5018), (0.9969, 0.5432), (0.9959, 0.5847), (0.9969, 0.6261), (0.9969, 0.6675), (0.9959, 0.7089), (0.9959, 0.7503), (0.9969, 0.7917), (0.9959, 0.8331), (0.9969, 0.8745), (0.9969, 0.916), (0.9969, 0.9574), (0.9959, 0.9988), (0.002, 0.9988), (0.0041, 0.9574), (0.002, 0.916), (0.002, 0.8745), (0.002, 0.8331), (0.002, 0.7917), (0.002, 0.7503), (0.002, 0.7089), (0.002, 0.6675), (0.002, 0.6261), (0.002, 0.5847), (0.002, 0.5432), (0.002, 0.5018), (0.002, 0.4604), (0.002, 0.419), (0.002, 0.3776), (0.002, 0.3362), (0.002, 0.2948), (0.002, 0.2533), (0.002, 0.2119), (0.002, 0.1705), (0.002, 0.1291), (0.002, 0.0877), (0.002, 0.0463), (0.002, 0.0049)],
    'fan': [(0.0126, 0.0), (0.9832, 0.0), (0.9832, 0.0084), (0.9789, 0.0462), (0.9747, 0.084), (0.9726, 0.1218), (0.9663, 0.1597), (0.9663, 0.1975), (0.9579, 0.2353), (0.9495, 0.2731), (0.9389, 0.3109), (0.9242, 0.3487), (0.9095, 0.3866), (0.8968, 0.4244), (0.8863, 0.4622), (0.8737, 0.5), (0.8632, 0.5378), (0.8463, 0.5756), (0.8232, 0.6134), (0.8021, 0.6513), (0.7811, 0.6891), (0.7621, 0.7269), (0.7389, 0.7647), (0.72, 0.8025), (0.6968, 0.8403), (0.6779, 0.8782), (0.6211, 0.916), (0.5768, 0.9538), (0.5347, 0.9916), (0.4695, 0.9916), (0.4189, 0.9538), (0.3726, 0.916), (0.3179, 0.8782), (0.2989, 0.8403), (0.2758, 0.8025), (0.2568, 0.7647), (0.2337, 0.7269), (0.2147, 0.6891), (0.1916, 0.6513), (0.1726, 0.6134), (0.1495, 0.5756), (0.1326, 0.5378), (0.1221, 0.5), (0.1095, 0.4622), (0.0968, 0.4244), (0.0821, 0.3866), (0.0716, 0.3487), (0.0568, 0.3109), (0.0484, 0.2731), (0.0358, 0.2353), (0.0316, 0.1975), (0.0295, 0.1597), (0.0232, 0.1218), (0.0211, 0.084), (0.0189, 0.0462), (0.0126, 0.0084)],
    'panes': [(0.0063, 0.0), (0.9906, 0.0), (0.9906, 0.0174), (0.9906, 0.0582), (0.9906, 0.0991), (0.9906, 0.1399), (0.9906, 0.1808), (0.9906, 0.2217), (0.9906, 0.2625), (0.9906, 0.3034), (0.9906, 0.3442), (0.9906, 0.3851), (0.9906, 0.4259), (0.9906, 0.4668), (0.9906, 0.5077), (0.9906, 0.5485), (0.9906, 0.5894), (0.9906, 0.6302), (0.9906, 0.6711), (0.9906, 0.712), (0.9906, 0.7528), (0.9906, 0.7937), (0.9906, 0.8345), (0.9906, 0.8754), (0.9906, 0.9162), (0.9906, 0.9571), (0.9906, 0.998), (0.0063, 0.998), (0.0063, 0.9571), (0.0063, 0.9162), (0.0063, 0.8754), (0.0063, 0.8345), (0.0125, 0.7937), (0.0063, 0.7528), (0.0063, 0.712), (0.0063, 0.6711), (0.0063, 0.6302), (0.0094, 0.5894), (0.0063, 0.5485), (0.0063, 0.5077), (0.0063, 0.4668), (0.0063, 0.4259), (0.0063, 0.3851), (0.0063, 0.3442), (0.0063, 0.3034), (0.0063, 0.2625), (0.0063, 0.2217), (0.0063, 0.1808), (0.0063, 0.1399), (0.0063, 0.0991), (0.0063, 0.0582), (0.0125, 0.0174)],
}
def outline(kind, w, h):
    """The opening's outline in 0..1 rect space, counter-clockwise from bottom-left: arches are arched, the leaded
    windows have their cut corners, so the wall shows around the picture instead of the atlas background."""
    if kind in TRACED: return TRACED[kind]
    if kind == "fan":
        return [(0, 0), (1, 0)] + [(0.5 + 0.5 * math.cos(math.pi * i / 12), math.sin(math.pi * i / 12)) for i in range(1, 12)]
    if kind in ("arched", "gothic", "archdoor"):
        spring = 1 - (w / 2) / h
        pts = [(0, 0), (1, 0), (1, spring)]
        for i in range(1, 12):
            a = math.pi * i / 12
            pts.append((0.5 + 0.5 * math.cos(a), spring + (1 - spring) * math.sin(a)))
        return pts + [(0, spring)]
    if kind == "leaded":
        c = 0.2; cy = c * w / h
        return [(0, 0), (1, 0), (1, 1 - cy), (1 - c, 1), (c, 1), (0, 1 - cy)]
    return [(0, 0), (1, 0), (1, 1), (0, 1)]

# ---------------------------------------------------------------- geometry accumulator (one mesh per material)
GEO = {}          # (part, material key) -> faces; part: "body" (the building), "roof" (its slopes), "site" (terrace, stair)
PART = "body"
COLL = {}         # part -> collision triangles (simple solids only: walls as blocks, roof planes, stair ramps)
NOCOLL_IDS = set()   # (part, key, index): faces drawn but kept out of the interior's collision, and COLL_ONLY: part ->
COLL_ONLY = {}       # triangles that collide but are not drawn (2026-10-26: the tower stair, in vanilla's chamfered profile)
def coll_tri(a, b, c): COLL.setdefault(PART, []).append([tuple(a), tuple(b), tuple(c)])
def coll_quad(q): coll_tri(q[0], q[1], q[2]); coll_tri(q[0], q[2], q[3])
RAMPS = []        # (2026-11-13) each outdoor stair's walking surface as rows across it, foot to top: [[(left xyz), (right xyz)], ...], for
                  # outdoor_nav.py, which lays each stair's navmesh as a ramp on them (as vanilla meshes a stair), not a region per tread
FRAME = None                                                # (a rigid turn for what is drawn while it is set: the downpipe, drawn on the podium's north face, stands on the forecourt's side)
def coll_box(lo, hi):
    if FRAME:
        a_, b_ = FRAME(lo), FRAME(hi); lo, hi = tuple(map(min, a_, b_)), tuple(map(max, a_, b_))
    x0, y0, z0 = lo; x1, y1, z1 = hi
    v = [(x, y, z) for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)]
    for f in [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (3, 2, 6, 7), (2, 0, 4, 6), (1, 3, 7, 5)]: coll_quad([v[i] for i in f])
FIX_FACES = os.environ.get("AG_FIX_FACES", "1") == "1"   # (2026-10-25, leak_check.py) poly's outline normal, beam's outward sides
                    # and back. The interior had them first; the exterior since hall2r (seams at the
                    # gable's roof edge: every outside timber was wound inside out, so sky showed through a
                    # bargeboard's underside), with its own flicker pass (the patio parapets, pwall). AG_FIX_FACES=0: the old
                    # faces, for comparing. They change the age bake's T-junction splits (+2439 plaster faces).
def poly(key, pts, uvs=None, scale=S, swap=False):
    pts = [Vector(FRAME(p) if FRAME else p) for p in pts]
    if FIX_FACES:
        keep = [i for i in range(len(pts)) if (pts[i] - pts[i - 1]).length > 1e-6]   # a corner given twice (a strip that ends
        pts = [pts[i] for i in keep]                                                   # in a point) is dropped, not the face
        if uvs is not None: uvs = [uvs[i] for i in keep]
        if len(pts) < 3: return
        n = Vector((0, 0, 0))                 # Newell's normal, from the whole outline: taken from the first three corners, a
        for i in range(len(pts)):             # face that began along a straight edge was silently lost (the gables' end
            a_, b_ = pts[i - 1], pts[i]       # strips and the small windows inside)
            n += Vector(((a_.y - b_.y) * (a_.z + b_.z), (a_.z - b_.z) * (a_.x + b_.x), (a_.x - b_.x) * (a_.y + b_.y)))
    else:
        n = (pts[1] - pts[0]).cross(pts[2] - pts[0])
    if n.length < 1e-9: return
    n.normalize()
    if uvs is None:
        t = Vector((1, 0, 0)) if abs(n.z) > 0.999 else UP.cross(n).normalized()
        bt = n.cross(t)
        uvs = [((p.dot(t)) / scale, (p.dot(bt)) / scale) for p in pts]
        if swap: uvs = [(v, u) for u, v in uvs]
    GEO.setdefault(("roof" if key == "roof" else PART, key), []).append((pts, uvs))

def quad_on(W, u0, z0, u1, z1, d, key, rect=None, swap=False, kind=None):
    """A rectangle on wall W (origin, right, out), d out from the wall face."""
    o, r, n = W
    p = [o + r * u0 + UP * z0 + n * d, o + r * u1 + UP * z0 + n * d, o + r * u1 + UP * z1 + n * d, o + r * u0 + UP * z1 + n * d]
    if rect:
        a, b, c, e = rect
        shape = outline(kind, abs(u1 - u0), z1 - z0) if kind else [(0, 0), (1, 0), (1, 1), (0, 1)]
        pts = [o + r * (u0 + fx * (u1 - u0)) + UP * (z0 + fy * (z1 - z0)) + n * d for fx, fy in shape]
        poly(key, pts, [(a + fx * (c - a), 1 - e + fy * (e - b)) for fx, fy in shape])
    else:
        poly(key, p, swap=swap)

import sys as _s; _s.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from window_parts import parts as win_parts, place as win_place, hood as win_hood, spring as win_spring   # (2026-11-01: real windows, blender/window_parts.py)
GLAZE = os.environ.get("AG_GLAZE", "")                               # "all", or the openings' names by prefix, comma separated: the test bay
def glazed(what): return GLAZE == "all" or any(what.startswith(g_) for g_ in GLAZE.split(",") if g_)
def glaze(W, uc, z0, w, h, kind, d, side, pattern=None):
    global PART
    keep_ = PART
    for key_, faces_ in win_parts(kind, w, h, side, int(abs(uc) * 7 + z0 * 3), pattern).items():
        for pts_, uvs_ in win_place(faces_, W, uc, z0, d): poly(key_, pts_, uvs_)
        PART = keep_

OPENINGS = []   # every window, door and shutter leaf (hall frame): what clearance_check.py tests for things in front of it
WHERE = [""]    # the elevation being built, for its labels
def register(kind, W, u0, z0, u1, z1, d=0.0):
    o, r, n = W
    OPENINGS.append({"what": f"{WHERE[0]} {kind} u{round((u0 + u1) / 2)}", "kind": kind, "n": [n.x, n.y, n.z],
                     "c": [list(o + r * u + UP * zz + n * d) for u, zz in ((u0, z0), (u1, z0), (u1, z1), (u0, z1))]})

def box(key, lo, hi, grain=None):
    x0, y0, z0 = lo; x1, y1, z1 = hi
    v = [Vector((x, y, z)) for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)]
    faces = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (3, 2, 6, 7), (2, 0, 4, 6), (1, 3, 7, 5)]
    for f in faces:
        pts = [v[i] for i in f]
        nrm = (pts[1] - pts[0]).cross(pts[2] - pts[0])
        swap = grain == "z" and abs(nrm.z) < 1e-6 * max(1, nrm.length)
        poly(key, pts, swap=swap)

def obox(key, p0, p1, w, z0, z1, off=0.0, coll=True):
    """A block along the line p0 -> p1 (2D), w wide, from z0 to z1; off shifts it sideways (+ = to the line's left)."""
    p0, p1 = Vector((p0[0], p0[1], 0)), Vector((p1[0], p1[1], 0))
    d = (p1 - p0).normalized(); sd = Vector((-d.y, d.x, 0))
    c = [p0 + sd * (off - w / 2), p1 + sd * (off - w / 2), p1 + sd * (off + w / 2), p0 + sd * (off + w / 2)]
    lo = [Vector((q.x, q.y, z0)) for q in c]; hi = [Vector((q.x, q.y, z1)) for q in c]
    faces = [hi, lo[::-1]] + [[lo[i], lo[(i + 1) % 4], hi[(i + 1) % 4], hi[i]] for i in range(4)]
    for f in faces: poly(key, f)
    if coll:
        for f in faces: coll_quad(f)

def prism(key, pts2, zb, zt, coll=True):
    """a solid from a convex 2D polygon, bottom zb to top zt"""
    P = [Vector((q[0], q[1], 0)) for q in pts2]
    area = sum(P[i].x * P[(i + 1) % len(P)].y - P[(i + 1) % len(P)].x * P[i].y for i in range(len(P)))
    if area < 0: P = P[::-1]
    top = [Vector((q.x, q.y, zt)) for q in P]; bot = [Vector((q.x, q.y, zb)) for q in P][::-1]
    faces = [top, bot] + [[Vector((P[i].x, P[i].y, zb)), Vector((P[(i + 1) % len(P)].x, P[(i + 1) % len(P)].y, zb)),
                           Vector((P[(i + 1) % len(P)].x, P[(i + 1) % len(P)].y, zt)), Vector((P[i].x, P[i].y, zt))] for i in range(len(P))]
    for f in faces: poly(key, f)
    if coll:
        for f in faces: coll_quad(f) if len(f) == 4 else [coll_tri(f[0], f[i], f[i + 1]) for i in range(1, len(f) - 1)]

def rake_wall(key, A, B, tA, tB, base, th, coll=True, s0=0.0, along=False):
    """a wall along A -> B (2D), th thick (centred on the line), from base up to a top sloping from tA to tB;
    base may be (bA, bB) for a band whose underside slopes too (a coping)"""
    bA, bB = base if isinstance(base, tuple) else (base, base)
    A, B = Vector((A[0], A[1], 0)), Vector((B[0], B[1], 0)); d = (B - A); d.z = 0
    if d.length < 1e-6: return
    d.normalize(); n = Vector((-d.y, d.x, 0)) * (th / 2)
    a0, a1, b0, b1 = A + n, A - n, B + n, B - n
    V = lambda q, z: Vector((q.x, q.y, z))
    faces = [[V(a0, tA), V(a1, tA), V(b1, tB), V(b0, tB)],            # top (sloped)
             [V(a1, bA), V(a0, bA), V(b0, bB), V(b1, bB)],            # bottom
             [V(a0, bA), V(a0, tA), V(b0, tB), V(b0, bB)],            # one side
             [V(a1, bA), V(b1, bB), V(b1, tB), V(a1, tA)],            # the other
             [V(a0, bA), V(a1, bA), V(a1, tA), V(a0, tA)],            # end A
             [V(b0, bB), V(b0, tB), V(b1, tB), V(b1, bB)]]            # end B
    if along:                                    # a coping: the texture runs along the slope, continuous from s0
        L = (B - A).length
        def uv(q, across=None):
            t = (q - Vector((A.x, A.y, q.z))).to_2d().dot(d.to_2d()); lo = bA + (bB - bA) * t / L
            return ((s0 + t) / S, (q.z - lo) / S if across is None else across / S)
        top_uv = [uv(faces[0][0], 0), uv(faces[0][1], th), uv(faces[0][2], th), uv(faces[0][3], 0)]
        poly(key, faces[0], top_uv)
        poly(key, faces[1], [uv(faces[1][0], th), uv(faces[1][1], 0), uv(faces[1][2], 0), uv(faces[1][3], th)])   # underside: across, not smeared
        for f in faces[2:4]: poly(key, f, [uv(q) for q in f])
        for f, c0, z0 in ((faces[4], a0, bA), (faces[5], b0, bB)):    # the ends: across x up
            poly(key, f, [((q - c0).to_2d().length / S, (q.z - z0) / S) for q in f])
    else:
        for f in faces: poly(key, f)
    if coll:
        for f in faces: coll_quad(f)

def band(key, P, A, half, tops, bases, coll=True):
    """a wall along the 2D polyline P: its section at point i spans P[i] +- A[i] * half (A carries the mitre), from
    bases[i] to tops[i]; one solid, ends closed. Texture runs along the wall (u = distance along it, v = height)."""
    n = len(P); Lp = [P[i] + A[i] * half for i in range(n)]; Rp = [P[i] - A[i] * half for i in range(n)]
    sl = [0.0]
    for i in range(1, n): sl.append(sl[-1] + (P[i] - P[i - 1]).length)
    V = lambda q, z: Vector((q.x, q.y, z))
    def put(pts, uvs, inside):
        nn = (pts[1] - pts[0]).cross(pts[2] - pts[0])
        if nn.dot(sum(pts, Vector()) / len(pts) - inside) < 0: pts, uvs = pts[::-1], uvs[::-1]
        poly(key, pts, [(u_ / S, v_ / S) for u_, v_ in uvs])
        if coll: coll_quad(pts)
    for i in range(n - 1):
        mid = V((P[i] + P[i + 1]) / 2, (tops[i] + bases[i] + tops[i + 1] + bases[i + 1]) / 4)
        put([V(Lp[i], tops[i]), V(Rp[i], tops[i]), V(Rp[i + 1], tops[i + 1]), V(Lp[i + 1], tops[i + 1])],
            [(sl[i], 0), (sl[i], 2 * half), (sl[i + 1], 2 * half), (sl[i + 1], 0)], mid)
        put([V(Lp[i], bases[i]), V(Rp[i], bases[i]), V(Rp[i + 1], bases[i + 1]), V(Lp[i + 1], bases[i + 1])],
            [(sl[i], 0), (sl[i], 2 * half), (sl[i + 1], 2 * half), (sl[i + 1], 0)], mid)
        for Q in (Lp, Rp):
            put([V(Q[i], bases[i]), V(Q[i + 1], bases[i + 1]), V(Q[i + 1], tops[i + 1]), V(Q[i], tops[i])],
                [(sl[i], bases[i]), (sl[i + 1], bases[i + 1]), (sl[i + 1], tops[i + 1]), (sl[i], tops[i])], mid)
    for i, j in ((0, 1), (n - 1, n - 2)):                    # the two ends
        inside = V(P[j], (tops[i] + bases[i]) / 2)
        put([V(Lp[i], bases[i]), V(Rp[i], bases[i]), V(Rp[i], tops[i]), V(Lp[i], tops[i])],
            [(0, bases[i]), (2 * half, bases[i]), (2 * half, tops[i]), (0, tops[i])], inside)

def xslab(key, O, out, along, pts, half):
    """a convex profile pts [(s, z)] (s out from the wall at O) extruded half either side along the wall"""
    O, out, along = Vector((O[0], O[1], 0)), Vector((out[0], out[1], 0)), Vector((along[0], along[1], 0))
    Wp = lambda q, x: O + out * q[0] + along * x + Vector((0, 0, q[1]))
    A_ = [Wp(q, -half) for q in pts]; B_ = [Wp(q, half) for q in pts]
    cen = (sum(A_, Vector()) + sum(B_, Vector())) / (2 * len(pts))
    faces = [A_, B_] + [[A_[i], A_[(i + 1) % len(pts)], B_[(i + 1) % len(pts)], B_[i]] for i in range(len(pts))]
    for f in faces:
        nn = (f[1] - f[0]).cross(f[2] - f[0])
        if nn.length < 1e-9: continue
        if nn.dot(sum(f, Vector()) / len(f) - cen) < 0: f = f[::-1]
        poly(key, f)

def turned(c, z_top, prof, key="wood", n=8):
    """a turned timber (a lathe piece, n-sided) hanging from z_top: prof [(d, r)] goes down d from the top with radius r;
    open at the top (it hangs under something), closed to a point or a flat end at the bottom"""
    P = lambda r, a, d: Vector((c[0] + r * math.cos(a), c[1] + r * math.sin(a), z_top - d))
    for (d0, r0), (d1, r1) in zip(prof, prof[1:]):
        for k in range(n):
            a0, a1 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
            if r1 < 0.01: poly(key, [P(r0, a0, d0), P(0, a0, d1), P(r0, a1, d0)])
            else: poly(key, [P(r0, a0, d0), P(r1, a0, d1), P(r1, a1, d1), P(r0, a1, d0)])
    if prof[-1][1] >= 0.01: poly(key, [P(prof[-1][1], 2 * math.pi * k / n, prof[-1][0]) for k in range(n)][::-1])

def bracket(O, out, along, z_top, depth, drop, thick=16, t=14, key="wood", pendant=False):
    """A carved timber bracket under an overhang: a leg up the wall, an arm under the overhang, and a web between them
    whose lower edge is a concave quarter ellipse (the classic Solitude bracket). O: the wall point under its centre;
    out: unit 2D away from the wall; along: unit 2D along it."""
    zb = z_top - drop; K = (t, z_top - t); Rs, Rz = depth - t, drop - t; N = 6
    arc = [(depth - Rs * math.cos(math.radians(90 * k / N)), zb + Rz * math.sin(math.radians(90 * k / N))) for k in range(N + 1)]
    xslab(key, O, out, along, [(0, zb), (t, zb), (t, z_top), (0, z_top)], thick / 2)                   # the leg
    xslab(key, O, out, along, [(t, z_top - t), (depth, z_top - t), (depth, z_top), (t, z_top)], thick / 2)   # the arm
    for a_, b_ in zip(arc, arc[1:]): xslab(key, O, out, along, [K, a_, b_], thick / 2)              # the web
    if pendant:                                                  # a turned drop under the leg: collar, neck, bulb, point
        r = min(t, thick) / 2
        c = (O[0] + out[0] * t / 2, O[1] + out[1] * t / 2)
        turned(c, zb, [(0, r), (4, r + 2), (10, r + 2), (14, r - 1), (24, r + 1.5), (34, r * 0.6), (42, 0)], key)

MOSS_A = {}          # (part, "moss") -> per face, per vertex alpha: the ribbons fade through vertex alpha, as vanilla's do
def _n1(u, seed=0.0):
    """smooth value noise in 0..1, the same every build"""
    i = math.floor(u); f = u - i
    h = lambda k: (math.sin((k + seed * 57.0) * 127.1 + 311.7) * 43758.5453) % 1.0
    f = f * f * (3 - 2 * f); return h(i) * (1 - f) + h(i + 1) * f

def moss_quad(part, pts3, alphas):
    """one face of a moss decal, facing up"""
    a3, b3, c3 = Vector(pts3[0]), Vector(pts3[1]), Vector(pts3[2])
    if (b3 - a3).cross(c3 - a3).z < 0: pts3, alphas = pts3[::-1], alphas[::-1]
    GEO.setdefault((part, "moss"), []).append((pts3, [(q[0] / 220.0, q[1] / 220.0) for q in pts3]))
    MOSS_A.setdefault((part, "moss"), []).append(list(alphas))

def wear_quad(part, key, pts3, uvs, want, alpha=1.0):
    """a wear decal on a face (small details to break up the stair: a crack along the top of the
    stair's wall, a stain): as Whiterun's and Windhelm's stonework wears its own (wrplasterdecals, whbrickdecal1: alpha-tested strips
    laid over the walls), our textures (AGH2XWearCrack, AGH2XWearStain), 0.6 off the face, wound to face want"""
    P_ = [Vector(q) for q in pts3]
    if (P_[1] - P_[0]).cross(P_[2] - P_[0]).dot(Vector(want)) < 0: pts3, uvs = pts3[::-1], uvs[::-1]
    GEO.setdefault((part, key), []).append((pts3, list(uvs)))
    MOSS_A.setdefault((part, key), []).append([alpha] * len(pts3))

SCAR_TONE = {}   # a chip's scar points (notched_box) -> their shade: the age pass multiplies it in, light at the broken rim, dark in the hollow

def notched_box(key, p0, p1, w, z0, z1, breaks, seed="pier chip"):
    """obox's block with its arris at p0's end on its right knocked (the stair's gate piers: a chipped corner block
    and a hairline crack; the first build's lens cut, smoothed round, read as a perfectly round hole, nothing like real
    damage). As a knock breaks an arris (the conservators' "snip", ASTM C119: the concave scar a chip leaves): long
    along the edge and shallow into the faces, widest off-centre where the blow landed, its outline rough at every scale and unlike on the two faces,
    its scar a hollow of flat facets whose ridges run on from row to row, never smoothed; smaller nicks along the same edge. On its own texture,
    freshly split stone (break, AGH2XStoneBreak: Bethesda's broken stone is a second texture, Fallout 3's edges).
    breaks: [(J, rows)], low to high, apart: J the foot's height; rows [(dz over J, into the side face, into the front face)], 0, 0 at the top row
    (where the arris resumes) and at the foot of a nick; a foot that is not 0, 0 stands on a bed joint (J one of the face's own coursing), the
    block below left as a small ledge. The collision the whole block"""
    p0, p1 = Vector((p0[0], p0[1], 0)), Vector((p1[0], p1[1], 0))
    d = (p1 - p0).normalized(); s = Vector((-d.y, d.x, 0))
    c = [p0 - s * w / 2, p1 - s * w / 2, p1 + s * w / 2, p0 + s * w / 2]
    lo = [Vector((q.x, q.y, z0)) for q in c]; hi = [Vector((q.x, q.y, z1)) for q in c]
    for f in [hi, lo[::-1]] + [[lo[i], lo[(i + 1) % 4], hi[(i + 1) % 4], hi[i]] for i in range(4)]: coll_quad(f)
    poly(key, hi); poly(key, lo[::-1])
    for i in (1, 2): poly(key, [lo[i], lo[(i + 1) % 4], hi[(i + 1) % 4], hi[i]])           # the back and the far side, whole
    A = lambda u, v, z: Vector((c[0].x, c[0].y, z)) + d * u + s * v      # u into the near side face (along d), v across the front (along s)
    R = random.Random(seed)
    def rough(rows):
        """the outline rough at every scale, as a break's edge is: each run halved twice, its midpoint knocked off the straight by a seeded amount
        in proportion to the break (the first build's long straight runs read as a cut); the ends stay where they are"""
        size_ = max(max(q[1], q[2]) for q in rows)
        for amp_ in (0.08 * size_, 0.045 * size_):
            dense_ = [rows[0]]
            for (z_, a_, b_), (z2_, a2_, b2_) in zip(rows, rows[1:]):
                k_ = 0.5 if (a_ == 0 and b_ == 0) or (a2_ == 0 and b2_ == 0) else 1.0
                dense_.append(((z_ + z2_) / 2 + R.uniform(-0.15, 0.15) * (z2_ - z_), max(0.3, (a_ + a2_) / 2 + R.uniform(-amp_, amp_) * k_),
                               max(0.3, (b_ + b2_) / 2 + R.uniform(-amp_, amp_) * k_)))
                dense_.append((z2_, a2_, b2_))
            rows = dense_
        return rows
    breaks = [(J_, rough(rows_)) for J_, rows_ in breaks]
    am = max(q[1] for _, r_ in breaks for q in r_) + 1; bm = max(q[2] for _, r_ in breaks for q in r_) + 1
    D_ = (p1 - p0).length
    def face(pts, want): poly(key, facing(pts, want))
    # the front face (v 0..w at u 0) and the near side (u 0..D_ at v 0): beyond the breaks' widest, whole; within it, whole between the breaks
    # and the strips between each break's edge and that line
    face([A(0, bm, z0), A(0, w, z0), A(0, w, z1), A(0, bm, z1)], -d); face([A(D_, 0, z0), A(am, 0, z0), A(am, 0, z1), A(D_, 0, z1)], -s)
    gaps_ = [z0] + [z_ for J_, r_ in breaks for z_ in (J_, J_ + r_[-1][0])] + [z1]
    for za_, zb_ in zip(gaps_[::2], gaps_[1::2]):
        face([A(0, 0, za_), A(0, bm, za_), A(0, bm, zb_), A(0, 0, zb_)], -d); face([A(0, 0, za_), A(am, 0, za_), A(am, 0, zb_), A(0, 0, zb_)], -s)
    out = (d + s).normalized(); br_ = (d - s).normalized(); K_ = 3
    TS = 48.0                                                            # (the split stone's grain at its own size: a tile in 48 units)
    uv_ = lambda q_: (q_.dot(br_) / TS, q_.z / TS)                      # (one projection across the arris for the whole break)
    def face_n(pts, want):                                              # (wound by its whole outline's normal: a concave face's first three
        n_ = Vector((0, 0, 0))                                          # corners may turn the wrong way; and, either way round, begun at its
        for k_ in range(len(pts)): n_ += pts[k_ - 1].cross(pts[k_])     # two square corners, as the age pass reads a face's normal off its
        poly(key, pts if n_.dot(Vector(want)) >= 0 else [pts[1], pts[0]] + pts[2:][::-1])   # first three: begun on the broken edge, it shaded
                                                                        # the face as unseen, 0.3)
    for J, rows in breaks:
        # beside the break's edge, to its own widest and on to the breaks' widest: one face each side, its edge the break's (a strip a row,
        # the second build's, took the age pass's shade row by row and streaked the stone beside the nicks)
        bmb_ = max(q[2] for q in rows) + 1; amb_ = max(q[1] for q in rows) + 1; H_ = rows[-1][0]
        face_n([A(0, bmb_, J), A(0, bmb_, J + H_)] + [A(0, b_, J + z_) for z_, a_, b_ in reversed(rows)], -d)
        face_n([A(amb_, 0, J), A(amb_, 0, J + H_)] + [A(a_, 0, J + z_) for z_, a_, b_ in reversed(rows)], -s)
        if bmb_ < bm: face([A(0, bmb_, J), A(0, bm, J), A(0, bm, J + H_), A(0, bmb_, J + H_)], -d)
        if amb_ < am: face([A(amb_, 0, J), A(am, 0, J), A(am, 0, J + H_), A(amb_, 0, J + H_)], -s)
        # the scar: each row a line from its side edge to its front edge through three points pushed in off the chord, a hollow (a knock leaves a
        # scoop, not a plane across the corner: the first build's two shallow points read flat), deepest where the break is widest, the three by
        # depths and places set at knots every 4-6 units up the break and run straight between them, so the scar breaks into broad flat facets
        # that meet in ridges at the knots (each row's own random depth, the second build's, banded the scar in ruled lines a row apart); rows
        # joined in triangles, each its own flat facet
        ring = []; H_ = rows[-1][0]; kz_ = [0.0]
        while kz_[-1] < H_: kz_.append(min(H_, kz_[-1] + R.uniform(4.0, 6.0)))
        kt_ = [[min(0.88, max(0.12, b0_ + R.uniform(-0.12, 0.12))) for b0_ in (0.25, 0.5, 0.75)] for _ in kz_]
        km_ = [[R.uniform(0.4, 1.6) for _ in range(K_)] for _ in kz_]
        def at_(z_, tab_):
            j_ = max(0, min(len(kz_) - 2, next((j for j in range(len(kz_) - 1) if z_ <= kz_[j + 1]), len(kz_) - 2)))
            f_ = (z_ - kz_[j_]) / max(1e-6, kz_[j_ + 1] - kz_[j_])
            return [x0 + (x1 - x0) * f_ for x0, x1 in zip(tab_[j_], tab_[j_ + 1])]
        wide_ = max(q[1] + q[2] for q in rows)
        chs_ = [(A(a_, 0, 0) - A(0, b_, 0)).length for _, a_, b_ in rows]
        for i_, (z_, a_, b_) in enumerate(rows):
            if a_ == 0 and b_ == 0: ring.append([A(0, 0, J + z_)] * (K_ + 2)); continue
            e0, e1 = A(a_, 0, J + z_), A(0, b_, J + z_)
            win_ = chs_[max(0, i_ - 3):i_ + 4]; ch_ = sum(win_) / len(win_)   # (the break's width about this row, not its edge's every jag)
            deep = ch_ * (0.2 + 0.25 * (a_ + b_) / wide_)
            mid = []
            for t_, m_ in zip(sorted(at_(z_, kt_)), at_(z_, km_)):
                bow_ = 4 * t_ * (1 - t_)                                 # (a hollow: deepest mid-way, nothing at the edges)
                q_ = e0.lerp(e1, t_) + out * deep * bow_ * m_
                # (its shade by how far it lies inside the corner: a scar holds shadow and grime in its hollow, its rim catches the light; the
                # first renders' scar, all one tone, read as a pale patch laid on the stone, not a hole in it)
                in_ = min((q_ - A(0, 0, q_.z)).dot(d), (q_ - A(0, 0, q_.z)).dot(s))
                SCAR_TONE[tuple(round(v, 1) for v in q_)] = 1.0 - 0.3 * min(1.0, max(0.0, in_) / 5.0)
                mid.append(q_)
            ring.append([e0] + mid + [e1])
        for r0, r1 in zip(ring, ring[1:]):
            for k_ in range(K_ + 1):
                for t3 in ([r0[k_], r0[k_ + 1], r1[k_ + 1]], [r0[k_], r1[k_ + 1], r1[k_]]):
                    if (t3[1] - t3[0]).cross(t3[2] - t3[0]).length < 1e-4: continue      # (an end row is one point)
                    t3 = facing(t3, -out); poly("break", t3, [uv_(q_) for q_ in t3])
        if rows[0][1] or rows[0][2]:                                     # the ledge: the bed under a broken foot, the block below's top
            for q0_, q1_ in zip(ring[0], ring[0][1:]):                   # (in triangles from the arris's foot: the hollow's edge makes it concave)
                fl_ = facing([A(0, 0, J), q0_, q1_], (0, 0, 1)); poly("break", fl_, [(q_.dot(d) / TS, q_.dot(s) / TS) for q_ in fl_])   # (flat: its own two axes)

STONE_BEDS = (29.4, 65.6, 98.4, 130.4, 161.9, 192.8, 223.6, 253.4)   # AGH2XStone's eight bed joints in a tile (its rows' darkest lines,
def bed_under(z):                                                       # measured): a wall's texture runs v = z / 256 (poly)
    """the highest bed joint of the stone's coursing at or under z"""
    return max(256 * math.floor((z - b_) / 256) + b_ for b_ in STONE_BEDS)

# each course's head joints in the tile, by the bed under it (measured on the texture: the darkest columns of its middle rows), as u units along
# a face (poly: u = p . (UP x n) over 256)
STONE_HEADS = {29.4: (25.4, 114.6, 206.4), 65.6: (2.9, 23.6, 60.9, 93.0, 177.8, 247.4), 98.4: (25.2, 129.9, 204.1), 130.4: (0.0, 69.9, 136.4, 176.2),
               161.9: (28.5, 115.5, 185.0, 210.5), 192.8: (12.5, 88.1, 163.2, 240.6), 223.6: (28.8, 103.5, 130.6, 210.8, 224.4),
               253.4: (55.4, 84.8, 169.9, 185.6, 242.1)}
def head_into(corner, t, z, want):
    """how far into a face (from corner, along t as its texture's u runs, or against it if t is negative-going: pass the face's own u axis
    and +1/-1 in want's sign) the course at z has its head joint nearest to abs(want): a block's corner goes whole, to its joint"""
    bed_ = min(STONE_BEDS, key=lambda b_: (z - b_) % 256)
    u0_ = corner.dot(t); sg_ = 1 if want > 0 else -1
    cands_ = [((h_ - u0_) * sg_) % 256 for h_ in STONE_HEADS[bed_]]
    return min(cands_, key=lambda x_: abs(x_ - abs(want)))

def broken_box(key, p0, p1, w, z0, z1, Uc, Vc, seed, coll=True, bottom=True, whole_u=False, whole_v=False):
    """obox's block with the quarter at p0's end on its right broken away, Uc along the block and Vc across it (the
    gate pier's chip was too small: a full quarter of the pillar's top removed, the cap and the top courses of that quarter, the
    stone cleared away). Stacked one a course, they step back as ashlar fails: the blocks of a corner go whole at their beds, the faces where
    they tore from the rest broken. A face at a head joint (whole_u: the one at u ~ Uc, whole_v: at v ~ Vc) is a flat block side in the stone's
    own texture; a face where a block snapped is rough at a knot every 5-7 units, flat facets between (as the chip's scar), its edges on the outer
    face and the top jagged with it, on the break's own texture. The collision the two boxes that remain"""
    p0, p1 = Vector((p0[0], p0[1], 0)), Vector((p1[0], p1[1], 0))
    d = (p1 - p0).normalized(); s = Vector((-d.y, d.x, 0)); D_ = (p1 - p0).length
    c = [p0 - s * w / 2, p1 - s * w / 2, p1 + s * w / 2, p0 + s * w / 2]
    A = lambda u, v, z: Vector((c[0].x, c[0].y, z)) + d * u + s * v
    R = random.Random(seed)
    def knots(lo_, hi_):
        k_ = [lo_]
        while k_[-1] < hi_: k_.append(min(hi_, k_[-1] + R.uniform(5.0, 7.0)))
        return k_
    zs_ = knots(z0, z1); us_ = knots(0.0, Uc); vs_ = knots(0.0, Vc)
    amp_ = min(Uc, Vc) * 0.09 + 1.0; au_ = 0.0 if whole_u else amp_; av_ = 0.0 if whole_v else amp_
    cu_ = [R.uniform(-au_, au_) for _ in zs_]; cv_ = [R.uniform(-av_, av_) for _ in zs_]     # the inner corner's line, up the break
    # face 1 (its remaining stone at v > Vc, facing -s): columns along u, the last the inner corner; face 2 (u > Uc, facing -d) likewise along v
    F1 = [[A(min(u_, Uc) + (cu_[i] if k == len(us_) - 1 else 0), Vc + (cv_[i] if k == len(us_) - 1 else R.uniform(-av_, av_)), z_)
           for k, u_ in enumerate(us_)] for i, z_ in enumerate(zs_)]
    F2 = [[A(Uc + (cu_[i] if k == len(vs_) - 1 else R.uniform(-au_, au_)), min(v_, Vc) + (cv_[i] if k == len(vs_) - 1 else 0), z_)
           for k, v_ in enumerate(vs_)] for i, z_ in enumerate(zs_)]
    def fn(pts, want, k_=key):                                          # (wound by its whole outline's normal; begun at a square corner either
        n_ = Vector((0, 0, 0))                                          # way round, as the age pass reads a face's normal off its first three)
        for j_ in range(len(pts)): n_ += pts[j_ - 1].cross(pts[j_])
        poly(k_, pts if n_.dot(Vector(want)) >= 0 else [pts[1], pts[0]] + pts[2:][::-1])
    T = len(zs_) - 1
    # the outer faces: the front (u 0, facing -d) to its jagged edge at v ~ Vc, the near side (v 0, facing -s) to u ~ Uc; the back two whole
    fn([A(0, w, z0), A(0, w, z1)] + [F1[i][0] for i in range(T, -1, -1)], -d)
    fn([A(D_, 0, z0), A(D_, 0, z1)] + [F2[i][0] for i in range(T, -1, -1)], -s)
    for f_ in ([A(D_, 0, z0), A(D_, w, z0), A(D_, w, z1), A(D_, 0, z1)], [A(D_, w, z0), A(0, w, z0), A(0, w, z1), A(D_, w, z1)]):
        poly(key, f_)
    # the top (and the bottom, under an overhang): the L that remains, its inner edge the broken faces' top (bottom) row
    for zi_, want_ in ((T, (0, 0, 1)),) + (((0, (0, 0, -1)),) if bottom else ()):
        z_ = zs_[zi_]
        fn([A(D_, 0, z_), A(D_, w, z_), A(0, w, z_)] + F1[zi_] + F2[zi_][::-1][1:], want_)
    # the broken faces: triangles over the grid, each its own flat facet
    for G, want_, flat_ in ((F1, -s, whole_v), (F2, -d, whole_u)):
        for i in range(T):
            for k in range(len(G[0]) - 1):
                for t3 in ([G[i][k], G[i][k + 1], G[i + 1][k + 1]], [G[i][k], G[i + 1][k + 1], G[i + 1][k]]):
                    if (t3[1] - t3[0]).cross(t3[2] - t3[0]).length < 1e-4: continue
                    t3 = facing(t3, want_); poly(key, t3) if flat_ else poly("break", t3, [(q_.dot(d - s) / 48.0, q_.z / 48.0) for q_ in t3])
                    if not flat_:                                       # (an old break, weathered back toward the stone's own tone: 0.95 x 0.8; the
                        for q_ in t3: SCAR_TONE[tuple(round(v, 1) for v in q_)] = 0.8   # fresh chip's paleness over this much face read as plaster)
    if coll:                                                            # what remains: the far part whole, the near part beside the break
        for lo_u, hi_u, lo_v, hi_v in ((Uc, D_, 0, w), (0, Uc, Vc, w)):
            q_ = [A(lo_u, lo_v, 0), A(hi_u, lo_v, 0), A(hi_u, hi_v, 0), A(lo_u, hi_v, 0)]
            lo = [Vector((v_.x, v_.y, z0)) for v_ in q_]; hi = [Vector((v_.x, v_.y, z1)) for v_ in q_]
            for f in [hi, lo[::-1]] + [[lo[i], lo[(i + 1) % 4], hi[(i + 1) % 4], hi[i]] for i in range(4)]: coll_quad(f)

def moss_ribbon(path, z, side, base_w, seed=0.0, part="site", step=24.0, period=70.0):
    """SMoss01 laid on paving along a wall's foot, as vanilla lays it: path is the foot line (hall frame 2D), the paving on
    its left (side +1) or right (-1). The ribbon's width wanders between 0.55 and 1.45 of base_w and widens in the
    corners; alpha is 1 at the wall (itself uneven), 0.5 at mid-width, 0 at the outer edge, with the ends faded. The moss
    shader (Decal) keeps it off the paving's depth."""
    P = [Vector((q[0], q[1], 0)) for q in path]
    pts, sv, corner = [], [], []
    acc = 0.0
    for i in range(len(P) - 1):
        a, b = P[i], P[i + 1]; L = (b - a).length; k = max(1, math.ceil(L / step))
        for j in range(k):
            pts.append(a.lerp(b, j / k)); sv.append(acc + L * j / k); corner.append(j == 0 and i > 0)
        acc += L
    pts.append(P[-1]); sv.append(acc); corner.append(False)
    Ltot = acc
    nrm = lambda d: Vector((-d.y, d.x, 0)) * side
    cs_ = [sv[i] for i in range(len(pts)) if corner[i]]
    rows = []
    for i, p_ in enumerate(pts):
        dp_ = (pts[i] - pts[i - 1]).normalized() if i > 0 else None
        dn_ = (pts[i + 1] - pts[i]).normalized() if i < len(pts) - 1 else None
        if dp_ is None: m, sc = nrm(dn_), 1.0
        elif dn_ is None: m, sc = nrm(dp_), 1.0
        else:
            n1 = nrm(dp_); m = n1 + nrm(dn_)
            m = n1 if m.length < 1e-6 else m.normalized(); sc = 1.0 / max(0.35, m.dot(n1))
        w = base_w * (0.55 + 0.9 * _n1(sv[i] / period, seed))
        for c in cs_: w += 30 * max(0.0, 1 - abs(sv[i] - c) / 80)
        fade = min(1.0, sv[i] / 60.0, (Ltot - sv[i]) / 60.0) if Ltot > 120 else 0.6
        aw = (0.7 + 0.3 * _n1(sv[i] / 23.0, seed + 3)) * fade
        rows.append([(p_, aw), (p_ + m * w * sc * 0.45, 0.5 * aw), (p_ + m * w * sc, 0.0)])
    for i in range(len(rows) - 1):
        for r in range(2):
            q = [rows[i][r], rows[i + 1][r], rows[i + 1][r + 1], rows[i][r + 1]]
            moss_quad(part, [(v[0].x, v[0].y, z) for v in q], [v[1] for v in q])

def beam(p0, p1, w, deep, nrm, key="wood", back=True):
    """A squared timber from p0 to p1, w wide in the wall plane, deep out along nrm (unit), grain along its length; every
    face looks out, the back too (back=False: it lies on a face that hides it)."""
    p0, p1, nrm = Vector(p0), Vector(p1), Vector(nrm)
    a = (p1 - p0); L = a.length
    if L < 1e-6: return
    a.normalize(); s = nrm.cross(a).normalized() * (w / 2)
    c = [p0 - s, p1 - s, p1 + s, p0 + s]
    front = [p + nrm * deep for p in c]
    def put(pts, along):
        q = [Vector(x) for x in pts]
        uv = [((x - p0).dot(a) / S, (x - p0).dot(along) / S) for x in q]
        poly(key, q, uv)
    put(front, s.normalized())
    if FIX_FACES:   # (the sides and ends faced in until 2026-10-25: every shape is one-sided in game; see FIX_FACES)
        put([c[0], c[1], front[1], front[0]], nrm); put([c[2], c[3], front[3], front[2]], nrm)
        put([c[3], c[0], front[0], front[3]], nrm); put([c[1], c[2], front[2], front[1]], nrm)
        if back: put(c[::-1], s.normalized())
    else:
        put([c[1], c[0], front[0], front[1]], nrm); put([c[3], c[2], front[2], front[3]], nrm)
        put([c[0], c[3], front[3], front[0]], nrm); put([c[2], c[1], front[1], front[2]], nrm)

def wall_beam(W, a, b, w=18, deep=8, d0=0, key="wood"):
    o, r, n = W
    beam(o + r * a[0] + UP * a[1] + n * d0, o + r * b[0] + UP * b[1] + n * d0, w, deep, n, key=key, back=d0 > 0)

def wall_brace(W, a, b, box_uz, w=14, deep=6, d0=0.0):
    """A brace from a to b (wall u, z) cut square to the rectangle box_uz (u0, u1, z0, z1): where braces meet, each
    stops at the joint instead of passing through the others (a mitred joint, and no faces fighting in one plane)."""
    o, r, n = W
    du, dz = b[0] - a[0], b[1] - a[1]; L = math.hypot(du, dz)
    if L < 1e-6: return
    tu, tz = du / L, dz / L; su, sz = -tz * w / 2, tu * w / 2
    P = [(a[0] - su, a[1] - sz), (b[0] - su, b[1] - sz), (b[0] + su, b[1] + sz), (a[0] + su, a[1] + sz)]
    u0, u1, z0, z1 = box_uz
    for k, lim, keep in ((0, u0, 1), (0, u1, -1), (1, z0, 1), (1, z1, -1)):     # Sutherland-Hodgman against each side
        out = []
        for i in range(len(P)):
            c, d = P[i - 1], P[i]
            ci, di = (c[k] - lim) * keep >= 0, (d[k] - lim) * keep >= 0
            if di:
                if not ci: t = (lim - c[k]) / (d[k] - c[k]); out.append((c[0] + (d[0] - c[0]) * t, c[1] + (d[1] - c[1]) * t))
                out.append(d)
            elif ci: t = (lim - c[k]) / (d[k] - c[k]); out.append((c[0] + (d[0] - c[0]) * t, c[1] + (d[1] - c[1]) * t))
        P = out
        if len(P) < 3: return
    back = [o + r * u + UP * z + n * d0 for u, z in P]; front = [q + n * deep for q in back]
    gu = lambda q: ((q - o).dot(r) * tu + q.z * tz) / S          # grain along the brace
    gv = lambda q: ((q - o).dot(r) * -tz + q.z * tu) / S
    f = front if (r.cross(UP)).dot(n) > 0 else front[::-1]           # P runs anticlockwise in (u, z): wound to face out
    poly("wood", f, [(gu(q), gv(q)) for q in f])
    for i in range(len(P)):
        q0, q1 = back[i - 1], back[i]; side = [q0, q1, q1 + n * deep, q0 + n * deep]
        if (q1 - q0).cross(n).dot(sum(back, Vector()) / len(back) - q0) > 0: side = side[::-1]
        poly("wood", side, [(gu(q), (q - q0).dot(n) / S) for q in side])

# ---------------------------------------------------------------- building parts
def walls_of(x0, y0, x1, y1):
    """The four walls of a rectangle, each (origin, right, out), with its length."""
    return {"front": ((Vector((x0, y0, 0)), Vector((1, 0, 0)), Vector((0, -1, 0))), x1 - x0),
            "right": ((Vector((x1, y0, 0)), Vector((0, 1, 0)), Vector((1, 0, 0))), y1 - y0),
            "back": ((Vector((x1, y1, 0)), Vector((-1, 0, 0)), Vector((0, 1, 0))), x1 - x0),
            "left": ((Vector((x0, y1, 0)), Vector((0, -1, 0)), Vector((-1, 0, 0))), y1 - y0)}

def stone_storey(x0, y0, x1, y1, z0, z1, windows=None, plinth=True, name="", abut=None, plinth_y1=None, door=None):
    """Ashlar ground storey: plinth course, wall, string course on top. windows: {side: [(u_centre, kind, w, h, sill)]}
    abut: "left" or "right", the end that stands against another storey with its own plinth and course: there they stop
    at that storey's (they would lie in its plinth's and course's planes). plinth_y1: where the plinth stops at the back,
    when the storey's back runs into another storey whose plinth takes over there. door: (x_left, x_right) of a doorway
    in the front wall, where the plinth's front stops (its ends die into the door's pilasters): run across it, it stood
    50 high over the door's foot and blocked the way in"""
    box("stone", (x0, y0, z0), (x1, y1, z1)); coll_box((x0, y0, z0), (x1, y1, z1))
    pl0, pl1 = (x0 + 12 if abut == "left" else x0 - 12), (x1 - 12 if abut == "right" else x1 + 12)
    sc0, sc1 = (x0 + 14 if abut == "left" else x0 - 14), (x1 - 14 if abut == "right" else x1 + 14)
    py1 = y1 + 12 if plinth_y1 is None else plinth_y1
    if plinth:
        parts = [(pl0, y0 - 12, pl1)] if not door else [(pl0, y0 - 12, door[0]), (door[0], y0 + 2, door[1]), (door[1], y0 - 12, pl1)]
        for a0, b0, a1 in parts:                        # (behind the doorway the plinth runs on inside the wall)
            box("base", (a0, b0, z0 - 40), (a1, py1, z0 + 50)); coll_box((a0, b0, z0 - 40), (a1, py1, z0 + 50))
    box("trim", (sc0, y0 - 14, z1 - 6), (sc1, y1 + 14, z1 + 18))
    for side, items in (windows or {}).items():
        W, L = walls_of(x0, y0, x1, y1)[side]
        for (uc, kind, w, h, sill) in items:
            key, rect = ATLAS[kind]; h = w * RATIO[kind]
            WHERE[0] = f"{name} {side}"
            if glazed(f"{WHERE[0]} {kind} u{round(uc)}"): glaze(W, uc, z0 + sill, w, h, kind, 1.0, "out")
            else: quad_on(W, uc - w / 2, z0 + sill, uc + w / 2, z0 + sill + h, 1.0, key, rect, kind=kind)
            register(kind, W, uc - w / 2, z0 + sill, uc + w / 2, z0 + sill + h, 1.0)
            o, r, n = W  # a projecting stone sill
            c = o + r * uc + UP * (z0 + sill)
            box("trim", tuple(min(a, b) for a, b in zip(c - r * (w / 2 + 10) - UP * 14, c + r * (w / 2 + 10) + n * 14)),
                tuple(max(a, b) for a, b in zip(c - r * (w / 2 + 10) - UP * 14, c + r * (w / 2 + 10) + n * 14)))

def board_shutters(W, uc, w, zb, h):
    """Board shutters standing open: two plank leaves hung on the window's jamb posts (at their outer faces, uc +- (w/2 +
    18)) and folded back flat on the infill. Open, a leaf shows its inside: two ledges and a brace rising from the hinge
    side; iron knuckles at the hinge, an iron stay at the free edge holding it to the wall. Returns the leaves' u ranges."""
    lw = w / 2 + 9; out = []
    for s_ in (-1, 1):
        hinge = uc + s_ * (w / 2 + 18); free = hinge + s_ * lw
        a_, b_ = sorted((hinge, free))
        wall_beam(W, ((a_ + b_) / 2, zb), ((a_ + b_) / 2, zb + h), w=b_ - a_, deep=4, d0=1, key="planks")
        za, zc = zb + h * 0.17, zb + h * 0.83
        for zz in (za, zc): wall_beam(W, (a_ + 3, zz), (b_ - 3, zz), w=12, deep=3, d0=5)          # ledges
        wall_brace(W, (hinge + s_ * 7, za + 6), (free - s_ * 7, zc - 6), (a_ + 3, b_ - 3, za + 6, zc - 6), w=10, deep=3, d0=5)
        o, r, n = W
        for zz in (za, zc):                                   # hinge knuckles (4 either side: past the ledges' ends at 3,
            c = o + r * hinge + UP * zz                       # which would otherwise share the knuckle's face)
            box("metal", tuple(min(p_, q_) for p_, q_ in zip(c - r * 4 - UP * 7, c + r * 4 + UP * 7 + n * 9)),
                tuple(max(p_, q_) for p_, q_ in zip(c - r * 4 - UP * 7, c + r * 4 + UP * 7 + n * 9)))
        c = o + r * (free + s_ * 3) + UP * (zb + h * 0.5)    # the stay
        box("metal", tuple(min(p_, q_) for p_, q_ in zip(c - r * 3 - UP * 3, c + r * 3 + UP * 3 + n * 8)),
            tuple(max(p_, q_) for p_, q_ in zip(c - r * 3 - UP * 3, c + r * 3 + UP * 3 + n * 8)))
        register("shutter", W, a_, zb, b_, zb + h, 5)
        out.append((a_ - 4, b_ + 4))
    return out

def timber_storey(x0, y0, x1, y1, z0, z1, windows=None, braces=True, sides=("front", "right", "back", "left"), posts_at=None, name=""):
    """Half-timbered storey: stucco infill, sill and wall plates, posts at the corners, at the bay posts given by hand
    (posts_at: {side: [u]}) and as jambs beside every opening, K-braces only in blank panels.
    windows: {side: [(u_centre, kind, w, h, sill[, opts])]}; opts {"shutters": True} hangs board shutters on its jambs.
    A doorway stops the sill plate; a window rising past the wall plate (the great window) stops the wall plate."""
    coll_box((x0, y0, z0), (x1, y1, z1))
    poly("wood", [(x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (x1, y0, z0)])      # the soffit, facing down
    for side in ("front", "right", "back", "left"):
        (o, r, n), L = walls_of(x0, y0, x1, y1)[side]
        pts = [o + UP * z0, o + r * L + UP * z0, o + r * L + UP * z1, o + UP * z1]
        u_off = (o.x + o.y) / S
        poly("stucco", pts, [(u_off, 0), (u_off + L / S, 0), (u_off + L / S, 1), (u_off, 1)])
    windows = windows or {}
    def minus(runs, cuts):
        for a_, b_ in cuts: runs = [q for r0, r1 in runs for q in ((r0, min(r1, a_)), (max(r0, b_), r1)) if q[1] - q[0] > 1]
        return runs
    for side in sides:
        WHERE[0] = f"{name} {side}"
        W, L = walls_of(x0, y0, x1, y1)[side]
        e0, e1 = (-10, L + 10) if side in ("front", "back") else (0, L)  # the front and back plates cover the corners
        items = []
        for it in windows.get(side, []):
            uc, kind, w, h, sill = it[:5]; opts = it[5] if len(it) > 5 else {}
            if kind not in ("opening", "glazed_door", "blank"): h = w * RATIO[kind]
            items.append((uc, kind, w, h, sill, opts))
        doors = [(uc - w / 2, uc + w / 2) for uc, kind, w, h, sill, _ in items if kind in ("opening", "glazed_door") and sill < 20]   # (between the posts: they stand on the sill, so no gaps at the bottom)
        tall = [(uc - w / 2 - 9, uc + w / 2 + 9) for uc, kind, w, h, sill, _ in items if z0 + sill + h > z1 - 20]
        for r0, r1 in minus([(e0, e1)], doors): wall_beam(W, (r0, z0 + 10), (r1, z0 + 10), w=20, deep=10)    # sill plate
        for r0, r1 in minus([(e0, e1)], tall): wall_beam(W, (r0, z1 - 10), (r1, z1 - 10), w=20, deep=10)     # wall plate
        posts = {9.0, L - 9.0} | set((posts_at or {}).get(side, []))
        busy = []                                          # u ranges no brace may cross: openings, jambs, shutter leaves
        for (uc, kind, w, h, sill, opts) in items:
            if kind == "blank":                                 # a plain panel kept clear (the crest hangs on it)
                busy.append((uc - w / 2, uc + w / 2)); continue
            if kind == "opening":                               # a doorway: dark reveal; the door itself is a placed piece
                quad_on(W, uc - w / 2, z0 + sill, uc + w / 2, z0 + sill + h, 0.6, "wood")
                register("door", W, uc - w / 2, z0 + sill, uc + w / 2, z0 + sill + h, 0.6)
            elif kind == "glazed_door":                         # two glazed leaves meeting on a stile
                for s_ in (-1, 1):
                    a_, b_ = sorted((uc + s_ * 3, uc + s_ * w / 2))
                    if glazed(f"{WHERE[0]} door leaf u{round((a_ + b_) / 2)}"): glaze(W, (a_ + b_) / 2, z0 + sill, b_ - a_, h, "panes", 1.5, "out")
                    else: quad_on(W, a_, z0 + sill, b_, z0 + sill + h, 1.5, *ATLAS["panes"], kind="panes")
                    register("door leaf", W, a_, z0 + sill, b_, z0 + sill + h, 1.5)
                wall_beam(W, (uc, z0 + sill), (uc, z0 + sill + h), w=6, deep=4)
            else:
                key, rect = ATLAS[kind]
                if glazed(f"{WHERE[0]} {kind} u{round(uc)}"): glaze(W, uc, z0 + sill, w, h, kind, 1.5, "out")
                else: quad_on(W, uc - w / 2, z0 + sill, uc + w / 2, z0 + sill + h, 1.5, key, rect, kind=kind)
                register(kind, W, uc - w / 2, z0 + sill, uc + w / 2, z0 + sill + h, 1.5)
                if opts.get("shutters"): busy += board_shutters(W, uc, w, z0 + sill, h)
            posts |= {uc - w / 2 - 9, uc + w / 2 + 9}
            busy.append((uc - w / 2 - 22, uc + w / 2 + 22))
            if kind not in ("opening", "glazed_door"):
                wall_beam(W, (uc - w / 2 - 22, z0 + sill - 8), (uc + w / 2 + 22, z0 + sill - 8), w=16, deep=12)  # sill
            wall_beam(W, (uc - w / 2 - 22, z0 + sill + h + 8), (uc + w / 2 + 22, z0 + sill + h + 8), w=16, deep=11)  # lintel
        ps = sorted(posts)
        for u in ps: wall_beam(W, (u, z0 + 18), (u, z1 - 18), w=18, deep=8)
        if braces:
            for a, b in zip(ps, ps[1:]):
                if b - a < 150: continue
                if any(b0 < b - 9 and b1 > a + 9 for b0, b1 in busy): continue
                m = (a + b) / 2; zm = (z0 + z1) / 2  # braces meeting at mid-height: the Solitude chevron, mitred at the joint
                wall_brace(W, (a + 9, z0 + 18), (m, zm), (a + 9, m, z0 + 18, zm))
                wall_brace(W, (b - 9, z0 + 18), (m, zm), (m, b - 9, z0 + 18, zm))
                wall_brace(W, (m, zm), (a + 9, z1 - 18), (a + 9, m, zm, z1 - 18))
                wall_brace(W, (m, zm), (b - 9, z1 - 18), (m, b - 9, zm, z1 - 18))

def jetty_joists(W, L, z, step=48, out=None):
    """Joist ends showing under an overhanging upper storey."""
    o, r, n = W; out = J if out is None else out
    u = step / 2
    while u < L:
        c = o + r * u + UP * z
        lo = c - r * 7 - UP * 14; hi = c + r * 7 + n * out
        box("wood", tuple(min(a, b) for a, b in zip(lo, hi)), tuple(max(a, b) for a, b in zip(lo, hi)))
        u += step

ROOF_PLAN = []    # (plan polygon (x, y), lowest z of the roof's top): what each roof covers, for roof_cover_check.py
ROOF_FILL = os.environ.get("AG_ROOF_FILL", "1") != "0"     # 0: the roofs as before the valley fill (roof_cover_check's own test)

def gable_roof(x0, y0, x1, y1, z, pitch, axis, over=36, verge=30, th=14, key="roof", gable_ends=True, notch=()):
    """A pitched roof on the rectangle, ridge along axis ('x' or 'y'), eaves at z. Returns the ridge height.
    gable_ends: True, False, or the ends to close (("front", "back") for axis y, ("left", "right") for axis x).
    notch (axis x): [(slope -1 front / +1 back, x from, x to[, valleys])] where the eave stops at the wall line, because a
    gable breaks through the eave there (a cross gable, a porch) and its roof takes over. valleys (abut_valleys): where
    that roof meets this slope; wherever one runs below this slope's lower edge (near its eave corners it does), the
    slope is carried down to it, so the two roofs meet with no sky between them."""
    if axis == "y":
        half = (x1 - x0) / 2; h = half * math.tan(math.radians(pitch)); xm = (x0 + x1) / 2
        rise = over * math.tan(math.radians(pitch))
        ya, yb = y0 - verge, y1 + verge
        ROOF_PLAN.append(([(x0 - over, ya), (x1 + over, ya), (x1 + over, yb), (x0 - over, yb)], z - rise))
        for sgn, xe in ((-1, x0 - over), (1, x1 + over)):
            lo_z = z - rise
            top = [(xe, ya, lo_z), (xm, ya, z + h), (xm, yb, z + h), (xe, yb, lo_z)]
            if sgn > 0: top = [top[1], top[0], top[3], top[2]]
            poly(key, top); coll_quad(top)
            bot = [(p[0], p[1], p[2] - th) for p in top][::-1]
            poly("wood", bot)
            poly("wood", [(xe, ya, lo_z - th), (xe, yb, lo_z - th), (xe, yb, lo_z), (xe, ya, lo_z)][::(1 if sgn < 0 else -1)])
            # bargeboards along the rakes
            for yy, nn in ((ya, (0, -1, 0)), (yb, (0, 1, 0))):
                beam((xe, yy, lo_z - 8), (xm, yy, z + h - 8), 22, 6 if sgn < 0 else 7, nn)
        if gable_ends:
            for yy, nrm, nm in ((y0, -1, "front"), (y1, 1, "back")):
                if gable_ends is not True and nm not in gable_ends: continue
                poly("stucco", [(x0, yy, z), (x1, yy, z), (xm, yy, z + h)][::(1 if nrm < 0 else -1)]); coll_tri((x0, yy, z), (x1, yy, z), (xm, yy, z + h))
        box("wood", (xm - 10, ya, z + h - 12), (xm + 10, yb, z + h + 10))  # ridge cap
        return z + h
    else:
        half = (y1 - y0) / 2; h = half * math.tan(math.radians(pitch)); ym = (y0 + y1) / 2
        rise = over * math.tan(math.radians(pitch))
        xa, xb = x0 - verge, x1 + verge
        ROOF_PLAN.append(([(xa, y0 - over), (xb, y0 - over), (xb, y1 + over), (xa, y1 + over)], z - rise))
        for sgn, ye, yw in ((-1, y0 - over, y0), (1, y1 + over, y1)):
            lo_z = z - rise
            cuts = sorted((max(xa, c0), min(xb, c1)) for s_, c0, c1, *_ in notch if s_ == sgn and c1 > xa and c0 < xb)
            valleys = [v for s_, c0, c1, *vs in notch if s_ == sgn and ROOF_FILL for v in (vs[0] if vs else ())]
            segs, x_ = [], xa                                  # along the slope: (from, to, with its eave overhang?)
            for c0, c1 in cuts:
                if c0 > x_: segs.append((x_, c0, True))
                segs.append((max(x_, c0), c1, False)); x_ = max(x_, c1)
            if x_ < xb: segs.append((x_, xb, True))
            low = {}                                           # each verge's lowest roof point on this slope: its board starts there
            for s0, s1, eave in segs:
                yl, zl = (ye, lo_z) if eave else (yw, z)
                top = [(s0, yl, zl), (s1, yl, zl), (s1, ym, z + h), (s0, ym, z + h)]
                if sgn > 0: top = [top[1], top[0], top[3], top[2]]
                poly(key, top); coll_quad(top)
                poly("wood", [(p[0], p[1], p[2] - th) for p in top][::-1])
                for xx in (xa, xb):
                    if s0 <= xx <= s1: low[xx] = (yl, zl)
                for E, R in valleys:                           # a valley below this lower edge: the slope down to it
                    if E[2] >= zl: continue
                    at = lambda x_: [E[i] + (x_ - E[0]) / (R[0] - E[0]) * (R[i] - E[i]) for i in (1, 2)]   # the valley at x
                    xc = E[0] + (zl - E[2]) / (R[2] - E[2]) * (R[0] - E[0])                               # where it crosses the edge
                    f0, f1 = max(s0, min(E[0], xc)), min(s1, max(E[0], xc))
                    if f1 - f0 < 1e-6: continue
                    pts = [(f0, yl, zl), (f1, yl, zl), (f1, *at(f1)), (f0, *at(f0))]
                    pts = [p for i, p in enumerate(pts) if (Vector(p) - Vector(pts[i - 1])).length > 1e-6]
                    poly(key, facing(pts, (0, sgn, 1))); coll_tri(*pts[:3])
                    if len(pts) == 4: coll_tri(pts[0], pts[2], pts[3])
                    poly("wood", facing([(p[0], p[1], p[2] - th) for p in pts], (0, -sgn, -1)))
                    for xx in (xa, xb):
                        if min(abs(xx - f0), abs(xx - f1)) < 1e-6 and at(xx)[1] < low[xx][1]: low[xx] = tuple(at(xx))
            for (a0, a1, ea), (b0, b1, eb) in zip(segs, segs[1:]):   # where the eave stops, the end of its slab is closed
                if ea != eb:
                    poly("wood", facing([(a1, ye, lo_z), (a1, yw, z), (a1, yw, z - th), (a1, ye, lo_z - th)], (1 if ea else -1, 0, 0)))
            for xx, nn in ((xa, (-1, 0, 0)), (xb, (1, 0, 0))):
                yy, zz = low[xx]
                beam((xx, yy, zz - 8), (xx, ym, z + h - 8), 22, 6 if sgn < 0 else 7, nn)
        if gable_ends:
            for xx, nrm in ((x0, -1), (x1, 1)):
                if gable_ends is not True and ("left" if nrm < 0 else "right") not in gable_ends: continue
                poly("stucco", [(xx, y1, z), (xx, y0, z), (xx, ym, z + h)][::(1 if nrm < 0 else -1)]); coll_tri((xx, y1, z), (xx, y0, z), (xx, ym, z + h))
        box("wood", (xa, ym - 10, z + h - 12), (xb, ym + 10, z + h + 10))
        return z + h

def gable_frame(W, L, z, h, pair=None, skip=None, post_from=None, collar_at=None, struts=None):
    """A gable's framing as Solitude builds it: a tie at its foot, the king post to the apex, and either the collar and
    raking struts, or (pair = (kind, w, sill)) two small casements either side of the king post, each in its own jambs
    with a sill and a head, under a collar; nothing crosses them. skip = (u0, u1): the tie stops there (a great window
    rising into the gable); post_from: where the king post starts; collar_at / struts ((u_foot, u_top) pairs): by hand."""
    o, r, n = W; mid = L / 2
    for a_, b_ in ([(0, skip[0]), (skip[1], L)] if skip else [(0, L)]): wall_beam(W, (a_, z + 10), (b_, z + 10), w=20, deep=10)
    rake = lambda zz: mid * (1 - (zz - z) / h)                 # half-width of the gable at height zz
    if not pair:
        zc = collar_at or z + h * 0.45
        wall_beam(W, (mid, post_from or z + 16), (mid, z + h - 20), w=18, deep=8)
        half = rake(zc) - 8
        wall_beam(W, (mid - half, zc), (mid + half, zc), w=16, deep=10)
        for uf, ut in (struts or [(mid * 0.4, mid), (mid * 1.6, mid)]):
            wall_beam(W, (uf, z + 16), (ut, zc), w=14, deep=6)
        return
    kind, w, sill, *more = pair; key, rect = ATLAS[kind]; hh = w * RATIO[kind]
    off = 9 + 14 + 9 + w / 2 + (more[0] if more else 0)       # each window's centre: its inner jamb 14 off the king post (and a
                                                               # gap more, where a chimney's flue rises behind the post inside)
    zt = z + sill + hh; zc = zt + 26
    assert rake(zt + 8) >= off + w / 2 + 18, ("gable too small for its windows", L, h, pair)
    wall_beam(W, (mid, z + 16), (mid, z + h - 20), w=18, deep=8)
    half = rake(zc) - 8
    wall_beam(W, (mid - half, zc), (mid + half, zc), w=16, deep=10)
    for s_ in (-1, 1):
        c = mid + s_ * off
        if glazed(f"{WHERE[0]} {kind} u{round(c)}"): glaze(W, c, z + sill, w, zt - z - sill, kind, 2.0, "out")
        else: quad_on(W, c - w / 2, z + sill, c + w / 2, zt, 2.0, key, rect, kind=kind)
        register(kind, W, c - w / 2, z + sill, c + w / 2, zt, 2.0)
        for u in (c - w / 2 - 9, c + w / 2 + 9): wall_beam(W, (u, z + 16), (u, zc - 8), w=14, deep=8)
        wall_beam(W, (c - w / 2 - 16, z + sill - 6), (c + w / 2 + 16, z + sill - 6), w=12, deep=11)
        wall_beam(W, (c - w / 2 - 16, zt + 6), (c + w / 2 + 16, zt + 6), w=12, deep=10)

def facing(pts, want):
    """the polygon wound so its normal points along want (a rough direction)"""
    P = [Vector(q) for q in pts]
    nn = (P[1] - P[0]).cross(P[2] - P[0])
    return pts if nn.dot(Vector(want)) >= 0 else pts[::-1]

def abut_valleys(x0, x1, y_front, out, z, pitch, main, over=32):
    """abut_gable_roof's two valleys with the main slope, each (its eave end, its ridge end): the main roof's notch
    needs them before that roof is built (gable_roof's notch)"""
    half = (x1 - x0) / 2; xm = (x0 + x1) / 2; tp = math.tan(math.radians(pitch)); zr = z + half * tp
    yw, zw, mp = main; tm = math.tan(math.radians(mp))
    y_at = lambda zz: yw - out * (zz - zw) / tm                # where the main slope reaches height zz
    ze = z - over * tp
    return [((xe, y_at(ze), ze), (xm, y_at(zr), zr)) for xe in (x0 - over, x1 + over)]

def abut_gable_roof(x0, x1, y_front, out, z, pitch, main, over=32, verge=36, th=14, key="roof"):
    """A gable roof (ridge along y, gable end at y_front facing out: -1 = -y, +1 = +y) whose back runs into a main roof
    slope: each plane stops on its valley with that slope, so nothing pokes through the main roof behind and there is
    no back gable. main = (y_wall, z_wall, pitch): the main slope's height at its wall line, rising away from the
    gable's front. Returns the ridge height."""
    xm = (x0 + x1) / 2
    yf = y_front + out * verge
    (E0, R0), (E1, R1) = abut_valleys(x0, x1, y_front, out, z, pitch, main, over)
    ze, zr = E0[2], R0[2]
    for s_, E, R in ((-1, E0, R0), (1, E1, R1)):
        top = facing([(E[0], yf, ze), (xm, yf, zr), R, E], (s_, 0, 1))
        poly(key, top); coll_quad(top)
        poly("wood", facing([(q[0], q[1], q[2] - th) for q in top], (-s_, 0, -1)))
        beam((E[0], yf, ze - 8), (xm, yf, zr - 8), 22, 6 if s_ < 0 else 7, (0, out, 0))
    tri = facing([(x0, y_front, z), (x1, y_front, z), (xm, y_front, zr)], (0, out, 0))
    poly("stucco", tri); coll_tri(*tri)
    ya, yb = sorted((yf, R0[1]))
    box("wood", (xm - 10, ya, zr - 12), (xm + 10, yb, zr + 10))     # ridge cap
    ROOF_PLAN.append(([(E0[0], ya), (E1[0], ya), (E1[0], yb), (E0[0], yb)], ze))   # its whole rectangle: behind the valleys, the main roof
    return zr

def gable_timbers(W, L, z, h, window=None):
    """Framing on a gable triangle: king post, collar, raking struts, and an optional window."""
    o, r, n = W
    mid = L / 2
    wall_beam(W, (0, z + 10), (L, z + 10), w=20, deep=10)
    wall_beam(W, (mid, z + 16), (mid, z + h - 20), w=18, deep=8)
    zc = z + h * 0.45; half = mid * (1 - 0.45)
    wall_beam(W, (mid - half + 10, zc), (mid + half - 10, zc), w=16, deep=10)
    wall_beam(W, (mid - mid * 0.6, z + 16), (mid, zc), w=14, deep=6)
    wall_beam(W, (mid + mid * 0.6, z + 16), (mid, zc), w=14, deep=6)
    if window:
        kind, w, hh, sill = window
        key, rect = ATLAS[kind]; hh = w * RATIO[kind]
        if glazed(f"{WHERE[0]} {kind} u{round(mid)}"): glaze(W, mid, z + sill, w, hh, kind, 2.0, "out")
        else: quad_on(W, mid - w / 2, z + sill, mid + w / 2, z + sill + hh, 2.0, key, rect, kind=kind)

def pyramid(x0, y0, x1, y1, z, h, key="roof", over=30):
    xm, ym = (x0 + x1) / 2, (y0 + y1) / 2
    c = [(x0 - over, y0 - over, z - 14), (x1 + over, y0 - over, z - 14), (x1 + over, y1 + over, z - 14), (x0 - over, y1 + over, z - 14)]
    ROOF_PLAN.append(([q[:2] for q in c], z - 14))
    ap = (xm, ym, z + h)
    for i in range(4): poly(key, [c[i], c[(i + 1) % 4], ap]); coll_tri(c[i], c[(i + 1) % 4], ap)
    poly("wood", c[::-1])
    box("metal", (xm - 4, ym - 4, z + h - 10), (xm + 4, ym + 4, z + h + 140))  # finial
    box("metal", (xm - 12, ym - 12, z + h + 40), (xm + 12, ym + 12, z + h + 56))

CHIMNEYS = []        # (x, y, flue top): soot for the age pass, smoke for the kitchen's
def chimney(x, y, z0, z1):
    CHIMNEYS.append((x, y, z1 + 60))
    box("stone", (x - 45, y - 45, z0), (x + 45, y + 45, z1)); coll_box((x - 45, y - 45, z0), (x + 45, y + 45, z1 + 60))
    box("trim", (x - 56, y - 56, z1 - 4), (x + 56, y + 56, z1 + 18))
    box("stone", (x - 30, y - 30, z1 + 18), (x + 30, y + 30, z1 + 60))

def dormer(xc, y_face, z_eave, pitch_main, w=170, h=150):
    """A gabled dormer sitting on a front roof slope (ridge along x) whose eave line is at y_face, z_eave."""
    run = 120; z0 = z_eave + run * math.tan(math.radians(pitch_main)) * 0.15
    x0, x1 = xc - w / 2, xc + w / 2
    yf = y_face + run * 0.25
    box("stucco", (x0, yf, z0 - 60), (x1, yf + 260, z0 + h)); coll_box((x0, yf, z0 - 60), (x1, yf + 260, z0 + h))
    W = (Vector((x0, yf, 0)), Vector((1, 0, 0)), Vector((0, -1, 0)))
    # (the dormers were too large: now the casements' size, a timber cross and the diamond) a sill and jambs as the casements below have them
    dw_, dh_, dz_ = 84, 111, z0 + 18
    glaze(W, w / 2, dz_, dw_, dh_, "grid", 1.5, "out", "cross_diamond")
    WHERE[0] = f"dormer x{round(xc)}"; register("grid", W, w / 2 - dw_ / 2, dz_, w / 2 + dw_ / 2, dz_ + dh_, 1.5)
    wall_beam(W, (w / 2 - dw_ / 2 - 12, dz_ - 7), (w / 2 + dw_ / 2 + 12, dz_ - 7), w=14, deep=11)
    for s_ in (-1, 1): wall_beam(W, (w / 2 + s_ * (dw_ / 2 + 6), dz_ - 1), (w / 2 + s_ * (dw_ / 2 + 6), dz_ + dh_ + 1), w=12, deep=8)
    for u in (9, w - 9): wall_beam(W, (u, z0 - 50), (u, z0 + h - 9), w=18, deep=8)
    wall_beam(W, (-4, z0 + h - 9), (w + 4, z0 + h - 9), w=18, deep=10)
    r = gable_roof(x0, yf, x1, yf + 260, z0 + h, 52, "y", over=22, verge=24, gable_ends=True)
    gable_timbers(W, w, z0 + h, r - (z0 + h))

def balcony(xc, y_face, z, w=420, d=140):
    box("trim", (xc - w / 2, y_face - d, z - 10), (xc + w / 2, y_face, z + 14)); coll_box((xc - w / 2, y_face - d, z - 10), (xc + w / 2, y_face, z + 14))
    coll_box((xc - w / 2, y_face - d, z + 14), (xc + w / 2, y_face - d + 16, z + 110))
    coll_box((xc - w / 2, y_face - d, z + 14), (xc - w / 2 + 12, y_face, z + 110)); coll_box((xc + w / 2 - 12, y_face - d, z + 14), (xc + w / 2, y_face, z + 110))
    for u in (-w / 2 + 40, w / 2 - 40):  # carved brackets from the stone wall (none in the middle: the fanlight is under it)
        bracket((xc + u, y_face + J), (0, -1), (1, 0), z - 10, d + J - 6, 170, thick=22, t=18, pendant=True)
    # wooden balustrade
    inner = w - 24; nb = max(1, round(inner / 40))
    for k in range(1, nb):
        u = -inner / 2 + k * inner / nb
        box("wood", (xc + u - 4, y_face - d + 4, z + 14), (xc + u + 4, y_face - d + 12, z + 96))
    box("wood", (xc - w / 2 + 12, y_face - d, z + 96), (xc + w / 2 - 12, y_face - d + 16, z + 110))
    for xx in (xc - w / 2, xc + w / 2 - 12):
        box("wood", (xx, y_face - d, z + 14), (xx + 12, y_face, z + 118))

def steps(xc, y_top, z_top, z_bot, w, tread=34, rise=20, base=None):
    """A flight down from (y_top, z_top) to z_bot; base: where its blocks and cheek walls start (the ground below)."""
    n = max(1, int(round((z_top - z_bot) / rise)))
    zb = (z_bot - 20) if base is None else base
    for i in range(n):
        zt = z_top - i * (z_top - z_bot) / n
        zs = ground_under(xc - w / 2, xc + w / 2, y_top - (i + 1) * tread, y_top - i * tread) - 30 if SITE else zb
        box("steps", (xc - w / 2, y_top - (i + 1) * tread, zs), (xc + w / 2, y_top - i * tread, zt))
    # collision: one ramp over the flight (vanilla stairs collide as ramps), solid down to the base
    yb = y_top - n * tread; zr = z_top - (z_top - z_bot) * (n - 1) / n
    coll_quad([(xc - w / 2, yb, zr), (xc + w / 2, yb, zr), (xc + w / 2, y_top, z_top), (xc - w / 2, y_top, z_top)])
    coll_box((xc - w / 2, yb, (ground_under(xc - w / 2, xc + w / 2, yb, y_top) - 30) if SITE else zb), (xc + w / 2, y_top, zr))
    for sx in (-1, 1):  # stone cheek walls
        xx = xc + sx * (w / 2 + 20)
        zc = ground_under(xx - 20, xx + 20, y_top - n * tread, y_top) - 30 if SITE else zb
        box("stone", (xx - 20, y_top - n * tread, zc), (xx + 20, y_top, z_top + 30)); coll_box((xx - 20, y_top - n * tread, zc), (xx + 20, y_top, z_top + 44))
        box("trim", (xx - 26, y_top - n * tread - 6, z_top + 30), (xx + 26, y_top, z_top + 44))

# ---------------------------------------------------------------- the hall
# Laid out by hand (DESIGN-hall2.md): every opening has a room behind it and a place in the frame. Leaded glass in the
# guild's public rooms (pavilion, tower, the stone ground storey), no shutters on it; timber-grid casements with board
# shutters in the wings' members' rooms; nothing on a wall a roof or another wall stands in front of; windows stacked on
# one axis from storey to storey; brackets under the jetty only between openings. clearance_check.py tests it.
G = 0            # floor of the hall (terrace top)
S1 = 400         # ground storey (stone) top: tall, the great hall's ground floor
T1 = S1 + 256    # first timber storey
T2 = T1 + 256    # second timber storey (pavilion only)
J = 36           # jetty: upper storeys overhang the stone storey (on carved brackets)
SH = {"shutters": True}
CW = 84                                      # the members' casements (timber grid), shuttered: 84 x 130, heads clear of the eave
CS = 60                                      # their sill above the storey's floor (30 at first: the
                                             # rooms' windows were too low; inside they sit at 70, outside a little higher; 40
                                             # in hall2t, then 60: from the terrace they still read low)
JB = dict(thick=22, t=18, pendant=True)      # jetty brackets: chunky enough to read from the terrace, a turned drop under each

# Central pavilion: three storeys, the front gable facing the road. The great hall below, the guild master's room
# behind the balcony, the library under the great window.
PX0, PX1, PY0, PY1 = -380, 380, 0, 1100
PAX = 280                                    # the pavilion's window axes either side of the door, on every storey
DSC = 1.3; DW, DH = 184 * DSC, 176 * DSC        # the Solitude double door's bounds, scaled
PIL = DW / 2 + 26                                # the portal's pilasters (52 wide) centred here: their inner faces at the vanilla
# door's edges. A wider replacer (Glorious Doors of Skyrim's is 192 across, its outer panels 17 from the edge) tucks only its
# plain border behind them; when they lapped the door by 18 (2026-10-24, MGO) they stood on its outer panels, and from close
# by, 13 proud of the door, hid a strip of them.
stone_storey(PX0, PY0, PX1, PY1, G, S1, {"front": [(PX1 - PAX, "arched", 110, 0, 90), (PX1 + PAX, "arched", 110, 0, 90)]},
             name="pavilion ground", door=(-PIL, PIL))   # its sides are party walls with the wings: no windows
W_front = walls_of(PX0, PY0, PX1, PY1)["front"][0]
quad_on(W_front, 380 - DW / 2 - 4, G, 380 + DW / 2 + 4, G + DH + 4, 0.6, "wood")   # the reveal behind the door's edges
FW = DW - 16; FH = FW / 2                        # fanlight: the top of the arched window, a half round over the door
if GLAZE == "all": glaze(W_front, 380, G + DH + 34, FW, FH, "fan", 1.0, "out")
else: quad_on(W_front, 380 - FW / 2, G + DH + 34, 380 + FW / 2, G + DH + 34 + FH, 1.0, *ATLAS["fan"], kind="fan")
# (the outside already has a window above the door: the fanlight was never registered, so the
# interior, which builds its windows from OPENINGS, never had it, and the dead space it left was filled with a transom)
WHERE[0] = "pavilion ground front"; register("fan", W_front, 380 - FW / 2, G + DH + 34, 380 + FW / 2, G + DH + 34 + FH, 1.0)
for sx in (-1, 1):  # portal: pilasters, the lintel between door and fanlight, a cornice over it all
    box("trim", (sx * PIL - 26, PY0 - 34, G), (sx * PIL + 26, PY0, G + DH + FH + 50))
    coll_box((sx * PIL - 26, PY0 - 34, G), (sx * PIL + 26, PY0, G + DH + FH + 50))
DSI = PIL - 26                                   # the door's sill: one worn stone between the pilasters, 4 over the
box("steps", (-DSI, PY0 - 34, G), (DSI, PY0, G + 4)); coll_box((-DSI, PY0 - 34, G), (DSI, PY0, G + 4))   # paving
WHERE[0] = "pavilion ground front"; register("door", W_front, 380 - DSI + 1, G + 4, 380 + DSI - 1, G + DH, 0.6)   # (what shows of it)
box("trim", (-PIL - 42, PY0 - 44, G + DH + 4), (PIL + 42, PY0, G + DH + 34))
box("trim", (-PIL - 52, PY0 - 48, G + DH + FH + 40), (PIL + 52, PY0, G + DH + FH + 66))
PU = PX1 + J                                 # the pavilion's timber walls are 2 * PU long; u = PU is the axis
HALL_HEARTH = os.environ.get("AG_HEARTH", "1") != "0"   # the great hearth in the hall's back bay (the
# Great Hall Layout): its breast rises inside between the back windows and out as a stack on the ridge's back end
# (interior_gen.py, W); AG_HEARTH=0 leaves it off, for a study of the hall before it
BACK_DX = [float(v_) for v_ in os.environ.get("AG_BACK_WIN", "-140,140" if HALL_HEARTH else "-120,120").split(",")]   # its back
# windows' axes: two a storey, under the gable's apex and clear of the tower (three at -250, 0, 250 were squeezed
# once the tower took the gable's right end; then +-140 with the hearth, each centred between its breast and the masses beside
# it, 28 clear of both, inside and out; AG_BACK_WIN overrides for a study)
timber_storey(PX0 - J, PY0 - J, PX1 + J, PY1, S1 + 18, T1,
              {"front": [(PU, "glazed_door", 136, 196, 14), (PU - PAX, "leaded", 96, 0, 36), (PU + PAX, "leaded", 96, 0, 36)],
               "back": [(PU + dx, "leaded", 96, 0, 36) for dx in BACK_DX]}, name="pavilion first")
jetty_joists(walls_of(PX0, PY0, PX1, PY1)["front"][0], PX1 - PX0, S1 + 18)
# The Guild crest is carried by a dressed-stone roundel: a flat medallion with a moulded rim, set into the second
# storey's centre bay and bearing on its sill plate, the timbers it crosses (the wall plate, the gable's tie) butting into
# its rim like a chimney breast; the crest is inlaid on its face, inside the rim. The great window above it, in the gable.
RR, RF = 150, 130                                              # the roundel's outer radius, its face's radius (inside the rim)
CREST_S = 1.5                                                  # the crest: ring radius 137, the sword's tips at +-165 (inside the face)
RZ = T1 + 20 + RR                                              # the roundel's centre: its foot on the second storey's sill plate
chord = lambda z: math.sqrt(max(0.0, RR * RR - (z - RZ) ** 2))   # the roundel's half-width at height z
timber_storey(PX0 - J, PY0 - J, PX1 + J, PY1, T1, T2,
              {"front": [(PU, "blank", 2 * (chord(T2 - 10) - 9), 2 * RR, 20), (PU - PAX, "leaded", 90, 0, 40), (PU + PAX, "leaded", 90, 0, 40)],
               "back": [(PU + dx, "leaded", 90, 0, 40) for dx in BACK_DX]}, name="pavilion second")
ridge = gable_roof(PX0 - J, PY0 - J, PX1 + J, PY1, T2, 54, "y", over=40, verge=40)
gw = walls_of(PX0 - J, PY0 - J, PX1 + J, PY1)["front"][0]; gh_ = ridge - T2
rake_z = lambda u: T2 + gh_ * (1 - abs(u - PU) / PU)
def roundel(W, uc, zc, rr, rf, d_face=8, d_rim=14, n=48):
    """a flat stone medallion on wall W: a face of radius rf d_face proud, a rim from rf to rr d_rim proud, and its sides.
    The face wears one smooth square of SSteps01 (image u 0.60-0.82, v 0.62-0.84: the cleanest square in it, measured:
    no joint line across it, so nothing reads as bricks behind the crest); the rim wears StRims01's moulding lines (v 0.125-0.235) run
    round the ring, so it reads as a turned moulding; its edges StRims01's plain top band."""
    o, r, nn = W
    P = lambda rad, a, d: o + r * (uc + rad * math.cos(a)) + UP * (zc + rad * math.sin(a)) + nn * d
    face_uv = lambda rad, a: (0.60 + 0.22 * (0.5 + rad * math.cos(a) / (2 * rf)), 1 - (0.84 - 0.22 * (0.5 + rad * math.sin(a) / (2 * rf))))
    A = [2 * math.pi * k / n for k in range(n + 1)]
    circ = 2 * math.pi * (rf + rr) / 2
    for k, (a, b) in enumerate(zip(A, A[1:])):
        ua, ub = circ * k / n / S, circ * (k + 1) / n / S          # along the ring, one texture tile per 256
        def put(key, pts, uvs, want):
            if (Vector(pts[1]) - Vector(pts[0])).cross(Vector(pts[2]) - Vector(pts[0])).dot(Vector(want)) < 0: pts, uvs = pts[::-1], uvs[::-1]
            poly(key, pts, uvs)
        put("steps", [P(0, a, d_face), P(rf, a, d_face), P(rf, b, d_face)], [face_uv(0, a), face_uv(rf, a), face_uv(rf, b)], nn)
        put("trim", [P(rf, a, d_rim), P(rr, a, d_rim), P(rr, b, d_rim), P(rf, b, d_rim)],
            [(ua, 1 - 0.235), (ua, 1 - 0.125), (ub, 1 - 0.125), (ub, 1 - 0.235)], nn)
        rad_ab = P(1, (a + b) / 2, 0) - P(0, 0, 0)
        put("trim", [P(rf, a, d_face), P(rf, b, d_face), P(rf, b, d_rim), P(rf, a, d_rim)], [(ua, 0.98), (ub, 0.98), (ub, 0.95), (ua, 0.95)], -rad_ab)
        put("trim", [P(rr, a, 0), P(rr, b, 0), P(rr, b, d_rim), P(rr, a, d_rim)], [(ua, 0.98), (ub, 0.98), (ub, 0.93), (ua, 0.93)], rad_ab)
    coll_box(tuple(min(p_, q_) for p_, q_ in zip(P(rr, math.pi, 0) - UP * rr, P(rr, 0, d_rim) + UP * rr)),
             tuple(max(p_, q_) for p_, q_ in zip(P(rr, math.pi, 0) - UP * rr, P(rr, 0, d_rim) + UP * rr)))
roundel(gw, PU, RZ, RR, RF)
def crest_relief(W, uc, zc, size, d0, N=170, key="crest"):
    _poly = globals()["poly"]
    def ppoly(k_, pts):                                   # painted: each face takes the crest picture's colours at its place
        o_, r_, n_ = W
        return _poly(k_, pts, [(((Vector(q) - o_).dot(r_) - uc + size / 2) / size, (Vector(q).z - zc + size / 2) / size) for q in pts])
    """the Guild crest carved in relief and painted in its own colours (AGHallCrest.dds mapped on it from the front), on
    wall W, size x size, its back at d0 out from the wall: AGHallCrest.dds
    sampled on an N x N grid and sorted by what each part is (its colour and place), each part raised its own height:
    the shield's wooden field 3, its iron rim and straps 5, the dragon ring 6, the boss 8, the sword 10 (over all).
    Tops are merged along rows, sides along their runs, so it stays a few thousand faces."""
    img = bpy.data.images.load(os.path.join(root, "textures", "adventurersguild", "hall", "AGHallCrest.dds"))
    Wd, Hd = img.size; px = img.pixels[:]
    def at(fx, fy):                                       # fx, fy in 0..1, fy up from the bottom (Blender's pixel order)
        i_ = (min(Hd - 1, int(fy * Hd)) * Wd + min(Wd - 1, int(fx * Wd))) * 4
        return px[i_:i_ + 4]
    H = [[0] * N for _ in range(N)]
    for i in range(N):
        for j in range(N):
            x_, yb = (j + 0.5) / N, (i + 0.5) / N; yi = 1 - yb   # yi: down from the top, as the picture is drawn
            r_, g_, b_, a_ = at(x_, yb)
            if a_ < 0.5: continue
            mx, mn = max(r_, g_, b_), min(r_, g_, b_); sat = (mx - mn) / (mx + 1e-6)
            if (abs(x_ - 0.5) < 0.034 and sat < 0.3) or (0.185 < yi < 0.25 and abs(x_ - 0.5) < 0.17) or (yi < 0.2 and abs(x_ - 0.5) < 0.045): h = 17
            elif r_ - b_ > 0.12 and r_ >= g_: h = 11
            elif math.hypot(x_ - 0.5, (yi - 0.535) * 1.0) < 0.085: h = 14
            elif r_ - b_ < 0.035: h = 8
            else: h = 5
            H[i][j] = h
    o, r, n = W; cell = size / N
    U = lambda j: uc - size / 2 + j * cell; Z = lambda i: zc - size / 2 + i * cell
    P = lambda u, z, d: o + r * u + UP * z + n * d
    done = [[False] * N for _ in range(N)]                # tops, as maximal rectangles of one height
    for i in range(N):
        for j in range(N):
            h = H[i][j]
            if h == 0 or done[i][j]: continue
            k = j
            while k + 1 < N and H[i][k + 1] == h and not done[i][k + 1]: k += 1
            m = i
            while m + 1 < N and all(H[m + 1][q] == h and not done[m + 1][q] for q in range(j, k + 1)): m += 1
            for a_ in range(i, m + 1):
                for q in range(j, k + 1): done[a_][q] = True
            ppoly(key, facing([P(U(j), Z(i), d0 + h), P(U(k + 1), Z(i), d0 + h), P(U(k + 1), Z(m + 1), d0 + h), P(U(j), Z(m + 1), d0 + h)], n))
    for j in range(N + 1):                                # sides between columns, merged up each boundary
        i = 0
        while i < N:
            hl = H[i][j - 1] if j > 0 else 0; hr = H[i][j] if j < N else 0
            if hl == hr: i += 1; continue
            k = i
            while k + 1 < N and (H[k + 1][j - 1] if j > 0 else 0) == hl and (H[k + 1][j] if j < N else 0) == hr: k += 1
            lo_, hi_ = min(hl, hr), max(hl, hr)
            ppoly(key, facing([P(U(j), Z(i), d0 + lo_), P(U(j), Z(k + 1), d0 + lo_), P(U(j), Z(k + 1), d0 + hi_), P(U(j), Z(i), d0 + hi_)], r if hl > hr else -r))
            i = k + 1
    for i in range(N + 1):                                # sides between rows, merged along each boundary
        j = 0
        while j < N:
            hb = H[i - 1][j] if i > 0 else 0; ht = H[i][j] if i < N else 0
            if hb == ht: j += 1; continue
            k = j
            while k + 1 < N and (H[i - 1][k + 1] if i > 0 else 0) == hb and (H[i][k + 1] if i < N else 0) == ht: k += 1
            lo_, hi_ = min(hb, ht), max(hb, ht)
            ppoly(key, facing([P(U(j), Z(i), d0 + lo_), P(U(k + 1), Z(i), d0 + lo_), P(U(k + 1), Z(i), d0 + hi_), P(U(j), Z(i), d0 + hi_)], UP if hb > ht else -UP))
            j = k + 1
    print("CREST relief", N, "x", N, "cells of", round(cell, 2), "| parts:", {h: sum(row.count(h) for row in H) for h in (5, 8, 11, 14, 17)})
def crest_mesh(W, uc, zc, d0, path, key="crest3d"):
    """the Guild crest sculpted (crest_game.py: the approved emblem at a budget per part, its scales, rivets and cast colour
    baked into AGCrest.dds and AGCrest_n.dds), its back on the roundel's face d0 out from the wall: the ring inside the face,
    the sword's ends and the heads' horns over the rim (clear of it)"""
    o, r, n = W; C = json.load(open(path))
    V = [o + r * (uc + x) + UP * (zc + y) + n * (d0 + z) for x, y, z in C["v"]]
    for f, uv in zip(C["f"], C["uv"]): poly(key, [V[i] for i in f], [tuple(t) for t in uv])
    print("CREST mesh", len(C["f"]), "triangles from", path)
import json
CREST3D = os.environ.get("AG_CREST3D") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "hall-private", "assets", "crest3d", "crest_low.json")
if os.path.exists(CREST3D): crest_mesh(gw, PU, RZ, 8, CREST3D)
else: crest_relief(gw, PU, RZ, 2 * RF - 12, 8)
# the great window: the library's, in the gable over the roundel, on a sill beam of its own, jambs from the sill to its
# springing, the king post standing on its head
GWW = 190; GB = RZ + RR + 24; GH = GB + GWW * RATIO["gothic"]
assert rake_z(PU + GWW / 2 + 18) > GH - GWW / 2 + 10, "the great window does not fit the gable"
if glazed("pavilion gable gothic"): glaze(gw, PU, GB, GWW, GH - GB, "gothic", 2.0, "out")
else: quad_on(gw, PU - GWW / 2, GB, PU + GWW / 2, GH, 2.0, *ATLAS["gothic"], kind="gothic")
WHERE[0] = "pavilion gable"; register("gothic", gw, PU - GWW / 2, GB, PU + GWW / 2, GH, 2.0)
tc = chord(T2 + 10)                                            # the gable's tie, butting into the roundel's rim
wall_beam(gw, (0, T2 + 10), (PU - tc, T2 + 10), w=20, deep=10); wall_beam(gw, (PU + tc, T2 + 10), (2 * PU, T2 + 10), w=20, deep=10)
wall_beam(gw, (PU - GWW / 2 - 22, GB - 8), (PU + GWW / 2 + 22, GB - 8), w=16, deep=12)  # its sill
for u in (PU - GWW / 2 - 9, PU + GWW / 2 + 9): wall_beam(gw, (u, GB - 16), (u, GB + win_spring(GH - GB)), w=18, deep=8)
for pts_, uvs_ in win_place(win_hood("gothic", GWW, GH - GB, 18, 8), gw, PU, GB, 0.0): poly("wframe", pts_, uvs_)   # (the jambs carried round the head, so the edge is even)
for u in (PU - RR - 40, PU + RR + 40): wall_beam(gw, (u, T2 + 20), (u, rake_z(u) - 16), w=16, deep=8)   # studs clear of the rim
wall_beam(gw, (PU, GH + 18), (PU, T2 + gh_ - 20), w=18, deep=8)                     # the king post over its head
HALL_PLACE = []                                                # (the crest is carved on the roundel, above)
gable_frame(walls_of(PX0 - J, PY0 - J, PX1 + J, PY1)["back"][0], 2 * PU, T2, ridge - T2,
            pair=("small", 76, 60, 24) if HALL_HEARTH else ("small", 76, 60))   # (the hearth's flue rises behind the king
if HALL_HEARTH: chimney(0, 1035, T2, ridge + 180)          # post inside, 56 wide: the pair stands 28 clear of it); its stack
balcony(0, PY0 - J, S1 + 18, w=360, d=130)
WHERE[0] = "pavilion second"; register("crest", gw, PU - RR, RZ - RR, PU + RR, RZ + RR, 14)

# Wings: two storeys, ridges parallel to the road, each ending in a cross gable; dormers between. Below, the dining hall
# (left) and the training hall (right); above, the members' rooms, one shuttered casement each.
WING_WIN = (571, 881)                        # |x| of the window axes on a wing's front: two rooms, the bay post between
WING_END = (290, 540, 790)                   # y of the window axes on a wing's outer end
WING_BACK_L = (-1299, -946, -593)            # x of the window axes on the left wing's back (three rooms)
if os.environ.get("AG_INTERIOR"):            # inside, the tavern's two back windows (both storeys) on the front's axes, so its
    WING_BACK_L = (-1299, -881, -571)        # brace pairs sit centred on both long walls (the back pair stood
                                             # 43.5 off its windows; the exterior keeps its three, inside and out not matching by design)
WING_BACK_LG = (-1250,) + WING_BACK_L[1:] if os.environ.get("AG_INTERIOR") else WING_BACK_L   # the ground storey's: inside, the
                                             # kitchen's window centred on its back wall (-1400..-1100; it was off centre);
                                             # the window over it and the outside keep -1299
WY0, WY1 = 170, 930                         # the wings' front and back walls (stone storey)
REAR_X = 928                                 # the back door (right wing): its porch's posts PORCH_W apart, PORCH_D out from
PORCH_W, PORCH_D, PORCH_Z = 300, 170, S1 + 18 + 232   # the wall, its tie beam's top; its roof (abut_gable_roof's arguments)
PORCH_ROOF = dict(x0=REAR_X - PORCH_W / 2 - 12, x1=REAR_X + PORCH_W / 2 + 12, y_front=WY1 + PORCH_D + 10, out=1, z=PORCH_Z + 4,
                  pitch=45, main=(WY1, T1, 48), over=22)
PORCH = (PORCH_ROOF["x0"] - PORCH_ROOF["over"], PORCH_ROOF["x1"] + PORCH_ROOF["over"])   # the wing's back eave stops over it
for sgn in (-1, 1):
    a, b = (PX0 - 1060, PX0) if sgn < 0 else (PX1, PX1 + 1060)
    wy_t = WY0 - J
    tx0, tx1 = a - (J if sgn < 0 else 0), b + (J if sgn > 0 else 0)
    outer = "left" if sgn < 0 else "right"
    ga, gb = (a - J, a - J + 440) if sgn < 0 else (b + J - 440, b + J)   # the cross gable's span
    gy0 = 110
    sa, sb = (a + 1, gb - J * 0.5) if sgn < 0 else (ga + J * 0.5, b - 1)
    ta, tb = (ga + 1, gb) if sgn < 0 else (ga, gb - 1)
    GX = (ta + tb) / 2                                         # the cross gable's axis
    nm = "wing " + ("L" if sgn < 0 else "R")
    # u along each wall: front x - x0; back x1 - x; left side y1 - y; right side y - y0
    stone_win = {"front": [(sgn * x_ - a, "arched", 120, 0, 90) for x_ in WING_WIN],
                 outer: [((WY1 - y_) if sgn < 0 else (y_ - WY0), "arched", 120, 0, 90) for y_ in WING_END
                         if sgn < 0 or y_ < 700]}                # the right end's back bay is in the hill (ground and rock to 99-187)
    if sgn < 0: stone_win["back"] = [(b - x_, "arched", 120, 0, 90) for x_ in WING_BACK_LG]
    stone_storey(a, WY0, b, WY1, G, S1, stone_win, plinth=True, name=nm + " ground", abut="right" if sgn < 0 else "left")
    up = {"front": [(sgn * x_ - tx0, "grid", CW, 0, CS, SH) for x_ in WING_WIN],
          outer: [((WY1 - y_) if sgn < 0 else (y_ - wy_t), "grid", CW, 0, CS, SH) for y_ in WING_END]}
    if sgn < 0: up["back"] = [(tx1 - x_, "grid", CW, 0, CS, SH) for x_ in WING_BACK_L]
    else: up["back"] = [(tx1 - REAR_X, "opening", 200, 196, 0), (tx1 - 1265, "grid", CW, 0, CS, SH)]   # its shutters clear the barrel in the patio's far corner
    bay = {"front": [sgn * x_ - tx0 for x_ in (416, 726, 1036)]}
    timber_storey(tx0, wy_t, tx1, WY1, S1 + 18, T1, up, posts_at=bay, name=nm + " upper")
    if sgn > 0: REAR_DOOR = (REAR_X, WY1, S1 + 18)
    fx0, fx1 = sorted((sgn * 380, sgn * 1036))                 # joist ends under the open part of the wing's jetty
    jetty_joists(walls_of(fx0, WY0, fx1, WY1)["front"][0], fx1 - fx0, S1 + 18)
    # the wing roof: its inner end runs into the pavilion's roof slope (its ridge meets that slope at |x| 281), only
    # its outer end has a gable; the eave stops where the cross gable (front) and the porch (back) break through it
    xin = sgn * 281
    cross = dict(x0=ga, x1=gb, y_front=gy0, out=-1, z=T1, pitch=54, main=(wy_t, T1, 48), over=32)   # the cross gable's roof
    notch = [(-1, ta - 1, tb + 31, abut_valleys(**cross)) if sgn > 0 else (-1, ta - 31, tb + 1, abut_valleys(**cross))]
    if sgn > 0: notch.append((1, PORCH[0], PORCH[1], abut_valleys(**PORCH_ROOF)))
    rx0, rx1 = sorted((xin, sgn * (1440 + J)))
    gable_roof(rx0, wy_t, rx1, WY1, T1, 48, "x", over=32, verge=30, gable_ends=(outer,), notch=notch)   # its eave stays above the window heads
    # the cross gable: arched window below, a shuttered casement above, two small casements in the gable, all on its axis
    stone_storey(sa, gy0 + J, sb, WY0 + 200, G, S1, {"front": [(GX - sa, "arched", 120, 0, 90)]}, name=nm + " cross gable ground",
                 plinth_y1=WY0 - 12)                           # behind that, the wing's plinth (their tops would share a plane)
    timber_storey(ta, gy0, tb, WY0 + 200, S1 + 18, T1, {"front": [(GX - ta, "grid", CW, 0, CS, SH)]},
                  sides=("front", "right") if sgn < 0 else ("front", "left"), name=nm + " cross gable upper")
    jetty_joists(walls_of(sa, gy0 + J, sb, WY1)["front"][0], sb - sa, S1 + 18)
    gr = abut_gable_roof(**cross, verge=36)
    gable_frame(walls_of(ga, gy0, gb, WY1)["front"][0], gb - ga, T1, gr - T1, pair=("small", 60, 40))
    # dormers on the front slope, over the two casements
    for x_ in WING_WIN: dormer(sgn * x_, wy_t, T1, 48)
    chimney((a + b) / 2 + sgn * 180, (WY0 + WY1) / 2 + 160, T1, T1 + 560)

# carved brackets under the jetties, only where the wall below is solid: the pavilion's corners (the balcony has its
# own), each wing's bay post, the cross gables' corners
for x_ in (-PX1 + 24, PX1 - 24):
    bracket((x_, PY0), (0, -1), (1, 0), S1 + 18, J - 3, 124, **JB)
for sgn in (-1, 1):
    bracket((sgn * 726, 170), (0, -1), (1, 0), S1 + 18, J - 3, 124, **JB)
    sa_, sb_ = (PX0 - 1060 + 1, PX0 - 1060 - J + 440 - J * 0.5) if sgn < 0 else (PX1 + 1060 - 440 + J + J * 0.5, PX1 + 1060 - 1)
    for x_ in (sa_ + 24, sb_ - 24):
        bracket((x_, 110 + J), (0, -1), (1, 0), S1 + 18, J - 3, 124, **JB)

# Tower: the lookout, behind the right junction. Its lower part stands among the roofs, so it opens only where it is
# clear of them (the back over the yard, the right side over the patio); its lookout storey rises above every roof,
# a leaded window on each face clear of them. For the stair inside (its drawn line): it takes the great hall's
# back-right corner (from x 216, hiding the hall roof's strip between it and the back gable), reaches 40 to the right
# (into the patio's empty end), 28 forward and just past the back gable's verge (1140), so that ends inside it.
TX0, TX1, TY0, TY1 = 216, PX1 + 340, 732, 1160      # (until then: PX1 - 40, PX1 + 300, 760, 1112)
if os.environ.get("AG_TOWER_BOX"):   # a study: x0,y0,x1,y1; the patio's left end follows TX1
    TX0, TY0, TX1, TY1 = (float(v_) for v_ in os.environ["AG_TOWER_BOX"].split(","))
TT = 1400
stone_storey(TX0, TY0, TX1, TY1, G, S1, {}, name="tower ground")
timber_storey(TX0, TY0, TX1, TY1, S1 + 18, T2,
              {"back": [((TX1 - TX0) / 2, "leaded", 80, 0, 150)],   # its right one only clear of the porch's roof (at x 720 the
               "right": [(1041 - TY0, "leaded", 70, 0, 120)] if PORCH[0] - TX1 >= 60 else []},   # roof's verge is 24 off)
              braces=False, name="tower lower")
look = (TX1 - TX0) / 2, (TY1 - TY0) / 2
roof_at = lambda x_: ridge - abs(x_) * math.tan(math.radians(54))   # the pavilion roof's top over x: a tower further left rises
look_left = [(look[1], "leaded", 80, 0, 258)] if roof_at(TX0) <= T2 + 258 - 60 else []   # out of it, its left window then gone
timber_storey(TX0, TY0, TX1, TY1, T2, TT,
              {"front": [(look[0], "leaded", 80, 0, 258)], "back": [(look[0], "leaded", 80, 0, 258)],
               "left": look_left, "right": [(look[1], "leaded", 80, 0, 258)]},
              braces=False, name="tower lookout")
pyramid(TX0, TY0, TX1, TY1, TT, 520)

# Terrace and front steps: the hillside answer of the Korean reference (a stone podium with a stair up the middle)
BRAZIERS = [(-300, -420), (300, -420)]
EXTRA_PLACE = list(HALL_PLACE)         # the hall's own pieces, then what the approach adds (the sign's crests); PLACE is made from it
PART = "site"
CLEAR = [(-1700, 1700, -1000, 1250)]   # where trees and small landscape pieces are hidden (hall frame: x0, x1, y0, y1)
CLEAR_ALL = []                           # where every landscape piece is hidden, ledges included (the approach's corridor)
import json
if SITE:
    # the terrace reaches the ground everywhere (its foot below the lowest point under it); the stair runs out to where
    # the ground meets it, with a landing every 10 steps
    lows = [ground(x, y) for x in range(-1600, 1601, 100) for y in range(-460, 1151, 100)]
    PB = min(lows) - 96
    AP0 = json.load(open(os.environ["AG_APPROACH"])) if os.environ.get("AG_APPROACH") else {}
    BEDS = [tuple(b["x"]) + tuple(b["y"]) for b in AP0.get("beds", [])]
    TER = AP0.get("terrace", [[-1600, 1600, -460, 930]])        # rectangles (x0, x1, y0, y1) that are paved
    CUT = [tuple(c) for c in AP0.get("terrace_cut", [])] + BEDS
    def minus(r, c):
        """rectangle r minus rectangle c, as up to four rectangles"""
        x0, x1, y0, y1 = r; a0, a1, b0, b1 = c
        if a1 <= x0 or a0 >= x1 or b1 <= y0 or b0 >= y1: return [r]
        out = []
        if b0 > y0: out.append((x0, x1, y0, b0))
        if b1 < y1: out.append((x0, x1, b1, y1))
        if a0 > x0: out.append((x0, a0, max(y0, b0), min(y1, b1)))
        if a1 < x1: out.append((a1, x1, max(y0, b0), min(y1, b1)))
        return out
    tiles = [tuple(t) for t in TER]
    for c in CUT: tiles = [q for t in tiles for q in minus(t, c)]
    def culvert(W, uc, zb, w=72, h=66, label="drain"):
        """a drain's outlet on a retaining wall's face W at its foot: a dark mouth in a dressed stone frame (jambs, lintel,
        a lip it spills over) behind an iron grate; the frame stands proud of the face, so the mouth reads deep"""
        o, r, n = W
        P = lambda u, z, d: o + r * u + UP * z + n * d
        def blk(key, u0, u1, z0, z1, d0, d1):
            a_, b_ = P(u0, z0, d0), P(u1, z1, d1)
            box(key, tuple(min(p_, q_) for p_, q_ in zip(a_, b_)), tuple(max(p_, q_) for p_, q_ in zip(a_, b_)))
        poly("dirt", facing([P(uc - w / 2, zb, 0.6), P(uc + w / 2, zb, 0.6), P(uc + w / 2, zb + h, 0.6), P(uc - w / 2, zb + h, 0.6)], n))
        for u0 in (uc - w / 2 - 16, uc + w / 2): blk("trim", u0, u0 + 16, zb - 4, zb + h, 0, 12)                   # jambs
        blk("trim", uc - w / 2 - 26, uc + w / 2 + 26, zb + h, zb + h + 22, 0, 14)                               # lintel
        blk("trim", uc - w / 2 - 10, uc + w / 2 + 10, zb - 12, zb, 0, 34)                                       # the lip
        for k in range(6): u_ = uc - w / 2 + 8 + k * (w - 16) / 5; blk("metal", u_ - 2, u_ + 2, zb, zb + h, 7, 11)
        for z_ in (zb + 18, zb + h - 18): blk("metal", uc - w / 2 + 1, uc + w / 2 - 1, z_ - 2, z_ + 2, 5, 13)
    PD_ = AP0.get("podium_drain")                          # a drain in the podium's face, where the ground along it is lowest
    if PD_:
        W_ = (Vector((PD_["x"], 0, 0)), Vector((0, 1, 0)), Vector((1, 0, 0)))
        g_ = max(ground(PD_["x"] + dx_, PD_["y"] + dy_) for dx_ in (2, 18, 34) for dy_ in (-46, 0, 46))   # the highest ground under its lip
        culvert(W_, PD_["y"], g_ + 40, label="podium drain")          # 40 up: clear of the grass that grows there
        globals()["PODIUM_DRAIN"] = (PD_["x"], PD_["y"], g_ + 40 - 12)      # face x, centre y, under its lip
        for sd_ in (-1, 1):
            EXTRA_PLACE.append(("meshes/landscape/plants/swordferncluster06.nif", (PD_["x"] + 50, PD_["y"] + sd_ * 105, ground(PD_["x"] + 50, PD_["y"] + sd_ * 105) - 4), 70 * sd_ + 20, 0.75))
        print("PODIUM DRAIN at y", PD_["y"], "ground up to", round(g_), "mouth", round(g_ + 40), "-", round(g_ + 106))
    EXIT = AP0.get("exit")                                  # a walk's last stretch left unpaved: it steps down onto the ground
    built = [q for t in tiles for q in minus(t, (EXIT["x"][0], EXIT["x"][1], EXIT["y"][0], EXIT["y"][1]))] if EXIT else tiles
    for x0, x1, y0, y1 in built:                           # (the parapets still see the whole walk, so its wall runs on unchanged)
        tb = ground_under(x0, x1, y0, y1) - 60
        box("stone", (x0, y0, tb), (x1, y1, G - 4)); coll_box((x0, y0, tb), (x1, y1, G))
        box("floor", (x0, y0, G - 4), (x1, y1, G))
    if EXIT:                                                # steps of 22 down from the paving's end until the ground meets them
        ex0, ex1 = EXIT["x"]; ey, zt, ns = EXIT["y"][0], G, 0
        while ey + 34 <= EXIT["y"][1]:
            gm = sum(ground(x_, ey + 34) for x_ in (ex0 + 15, (ex0 + ex1) / 2, ex1 - 15)) / 3    # the ground at the tread's far edge
            if zt - gm <= 22: break
            zt -= 22; ns += 1
            box("steps", (ex0, ey, ground_under(ex0, ex1, ey, ey + 34) - 40), (ex1, ey + 34, zt))
            coll_box((ex0, ey, ground_under(ex0, ex1, ey, ey + 34) - 40), (ex1, ey + 34, zt))
            ey += 34
        print("EXIT unpaved from y", EXIT["y"][0], "-", ns, "step(s) down to", zt, "then the ground at", round(gm))
    if os.environ.get("AG_STAIR") != "approach":
        # the terrace's front edge: a trim course, broken where the stair goes down
        for a0, a1 in ((-1612, -310), (310, 1612)):
            box("trim", (a0, -472, G - 10), (a1, -440, G + 10))
    else:
        # the podium's edges: a parapet wherever the ground outside falls more than a step below the paving, nothing where
        # the bank comes up to meet it, the head of the flight to the forecourt left open between two piers
        FOOT = [(-1452, 1452, 158, 942), (-392, 392, -12, 1112), (328, 692, 748, 1124)]    # the building's foundations
        OPEN = AP0.get("upper", {}).get("w", 600) / 2 + 40
        PT, PH_ = 34, 64                                     # parapet thickness and height above the paving
        def in_rects(x, y, rs): return any(a <= x <= b and c <= y <= d for a, b, c, d in rs)
        runs = []                                            # [axis, fixed, a0, a1, out]: axis "x" runs along x at y = fixed
        RECTS = list(tiles) + list(BEDS) + FOOT
        for x0, x1, y0, y1 in tiles:
            for axis, fixed, a0, a1, ow in (("x", y0, x0, x1, -1), ("x", y1, x0, x1, 1), ("y", x0, y0, y1, -1), ("y", x1, y0, y1, 1)):
                brk = sorted({a0, a1} | {v for R_ in RECTS for v in ((R_[0], R_[1]) if axis == "x" else (R_[2], R_[3])) if a0 < v < a1})
                segs = []                                    # split where another rectangle starts or ends, then into 50s
                for b0, b1 in zip(brk, brk[1:]):
                    k_ = max(1, math.ceil((b1 - b0) / 50)); segs += [(b0 + (b1 - b0) * i / k_, b0 + (b1 - b0) * (i + 1) / k_) for i in range(k_)]
                cur = None
                for s0, s1 in segs:
                    m = (s0 + s1) / 2
                    nb = (m, fixed + ow * 20) if axis == "x" else (fixed + ow * 20, m)
                    far = (m, fixed + ow * 80) if axis == "x" else (fixed + ow * 80, m)
                    inner = (m, fixed - ow * 20) if axis == "x" else (fixed - ow * 20, m)   # paving under the hall has no edge
                    drop = not in_rects(*nb, RECTS) and not in_rects(*inner, FOOT) and ground(*far) < G - 60
                    if drop and cur: cur[3] = s1
                    elif drop: cur = [axis, fixed, s0, s1, ow]; runs.append(cur)
                    else: cur = None
        cut = []                                             # the flight's mouth on the front edge
        for r in runs:
            if r[0] == "x" and r[4] < 0 and r[2] < OPEN and r[3] > -OPEN:
                if r[2] < -OPEN: cut.append([r[0], r[1], r[2], -OPEN, r[4]])
                if r[3] > OPEN: cut.append([r[0], r[1], OPEN, r[3], r[4]])
            else: cut.append(r)
        runs = []                                            # neighbouring tiles' runs on one line become one run
        for r in sorted(cut, key=lambda r: (r[0], r[1], r[4], r[2])):
            if runs and runs[-1][0] == r[0] and abs(runs[-1][1] - r[1]) < 1 and runs[-1][4] == r[4] and abs(runs[-1][3] - r[2]) < 1: runs[-1][3] = r[3]
            else: runs.append(list(r))
        for r in runs: r += [[5.0, 5.0]]                    # how far the coping runs on past each end (5: a free end overhangs)
        strip = lambda r: (min(r[1], r[1] - r[4] * PT), max(r[1], r[1] - r[4] * PT))
        for r in runs:                                       # corners between a run along y and one along x
            if r[0] != "y": continue
            for e in (0, 1):
                for q in runs:
                    if q[0] != "x" or abs(q[1] - r[2 + e]) > 1: continue
                    lo_, hi_ = strip(r)
                    if q[2] - 1 <= lo_ and hi_ <= q[3] + 1:  # outside corner: q runs past r's end; r stops at q's inner face
                        new = q[1] - q[4] * PT
                        if (e == 0 and new > r[2]) or (e == 1 and new < r[3]): r[2 + e] = new; r[5][e] = -5.0
                        break
                    for f in (0, 1):                         # inside corner: they meet end to end; r's coping covers it
                        if abs(q[2 + f] - r[1]) < 1:
                            q[5][f] = -5.0
                            qlo, qhi = strip(q)              # q's wall lies past r's end (the paving turns outward here, as
                            if e == 1 and qlo >= r[3] - 1: r[3] = qhi     # at the overlook): r runs on across q's
                            if e == 0 and qhi <= r[2] + 1: r[2] = qlo     # thickness, or the corner square stays open
        for r in runs:
            axis, fixed, a0, a1, ow, ext = r
            if a1 - a0 < 10: continue
            i0, i1 = sorted((fixed, fixed - ow * PT))       # across: from the edge inward
            if axis == "x":
                box("stone", (a0, i0, G), (a1, i1, G + PH_)); coll_box((a0, i0, G), (a1, i1, G + PH_))
                box("trim", (a0 - ext[0], i0 - 5, G + PH_), (a1 + ext[1], i1 + 5, G + PH_ + 12))
                if AP0.get("floor_course") and ow < 0 and abs(fixed - TER[0][2]) < 1:
                    # the podium's north face carries a string course at the terrace's floor (under its paving): from
                    # below, the floor behind the parapet is otherwise invisible, and a drain starting there read as a
                    # pipe hanging halfway up a blank wall. It stops either side of the hopper.
                    cuts = [(AP0["downpipe"]["x"] - 15, AP0["downpipe"]["x"] + 15)] if AP0.get("downpipe") and not AP0["downpipe"].get("at") else []
                    segs = [(a0, a1)]
                    for c0, c1 in cuts: segs = [q for s0, s1 in segs for q in ((s0, min(s1, c0)), (max(s0, c1), s1)) if q[1] - q[0] > 1]
                    for s0, s1 in segs: box("trim", (s0, fixed - 8, G - 12), (s1, fixed, G - 2))
            else:
                box("stone", (i0, a0, G), (i1, a1, G + PH_)); coll_box((i0, a0, G), (i1, a1, G + PH_))
                box("trim", (i0 - 5, a0 - ext[0], G + PH_), (i1 + 5, a1 + ext[1], G + PH_ + 12))
        for sx in (-1, 1):                                   # piers at the head of the flight down to the forecourt
            px, py = sx * (OPEN - 24), -460 + 24                 # just inside the parapet's end, which abuts it
            box("stone", (px - 24, py - 24, G), (px + 24, py + 24, G + 110)); coll_box((px - 24, py - 24, G), (px + 24, py + 24, G + 110))
            box("trim", (px - 30, py - 30, G + 110), (px + 30, py + 30, G + 124))
        print("PODIUM parapets:", [(r[0], round(r[1]), round(r[2]), round(r[3])) for r in runs])
        PDR = AP0.get("podium_dress", {})
        def loft(key, bot, zb, top, zt, coll=True):
            """a solid between two horizontal quads (2D corner lists in the same order): its sides and its top"""
            B_ = [Vector((q[0], q[1], zb)) for q in bot]; T_ = [Vector((q[0], q[1], zt)) for q in top]
            cen = (sum(B_, Vector()) + sum(T_, Vector())) / 8
            for i in range(4):
                f = [B_[i], B_[(i + 1) % 4], T_[(i + 1) % 4], T_[i]]
                if (f[1] - f[0]).cross(f[3] - f[0]).length < 1e-6: f = [B_[i], B_[(i + 1) % 4], T_[i]]
                poly(key, facing(f, sum(f, Vector()) / len(f) - cen))
                if coll and len(f) == 4: coll_quad(facing(f, sum(f, Vector()) / len(f) - cen))
            poly(key, facing(T_, UP))
        def frame_of(r):                                     # a run's face: along (unit 2D), out (unit 2D), and a point on it
            axis, fixed, a0, a1, ow = r[:5]
            return (Vector((1, 0, 0)), Vector((0, ow, 0)), lambda u: Vector((u, fixed, 0))) if axis == "x" else \
                   (Vector((0, 1, 0)), Vector((ow, 0, 0)), lambda u: Vector((fixed, u, 0)))
        KB = 0.22                                            # the batter's slope: 0.22 out per unit down (about 12 degrees)
        BATTER = []                                          # (run, z_b) for the slits and the buttresses
        for r in runs:
            al, ou, at_ = frame_of(r); a0, a1 = r[2], r[3]
            if a1 - a0 < 200: continue
            segs = [a0 + (a1 - a0) * k / max(1, round((a1 - a0) / 50)) for k in range(max(1, round((a1 - a0) / 50)) + 1)]
            gs = [ground(*(at_(u) + ou * 20).to_2d()) for u in segs]
            zmin = min(gs)
            if G - zmin < 220: continue
            zb_ = zmin + 0.42 * (G - zmin); BATTER.append((r, zb_))
            keep = [max(g0, g1) <= zb_ - 20 for g0, g1 in zip(gs, gs[1:])]
            for k, ((u0, g0), (u1, g1)) in enumerate(zip(zip(segs, gs), zip(segs[1:], gs[1:]))):
                if not keep[k]: continue
                b0, b1 = g0 - 40, g1 - 40
                q = [at_(u0) + UP * zb_, at_(u1) + UP * zb_, at_(u1) + ou * KB * (zb_ - b1) + UP * b1, at_(u0) + ou * KB * (zb_ - b0) + UP * b0]
                poly("base", facing(q, ou)); coll_quad(facing(q, ou))
                if k == 0 or not keep[k - 1]:                # a closing triangle where the batter starts ...
                    poly("base", facing([at_(u0) + UP * zb_, at_(u0) + ou * KB * (zb_ - b0) + UP * b0, at_(u0) + UP * b0], -al))
                if k == len(keep) - 1 or not keep[k + 1]:    # ... and where it ends
                    poly("base", facing([at_(u1) + UP * zb_, at_(u1) + ou * KB * (zb_ - b1) + UP * b1, at_(u1) + UP * b1], al))
        def buttress(base2d, w_in, along, out_, zt_, p_top=14, cap=26):
            """a tapering buttress on a face, its foot below the ground: projection from p_bot at the foot to p_top at
            zt_, then a sloped weathering to the face; w_in either side along the face"""
            gz = min(ground(*(base2d + along * s_ + out_ * 30).to_2d()) for s_ in (-w_in, 0, w_in)) - 40
            p_bot = p_top + 0.11 * (zt_ - gz) + 30
            rect = lambda pj, k_in=0: [base2d - along * w_in, base2d + along * w_in, base2d + along * w_in + out_ * pj, base2d - along * w_in + out_ * pj]
            loft("stone", [q.to_2d() for q in rect(p_bot)], gz, [q.to_2d() for q in rect(p_top)], zt_)
            loft("trim", [q.to_2d() for q in rect(p_top + 2)], zt_, [q.to_2d() for q in rect(1.0)], zt_ + cap, coll=False)
            return gz
        for bx, by, kind in PDR.get("buttresses", []):
            c2 = Vector((bx, by, 0))
            if kind == "corner":                             # clasping buttress round an outer corner (the faces' outward signs)
                sx_ = 1 if bx > 0 else -1; sy_ = -1
                gz = min(ground(bx + sx_ * 40, by + sy_ * 40), ground(bx - sx_ * 60, by + sy_ * 40), ground(bx + sx_ * 40, by - sy_ * 60)) - 40
                zt_ = G + 34; pt_, pb_ = 16, 16 + 0.11 * (zt_ - gz) + 40
                R = lambda pj: [(bx - sx_ * 95, by - sy_ * 95), (bx + sx_ * pj, by - sy_ * 95), (bx + sx_ * pj, by + sy_ * pj), (bx - sx_ * 95, by + sy_ * pj)]
                loft("stone", R(pb_), gz, R(pt_), zt_)
                loft("trim", R(pt_ + 2), zt_, R(1.0), zt_ + 26, coll=False)
                print("BUTTRESS corner", (bx, by), "foot", round(gz), "projection", round(pb_), "->", pt_)
            else:
                al_ = Vector((1, 0, 0)) if kind in ("+y", "-y") else Vector((0, 1, 0))
                ou_ = Vector({"-y": (0, -1, 0), "+y": (0, 1, 0), "-x": (-1, 0, 0), "+x": (1, 0, 0)}[kind])
                gz = buttress(c2, 45, al_, ou_, G + 34)
                print("BUTTRESS", kind, (bx, by), "foot", round(gz))
        avoid = [(b[0], b[1], 130) for b in PDR.get("buttresses", [])] + ([(AP0["podium_drain"]["x"], AP0["podium_drain"]["y"], 110)] if AP0.get("podium_drain") else [])
        def weep_slit(c_, al, ou, zs):
            q = [c_ - al * 6 + ou * 1.0 + UP * zs, c_ + al * 6 + ou * 1.0 + UP * zs, c_ + al * 6 + ou * 1.0 + UP * (zs + 30), c_ - al * 6 + ou * 1.0 + UP * (zs + 30)]
            poly("dirt", facing(q, ou))
            for s_ in (-1, 1):                               # dressed jambs and a sill: the slit reads as a hole in the wall
                p0_ = c_ + al * s_ * 6; p1_ = c_ + al * s_ * 12 + ou * 7
                box("trim", (min(p0_.x, p1_.x), min(p0_.y, p1_.y), zs - 2), (max(p0_.x, p1_.x), max(p0_.y, p1_.y), zs + 32))
            p0_ = c_ - al * 14 + UP * 0; p1_ = c_ + al * 14 + ou * 10
            box("trim", (min(p0_.x, p1_.x), min(p0_.y, p1_.y), zs - 8), (max(p0_.x, p1_.x), max(p0_.y, p1_.y), zs - 2))
        nsl = 0
        for r, zb_ in BATTER:                                # weep slits just above the batter, every ~230 along the face
            al, ou, at_ = frame_of(r); a0, a1 = r[2], r[3]
            k_ = max(1, int((a1 - a0) // 230))
            for i in range(k_):
                u = a0 + (a1 - a0) * (i + 0.5) / k_; c_ = at_(u)
                if any(math.hypot(c_.x - ax_, c_.y - ay_) < rad_ for ax_, ay_, rad_ in avoid): continue
                if ground(*(c_ + ou * 20).to_2d()) > zb_ - 50: continue   # well clear of the ground, or the grass hides it
                weep_slit(c_, al, ou, zb_ + 26); nsl += 1
        DP = AP0.get("downpipe")
        if DP:
            # The terrace's rain off its north edge, on the plain panel between the forecourt's right wall and the front
            # buttress (PLAN-hall2m item 9): a scupper through the parapet at the paving, a stone spout over an iron hopper
            # head, the downpipe on two holderbats standing 4 off the wall (so the wall behind it dries), its shoe over a
            # grated gully in a dressed stone frame at the foot; a weep slit either side, as the podium's other faces have
            # (out on wall F: 70 up they read as little barred windows; the pipe shows where the water goes).
            dx_, yf = DP["x"], TER[0][2]; ou_ = Vector((0, -1, 0)); al_ = Vector((1, 0, 0))
            # (the wall marked for it is F on the plan, the forecourt's side that faces Riverwood; it was first read as this north face, the compass a quarter turn out.
            # "at": where the wall's face, the pipe's line and the floor behind it are: everything below is still drawn as on the north face, and turned there. Its floor there is the platform's)
            AT_ = DP.get("at"); ground_ = ground
            if AT_:
                FX_, FY_, FZ_ = AT_
                globals()["FRAME"] = lambda p: (FX_ + (p[1] - yf), FY_ - (p[0] - dx_), p[2] + FZ_)
                ground_ = lambda x_, y_: ground(*FRAME((x_, y_, 0))[:2]) - FZ_
            def blk(key, x0, x1, y0, y1, z0, z1): box(key, (min(x0, x1), min(y0, y1), min(z0, z1)), (max(x0, x1), max(y0, y1), max(z0, z1)))
            # The ironwork wears the plain dark iron of smetaldet01 (its lower half; the upper half is riveted bronze plate,
            # which the planar mapping put on half the pipe), under its own key: the age pass must not read a pipe 4 off
            # the wall as an inside corner and darken a band either side of it.
            IRON = (0.04, 0.06, 0.36)                           # u from 0.04; v from 0.06, at most 0.36 of the sheet
            def iron_poly(pts, want):
                P_ = [Vector(p_) for p_ in facing(pts, want)]
                n_ = (P_[1] - P_[0]).cross(P_[2] - P_[0]).normalized()
                t_ = Vector((1, 0, 0)) if abs(n_.z) > 0.9 else UP.cross(n_).normalized(); b_ = n_.cross(t_)
                us = [q_.dot(t_) for q_ in P_]; vs = [q_.dot(b_) for q_ in P_]; h_ = max(1e-3, max(vs) - min(vs))
                poly("pipe", [tuple(q_) for q_ in P_], [(IRON[0] + (u - min(us)) / S, IRON[1] + min(IRON[2], h_ / S) * (v - min(vs)) / h_) for u, v in zip(us, vs)])
            def iron_box(x0, x1, y0, y1, z0, z1):
                x0, x1 = sorted((x0, x1)); y0, y1 = sorted((y0, y1)); z0, z1 = sorted((z0, z1))
                v = [Vector((x, y, z)) for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)]; cen = sum(v, Vector()) / 8
                for f in [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (3, 2, 6, 7), (2, 0, 4, 6), (1, 3, 7, 5)]:
                    q = [v[i] for i in f]; iron_poly([tuple(p_) for p_ in q], sum(q, Vector()) / 4 - cen)
            def pipe_path(pts, rad=4.5, seg=10):
                """a round pipe through pts (2+ points), mitred at each bend; its ends stay open (they run into the hopper
                and pour into the gully)"""
                P_ = [Vector(p_) for p_ in pts]; rings = []
                for i_, c_ in enumerate(P_):
                    d_ = ((P_[min(i_ + 1, len(P_) - 1)] - c_) + (c_ - P_[max(i_ - 1, 0)])).normalized()
                    u_ = Vector((1, 0, 0)); v_ = d_.cross(u_).normalized()
                    rings.append([c_ + (u_ * math.cos(2 * math.pi * k / seg) + v_ * math.sin(2 * math.pi * k / seg)) * rad for k in range(seg)])
                for i_ in range(len(P_) - 1):
                    ax_ = (P_[i_ + 1] - P_[i_]).normalized()
                    for k in range(seg):
                        q = [rings[i_][k], rings[i_][(k + 1) % seg], rings[i_ + 1][(k + 1) % seg], rings[i_ + 1][k]]
                        w_ = sum(q, Vector()) / 4 - P_[i_]; w_ -= ax_ * w_.dot(ax_)
                        iron_poly([tuple(p_) for p_ in q], w_)
            # The water's way has to read from the ground (a hopper with nothing visibly feeding it
            # makes no sense). The terrace's floor is the paving at G, hidden behind the parapet, so the floor line is
            # shown where the water leaves it: a framed opening through the parapet's foot, sill level with the paving,
            # a channelled stone spout out of it, and the hopper's rim right under the spout's lip.
            yi = yf + 34                                        # the parapet's inner face (PT)
            poly("dirt", facing([(dx_ - 11, yf - 0.6, 0), (dx_ + 11, yf - 0.6, 0), (dx_ + 11, yf - 0.6, 14), (dx_ - 11, yf - 0.6, 14)], ou_))
            for x0, x1 in ((dx_ - 17, dx_ - 11), (dx_ + 11, dx_ + 17)):
                blk("trim", x0, x1, yf + 1, yf - 3, -2, 14)     # its jambs
            blk("trim", dx_ - 17, dx_ + 17, yf + 1, yf - 3, 14, 20)          # its lintel
            blk("trim", dx_ - 12, dx_ + 12, yf + 2, yf - 16, -6, 0)          # the spout: a slab 16 out, its top the sill
            for x0, x1 in ((dx_ - 12, dx_ - 9), (dx_ + 9, dx_ + 12)):
                blk("trim", x0, x1, yf - 3, yf - 16, 0, 5)      # the channel's sides
            poly("dirt", facing([(dx_ - 9, yf - 3, 0.3), (dx_ + 9, yf - 3, 0.3), (dx_ + 9, yf - 16, 0.3), (dx_ - 9, yf - 16, 0.3)], UP))   # wet
            # on the terrace: the same opening with an iron grate, a lintel over it, and a grated drain in the paving
            # in front of it, so whoever walks the terrace sees where its water goes
            poly("dirt", facing([(dx_ - 11, yi + 0.6, 0.5), (dx_ + 11, yi + 0.6, 0.5), (dx_ + 11, yi + 0.6, 14), (dx_ - 11, yi + 0.6, 14)], -ou_))
            for k in (-7.5, -2.5, 2.5, 7.5): iron_box(dx_ + k - 0.8, dx_ + k + 0.8, yi + 0.2, yi + 1.8, 0, 14)
            blk("trim", dx_ - 15, dx_ + 15, yi - 1, yi + 2, 14, 19)
            poly("dirt", facing([(dx_ - 11, yi + 1, 0.4), (dx_ + 11, yi + 1, 0.4), (dx_ + 11, yi + 19, 0.4), (dx_ - 11, yi + 19, 0.4)], UP))
            for k in range(5):
                yb_ = yi + 1 + 18 * (k + 0.5) / 5; iron_box(dx_ - 11, dx_ + 11, yb_ - 0.9, yb_ + 0.9, 0.6, 1.4)
            # the hopper head under the spout's lip: an open iron box with a proud rim, a funnel down to the pipe
            hz0, hz1 = -39, -13; pyc = yf - 8.5                 # its rim just under the floor course; pyc: the pipe's axis, 4 off the wall
            iron_box(dx_ - 11, dx_ + 11, yf + 1, yf - 19, hz0, hz1 - 2)
            poly("dirt", facing([(dx_ - 9.5, yf - 1.5, hz1 - 1.6), (dx_ + 9.5, yf - 1.5, hz1 - 1.6), (dx_ + 9.5, yf - 17.5, hz1 - 1.6), (dx_ - 9.5, yf - 17.5, hz1 - 1.6)], UP))
            for x0, x1, y0, y1 in ((dx_ - 12.5, dx_ + 12.5, yf - 18, yf - 20.5), (dx_ - 12.5, dx_ + 12.5, yf + 1, yf - 2),
                                   (dx_ - 12.5, dx_ - 9.5, yf - 2, yf - 18), (dx_ + 9.5, dx_ + 12.5, yf - 2, yf - 18)):
                iron_box(x0, x1, y0, y1, hz1 - 4, hz1)          # the rim
            fb = [(dx_ - 5, pyc + 5), (dx_ + 5, pyc + 5), (dx_ + 5, pyc - 5), (dx_ - 5, pyc - 5)]
            ft = [(dx_ - 11, yf + 1), (dx_ + 11, yf + 1), (dx_ + 11, yf - 19), (dx_ - 11, yf - 19)]
            fc = Vector((dx_, yf - 9, hz0 - 4))
            for i in range(4):                                  # the funnel's four sides
                q = [(*fb[i], hz0 - 9), (*fb[(i + 1) % 4], hz0 - 9), (*ft[(i + 1) % 4], hz0 + 0.5), (*ft[i], hz0 + 0.5)]
                iron_poly(q, sum((Vector(p_) for p_ in q), Vector()) / 4 - fc)
            # the gully at the foot: a dressed frame round a grate over a dark pit, its top 3 over the ground there
            gs_ = [ground_(x_, y_) for x_ in (dx_ - 20, dx_, dx_ + 20) for y_ in (yf - 2, yf - 20, yf - 40)]
            gt = sum(gs_) / len(gs_) + 3; gb = min(gs_) - 12
            for x0, x1, y0, y1 in ((dx_ - 20, dx_ + 20, yf - 40, yf - 34), (dx_ - 20, dx_ + 20, yf - 6, yf + 1),
                                   (dx_ - 20, dx_ - 13, yf - 34, yf - 6), (dx_ + 13, dx_ + 20, yf - 34, yf - 6)):
                blk("trim", x0, x1, y0, y1, gb, gt); coll_box((x0, min(y0, y1), gb), (x1, max(y0, y1), gt))
            poly("dirt", facing([(dx_ - 13, yf - 6, gt - 9), (dx_ + 13, yf - 6, gt - 9), (dx_ + 13, yf - 34, gt - 9), (dx_ - 13, yf - 34, gt - 9)], UP))
            for k in range(5):
                yb_ = yf - 6 - 28 * (k + 0.5) / 5; iron_box(dx_ - 13, dx_ + 13, yb_ - 1.2, yb_ + 1.2, gt - 2.6, gt - 0.8)
            for xk in (-6.5, 6.5): iron_box(dx_ + xk - 1.2, dx_ + xk + 1.2, yf - 34, yf - 6, gt - 4.4, gt - 2.6)   # its bearers
            # the pipe: down from the funnel, a shoe kicking out over the grate, its mouth 4 above it
            zs_ = gt + 11
            pipe_path([(dx_, pyc, hz0 - 8), (dx_, pyc, zs_), (dx_, pyc - 7, zs_ - 7)])
            BR = [hz0 - 8 - (hz0 - 8 - zs_) * f_ for f_ in (0.3, 0.72)]
            for zb_ in BR:                                      # holderbats: a band round the pipe, a stem, a plate on the wall
                for x0, x1, y0, y1 in ((dx_ - 6, dx_ + 6, pyc - 6, pyc - 4.6), (dx_ - 6, dx_ - 4.6, pyc - 4.6, pyc + 4.6), (dx_ + 4.6, dx_ + 6, pyc - 4.6, pyc + 4.6)):
                    iron_box(x0, x1, y0, y1, zb_ - 1.8, zb_ + 1.8)
                iron_box(dx_ - 1.5, dx_ + 1.5, pyc + 4.6, yf + 1, zb_ - 1.8, zb_ + 1.8)
                iron_box(dx_ - 7, dx_ + 7, yf - 1, yf + 1, zb_ - 3, zb_ + 3)
            for sx_ in DP.get("slits", []):
                weep_slit(Vector((sx_, yf, 0)), al_, ou_, DP.get("slit_z", gt + 70)); nsl += 1
            if AT_ and DP.get("course"):                        # the floor's line along this face too, as the north face carries it, stopping either side of the hopper
                c0_, c1_ = DP["course"]
                for a_, b_ in ((c0_, FY_ - 15), (FY_ + 15, c1_)):
                    box("trim", (dx_ - (b_ - FY_), yf - 8, -12), (dx_ - (a_ - FY_), yf, -2))
            globals()["FRAME"] = None
            if AT_:                                             # (for the age pass: where the wall is, in the hall's frame)
                globals()["DOWNPIPE"] = {"face_x": FX_, "x": FY_, "y": FX_, "y_in": FX_ + 34, "z_hopper": hz0 - 9 + FZ_, "brackets": [b_ + FZ_ for b_ in BR], "z_foot": gt + FZ_}
            else:
                globals()["DOWNPIPE"] = {"x": dx_, "y": yf, "y_in": yi, "z_hopper": hz0 - 9, "brackets": BR, "z_foot": gt}
            print("DOWNPIPE at", AT_ or dx_, "| hopper", hz0, "-", hz1, "| gully top", round(gt), "| ground", [round(g_) for g_ in gs_], "| brackets", [round(b_) for b_ in BR], "| slits at", DP.get("slits", []))
        print("PODIUM batter on", len(BATTER), "faces;", nsl, "weep slits")
    # the building's foundation, rough stone from below the ground to the plinth, wherever no terrace holds it
    for x0, x1, y0, y1 in ((-1452, 1452, 158, 942), (-392, 392, -12, 1112), (328, 692, 748, 1124)):
        box("base", (x0, y0, ground_under(x0, x1, y0, y1) - 60), (x1, y1, G - 40)); coll_box((x0, y0, ground_under(x0, x1, y0, y1) - 60), (x1, y1, G - 40))
    SOIL = G + 30                                            # the beds' soil: just under the kerb's top (G + 45)
    def plant_bed(x0, x1, y0, y1):
        """a border planted full, mirrored about the door (vanilla TREE records). A jittered hex grid 84 apart covers the
        soil from the wall to the kerb, every plant wider than that; what grows where goes by depth: shrubs, ferns and
        lavender at the back, flowers and fern through the middle, low flowers and jazbay spilling at the kerb. Under
        a window only plants that stay below its sill (90 over the floor, 60 over the soil). Clover under everything.
        The same every build (a fixed random sequence per bed)."""
        sg = 1 if x0 > 0 else -1
        X = lambda u: sg * u                                 # u: distance from the door's axis
        lo, hi = min(abs(x0), abs(x1)) + 30, max(abs(x0), abs(x1)) - 30
        yk = y0 + 30                                         # the front kerb's inner face
        wall_y = lambda u: -12 if u < 392 else (134 if u >= 1042 else 158)   # the pavilion, the wing, the cross gable (plinths)
        WIN = (571, 881, 1256)                               # the arched windows over the bed
        PL = "meshes/plants/"; LP = "meshes/landscape/plants/"
        SPC = {"lav": (PL + "floralavender01.nif", 102, 149), "dt1": (PL + "floradragonstongue01.nif", 84, 132),
               "dt2": (PL + "floradragonstongue02.nif", 84, 154), "mf1b": (PL + "floramountainflower01blue.nif", 64, 115),
               "mf1p": (PL + "floramountainflower01purple.nif", 64, 115), "mf1r": (PL + "floramountainflower01red.nif", 64, 115),
               "mf2r": (PL + "floramountainflower02red.nif", 47, 139), "mf2b": (PL + "floramountainflower02blue.nif", 47, 139),
               "mf2p": (PL + "floramountainflower02purple.nif", 47, 139), "sfc6": (LP + "swordferncluster06.nif", 89, 140),
               "sfc1": (LP + "swordferncluster01.nif", 95, 207), "sf1": (LP + "swordfern01.nif", 70, 122),
               "sf3": (LP + "swordfern03.nif", 54, 124), "rf1": (LP + "reachfern01.nif", 42, 161),
               "jaz": (PL + "florajazbay01.nif", 15, 167), "ffs2": (LP + "fallforestshrub02.nif", 134, 207)}
        BACK = ["lav", "sfc6", "sfc1", "lav", "ffs2", "sfc6", "lav", "sfc1"]
        UNDER = ["sf3", "mf2r", "rf1", "mf2b", "sf3", "mf2p"]
        MID = ["lav", "dt1", "mf1b", "sf1", "dt2", "lav", "mf1p", "dt1", "mf1r", "sf1"]
        FRONT = ["mf2r", "rf1", "mf2b", "jaz", "mf2p", "rf1", "mf2r", "mf2b"]
        seed = [12345 + (7 if sg > 0 else 0)]
        def rnd():                                           # a fixed sequence: the same garden every build
            seed[0] = (seed[0] * 1103515245 + 12345) % 2147483648; return seed[0] / 2147483648
        d = 84; placed = []; nrow = 0
        y = yk + 22
        while y < 158 - 20:
            u = lo + 10 + (d / 2 if nrow % 2 else 0)
            while u <= hi - 10:
                uu = u + (rnd() - 0.5) * d * 0.5; yy = y + (rnd() - 0.5) * d * 0.4
                wy = wall_y(uu)
                if yy > wy - 26 or not lo - 10 <= uu <= hi + 10: u += d; continue
                t = (wy - yy) / (wy - yk)                    # 0 at the wall, 1 at the kerb
                under = t < 0.5 and any(abs(uu - w_) < 80 for w_ in WIN)
                pool = UNDER if under else (BACK if t < 0.34 else (MID if t < 0.68 else FRONT))
                key = pool[int(rnd() * len(pool))]
                if key == "ffs2" and (uu < 400 or any(abs(uu - w_) < 140 for w_ in WIN)): key = "sfc6"   # the tall shrub only on blank wall
                model, h, w = SPC[key]
                sc = 0.9 + 0.3 * rnd()
                if under: sc = min(sc, 58.0 / h)              # stays under the sill
                if key == "ffs2": sc = 0.8
                r = 0.42 * w * sc
                yy = min(yy, wy - 0.45 * r)                  # leaves may touch the wall, the plant does not stand in it
                half = 0.5 * w * sc                          # its leaves' reach, whichever way it is turned
                yy = max(yy, y0 + 4 + half)                  # it may lean over the kerb, never past its outer face onto the walk,
                uu = min(max(uu, lo - 26 + half), hi + 26 - half)   # nor past the end kerbs' outer faces
                placed.append((model, uu, yy, sc, r, key))
                u += d
            y += d * 0.866; nrow += 1
        for u in range(int(lo) + 110, int(hi) - 109, 175):   # clover, low under everything, so no soil shows between (kept off the ends)
            for t_ in (0.3, 0.7):
                yy = wall_y(u) - t_ * (wall_y(u) - yk)
                if yy > wall_y(u) - 40: continue
                sc_ = 1.0 + 0.2 * rnd()
                yy = max(yy + (rnd() - 0.5) * 40, y0 + 4 + 128 * sc_)        # clover is 207 x 256: kept inside the kerb too
                if yy > wall_y(u) - 30: continue
                uc_ = min(max(u + (rnd() - 0.5) * 60, lo - 26 + 128 * sc_), hi + 26 - 128 * sc_)
                placed.append((LP + "clover01.nif", uc_, yy, sc_, 95, "clover"))
        for model, uu, yy, sc, r, key in placed:
            EXTRA_PLACE.append((model, (X(uu), yy, SOIL), rnd() * 360, sc))
        # how much soil is covered: sample it every 12, a point is covered when a plant's reach (0.42 x its width) is over it
        pts = [(u_, y_) for u_ in range(int(lo), int(hi) + 1, 12) for y_ in range(int(yk), 158, 12) if y_ < wall_y(u_) - 6]
        cov = lambda use: sum(1 for (u_, y_) in pts if any((u_ - uu) ** 2 + (y_ - yy) ** 2 <= r * r for _, uu, yy, _, r, k in placed if use(k))) / len(pts)
        print("BED planted", len(placed), "plants (%d clover)" % sum(1 for q in placed if q[5] == "clover"),
              "| soil covered: by plants %.0f%%, with the clover %.0f%%" % (100 * cov(lambda k: k != "clover"), 100 * cov(lambda k: True)))
    # planter beds: a stone kerb, soil a little above the ground (grass and plants grow through it where the ground is high)
    for x0, x1, y0, y1 in BEDS:
        gmax = max(ground(x, y) for x in range(int(x0), int(x1) + 1, 40) for y in range(int(y0), int(y1) + 1, 40))
        top = G + 45                                         # the kerb's top: a low garden kerb
        for k, r in enumerate(((x0, x1, y0, y0 + 30), (x0, x0 + 30, y0 + 30, y1), (x1 - 30, x1, y0 + 30, y1))):   # front and ends; the wall is the back
            if k:                                            # an end runs back to the wall, or into the bank where it rises over the kerb
                ye = r[2]
                while ye < r[3] and max(ground(r[0], ye + 20), ground(r[1], ye + 20)) < top - 6: ye = min(r[3], ye + 20)
                if ye - r[2] < 20: continue
                r = (r[0], r[1], r[2], ye)
            kb = ground_under(*r) - 40
            box("stone", (r[0], r[2], kb), (r[1], r[3], top)); coll_box((r[0], r[2], kb), (r[1], r[3], top))
            if k == 0: box("trim", (r[0] - 4, r[2] - 4, top), (r[1] + 4, r[3] + 4, top + 10))
            else: box("trim", (r[0] - 4, r[2] + 4, top), (r[1] + 4, r[3] + 4, top + 10))
        step = 60
        x = x0 + 30
        while x < x1 - 30:
            y = y0 + 30
            while y < y1:
                xa, xb, ya, yb = x, min(x + step, x1 - 30), y, min(y + step, y1)
                gz = max(ground(xa, ya), ground(xb, ya), ground(xa, yb), ground(xb, yb))
                if gz < SOIL - 6:                                # soil wherever the ground is below it; ground above stays itself
                    box("dirt", (xa, ya, ground_under(xa, xb, ya, yb) - 30), (xb, yb, SOIL))
                y += step
            x += step
        coll_box((x0, y0, G), (x1, y1, SOIL))
        print("BED", (x0, x1, y0, y1), "kerb top", round(top), "ground up to", round(gmax))
        plant_bed(x0, x1, y0, y1)
    # the rear door: a stone patio at its sill (clear of the tower, x 680), a gabled timber porch over the door, and a
    # flight from the patio's back edge down to the yard (on the tower's side, where the yard is level; it falls away
    # to the right)
    if "REAR_DOOR" in globals():
        rx, ry, rz = REAR_DOOR
        X0p, X1p, Y1p = max(700, TX1), 1476, ry + 230       # across the wing's back, from the tower to its end
        lb = ground_under(X0p, X1p, ry, Y1p) - 40
        box("base", (X0p, ry, lb), (X1p, Y1p, rz - 6)); coll_box((X0p, ry, lb), (X1p, Y1p, rz))
        box("floor", (X0p, ry + 14, rz - 6), (X1p, Y1p, rz))      # from the string course's edge: its plate is the threshold
        fx0, fx1 = rx - 100, rx + 100                        # the flight on the door's axis (door, porch, steps: one centre line),
                                                             # its cheeks just inside the porch posts
        gb_ = ground((fx0 + fx1) / 2, Y1p + 220)
        n = max(2, round((rz - gb_) / 21)); rise = (rz - gb_) / n
        for i in range(n - 1):
            ya, yb = Y1p + i * 34, Y1p + (i + 1) * 34; top = rz - (i + 1) * rise
            box("steps", (fx0, ya, ground_under(fx0, fx1, ya, yb) - 40), (fx1, yb, top))
        ye = Y1p + (n - 1) * 34
        coll_quad([(fx0, Y1p, rz), (fx1, Y1p, rz), (fx1, ye, gb_), (fx0, ye, gb_)])
        RAMPS.append([[(fx0, ye, gb_), (fx1, ye, gb_)], [(fx0, Y1p, rz), (fx1, Y1p, rz)]])
        for xw in (fx0 - 20, fx1 + 20):                      # raked cheeks on the flight's nosing line + 64
            prof = [(Y1p, rz + 64)] + [(Y1p + (i + 1) * 34, rz - (i + 1) * rise + 64) for i in range(n - 1)]
            for (ya_, za_), (yb_, zb_) in zip(prof, prof[1:]):
                base = min(ground(xw, ya_), ground(xw, yb_)) - 40
                rake_wall("stone", (xw, ya_), (xw, yb_), za_, zb_, base, 40)
                rake_wall("trim", (xw, ya_), (xw, yb_), za_ + 12, zb_ + 12, (za_, zb_), 50, coll=False, s0=ya_ - Y1p, along=True)
        def pwall(x0, x1, y0, y1, cx0, cx1, cy0, cy1, z0=0.0):   # a level parapet and its coping (coping extents given)
            box("stone", (x0, y0, rz + z0), (x1, y1, rz + 64)); coll_box((x0, y0, rz), (x1, y1, rz + 64))
            box("trim", (cx0, cy0, rz + 64), (cx1, cy1, rz + 76))
        pwall(X0p, X0p + 40, ry, Y1p - 0.5, X0p - 5, X0p + 45, ry, Y1p + 5)   # left (0.5 short of the tower's corner post's
                                                                              # face, and the right one of the wing's corner post
        pwall(X1p - 40, X1p - 0.5, ry, Y1p, X1p - 45, X1p + 5, ry, Y1p + 5, z0=0.5)   # and the sill's underside: they lay in
                                                                              # their planes once the timbers' sides faced out,
                                                                              # FIX_FACES on outside since 2026-10-26)
        pwall(X0p + 40, fx0 - 40, Y1p - 40, Y1p, X0p + 45, fx0 - 45, Y1p - 45, Y1p + 5)   # back, either side of the flight,
        pwall(fx1 + 40, X1p - 40, Y1p - 40, Y1p, fx1 + 45, X1p - 45, Y1p - 45, Y1p + 5)   # up to its cheeks
        # (a gap between the steps' walls and the patio's) the cheeks (40, centred
        # on fx0 - 20 and fx1 + 20) start at Y1p and the back parapets stop at their outer lines, so the two met only at an edge and
        # left a 40 x 40 hole in each corner: filled, the parapet's stone and coping run on over it to the flight's sides (the
        # coping to Y1p only, where the cheek's own coping starts)
        for xa_, xb_, ca_, cb_ in ((fx0 - 40, fx0, fx0 - 45, fx0 + 5), (fx1, fx1 + 40, fx1 - 5, fx1 + 45)):
            box("stone", (xa_, Y1p - 40, rz), (xb_, Y1p, rz + 64)); coll_box((xa_, Y1p - 40, rz), (xb_, Y1p, rz + 64))
            box("trim", (ca_, Y1p - 45, rz + 64), (cb_, Y1p, rz + 76))
        # the porch: a timber gable breaking through the wing's eave (the eave is stopped over it, see the wing roof).
        # Two posts, a tie beam on knee braces, side plates back to the wall, a boarded ceiling; the roof runs back into
        # the wing's slope with a valley, so there is no gable against the wall and no sky between
        PW, PD, ze = PORCH_W, PORCH_D, PORCH_Z
        px0, px1, pyf = PORCH_ROOF["x0"], PORCH_ROOF["x1"], PORCH_ROOF["y_front"]
        assert (rx, ry, rz) == (REAR_X, WY1, S1 + 18), "the porch roof is laid out for the back door"
        for sx in (-1, 1):
            px = rx + sx * PW / 2
            box("wood", (px - 9, ry + PD - 9, rz), (px + 9, ry + PD + 9, ze)); coll_box((px - 9, ry + PD - 9, rz), (px + 9, ry + PD + 9, ze))
            bracket((px - sx * 9, ry + PD), (-sx, 0), (0, 1), ze - 14, 56, 64, thick=12, t=10)
            box("wood", (px - 9, ry, ze - 14), (px + 9, ry + PD - 10, ze + 4))          # side plate, post to wall
        box("wood", (px0, ry + PD - 10, ze - 14), (px1, ry + PD + 10, ze + 4))           # tie beam
        box("planks", (px0 + 1, ry + 1, ze - 2), (px1 - 1, ry + PD - 10, ze + 2))       # the boarded ceiling
        rg = abut_gable_roof(**PORCH_ROOF, verge=20)
        gable_frame(walls_of(px0, ry, px1, pyf)["back"][0], PW + 24, ze + 4, rg - ze - 4)
        EXTRA_PLACE.append(("meshes/architecture/solitude/doors/sdoubledoorint01.nif", (rx, ry, rz), 180, 1.0))
        # the patio, laid out (DESIGN-hall2.md): a walk along the house wall (y 930-1045) from the porch to the far end, clear
        # of everything (it also keeps the window clear: its sill is 30 above the paving); against the parapet, firewood
        # by the porch, the table with a chair at each end facing it, a lantern on it; one barrel in the far corner.
        # CommonChair01's sitter faces +y at yaw 0 (the bench's NIF root is turned 180 degrees, so the bench's faces -y).
        EXTRA_PLACE += [("meshes/clutter/firewood/firewoodpilemedium01.nif", (1140, 1080, rz), 0, 1.0, "FirewoodPileMedium01"),
                        ("meshes/furniture/common/commonchair01.nif", (1212, 1066, rz), 90, 1.0, "CommonChair01"),
                        ("meshes/clutter/common/commontablesquare01.nif", (1290, 1066, rz), 0, 1.0, "CommonTableSquare01"),
                        ("meshes/furniture/common/commonchair01.nif", (1368, 1066, rz), 270, 1.0, "CommonChair01"),
                        ("meshes/clutter/common/candlelantern01.nif", (1302, 1056, rz + 63), 30, 1.0, "Lantern"),
                        ("meshes/clutter/barrel02.nif", (1406, 962, rz), 0, 1.0, "Barrel02Static")]
        REAR_BOX = (X0p, X1p, ry, ye)
        print("REAR door at", (round(rx), round(ry), round(rz)), "patio", (X0p, X1p, ry, Y1p), "flight", n, "risers of", round(rise, 1), "to the yard at", round(gb_))
    if os.environ.get("AG_STAIR") == "twin":
        LY0, LY1, LX = -660, -460, 270                       # the landing: in front of the terrace edge, as wide as the portal
        lb = ground_under(-LX, LX, LY0, LY1) - 30
        box("floor", (-LX, LY0, lb), (LX, LY1, G)); coll_box((-LX, LY0, lb), (LX, LY1, G))
        box("trim", (-LX - 6, LY0 - 6, G - 10), (LX + 6, LY1, G + 10))
        box("stone", (-LX, LY0 - 24, lb), (LX, LY0, G + 44)); coll_box((-LX, LY0 - 24, lb), (LX, LY0, G + 44))   # its parapet
        box("trim", (-LX - 6, LY0 - 30, G + 44), (LX + 6, LY0 + 6, G + 58))
        feet = []
        for sgn in (-1, 1):
            x, z, n = sgn * LX, G, 0                       # from the landing's own end
            while n < 40:
                xa, xb = sorted((x, x + sgn * 34))
                if ground_under(xa, xb, LY0, LY1) >= z - 25 or abs(x) > 1560: break     # the ground has come up to meet it
                z -= 20
                fb = ground_under(xa, xb, LY0 - 24, LY1) - 30
                box("steps", (xa, LY0, fb), (xb, LY1, z)); x += sgn * 34; n += 1
                box("stone", (xa, LY0 - 24, fb), (xb, LY0, z + 44)); coll_box((xa, LY0 - 24, fb), (xb, LY0, z + 44))  # outer parapet
                box("trim", (xa, LY0 - 30, z + 44), (xb, LY0 + 6, z + 56))
            if n:
                xa, xb = sorted((LX * sgn, x))
                za, zb_ = (G, z) if sgn > 0 else (z, G)
                coll_quad([(xa, LY0, za), (xb, LY0, zb_), (xb, LY1, zb_), (xa, LY1, za)])    # one ramp under the flight
                coll_box((xa, LY0, ground_under(xa, xb, LY0, LY1) - 30), (xb, LY1, min(za, zb_)))
            feet.append((x, (LY0 + LY1) / 2, z)); print("TWIN", "left" if sgn < 0 else "right", n, "steps, foot at x", round(x), "z", round(z))
        CLEAR.append((-1200, 1200, -900, -460))
        STAIR_FOOT = (feet[0][0] - 200, -560, feet[0][2])
        BRAZIERS[:] = [(-230, -620), (230, -620)]          # on the landing's corners
    if os.environ.get("AG_STAIR") == "approach":
        import json as _j
        AP = _j.load(open(os.environ["AG_APPROACH"]))
        DZ = AP.get("floor_ref", SITE[2]) - SITE[2]           # the approach was laid out against floor_ref: keep it in the world
        for C_ in AP["courts"]: C_["z"] += DZ
        def flight_down(w, y_top, z_top, z_bot, label):
            """a broad flight descending toward -y from (y_top, z_top) onto a paved level at z_bot, cheek walls both sides"""
            n = max(1, round((z_top - z_bot) / 20)); rise = (z_top - z_bot) / n
            for i in range(n - 1):                              # n risers, n - 1 treads: the last riser stands on the paving
                y1_, y0_ = y_top - i * 34, y_top - (i + 1) * 34; top = z_top - (i + 1) * rise
                box("steps", (-w / 2, y0_, z_bot - 10), (w / 2, y1_, top))
                for sx in (-1, 1):
                    xa = sx * (w / 2 + 20)
                    box("stone", (xa - 20, y0_, z_bot - 10), (xa + 20, y1_, top + 44)); coll_box((xa - 20, y0_, z_bot - 10), (xa + 20, y1_, top + 44))
                    box("trim", (xa - 25, y0_, top + 44), (xa + 25, y1_, top + 54))
            ye = y_top - (n - 1) * 34
            coll_quad([(-w / 2, y_top, z_top), (w / 2, y_top, z_top), (w / 2, ye, z_bot), (-w / 2, ye, z_bot)][::-1])
            RAMPS.append([[(-w / 2, ye, z_bot), (w / 2, ye, z_bot)], [(-w / 2, y_top, z_top), (w / 2, y_top, z_top)]])
            print(label, n, "risers of", round(rise, 1), "x 34, width", w)
            return ye
        def build_court(C):
            cx0, cx1 = C["x"]; cy0, cy1 = C["y"]; cz = C["z"]
            global TURRET_BOX
            # the corner turret (toward Helgen): its inner quarter on the court's corner, the rest out over the drop
            TUR = (cx1 + 34 - 140, cx1 + 34 + 70, cy0 - 34 - 70, cy0 - 34 + 140) if C.get("turret") else None
            if TUR: TURRET_BOX = TUR
            # the drain: a culvert through the front wall at its foot, where the plateau below is lowest (water runs there)
            DRAIN = None
            if C.get("drain"):
                xs_ = [x for x in range(int(cx0 + 250), int((TUR[0] if TUR else cx1) - 150), 10)
                       if not any(o0 - 120 < x < o1 + 120 for o0, o1 in C.get("openings", {}).get("front", []))]
                dx_ = min(xs_, key=lambda x: ground(x, cy0 - 70)); g0 = ground(dx_, cy0 - 50)
                if g0 + 24 + 66 < cz - 40: DRAIN = (dx_ - 36, dx_ + 36, g0 + 24, g0 + 90, g0); globals()["DRAIN_AT"] = (dx_, cy0 - 34)
                print("DRAIN at x", dx_, "ground", round(g0), "court", cz, "" if DRAIN else "- too shallow, none")
            inside = max(ground(x, y) for x in range(int(cx0), int(cx1) + 1, 80) for y in range(int(cy0), int(cy1) + 1, 80))
            if inside > cz + 2: print("WARNING court at", cz, "has ground up to", round(inside), "inside it: the hill shows through the paving")
            gb = ground_under(cx0, cx1, cy0, cy1) - 40
            box("base", (cx0, cy0, gb), (cx1, cy1, cz - 6)); coll_box((cx0, cy0, gb), (cx1, cy1, cz))
            box("floor", (cx0, cy0, cz - 6), (cx1, cy1, cz))
            def gap(edge, a0, a1):
                return any(a1 > o0 and a0 < o1 for o0, o1 in C.get("openings", {}).get(edge, []))
            def outside(edge, a0, a1):
                m = (a0 + a1) / 2
                pt = {"front": (m, cy0 - 80), "left": (cx0 - 80, m), "right": (cx1 + 80, m)}[edge]
                for L2 in C.get("_lower", []):               # the next court down: its paving is the ground there
                    if L2["x"][0] <= pt[0] <= L2["x"][1] and L2["y"][0] <= pt[1] <= L2["y"][1]: return L2["z"]
                return ground(*pt)
            def edge_wall(edge, a0, a1, first=False, last=False):
                """a parapet where the ground falls away, a retaining wall where it stands above the court, a kerb if level"""
                T = 34
                if edge == "front": r = (a0, a1, cy0 - T, cy0)
                elif edge == "left": r = (cx0 - T, cx0, a0, a1)
                else: r = (cx1, cx1 + T, a0, a1)
                gout = outside(edge, a0, a1)
                if gout < cz - 30: lo, hi, cap = min(gout, cz) - 40, cz + 64, True
                elif gout > cz + 12: lo, hi, cap = cz - 10, gout + 16, True
                else: lo, hi, cap = cz - 10, cz + 14, False
                m_ = (a0 + a1) / 2
                if TUR and ((edge == "front" and m_ > TUR[0]) or (edge == "right" and m_ < TUR[3])):
                    hi, cap = cz - 6, False                      # under the turret's floor: the retaining wall only
                cut = (max(a0, DRAIN[0]), min(a1, DRAIN[1])) if DRAIN and edge == "front" and a0 < DRAIN[1] and a1 > DRAIN[0] else None
                if hi - lo > 110:                                # a tall wall: rough foundation stone under a dressed parapet
                    if cut:                                      # the culvert's opening through it
                        for xa_, xb_, za_, zb_ in ((a0, cut[0], lo, hi - 64), (cut[1], a1, lo, hi - 64), (cut[0], cut[1], lo, DRAIN[2]), (cut[0], cut[1], DRAIN[3], hi - 64)):
                            if xb_ - xa_ > 0.5: box("base", (xa_, r[2], za_), (xb_, r[3], zb_)); coll_box((xa_, r[2], za_), (xb_, r[3], zb_))
                    else: box("base", (r[0], r[2], lo), (r[1], r[3], hi - 64))
                    box("stone", (r[0], r[2], hi - 64), (r[1], r[3], hi))
                else: box("stone", (r[0], r[2], lo), (r[1], r[3], hi))
                if cut: coll_box((r[0], r[2], hi - 64), (r[1], r[3], hi))
                else: coll_box((r[0], r[2], lo), (r[1], r[3], hi))
                if cap:                                      # across: 5 proud both sides; along: only at a run's ends
                    e0, e1 = (5 if first else 0), (5 if last else 0)
                    if edge == "front": box("trim", (r[0] - e0, r[2] - 5, hi), (r[1] + e1, r[3] + 5, hi + 12))
                    else: box("trim", (r[0] - 5, r[2] + (5 if a0 == cy0 else -e0), hi), (r[1] + 5, r[3] + e1, hi + 12))
            for edge, (e0, e1) in (("front", (cx0 - 34, cx1 + 34)), ("left", (cy0, cy1)), ("right", (cy0, cy1))):
                runs = [(e0, e1)]                            # the edge minus its openings (a pier stands at each side)
                for o0, o1 in C.get("openings", {}).get(edge, []):
                    runs = [q for r0, r1 in runs for q in ((r0, min(r1, o0)), (max(r0, o1), r1)) if q[1] - q[0] > 1]
                tcut = (TUR[0] if edge == "front" else TUR[3] if edge == "right" else None) if TUR else None
                for r0, r1 in runs:                          # pieces of ~100; a piece boundary on the turret's edge
                    spans = [(r0, tcut), (tcut, r1)] if tcut and r0 < tcut < r1 else [(r0, r1)]
                    pcs = []
                    for s0, s1 in spans:
                        n = max(1, math.ceil((s1 - s0) / 100)); pcs += [(s0 + (s1 - s0) * k / n, s0 + (s1 - s0) * (k + 1) / n) for k in range(n)]
                    for k, (q0, q1) in enumerate(pcs): edge_wall(edge, q0, q1, first=(k == 0), last=(k == len(pcs) - 1))
            for edge, ops in C.get("openings", {}).items():          # piers flanking every opening
                for o0, o1 in ops:
                    for c in (o0, o1):
                        px, py = {"front": (c, cy0 - 17), "left": (cx0 - 17, c), "right": (cx1 + 17, c)}[edge]
                        pb = min(outside(edge, c - 1, c + 1), cz) - 40
                        box("stone", (px - 34, py - 34, pb), (px + 34, py + 34, cz + 96)); coll_box((px - 34, py - 34, pb), (px + 34, py + 34, cz + 96))
                        box("trim", (px - 42, py - 42, cz + 96), (px + 42, py + 42, cz + 112))
            if DRAIN:                                        # the culvert's dressing: jambs, lintel, the spout's lip, an iron grate
                d0_, d1_, ob, ot, g0 = DRAIN; dx_ = (d0_ + d1_) / 2; yf_ = cy0 - 34
                for xa_, xb_ in ((d0_ - 16, d0_), (d1_, d1_ + 16)): box("trim", (xa_, yf_ - 6, ob - 4), (xb_, yf_, ot))
                box("trim", (d0_ - 26, yf_ - 9, ot), (d1_ + 26, yf_, ot + 22))
                box("trim", (d0_ - 10, yf_ - 30, ob - 12), (d1_ + 10, yf_, ob))
                for k in range(6):
                    xb_ = d0_ + 8 + k * 11.2; box("metal", (xb_ - 2, yf_ + 8, ob), (xb_ + 2, yf_ + 12, ot))
                for zb_ in (ob + 18, ot - 18): box("metal", (d0_ + 1, yf_ + 6, zb_ - 2), (d1_ - 1, yf_ + 14, zb_ + 2))
                EXTRA_PLACE.extend(("meshes/landscape/plants/swordferncluster06.nif", (dx_ + sx * 100, yf_ - 45, ground(dx_ + sx * 100, yf_ - 45) - 4), 70 * sx + 20, 0.75) for sx in (-1, 1))
            if TUR:                                          # the turret: floor out over the drop on stepped corbels, a dwarf
                X0_, X1_, Y0_, Y1_ = TUR; cxw, cyw = cx1 + 34, cy0 - 34                  # wall, four posts, a slate pyramid
                for q in ((cx1, Y0_, X1_, Y1_), (X0_, Y0_, cx1, cy0)):
                    box("floor", (q[0], q[1], cz - 6), (q[2], q[3], cz)); box("base", (q[0], q[1], cz - 36), (q[2], q[3], cz - 6))
                    coll_box((q[0], q[1], cz - 36), (q[2], q[3], cz))
                for k in range(3):
                    zt_ = cz - 36 - 16 * k; st = 23 * (k + 1)
                    box("trim", (cxw, Y0_ + st, zt_ - 16), (X1_ - st, Y1_, zt_)); box("trim", (X0_, Y0_ + st, zt_ - 16), (cxw, cyw, zt_))
                PH2 = 60
                for q, t_ in (((X1_ - 22, Y0_, X1_, Y1_), (X1_ - 22, Y0_ - 4, X1_ + 4, Y1_)), ((X0_, Y0_, X1_ - 22, Y0_ + 22), (X0_ - 4, Y0_ - 4, X1_ - 22, Y0_ + 22)),
                              ((X0_, Y0_ + 22, X0_ + 22, cyw), (X0_ - 4, Y0_ + 22, X0_ + 22, cyw)), ((cxw, Y1_ - 22, X1_ - 22, Y1_), (cxw, Y1_ - 22, X1_ - 22, Y1_ + 4))):
                    box("stone", (q[0], q[1], cz), (q[2], q[3], cz + PH2)); coll_box((q[0], q[1], cz), (q[2], q[3], cz + PH2))
                    box("trim", (t_[0], t_[1], cz + PH2), (t_[2], t_[3], cz + PH2 + 10))
                zp = cz + 256
                for px_, py_, on_wall in ((X0_ + 11, Y0_ + 11, True), (X1_ - 11, Y0_ + 11, True), (X1_ - 11, Y1_ - 11, True), (X0_ + 11, Y1_ - 11, False)):
                    zb_ = cz + PH2 + 10 if on_wall else cz
                    box("wood", (px_ - 8, py_ - 8, zb_), (px_ + 8, py_ + 8, zp)); coll_box((px_ - 8, py_ - 8, zb_), (px_ + 8, py_ + 8, zp))
                    for ox, oy in ((1 if px_ < (X0_ + X1_) / 2 else -1, 0), (0, 1 if py_ < (Y0_ + Y1_) / 2 else -1)):
                        bracket((px_ + ox * 8, py_ + oy * 8), (ox, oy), (-oy, ox), zp - 16, 40, 48, thick=10, t=8)
                box("wood", (X0_ + 3, Y0_ + 3, zp - 16), (X1_ - 3, Y0_ + 19, zp)); box("wood", (X0_ + 3, Y1_ - 19, zp - 16), (X1_ - 3, Y1_ - 3, zp))
                box("wood", (X0_ + 3, Y0_ + 19, zp - 16), (X0_ + 19, Y1_ - 19, zp)); box("wood", (X1_ - 19, Y0_ + 19, zp - 16), (X1_ - 3, Y1_ - 19, zp))
                box("wood", (X0_ + 19, Y0_ + 7, cz + 112), (X1_ - 19, Y0_ + 15, cz + 122)); box("wood", (X1_ - 15, Y0_ + 19, cz + 112), (X1_ - 7, Y1_ - 19, cz + 122))
                pyramid(X0_, Y0_, X1_, Y1_, zp, 200, over=26)
                print("TURRET", TUR, "court", cz, "ground under its outer corner", round(ground(X1_, Y0_)))
            print("COURT", C["x"], C["y"], "at", cz, "| ground inside up to", round(inside))
        courts = AP["courts"]
        for k in range(len(courts) - 1): courts[k]["_lower"] = [courts[k + 1]]
        if "path" in AP:                                     # where the path arrives, the forecourt's front is open
            PTH = _j.load(open(os.path.join(os.path.dirname(os.path.abspath(os.environ["AG_APPROACH"])), AP["path"]))); lt = PTH["treads"][-1]; Ex = PTH["route"][-1][0]
            ext = (AP.get("route_w", 240) / 2 + 40) / max(0.3, lt["uy"])
            courts[-1].setdefault("openings", {})["front"] = [[Ex - ext - 5, Ex + ext + 5]]
        for C in courts: build_court(C)
        U = AP["upper"]; uw = U.get("w", 600)
        yb = flight_down(uw, -460, 0, courts[0]["z"], "UPPER stair")
        # (closer to the front doors, at the natural spot the door landing already has: its two front corners, inside the
        # low walls' ends at the stair's head) up on the landing: 4 inside the piers' inner faces (x 292) and 4 behind the stair's head (y -460),
        # the bowl 82 across its feet; 410 clear between them over the 600 stair. (They stood on the forecourt by the stair's foot)
        BRAZIERS[:] = [(sx * (292 - 4 - 41.3), -460 + 4 + 40.7) for sx in (-1, 1)]
        for k in range(len(courts) - 1):
            flight_down(courts[k].get("steps_w", 700), courts[k]["y"][0], courts[k]["z"], courts[k + 1]["z"], f"STEPS court {k + 1} -> {k + 2}")
        C = courts[-1]; cx0, cx1 = C["x"]; cy0, cy1 = C["y"]; cz = C["z"]
        # --- the grand stair: from the court's front edge down the bank, even risers that meet the ground at the foot
        if "path" in AP:
            TR = PTH["treads"]; rr = PTH["r"]; zr = PTH["z_road"] + DZ
            for t in TR: t["z"] += DZ
            W2 = AP.get("route_w", 240); HW = W2 / 2; PH = 60      # walking width, parapet height above the nosings
            V2 = lambda x, y: Vector((x, y, 0))
            lft = lambda u_: Vector((-u_.y, u_.x, 0))
            n = len(TR); U = [V2(t["ux"], t["uy"]).normalized() for t in TR]; Cn = [V2(t["x"], t["y"]) for t in TR]
            BP, BU = [V2(*PTH["route"][0])], [U[0]]              # boundaries: the foot on the road's edge ...
            for i in range(1, n):                                # ... between neighbours, on the bisector ...
                BP.append(((Cn[i - 1] + U[i - 1] * TR[i - 1]["len"] / 2) + (Cn[i] - U[i] * TR[i]["len"] / 2)) / 2)
                BU.append((U[i - 1] + U[i]).normalized())
            BP.append(V2(*PTH["route"][-1])); BU.append(U[-1])  # ... and the forecourt's front edge at the top
            BA = [lft(u_) for u_ in BU]; BA[-1] = V2(-1, 0) if U[-1].y > 0 else V2(1, 0)
            def side(i, off):                                    # off to the left (+) / right (-) of the walking line
                return BP[i] + BA[i] * (off / BA[i].dot(lft(BU[i])))
            for i, t in enumerate(TR):                           # treads: wedges on a curve, 10 into each wall
                q = [side(i, HW + 10), side(i, -HW - 10), side(i + 1, -HW - 10), side(i + 1, HW + 10)]
                pts2 = [(v.x, v.y) for v in q]
                prism("floor" if t["level"] else "steps", pts2, min(ground(*v) for v in pts2) - 40, t["z"], coll=False)
            # walking surface: a ramp over the treads (running up the lower steps could catch for a moment, like a collision
            # bump; measured: on the curve the inner side's treads are 21 deep for the same
            # 22.7 rise, a 47-degree ramp at treads 4-7 where the middle is 33). Along each side, a tread steeper than 40
            # hands its excess rise to its neighbours (half from each end, repeated until none is), the flights' ends held,
            # so the ramp keeps to the treads where it can (spreading the whole flight evenly instead sank it 24 below them on
            # the curve) and leans a little across the stair there; and the last tread rises to the forecourt (a bare
            # 22.7 step from the landing before).
            # (followers' feet clipped badly into the steps): the ramp runs on the nosings, as
            # Whiterun's castle stairs and stair platform collide (measured: never below a tread, hovering over the back of each);
            # it ran through the risers' feet, up to a whole riser under the nosings, and no vanilla stair sinks its walking surface
            # below the drawn treads. At the foot it reaches out a tread's depth onto the road to meet it (the first nosing is a
            # riser up)
            ZB = [t["z"] for t in TR] + [max(TR[-1]["z"], courts[-1]["z"])]   # (the top boundary: the forecourt's front edge)
            TAN_ = math.tan(math.radians(40))
            def spread(off):
                L_ = [(side(i + 1, off) - side(i, off)).length for i in range(n)]
                fix_ = {0, n} | {k for k in range(1, n) if (ZB[k] == ZB[k - 1]) != (ZB[k + 1] == ZB[k])}   # (flights' ends)
                z_ = list(ZB)
                for _ in range(2000):
                    worst_ = 0.0
                    for k in range(n):
                        e_ = (z_[k + 1] - z_[k]) - TAN_ * L_[k]
                        if e_ <= 0.01: continue
                        worst_ = max(worst_, e_); lo_, hi_ = k in fix_, k + 1 in fix_
                        if lo_ and hi_: continue
                        if not hi_: z_[k + 1] -= e_ / (1 if lo_ else 2)
                        if not lo_: z_[k] += e_ / (1 if hi_ else 2)
                    if worst_ <= 0.01: break
                return z_
            ZL, ZR = spread(HW), spread(-HW)
            for i, t in enumerate(TR):
                a0, b0, b1, a1 = side(i, HW), side(i, -HW), side(i + 1, -HW), side(i + 1, HW)
                coll_quad([(a0.x, a0.y, ZL[i]), (b0.x, b0.y, ZR[i]), (b1.x, b1.y, ZR[i + 1]), (a1.x, a1.y, ZL[i + 1])])
            D_ = TR[0]["len"]; a0, b0 = side(0, HW), side(0, -HW); a1, b1 = a0 - BU[0] * D_, b0 - BU[0] * D_   # (the apron onto the road)
            coll_quad([(a1.x, a1.y, min(zr, ground(a1.x, a1.y)) - 1), (b1.x, b1.y, min(zr, ground(b1.x, b1.y)) - 1), (b0.x, b0.y, ZR[0]), (a0.x, a0.y, ZL[0])])
            RAMPS.append([[(a1.x, a1.y, min(zr, ground(a1.x, a1.y)) - 1), (b1.x, b1.y, min(zr, ground(b1.x, b1.y)) - 1)]] +
                         [[(side(i, HW).x, side(i, HW).y, ZL[i]), (side(i, -HW).x, side(i, -HW).y, ZR[i])] for i in range(n + 1)])
            sl_ = [math.degrees(math.atan2(abs(z_[i + 1] - z_[i]), (side(i + 1, o) - side(i, o)).length)) for z_, o in ((ZL, HW), (ZR, -HW)) for i in range(n)]
            dv_ = [z_[k] - ZB[k] for z_ in (ZL, ZR) for k in range(n + 1)]   # (0 on the nosing; below it where a steep tread spread its rise)
            print("PATH ramp: steepest", round(max(sl_), 1), "degrees at its sides | off the nosings", round(min(dv_), 1), "..", round(max(dv_), 1), "(riser", rr, ")")
            for sd in (1, -1):                                   # parapets: mitred bands on the nosing line + PH
                P = [side(i, sd * (HW + 20)) for i in range(n + 1)]
                A_ = [BA[i] * (1 / BA[i].dot(lft(BU[i]))) for i in range(n + 1)]
                tops = [TR[min(i, n - 1)]["z"] + PH for i in range(n + 1)]
                tops = [max(tp, ground(*(P[i] + BA[i] * sd * 40).to_2d()) + 16) for i, tp in enumerate(tops)]   # retaining where the bank is higher
                gs = [ground(*v.to_2d()) for v in P]
                bases = [min(gs[max(0, i - 1):i + 2]) - 40 for i in range(n + 1)]
                band("stone", P, A_, 20, tops, bases)
                band("trim", P, A_, 25, [tp + 10 for tp in tops], [tp - (0 if k_ in (0, n) else 2) for k_, tp in enumerate(tops)], coll=False)   # (sits on the wall
                                                                 # at its two ends, so their end faces do not share the wall's)
            # moss at the treads' edges against the parapets (feet keep the middle clean), broken: the width wanders and
            # some edges have none; the landings carry more
            for i, t in enumerate(TR):
                for sd in (1, -1):
                    w0 = 34 * (1.3 * _n1(i * 0.9 + (0 if sd > 0 else 17), 5.0) - 0.15) * (1.4 if t["level"] else 1.0)
                    if w0 < 14: continue
                    rw = [side(i, sd * HW), side(i + 1, sd * HW)]; rm = [side(i, sd * (HW - w0 * 0.45)), side(i + 1, sd * (HW - w0 * 0.45))]
                    ri = [side(i, sd * (HW - w0)), side(i + 1, sd * (HW - w0))]
                    zt_ = t["z"] + 0.4
                    moss_quad("site", [(rw[0].x, rw[0].y, zt_), (rw[1].x, rw[1].y, zt_), (rm[1].x, rm[1].y, zt_), (rm[0].x, rm[0].y, zt_)], [0.85, 0.85, 0.45, 0.45])
                    moss_quad("site", [(rm[0].x, rm[0].y, zt_), (rm[1].x, rm[1].y, zt_), (ri[1].x, ri[1].y, zt_), (ri[0].x, ri[0].y, zt_)], [0.45, 0.45, 0.0, 0.0])
            # (the mock-ups' spots A and C) a hairline crack along the right wall's coping over treads
            # 11-13, running off its inner edge and down the face; a run-off stain under the left wall's coping joint at boundary 10, 110 long
            # (a little bolder than the mock-ups rendered it: AGH2XWearStain's opacity, textures/make_wear_textures.py). (The walls are
            # band's 20 a half width: 40 thick, the inner face at HW; the coping 50 wide, its inner edge at HW - 5, its top 10 over the wall's)
            P3 = lambda v_, z_: (v_.x, v_.y, z_)            # (side() gives the hall's points with z 0)
            def wall_pt(sd_, s_, off_):
                i_ = min(int(s_), n - 1); f_ = s_ - i_
                return side(i_, sd_ * off_) * (1 - f_) + side(i_ + 1, sd_ * off_) * f_, (TR[min(i_, n - 1)]["z"] * (1 - f_) + TR[min(i_ + 1, n - 1)]["z"] * f_) + PH
            if n > 14:
                for j_ in range(8):
                    s0_, s1_ = 11.3 + 1.6 * j_ / 8, 11.3 + 1.6 * (j_ + 1) / 8
                    (a0_, t0_), (a1_, t1_) = wall_pt(-1, s0_, HW), wall_pt(-1, s1_, HW)
                    (b0_, _), (b1_, _) = wall_pt(-1, s0_, HW + 12), wall_pt(-1, s1_, HW + 12)
                    wear_quad("site", "wearcrack", [(a0_.x, a0_.y, t0_ + 10.6), (a1_.x, a1_.y, t1_ + 10.6), (b1_.x, b1_.y, t1_ + 10.6), (b0_.x, b0_.y, t0_ + 10.6)],
                              [(j_ / 8, 0.7), ((j_ + 1) / 8, 0.7), ((j_ + 1) / 8, 0.3), (j_ / 8, 0.3)], (0, 0, 1))
                (e_, te_) = wall_pt(-1, 12.9, HW - 5.6); (e2_, _) = wall_pt(-1, 12.95, HW - 5.6); dd_ = (e2_ - e_).normalized()
                (ea_, tea_) = wall_pt(-1, 12.9 - 4 / 34.15, HW - 5.6); (eb_, teb_) = wall_pt(-1, 12.9 + 4 / 34.15, HW - 5.6)   # (along the coping's slope)
                wear_quad("site", "wearcrack", [P3(ea_, tea_ + 9.5), P3(eb_, teb_ + 9.5), P3(eb_, teb_ - 1), P3(ea_, tea_ - 1)],
                          [(0.95, 0.7), (0.95, 0.3), (1.0, 0.3), (1.0, 0.7)], P3(side(12, 0) - e_, 0))
                (f_, tf_) = wall_pt(-1, 12.9, HW - 0.6); (fa_, ta_) = wall_pt(-1, 12.9 - 5 / 34.15, HW - 0.6); (fb_, tb_) = wall_pt(-1, 12.9 + 5 / 34.15, HW - 0.6)   # (its top 4 under the wall's, along its slope)
                wear_quad("site", "wearcrack", [P3(fa_, ta_ - 4), P3(fb_, tb_ - 4), P3(f_ + dd_ * 3, tf_ - 34), P3(f_ - dd_ * 7, tf_ - 34)],
                          [(0.0, 0.75), (0.0, 0.25), (0.06, 0.25), (0.06, 0.75)], P3(side(12, 0) - f_, 0))
                (ga_, ta_) = wall_pt(1, 10.0 - 15 / 34.15, HW - 0.6); (gb_, tb_) = wall_pt(1, 10.0 + 15 / 34.15, HW - 0.6)   # (its top 4 under the wall's at each corner: the wall rises along it)
                wear_quad("site", "wearstain", [P3(ga_, ta_ - 4), P3(gb_, tb_ - 4), P3(gb_, tb_ - 114), P3(ga_, ta_ - 114)],
                          [(0, 1), (1, 1), (1, 0), (0, 0)], P3(side(10, 0) - ga_, 0))
            runs_, cur_ = [], []                                 # the longest landing: leaves against its outer parapet
            for i, t in enumerate(TR):
                if t["level"]: cur_.append(i)
                else:
                    if cur_: runs_.append(cur_)
                    cur_ = []
            if cur_: runs_.append(cur_)
            if runs_:
                lr = max(runs_, key=len); iu = lr[-1] + 1             # the riser at the landing's uphill end
                lp_ = side(iu, HW - 36) - U[iu] * 40; ld_ = U[iu]     # in the corner it makes with the outer parapet
                STAIR_LEAVES = (lp_.x, lp_.y, TR[lr[0]]["z"] + 1.0, math.degrees(math.atan2(ld_.x, ld_.y)))
            ptop = zr + AP.get("pier_h", 230)                   # gate piers, square to the road, on the wall ends
            for sd in (1, -1):
                c_ = side(0, sd * (HW + 20)) - BU[0] * 20; pg = ground(c_.x, c_.y); u0 = BU[0]
                a_, b_ = c_ - u0 * 58, c_ + u0 * 58
                obox("base", (a_.x, a_.y), (b_.x, b_.y), 116, pg - 40, max(pg, zr) + 40)
                a_, b_ = c_ - u0 * 46, c_ + u0 * 46
                if sd > 0:   # (2026-11-03) the left one's stair-side front arris chipped (the mock-ups' spot E), its foot on a bed joint so the
                    # broken corner is one block's, never across a joint; (2026-11-04) a course lower than first built, ~115 over the road, clear of the
                    # broken quarter above
                    J_ = bed_under(zr + 118)
                    Jb_ = bed_under(ptop - 34); Jm_ = bed_under(ptop - 1)          # the broken quarter's two courses: Jb_..Jm_, Jm_..ptop
                    notched_box("stone", (a_.x, a_.y), (b_.x, b_.y), 92, max(pg, zr) + 40, Jb_, [
                        # the knock: most of one block's corner, from the bed joint 32 up the arris (the course is 36) and at most 22 into a face, widest low
                        # on the front, higher on the side (26 by 11, the first remake, read too small to notice, 2026-11-04); its
                        # outline a lumpy sweep with small breaks in it (the second build's large zigzags stepped like a pagoda: a pattern, not a break)
                        (J_, [(0, 15, 20), (2.5, 16.5, 21.5), (5.5, 15.5, 22), (8.5, 16, 20), (11, 13.5, 18.5), (14.5, 11.5, 15.5), (17.5, 8.5, 12.5), (21, 7, 9), (24.5, 4.2, 6), (28, 2, 2.8), (32, 0, 0)])])
                    # the top quarter at the same arris broken away, the cap's and the shaft's top two courses (the cap and one or two
                    # courses, the stone cleared away): stepping back up the courses as the corner's blocks went, the cap broken past them
                    # each course's corner blocks gone whole, to the head joints its own texture draws (the first try broke them anywhere on the
                    # break's texture: a pale patch, not missing stone); the upper course stepping back further than the lower
                    d0_ = Vector((b_.x - a_.x, b_.y - a_.y, 0)).normalized(); s0_ = Vector((-d0_.y, d0_.x, 0)); k0_ = Vector((a_.x, a_.y, 0)) - s0_ * 46       # the corner; side face u runs +d, front -s
                    # (the texture draws no quoins, so a face has a joint where it has one: course 1 goes to its joint along the side (49) and
                    # snapped across the front (its only joint there at 75); course 2 snapped along the side (its joints at 6 and 83) and goes
                    # to its joint across the front (38); each wider than the one under it, as a failing corner steps back)
                    for z_lo, z_hi, wu_, wv_, ju_, jv_, sd_ in ((Jb_, Jm_, 49, 30, True, False, "pier quarter 1"), (Jm_, ptop, 60, 38, False, True, "pier quarter 2")):
                        zm_ = (z_lo + z_hi) / 2
                        Uc_ = head_into(k0_, d0_, zm_, wu_) if ju_ else wu_; Vc_ = head_into(k0_, -s0_, zm_, -wv_) if jv_ else wv_
                        broken_box("stone", (a_.x, a_.y), (b_.x, b_.y), 92, z_lo, z_hi, Uc_, Vc_, sd_, bottom=False, whole_u=ju_, whole_v=jv_)
                        print("PIER QUARTER", sd_, "course", round(z_lo, 1), round(z_hi, 1), "blocks gone to", round(Uc_, 1), "along,", round(Vc_, 1), "across")
                    # its hairline crack, from the chip's foot down the block below (spot F), 0.6 off the front face
                    P3 = lambda v_, z_: (v_.x, v_.y, z_)
                    fr_ = c_ - u0 * 46.6
                    wear_quad("site", "wearcrack", [P3(fr_ - BA[0] * 38, J_ - 1), P3(fr_ - BA[0] * 30, J_ - 1), P3(fr_ - BA[0] * 14, zr + 58), P3(fr_ - BA[0] * 22, zr + 58)],
                              [(0, 0.62), (0, 0.30), (1, 0.30), (1, 0.62)], P3(-u0, 0))
                    a_, b_ = c_ - u0 * 56, c_ + u0 * 56
                    broken_box("trim", (a_.x, a_.y), (b_.x, b_.y), 112, ptop, ptop + 22, 74, 56, "pier cap 1", coll=False)   # (past the shaft's, which is 10 in)
                    a_, b_ = c_ - u0 * 36, c_ + u0 * 36
                    broken_box("trim", (a_.x, a_.y), (b_.x, b_.y), 72, ptop + 22, ptop + 46, 58, 42, "pier cap 2", coll=False)   # (20 in from the cap under it)
                    continue
                obox("stone", (a_.x, a_.y), (b_.x, b_.y), 92, max(pg, zr) + 40, ptop)
                a_, b_ = c_ - u0 * 56, c_ + u0 * 56
                obox("trim", (a_.x, a_.y), (b_.x, b_.y), 112, ptop, ptop + 22, coll=False)
                a_, b_ = c_ - u0 * 36, c_ + u0 * 36
                obox("trim", (a_.x, a_.y), (b_.x, b_.y), 72, ptop + 22, ptop + 46, coll=False)
            lp = side(0, HW + 20) - BU[0] * 20                   # the signpost: beyond the left pier, along the road
            AP["sign"] = {"pos": [(lp + BA[0] * 140).x, (lp + BA[0] * 140).y], "arm": [-BU[0].x, -BU[0].y]}
            xs = [side(i, sd * (HW + 80)).x for i in range(n + 1) for sd in (1, -1)]; ys = [side(i, sd * (HW + 80)).y for i in range(n + 1) for sd in (1, -1)]
            CLEAR.append((min(xs), max(xs), min(ys), max(ys)))  # trees and small pieces along it
            print("PATH stair", n, "treads,", sum(1 for t in TR if t["level"]), "level, risers of", rr, "| foot", [round(v) for v in PTH["route"][0]],
                  "bearing", round(math.degrees(math.atan2(U[0].y, U[0].x))), "| top", TR[-1]["z"], "| forecourt opening", courts[-1]["openings"]["front"])
            STAIR_FOOT_R = tuple((BP[0] - BU[0] * 250).to_2d()) + (ground(*(BP[0] - BU[0] * 250).to_2d()),)
            # (the long stair had no small details to break it up: one clutter object that makes sense there, a satchel,
            # openable, a little loot: Hall2.cs's AGHall2StairSatchel) a satchel someone set down on the
            # left wall's coping at the landing (tread 17, its top 10 over the wall's), as the mock-up placed it, a little off square
            if n > 18 and TR[17]["level"]:
                sm_ = (side(17, HW + 20) + side(18, HW + 20)) / 2 + U[17] * 8
                EXTRA_PLACE.append(("meshes/clutter/containers/satchel.nif", (sm_.x, sm_.y, TR[17]["z"] + PH + 10),
                                    math.degrees(math.atan2(U[17].x, U[17].y)) + 89, 1.0, "AGHall2StairSatchel"))
        elif "route" in AP:
            RT = _j.load(open(AP["route"])); TR = RT["treads"]; rr = RT["r"]; zr = RT["z_road"] + DZ
            for t in TR: t["z"] += DZ
            W2 = AP.get("route_w", 240); NF = AP.get("fan", 4); PH = 60     # parapet height above the nosing line
            def road_y(x):                                       # the road's inner edge (hall frame), as surveyed
                E_ = AP["road_edge"]
                for (x0_, y0_), (x1_, y1_) in zip(E_, E_[1:]):
                    if min(x0_, x1_) <= x <= max(x0_, x1_): return y0_ + (y1_ - y0_) * (x - x0_) / (x1_ - x0_)
                return E_[0][1]
            xc = TR[NF]["x"]; xL, xR = xc - W2 / 2, xc + W2 / 2
            y_sq = TR[NF]["y"] - TR[NF]["len"] / 2               # the first square tread's front edge
            yRL, yRR = road_y(xL), road_y(xR)
            def gmin(pts2): return min(ground(q[0], q[1]) for q in pts2)
            # the fan: winders from the road's line (bottom) to the square line, around the left corner
            for k in range(NF):
                yl0 = yRL + (y_sq - yRL) * k / NF; yl1 = yRL + (y_sq - yRL) * (k + 1) / NF
                yr0 = yRR + (y_sq - yRR) * k / NF; yr1 = yRR + (y_sq - yRR) * (k + 1) / NF
                pts2 = [(xL - 10, yl0), (xR + 10, yr0), (xR + 10, yr1), (xL - 10, yl1)]      # 10 into each wall: no shared face
                prism("steps", pts2, gmin(pts2) - 40, zr + (k + 1) * rr, coll=False)
            # the square treads and landings: boundaries shared exactly; a landing (a run of level treads) is one block
            yb_ = y_sq; blocks = []
            for t in TR[NF:]:
                ye_ = t["y"] + t["len"] / 2
                if t["level"] and blocks and blocks[-1][3] and blocks[-1][2] == t["z"]: blocks[-1][1] = ye_
                else: blocks.append([yb_, ye_, t["z"], t["level"]])
                yb_ = ye_
            for y0b, y1b, zt, lev in blocks:
                pts2 = [(xL, y0b), (xR, y0b), (xR, y1b), (xL, y1b)]
                obox("floor" if lev else "steps", (xc, y0b), (xc, y1b), W2 + 20, gmin(pts2) - 40, zt, coll=False)
            # walking surfaces for collision: a ramp per flight, flat landings (built from the run of treads)
            runs = []; cur = None
            for i, t in enumerate(TR):
                kind = "landing" if t["level"] and i >= NF else "flight"
                if not cur or cur[0] != kind: cur = [kind, i, i]; runs.append(cur)
                else: cur[2] = i
            for kind, i0, i1 in runs:
                y0_ = (y_sq if i0 >= NF else None)
                yb_ = TR[i0]["y"] - TR[i0]["len"] / 2; ye_ = TR[i1]["y"] + TR[i1]["len"] / 2
                if kind == "landing":
                    coll_quad([(xL, yb_, TR[i0]["z"]), (xR, yb_, TR[i0]["z"]), (xR, ye_, TR[i0]["z"]), (xL, ye_, TR[i0]["z"])])
                else:
                    zb_ = (zr if i0 == 0 else TR[i0 - 1]["z"]); ze_ = TR[i1]["z"]
                    if i0 == 0: yb_L, yb_R = yRL, yRR
                    else: yb_L = yb_R = yb_
                    coll_quad([(xL, yb_L, zb_), (xR, yb_R, zb_), (xR, ye_, ze_), (xL, ye_, ze_)])
            # raked parapets along both sides, on the nosing line + PH; retaining where the bank outside is higher
            for side, xw in ((-1, xL - 20), (1, xR + 20)):
                prof = [(road_y(xw) + 30, zr + PH)]              # starts at the road beside the fan (the pier sits there)
                for i, t in enumerate(TR):
                    yf = (yRL + (y_sq - yRL) * i / NF if side < 0 else yRR + (y_sq - yRR) * i / NF) if i < NF else t["y"] - t["len"] / 2
                    prof.append((yf, t["z"] + PH))
                prof.append((TR[-1]["y"] + TR[-1]["len"] / 2, TR[-1]["z"] + PH))
                prof = [(y_, max(z_, ground(xw + side * 40, y_) + 16)) for y_, z_ in prof]
                if os.environ.get("AG_DEBUG_PROF"): print("PROF", side, [(round(y_), round(z_)) for y_, z_ in prof])
                for (ya_, za_), (yb2, zb2) in zip(prof, prof[1:]):
                    if yb2 - ya_ < 1: continue
                    base = min(ground(xw, ya_), ground(xw, yb2)) - 40
                    rake_wall("stone", (xw, ya_), (xw, yb2), za_, zb2, base, 40)
                    rake_wall("trim", (xw, ya_), (xw, yb2), za_ + 10, zb2 + 10, (za_ - 2, zb2 - 2), 50, coll=False, s0=ya_ - prof[0][0], along=True)
            # gate piers at the foot, one height, standing on the road's edge each side of the fan
            ptop = zr + AP.get("pier_h", 420)
            for px, py in ((xL - 45, yRL - 10), (xR + 45, yRR - 10)):
                pg = ground(px, py)
                box("base", (px - 60, py - 60, pg - 40), (px + 60, py + 60, max(pg, zr) + 40))
                box("stone", (px - 48, py - 48, max(pg, zr) + 40), (px + 48, py + 48, ptop)); coll_box((px - 60, py - 60, pg - 40), (px + 60, py + 60, ptop + 40))
                box("trim", (px - 58, py - 58, ptop), (px + 58, py + 58, ptop + 22))
                box("trim", (px - 36, py - 36, ptop + 22), (px + 36, py + 36, ptop + 46))
            yfoot = min(yRL, yRR)
            print("ROUTE stair", len(TR), "treads,", sum(1 for t in TR if t["level"]), "level, risers of", rr, "| fan", NF, "from the road", round(yRL), round(yRR), "to", round(y_sq),
                  "| top", TR[-1]["z"], "at y", TR[-1]["y"] + TR[-1]["len"] / 2)
            STAIR_FOOT_R = (xc - 150, yRR - 250, ground(xc - 150, yRR - 250))
        else:
            Gd = AP["grand"]; gw = Gd.get("w", 400); every = Gd.get("landing_every", 9); LAND = Gd.get("landing", 160)
            def layout(n):
                y, out = cy0, []
                for i in range(n):
                    out.append(("step", y, y - 34)); y -= 34
                    if (i + 1) % every == 0 and i < n - 1: out.append(("landing", y, y - LAND)); y -= LAND
                return out, y
            best = None
            if "n" in Gd:                                         # a set flight: n steps, landings after the listed steps
                after = set(Gd.get("landing_after", []))
                def layout(n):
                    y, out = cy0, []
                    for i in range(n):
                        out.append(("step", y, y - 34)); y -= 34
                        if (i + 1) in after: out.append(("landing", y, y - LAND)); y -= LAND
                    return out, y
            for n in ([Gd["n"]] if "n" in Gd else range(6, 40)):
                parts, yfoot = layout(n)
                rise = (cz - (ground(0, yfoot) + 2)) / n           # the foot meets the ground on the stair's centre line
                if not 16 <= rise <= 23 and "n" not in Gd: continue
                # how far the walking line is buried anywhere, and how high it stands over the ground
                z, worst_b, worst_h = cz, 0, 0
                for kind, ya, yb in parts:
                    if kind == "step": z -= rise
                    gmax = max(ground(x, (ya + yb) / 2) for x in (-gw / 2, 0, gw / 2))
                    worst_b = max(worst_b, gmax - z); worst_h = max(worst_h, z - gmax)
                score = abs(rise - 20) * 4 + max(0, worst_b - 10) * 3
                if best is None or score < best[0]: best = (score, n, rise, parts, yfoot, worst_b, worst_h)
            _, n, rise, parts, yfoot, worst_b, worst_h = best
            z = cz; prev = cz
            for kind, ya, yb in parts:
                if kind == "step": z -= rise
                base = min(ground(x, y) for x in (-gw / 2, gw / 2) for y in (ya, yb)) - 40
                box("steps" if kind == "step" else "floor", (-gw / 2, yb, base), (gw / 2, ya, z))
                for sx in (-1, 1):
                    xa = sx * (gw / 2 + 22)
                    cb = min(ground(xa, y) for y in (ya, yb)) - 40
                    ct = max(z + 48, max(ground(xa + sx * 40, y) for y in (ya, yb)) + 16)   # retaining where the bank is higher
                    box("stone", (xa - 22, yb, cb), (xa + 22, ya, ct)); coll_box((xa - 22, yb, cb), (xa + 22, ya, ct))
                    box("trim", (xa - 28, yb, ct), (xa + 28, ya, ct + 12))
            coll_quad([(-gw / 2, cy0, cz), (gw / 2, cy0, cz), (gw / 2, yfoot, z), (-gw / 2, yfoot, z)][::-1])
            coll_box((-gw / 2, yfoot, min(ground(0, yfoot), z) - 60), (gw / 2, cy0, z - 4))
            print("GRAND stair", n, "steps of", round(rise, 1), "x 34, landings every", every, "| foot at y", round(yfoot), "z", round(z),
                  "ground", round(ground(0, yfoot)), "| buried up to", round(worst_b), "stands up to", round(worst_h), "over the ground")
            # --- stone pillars framing the foot of the grand stair
            for sx in (-1, 1):
                px, py = sx * (gw / 2 + 110), yfoot + 70; pg = ground(px, py)      # beside the bottom steps, off the road
                box("base", (px - 58, py - 58, pg - 40), (px + 58, py + 58, pg + 40))
                box("stone", (px - 46, py - 46, pg + 40), (px + 46, py + 46, pg + 380)); coll_box((px - 58, py - 58, pg - 40), (px + 58, py + 58, pg + 420))
                box("trim", (px - 56, py - 56, pg + 380), (px + 56, py + 56, pg + 404))
                box("trim", (px - 34, py - 34, pg + 404), (px + 34, py + 34, pg + 430))
        # --- the left gateway: the signpost beside the opening, facing the road
        sxp, syp = AP["sign"]["pos"]; sg = ground(sxp, syp)
        # (option B of a sheet of vanilla's 46 signs: a guild version of the others, on hooks, as physical as MGO's: blender/sign_nif.py) vanilla's post at the
        # inn pole's height, 1.36, and the towns' shield board on its own hinge, 1.25 (vanilla scales hinged signs too: 0.8 to 1.3); its bar along the old arm, 243 up, 4 under the post's collar
        arm = AP["sign"].get("arm", [-1, 0])
        EXTRA_PLACE += [("meshes/clutter/signage/whiterun/signwrpost01.nif", (sxp, syp, sg), 0, 1.36, "SignWRPost01"),
                        ("meshes/adventurersguild/hall2/aghall2sign.nif", (sxp, syp, sg + 243), math.degrees(math.atan2(arm[0], arm[1])), 1.25, "AGHall2Sign")]
        for (ax, ay), (bx, by) in AP.get("paths", []):
            A2, B2 = Vector((ax, ay, 0)), Vector((bx, by, 0)); dd = B2 - A2; Ln = dd.length; dd.normalize()
            k = max(1, int(Ln // 60))
            for i in range(k):
                a2 = A2 + dd * (Ln * i / k); b2 = A2 + dd * (Ln * (i + 1) / k); m = (a2 + b2) / 2
                gz = max(ground(m.x, m.y), min(cz, ground(m.x, m.y) + 40))
                obox("floor", (a2.x, a2.y), (b2.x, b2.y), 260, gz - 40, gz + 4, coll=False)
        for bx, by, byaw in AP.get("benches", []):           # vanilla benches (sittable): centred on their origin, the sitter
                                                             # facing -y at yaw 0, -x at 90, +y at 180, +x at 270
            EXTRA_PLACE.append(("meshes/furniture/common/commonbench01.nif", (bx, by, G), byaw, 1.0))
        for sx in (-1, 1):                                   # timber planters either side of the front door, clear of the
            cx_, cy_ = sx * 215, -80                         # banners on the pilasters (their fringe 33 over the paving)
            for (ax_, ay_, bx_, by_) in ((-40, -40, 40, -32), (-40, 32, 40, 40), (-40, -32, -32, 32), (32, -32, 40, 32)):
                box("wood", (cx_ + ax_, cy_ + ay_, G), (cx_ + bx_, cy_ + by_, G + 52))
            box("dirt", (cx_ - 32, cy_ - 32, G), (cx_ + 32, cy_ + 32, G + 44)); coll_box((cx_ - 40, cy_ - 40, G), (cx_ + 40, cy_ + 40, G + 52))
            EXTRA_PLACE.append(("meshes/plants/floralavender01.nif", (cx_, cy_, G + 44), 40 * sx, 0.55))
        for model, tx, ty, tsc in AP.get("trees", []):       # pines and bushes framing the hall, on the ground
            EXTRA_PLACE.append((model, (tx, ty, ground(tx, ty) - 8), (tx * 7 + ty * 3) % 360, tsc))
        # ivy, hung as vanilla hangs it (Riverwood's farmhouses: the patch's top under a beam or a sill, draping down),
        # from the copings of the podium's tall corners and the overlook, by hand from AP["ivy"] = [model, x, y, face,
        # scale, drop (a second patch lower in the same drape), why, standoff (optional)]. Measured on 29 of Riverwood's
        # (KNOWLEDGEBASE.local.md): Ivy02/03 are 138 tall round their origin and only 31-34 thick, the wall on the
        # patch's local +y, its origin 2-19 off the wall; on flat stone 4. (22, from a wrong 44 thick, floated the leaves
        # 17-37 off the overlook's wall, visibly.)
        IVY = []
        for e_ in AP.get("ivy", []):
            nm_, ix, iy, face, sc_, drop, why = e_[:7]; off_ = e_[7] if len(e_) > 7 else 4
            # (the right gate pier's, as in the mock-ups: its faces turned to the road, not to the hall's axes, and some 400 under
            # the hall's floor) face may be the face's outward normal [nx, ny]; a ninth item the patch's top, absolute (Ivy02/03's leaves 76 over their origin, the meshes' own bounds)
            if isinstance(face, list):
                nx_, ny_ = face; yaw_ = math.degrees(math.atan2(-nx_, -ny_)) % 360
            else:
                nx_, ny_ = {"-y": (0, -1), "+y": (0, 1), "-x": (-1, 0), "+x": (1, 0)}[face]
                yaw_ = {"-y": 0, "+y": 180, "-x": 90, "+x": 270}[face]          # local +y toward the wall
            # (the right gate pier's: the top of the ivy hangs from the bottom of the stone edge cap; the
            # mesh's top 20 are flat cards lying back into the wall, its dense leaves reach 55 over the origin (as the tavern's, 3a3a52c): the
            # ninth item is where the dense leaves start, the cards tuck behind the cap. The coping rule below is left as it was, deliberately)
            z_ = e_[8] - 55 * sc_ if len(e_) > 8 else G + 62 - 75 * sc_ - drop
            IVY.append((nm_, (ix + nx_ * off_ * sc_, iy + ny_ * off_ * sc_, z_), yaw_, sc_, why))
        for nm_, pos_, yaw_, sc_, why in IVY:
            EXTRA_PLACE.append((f"meshes/architecture/farmhouse/{nm_}.nif", pos_, yaw_, sc_, nm_.capitalize()))
        print("IVY", len(IVY), "patches:", "; ".join(sorted(set(w for *_, w in IVY))))
        # signs of life, each with a reason and out of every way through (DESIGN-hall2.md): a delivery stacked in the
        # forecourt's back left corner against the terrace wall, behind anyone walking from the stair to the terrace flight.
        # Training belongs in a training room or the yard behind, not in front of the door; a cart has no level verge at
        # the stair's foot that is off the road and out of the way (rock on the right, the signpost and the stair's mouth
        # on the left), so there is none.
        cz0 = courts[0]["z"]; C0 = courts[0]
        # (2026-10-28, the placement gate and the clutter audit: the barrels, 56 across, stood 56-58 apart and clipped, one
        # square to the court; 64 apart now, each turned its own way. The top crate on the lower one's top board (its lid 2
        # under its box's top: it floated 3); the long-side crate 8 off the terrace wall. 2026-10-29: the first two barrels 3 apart at
        # their bellies, 7 now; the crates beside the second 7 further, clear of it)
        LIFE = [("meshes/clutter/barrel02.nif", (C0["x"][0] + 37, C0["y"][1] - 34, cz0), 17, 1.0, "Barrel02Static"),
                ("meshes/clutter/barrel02.nif", (C0["x"][0] + 101, C0["y"][1] - 40, cz0), 41, 1.04, "Barrel02Static"),
                ("meshes/clutter/barrel02.nif", (C0["x"][0] + 38, C0["y"][1] - 98, cz0), 76, 0.97, "Barrel02Static"),
                ("meshes/clutter/common/cratesmall03.nif", (C0["x"][0] + 177, C0["y"][1] - 38, cz0 + 25), 8, 1.0, "CrateSmall03Weathered"),
                ("meshes/clutter/common/cratesmall04.nif", (C0["x"][0] + 175, C0["y"][1] - 40, cz0 + 72), 97, 1.0, "CrateSmall04Weathered"),
                ("meshes/clutter/common/cratesmall01.nif", (C0["x"][0] + 38, C0["y"][1] - 168, cz0 + 24), 93, 1.0, "CrateSmall01Weathered")]
        EXTRA_PLACE.extend(LIFE)
        print("LIFE", len(LIFE), "pieces: a delivery in the forecourt's back corner")
        # (an empty market stall stood in the bay along the terrace wall for a day; removed for now, the space left for later:
        # too tall, and vanilla's Solitude textures repainted by each install's replacers)
        # ---- age and life (DESIGN-hall2.md): every piece has a cause, and the cause gives its place
        cz_ = courts[0]["z"]; fx0 = courts[0]["x"][0]
        MOSS_RUNS = [   # (foot line, z, side the paving is on, base width, seed, why)
            ([(fx0, -720), (fx0, -460), (-345, -460)], cz_ + 0.4, -1, 60, 1.0, "forecourt: the foot of the podium wall, its north side in shade all day"),
            ([(-1452, 230), (-1452, 916)], G + 0.4, 1, 32, 2.0, "left walk: the wing's foot, a narrow damp passage (to the walk's back edge)"),
            ([(-1566, 690), (-1566, 160)], G + 0.4, 1, 26, 3.0, "left walk: the parapet's foot"),
            ([(1452, 318), (1452, 190)], G + 0.4, 1, 30, 4.0, "right walk: the wing's foot"),
            ([(1566, -100), (1566, 318)], G + 0.4, 1, 24, 5.0, "right walk: the parapet's foot"),
            ([(-1700, 724), (-1796, 724), (-1796, 792)], G + 0.4, -1, 42, 6.0, "overlook: its front inside corner"),
            ([(-1796, 828), (-1796, 896), (-1700, 896)], G + 0.4, -1, 42, 7.0, "overlook: its back inside corner")]
        for path_, z_, sd_, w_, sdd, why in MOSS_RUNS: moss_ribbon(path_, z_, sd_, w_, seed=sdd)
        print("MOSS", len(MOSS_RUNS), "ribbons +", "stair edges |", len(GEO.get(("site", "moss"), [])), "faces")
        AGE_PLACE = [   # (model, pos, yaw, scale, EditorID, why)
            ("meshes/architecture/riften/clutter/rtleavesflat01.nif", (355, courts[0]["y"][0] + 38, cz_ + 0.5), 32, 0.55, "RTLeavesFlat01",
             "leaves: the forecourt's front-right inside corner, where the wind drops them"),
            ("meshes/architecture/riften/clutter/rtleavesflat02.nif", (-1752, 858, G + 1.0), 205, 0.75, "RTLeavesFlat02", "leaves: the overlook's far corner"),
            ("meshes/architecture/riften/clutter/rtleavesflat02.nif", (1440, 1128, 418 + 0.5), 75, 0.45, "RTLeavesFlat02", "leaves: the patio's far corner, past the chair"),
            ("meshes/landscape/plants/swordfern01.nif", (878, -494, ground(878, -494) - 4), 30, 0.9, None, "fern: the front buttress's inside angle, north face"),
            ("meshes/landscape/plants/swordfern01.nif", (1042, -494, ground(1042, -494) - 4), 205, 0.8, None, "fern: the front buttress's other inside angle"),
            ("meshes/landscape/plants/swordferncluster06.nif", (226, courts[0]["y"][0] - 60, ground(226, courts[0]["y"][0] - 60) - 4), 110, 0.8, None,
             "ferns: the north foot of the forecourt's front wall")]
        if "STAIR_LEAVES" in globals():
            lx_, ly_, lz_, lyaw = STAIR_LEAVES
            AGE_PLACE.append(("meshes/architecture/riften/clutter/rtleavesflat02.nif", (lx_, ly_, lz_), lyaw + 90, 0.45, "RTLeavesFlat02", "leaves: the stair's long landing, its uphill corner against the parapet"))
        kitchen = min(CHIMNEYS, key=lambda c: c[0])           # the left wing's: the dining hall and its kitchen
        AGE_PLACE.append(("meshes/effects/ambient/fxsmokechimney02.nif", (kitchen[0], kitchen[1], kitchen[2] - 45), 0, 1.0, "FXSmokeChimney02",
                          "smoke: the kitchen fire, 45 down the flue as vanilla sets it"))
        for hx_, hy_, ht_ in CHIMNEYS:
            if abs(hx_) < 1:
                AGE_PLACE.append(("meshes/effects/ambient/fxsmokechimney02.nif", (hx_, hy_, ht_ - 45), 0, 1.0, "FXSmokeChimney02",
                                  "smoke: the great hearth in the hall, its stack on the ridge"))
        cbx, cby = 600, 1500                                 # level yard, 330 left of the back stairs' foot, under the pine
        cbz = sum(ground(cbx + dx_, cby + dy_) for dx_ in (-100, 0, 100) for dy_ in (-80, 0, 80)) / 9 - 2
        AGE_PLACE.append(("meshes/furniture/clutter/woodchoppingblock.nif", (cbx, cby, cbz), 0, 1.0, "WoodChoppingBlock",
                          "chopping block: wood for the hearths is split here and carried up to the stack by the back door"))
        # (the outside was barren and needed more clutter, each piece placed by best practice and validated). What vanilla sets round its halls and houses (HallSpike `pairs` over the
        # worldspaces: Jorrvaskr's terraces carry a bench, a chair with a goblet, a sack and food; Breezehome food barrels and a
        # woodpile), each with its cause, in the places no one walks through, measured on the export (the hall's sides stand 34
        # inside the parapet: nothing goes there; the front strip's ends past the beds, x 1402..1566, are dead ends)
        rl_ = random.Random("exterior life")
        j_ = lambda a: rl_.uniform(-a, a)
        # the delivery: the handcart that brought it, along the forecourt's left wall (its box 93 x 165, its axle 33 under its
        # origin), clear of the small crate; two sacks of flour among the barrels
        AGE_PLACE.append(("meshes/clutter/carts/handcart02.nif", (C0["x"][0] + 46.6 + 4 + j_(1), -769 + j_(4), cz0 + 33.2), j_(1.2), 1.0, "HandCart02",
                          "the delivery's handcart, left by the wall to go back to town"))
        for sx_, sy_ in ((-940, -566), (-878, -560)):
            AGE_PLACE.append(("meshes/clutter/containers/miscsacklarge.nif", (sx_ + j_(3), sy_ + j_(3), cz0 + 28), rl_.uniform(0, 360), 1.0, "MiscSackLarge",
                              "the delivery: a sack of flour for the kitchen"))
        # (in the way in game, so removed) the front strip's left end had a barrel
        # for a table with two chairs, tankards, a plate and bread: the barrel stood at x -1474, in the walk's way through (x -1566..-1469),
        # and furniture_check never ran outside. All of it removed; its 19 draws are still taken so the pieces after it keep their places
        for _ in range(19): rl_.random()
        # two benches with a tankard left at the end of the seat (the bench's seat 30 high, x -83..83, its sitters at x 0, +-46).
        # (it looked badly placed) a free turn could put the handle (8.3 out) over the seat's end, the
        # tankard on the very corner against the planter: its handle now turned in toward the bench's middle (BasicTankard01's
        # handle at local +y), its body 5.2 round, so it stands at most 77 out, 6 inside the end and clear of the outer sitter
        for bx_, ex_ in ((-1000, 72), (560, -72)):
            AGE_PLACE.append(("meshes/clutter/dining set/basictankard01.nif", (bx_ + ex_ + j_(1.5), -265 + j_(3), G + 30 + 0.15),
                              (270 if ex_ > 0 else 90) + rl_.uniform(-15, 15), 1.0, "BasicTankard01", "a tankard left on the bench"))
        # (option A) the overlook off the left walk (its paving x -1796..-1600, y 724..896; the walk's way through along x -1566..-1469 stays clear): a round table with
        # the view, two chairs before it facing the valley (CommonChair01's sitter faces +y at yaw 0), a basket by the parapet. Its own seed, so the pieces above and below keep theirs
        ro_ = random.Random("overlook 2026-11-02"); jo_ = lambda a: ro_.uniform(-a, a); ot_ = (-1722 + jo_(2), 816 + jo_(2))
        AGE_PLACE.append(("meshes/clutter/common/commontableround01.nif", (ot_[0], ot_[1], G), ro_.uniform(0, 360), 1.0, "CommonTableRound01", "a table with the view, on the overlook"))
        # (no one could sit in them, so one went; with the interior's lesson,
        # a chair sat in and left from its side) the two chairs were boxed in by the table and the walls (the seat gate's open
        # faults). The one by the basket (y 778) is gone; the other keeps its place and faces the table and the valley,
        # entered from its side into the room the first one left (its draws still taken, so the pieces after keep theirs)
        for y_, yaw_ in ((778, 258), (856, 286)):
            cx_, cy_, cyaw_ = -1648 + jo_(3), y_ + jo_(3), yaw_ + jo_(5)
            if y_ == 778: continue
            # (the seat gate: at x -1648 and yaw 286 its left was still the table's) square to the valley (yaw 270) and 8
            # back, its left (-y) clear of the table's corner (x up to -1666 turned), its right the wall: it sits and stands to its left
            cx_, cyaw_ = -1640 + (cx_ + 1648) / 3, 270 + (cyaw_ - yaw_) / 2.5
            # (getting up, the game stood the sitter forward into the table; it must sit down and stand up
            # from the open side) vanilla's CommonChair01L: the same chair, its front and right entries disabled (as vanilla sets a chair
            # with something at its front and right)
            AGE_PLACE.append(("meshes/furniture/common/commonchair01.nif", (cx_, cy_, G), cyaw_, 1.0, "CommonChair01L", "a chair at the table, facing the valley"))
        AGE_PLACE.append(("meshes/clutter/common/candlelanternwithcandle01.nif", (ot_[0] - 10 + jo_(3), ot_[1] + 8 + jo_(3), G + 63 + 0.15), ro_.uniform(0, 360), 1.0, "CandleLanternwithCandle01", "a lantern on the table"))
        for dx_, dy_, m_, ed_ in ((18, -16, "dining set/basictankard01", "BasicTankard01"), (14, 18, "dining set/basictankard01", "BasicTankard01"), (-4, -14, "common/flagon01", "Flagon")):
            AGE_PLACE.append((f"meshes/clutter/{m_}.nif", (ot_[0] + dx_ + jo_(3), ot_[1] + dy_ + jo_(3), G + 63 + 0.15), ro_.uniform(0, 360), 1.0, ed_, "set down on the table"))
        AGE_PLACE.append(("meshes/clutter/basket05.nif", (-1764 + jo_(3), 752 + jo_(3), G), ro_.uniform(0, 360), 1.0, "Basket05", "a basket by the parapet"))
        # the front strip's right end, past the bed (y -426..-240): the hall's split wood stacked (six hearths) against the side
        # wall, a medium pile and a small one (FirewoodPileMedium01: x -47..44, y -64..34; Small01 66 deep)
        # (the firewood was in the followers' way: Ghrulek stood stuck by it ~35 s
        # in game; the hall's wood stays by the back door and in the yard) gone; its draw still taken, so the pieces after keep theirs
        j_(1)
        # (a small pile beside it cut the corner pier's foot, the gate and the render: one pile)
        # the yard: the woodpile one takes an armful from, beside the block (WoodPickUp: x -109..42, y 3..123 of its origin), as
        # Breezehome's yard has it; the block's split wood stacked against the patio's wall behind it (y 1160)
        wpx_, wpy_ = 400 + j_(5), 1478 + j_(5)                    # (left of the block: right of it the back stairs come down)
        AGE_PLACE.append(("meshes/furniture/woodpickup.nif", (wpx_, wpy_, sum(ground(wpx_ + dx_, wpy_ + 60 + dy_) for dx_ in (-80, 0, 30) for dy_ in (-50, 0, 50)) / 9 - 2),
                          j_(4), 1.0, "WoodPile", "a woodpile by the block: wood to split, or an armful to carry"))
        fpx_ = 600 + j_(8)
        AGE_PLACE.append(("meshes/clutter/firewood/firewoodpilelarge01.nif", (fpx_, 1160 + 69 + 3, sum(ground(fpx_ + dx_, 1232 + dy_) for dx_ in (-80, 0, 100) for dy_ in (-60, 0, 60)) / 9 - 1),
                          j_(2), 1.0, "FirewoodPileLarge01", "the block's split wood, stacked against the patio's wall"))
        for m_, pos_, yaw_, sc_, ed_, why in AGE_PLACE:
            EXTRA_PLACE.append((m_, pos_, yaw_, sc_, ed_) if ed_ else (m_, pos_, yaw_, sc_))
        print("AGE pieces", len(AGE_PLACE), ":", "; ".join(w for *_, w in AGE_PLACE))
        CLEAR_ALL.extend(AP.get("clear", [])); CLEAR.extend(AP.get("clear_trees", []))
        if AP.get("tight_clear"):                            # hide trees and small pieces only where the hall and its terraces stand
            keep = [c for c in CLEAR if c != (-1700, 1700, -1000, 1250)]; m_ = 60
            near = list(tiles) + [tuple(b) for b in BEDS] + [(-1452, 1452, 158, 942), (-392, 392, -12, 1124), (328, 692, 748, 1124)] + \
                   ([TURRET_BOX] if "TURRET_BOX" in globals() else []) + \
                   [(C_["x"][0], C_["x"][1], C_["y"][0], C_["y"][1]) for C_ in courts] + ([REAR_BOX] if "REAR_BOX" in globals() else [])
            CLEAR[:] = keep + [(a_ - m_, b_ + m_, c_ - m_, d_ + m_) for a_, b_, c_, d_ in near]
        STAIR_FOOT = STAIR_FOOT_R if ("route" in AP or "path" in AP) else (0, yfoot - 300, ground(0, yfoot - 300))
    if os.environ.get("AG_STAIR") == "legs":
        import json as _j
        legs = _j.load(open(os.environ["AG_STAIR_LEGS"]))
        feet = []
        for leg in legs:
            if "landing" in leg:
                x0, x1, y0, y1 = leg["landing"]; z = leg["z"]
                lb = ground_under(x0, x1, y0, y1) - 40
                box("stone", (x0, y0, lb), (x1, y1, z - 6)); coll_box((x0, y0, lb), (x1, y1, z))
                box("floor", (x0, y0, z - 6), (x1, y1, z))
                for e in leg.get("parapet", []):
                    if e == "-x": r = (x0 - 24, x0, y0, y1)
                    elif e == "+x": r = (x1, x1 + 24, y0, y1)
                    elif e == "-y": r = (x0 - 24, x1 + 24, y0 - 24, y0)
                    else: r = (x0 - 24, x1 + 24, y1, y1 + 24)
                    pb = ground_under(r[0], r[1], r[2], r[3]) - 40
                    box("stone", (r[0], r[2], pb), (r[1], r[3], z + 50)); coll_box((r[0], r[2], pb), (r[1], r[3], z + 60))
                    box("trim", (r[0] - 4, r[2] - 4, z + 50), (r[1] + 4, r[3] + 4, z + 64))
            elif "flight" in leg:
                (ax, ay), (bx, by) = leg["flight"]; zt, zb_ = leg["z"]; w = leg.get("w", 240)
                A, Bp = Vector((ax, ay, 0)), Vector((bx, by, 0)); d = (Bp - A); L = d.length; d.normalize()
                n = max(1, round((zt - zb_) / 20)); tread = L / n; rise = (zt - zb_) / n
                left = Vector((-d.y, d.x, 0))                  # to the left walking from A to B (down the flight)
                walls = leg.get("walls", "both")
                for i in range(n):
                    a2 = A + d * (i * tread); b2 = A + d * ((i + 1) * tread)
                    top = zt - (i + 1) * rise
                    q = [a2 + left * (w / 2), a2 - left * (w / 2), b2 - left * (w / 2), b2 + left * (w / 2)]
                    base = min(ground(c.x, c.y) for c in q) - 40
                    obox("steps", a2, b2, w, base, top, coll=False)
                    for side in (("left", 1), ("right", -1)):
                        if walls in ("both", side[0]):
                            off = side[1] * (w / 2 + 18)
                            cq = [a2 + left * (off - 18), b2 + left * (off + 18)]
                            cb = min(ground(c.x, c.y) for c in cq) - 40
                            obox("stone", a2, b2, 36, cb, top + 48, off=off)
                            obox("trim", a2, b2, 46, top + 48, top + 58, off=off, coll=False)
                # walking surface: one ramp over the whole flight, solid to the ground under it
                coll_quad([tuple(A + left * (w / 2)) [:2] + (zt,), tuple(A - left * (w / 2))[:2] + (zt,),
                           tuple(Bp - left * (w / 2))[:2] + (zb_,), tuple(Bp + left * (w / 2))[:2] + (zb_,)][::-1])
                print("FLIGHT", n, "steps of", round(rise, 1), "x", round(tread, 1), "from", (ax, ay, zt), "to", (bx, by, zb_))
                feet.append((bx, by, zb_))
            elif "path" in leg:
                (ax, ay), (bx, by) = leg["path"]; w = leg.get("w", 200)
                A, Bp = Vector((ax, ay, 0)), Vector((bx, by, 0)); d = Bp - A; L = d.length; d.normalize()
                k = max(1, int(L // 60))
                for i in range(k):
                    a2 = A + d * (L * i / k); b2 = A + d * (L * (i + 1) / k); m = (a2 + b2) / 2
                    gz = ground(m.x, m.y)
                    obox("floor", a2, b2, w, gz - 30, gz + 6, coll=False)
                feet.append((bx, by, ground(bx, by)))
        xs = [c for leg in legs for pt in (leg.get("flight") or leg.get("path") or []) for c in pt[:1]]
        CLEAR.append((-2300, 2300, -1400, -460))
        f0 = min(feet, key=lambda f: f[2]) if feet else (0, -900, -300)
        STAIR_FOOT = (f0[0], f0[1] - 150, f0[2])
    if os.environ.get("AG_STAIR") == "line":
        tx, ty, fx, fy = (float(v) for v in os.environ["AG_STAIR_LINE"].split(","))
        T, Fp = Vector((tx, ty, 0)), Vector((fx, fy, 0)); d = (Fp - T).normalized(); L = (Fp - T).length
        W2, TREAD = 300, 34
        z, t, nsteps, nflat = G, -20.0, 0, 0              # starts a little inside the terrace edge
        while t < L + 60:
            a2 = T + d * t; b2 = T + d * (t + TREAD); mid = (a2 + b2) / 2
            ahead = ground(b2.x, b2.y)
            nz = z - 20 if ahead < z - 30 else z           # down a step only where the ground has dropped below it
            base = min(ground(q.x, q.y) for q in (a2, b2, mid)) - 40
            if nz <= ground(mid.x, mid.y) + 2 and t > L - 40: break     # at the foot: on the ground
            obox("steps", a2, b2, W2, base, nz, coll=False)
            coll_quad([(a2.x + (-d.y) * W2 / 2, a2.y + d.x * W2 / 2, z), (a2.x - (-d.y) * W2 / 2, a2.y - d.x * W2 / 2, z),
                       (b2.x - (-d.y) * W2 / 2, b2.y - d.x * W2 / 2, nz), (b2.x + (-d.y) * W2 / 2, b2.y + d.x * W2 / 2, nz)][::-1])
            for sd_ in (-1, 1):                                    # cheek walls with a cap
                obox("stone", a2, b2, 40, base, nz + 44, off=sd_ * (W2 / 2 + 20))
                obox("trim", a2, b2, 52, nz + 44, nz + 56, off=sd_ * (W2 / 2 + 20), coll=False)
            if nz < z: nsteps += 1
            else: nflat += 1
            z, t = nz, t + TREAD
        print("LINE stair", nsteps, "steps,", nflat, "level treads, foot at", (round(b2.x), round(b2.y)), "z", round(z), "ground", round(ground(b2.x, b2.y)))
        xs = (tx, fx); ys = (ty, fy)
        CLEAR.append((min(xs) - 300, max(xs) + 300, min(ys) - 300, max(ys) + 100))
        STAIR_FOOT = (fx, fy, ground(fx, fy))
    y_top, z_top, flights = -472, G, 0
    while os.environ.get("AG_STAIR") not in ("twin", "line", "legs", "approach"):
        n = 0; y = y_top; z = z_top
        while n < 10 and ground(0, y - 34) < z - 10:
            z -= 20; y -= 34; n += 1
        if n == 0: break
        steps(0, y_top, z_top, z, 420, base=PB)
        y_top, z_top, flights = y, z, flights + 1
        if ground(0, y_top - 34) < z_top - 10:                  # a landing, then the next flight
            box("steps", (-230, y_top - 120, PB), (230, y_top, z_top)); coll_box((-230, y_top - 120, PB), (230, y_top, z_top)); y_top -= 120
        if flights > 6: break
    print("STAIR", flights, "flights, foot at", round(y_top), "z", round(z_top), "terrace foot", round(PB))
    if os.environ.get("AG_STAIR") not in ("twin", "line", "legs", "approach"):
        CLEAR.append((-320, 320, y_top - 150, -900))
        STAIR_FOOT = (0, y_top - 200, z_top)
else:
    box("stone", (-1600, -460, G - 160), (1600, 1150, G - 4)); coll_box((-1600, -460, G - 160), (1600, 1150, G))
    box("floor", (-1600, -460, G - 4), (1600, 1150, G))
    box("trim", (-1612, -472, G - 10), (1612, -440, G + 10))
    steps(0, -472, G, G - 160, 420)
    STAIR_FOOT = (0, -900, G - 160)
PLACE = [("meshes/architecture/whiterun/wrclutter/wrbrazier01.nif", (b_[0], b_[1], b_[2] if len(b_) > 2 else G + 80), 0, 1.0) for b_ in BRAZIERS] + EXTRA_PLACE
# (the braziers outside were unlit, bowls only, while the ones inside burned) the fire vanilla stands in
# them, as the bath's: 19.7 over the origin at 0.87
PLACE += [("meshes/effects/fxfirewithembers01_cheap.nif", (b_[0], b_[1], (b_[2] if len(b_) > 2 else G + 80) + 19.7), 0, 0.87, "FXfireWithEmbers01_Cheap") for b_ in BRAZIERS]
PLACE += [("meshes/architecture/solitude/doors/sdoubledoorint01.nif", (0, PY0, G), 0, DSC)]

# banners on the portal's pilasters, as drawn on the plan (the standing ones beside the pilasters were half
# hidden by them): Jorrvaskr's hanging banner (its rod 19 out from its origin and 19 above it, the cloth 188 long, 40 wide),
# the rod against the pilaster's face, its top 1 under the lintel. Named: MarkarthBanner01 shares the mesh.
# (the Jorrvaskr banners are out everywhere in the guild hall, the door's pair among them: the hall has its own, and another faction's would break lore)
# (something else for the front door: vanilla's own habit at its great doors is light, its iron torches lit) vanilla's lit torch on each pilaster, 1.3
# (a little lower; DoorTorch.cs measured vanilla's torches by a door at 83-99 over the sill outside (Riften, Thirsk), about half
# the door, the flame's top near 140; at 160 ours topped out level with the door's head) 125: vanilla's outside height scaled to the 1.3 door
PLACE += [("meshes/clutter/common/torchpermanent01.nif", (sx * PIL, PY0 - 34, G + 125), 180, 1.3, "TorchPermanantOn") for sx in (-1, 1)]
# the guild's own banners on the wings' timber storey (sketch C, between the upper
# storey's windows, its largest, in style A, one gold frame; blender/banner_nif.py, textures/make_banner_texture.py): 330 x 90, two
# a wing, centred between the windows; their rods' tops at 620, 26 under the side gables' bargeboard ends (z 640..650, 43 out:
# measured on the meshes); their brackets on the timber face, measured at y 110 on the outer columns and 116 on the inner (its
# top rail); the cloth 20 out, in front of the overhang's beam (10 out) and the brackets under it (behind the face)
# (so they move with the wind like other banners: rigged, banner_nif.py; one variant each, its own loop, so no two move in step)
PLACE += [(f"meshes/adventurersguild/hall2/aghall2banner330{v_.lower()}.nif", (bx_, by_, G + 620), 0, 1.0, "AGHall2Banner330" + v_)
          for v_, bx_, by_ in (("A", -1076, 110), ("B", -726, 116), ("C", 726, 116), ("D", 1076, 110))]

# ground
if not SITE:
    poly("grass", [(-6000, -6000, G - 160), (6000, -6000, G - 160), (6000, 6000, G - 160), (-6000, 6000, G - 160)], scale=512)

PART = "body"

# ---------------------------------------------------------------- age: shade, grime and damp in the vertex colours
# (vanilla's way: Bryling House's walls carry vertex colours averaging 0.81, down to 0.24 in corners and under jetties)
AGE_CELL = {"stone": 16, "base": 24, "trim": 16, "stucco": 16, "steps": 16, "floor": 24, "roof": 32, "wood": 0, "planks": 0, "break": 0}
COLS = {}
def age_pass():
    from mathutils.bvhtree import BVHTree
    t0 = time.time()
    V_, F_ = [], []                                          # occluders: the hall and the ground round it
    for (pt_, k_), faces in GEO.items():
        if k_ in ("moss", "pipe", "break"): continue         # (a pipe 4 off a wall is no inside corner: it shades nothing; nor is a chip's few-unit
                                                             # scar, which darkened the stone pieces about its edge into patches, 2026-11-03)
        for pts, uvs in faces:
            F_.append(list(range(len(V_), len(V_) + len(pts)))); V_ += [Vector(p_) for p_ in pts]
    if SITE:
        xs_ = list(range(-2600, 2601, 96)); ys_ = list(range(-2600, 2401, 96))
        base_ = len(V_); V_ += [Vector((x_, y_, ground(x_, y_))) for y_ in ys_ for x_ in xs_]; nx_ = len(xs_)
        for j_ in range(len(ys_) - 1):
            for i_ in range(nx_ - 1):
                a_ = base_ + j_ * nx_ + i_; F_.append([a_, a_ + 1, a_ + nx_ + 1, a_ + nx_])
    NHALL = len(F_) if not SITE else len(F_) - (len(ys_) - 1) * (nx_ - 1)    # faces before this index are the hall's
    bvh = BVHTree.FromPolygons(V_, F_)
    north = Vector((0, 1, 0))
    if SITE:
        n0 = Vector(world_to_hall(SITE[0], SITE[1]) + (0,)); n1 = Vector(world_to_hall(SITE[0], SITE[1] + 100) + (0,)); north = (n1 - n0).normalized()
    HEMI = []
    for el, off in ((12, 0), (38, 45), (66, 22)):
        for k in range(4):
            az = math.radians(off + 90 * k); e = math.radians(el)
            HEMI.append(Vector((math.cos(e) * math.cos(az), math.cos(e) * math.sin(az), math.sin(e))))
    PDR = globals().get("PODIUM_DRAIN")
    cache = {}
    def colour(pv, n, key):
        ck = (round(pv.x, 1), round(pv.y, 1), round(pv.z, 1), round(n.x, 2), round(n.y, 2), round(n.z, 2), key)
        if ck in cache: return cache[ck]
        def dist(o, d, far):
            hit = bvh.ray_cast(o, d, far)
            return far if hit[0] is None else hit[3]
        vertical = abs(n.z) < 0.35
        hb = 300.0
        if vertical:
            tw = n.cross(Vector((0, 0, 1))).normalized()
            hit = bvh.ray_cast(pv + n * 20.0, Vector((0, 0, -1)), 300.0)    # height above the paving in front (the terrain:
            hb = hit[3] if (hit[0] is not None and hit[2] < NHALL) else 300.0  # the wall-moss decal takes that line instead)
            if hb < 300.0:                                                   # a floor runs on out from the wall; a sill, a
                h2 = bvh.ray_cast(pv + n * 60.0, Vector((0, 0, -1)), hb + 12.0) # beam or a string course stops short of 60
                if h2[0] is None or h2[1].z < 0.9 or abs(h2[3] - hb) > 10.0: hb = 300.0
            hit = bvh.ray_cast(pv + n * 5.0, Vector((0, 0, 1)), 160.0)       # an overhang above: jetty, sill, coping
            ha = hit[3] if (hit[0] is not None and hit[1].z < -0.5) else 160.0
            deep = 1.0                                                       # a jetty or eave (24 out) shades; a rail or sill barely
            if ha < 160.0:
                h2 = bvh.ray_cast(pv + n * 24.0, Vector((0, 0, 1)), ha + 30.0)
                deep = 1.0 if (h2[0] is not None and h2[1].z < -0.5) else 0.33
            dl = dist(pv + n * 12.0, tw, 90.0); dr = dist(pv + n * 12.0, -tw, 90.0)   # a wall at either side (12 out: past the timbers)
            foot = max(0.0, 1.0 - hb / 70.0)
            k_ = 1.0 - (0.40 if key not in ("roof", "wood", "planks") else 0.12) * foot   # the foot: splash, damp, shade
            k_ -= 0.65 * deep * max(0.0, 1.0 - ha / 90.0)                               # under an overhang
            k_ -= 0.36 * (max(0.0, 1.0 - dl / 80.0) + max(0.0, 1.0 - dr / 80.0))  # inside corners
            if ha < 160.0 and key not in ("roof", "wood", "planks"):                    # run-off streaks below the ledge
                u = pv.dot(tw)
                k_ *= 1.0 - 0.12 * (1.0 - ha / 160.0) * (0.35 + 0.65 * _n1(u / 44.0, 9.0))
        elif n.z > 0.35:                                     # floors, treads, tops: dark where they meet a wall
            d4 = [dist(pv + Vector((0, 0, 5)), Vector(v_), 100.0) for v_ in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0))]
            d4.sort()
            k_ = 1.0 - 0.22 * max(0.0, 1.0 - d4[0] / 60.0) - 0.12 * max(0.0, 1.0 - d4[1] / 60.0)
        else:                                                # soffits and other undersides
            k_ = 0.72
        r_ = g_ = b2 = max(0.3, k_)
        hn = Vector((n.x, n.y, 0.0))
        face_n = hn.dot(north) / (hn.length + 1e-6) if hn.length > 1e-3 else 0.0
        if face_n > 0.25:                                    # north faces: algae, more where it stays damp
            damp = 0.5 + 0.5 * max(0.0, 1.0 - hb / 200.0)
            kq = min(1.0, (face_n - 0.25) / 0.6) * damp
            r_ *= 1 - 0.06 * kq; g_ *= 1 - 0.012 * kq; b2 *= 1 - 0.09 * kq
        for cx_, cy_, top_ in CHIMNEYS:                       # soot on the stacks' top courses
            if abs(pv.x - cx_) < 75 and abs(pv.y - cy_) < 75 and pv.z > top_ - 220:
                f_ = min(1.0, (pv.z - (top_ - 220)) / 220.0) ** 1.5
                r_ *= 1 - 0.5 * f_; g_ *= 1 - 0.52 * f_; b2 *= 1 - 0.55 * f_
        if PDR and vertical and n.x > 0.9 and abs(pv.x - PDR[0]) < 6:       # the drain: a wet fan under its lip, rust under the grate
            dy_ = abs(pv.y - PDR[1]); dz_ = PDR[2] - pv.z
            if 0 < dz_ < 260:
                spread = 40 + dz_ * 0.25
                if dy_ < spread:
                    f_ = (1 - dz_ / 260.0) * (1 - dy_ / spread) ** 0.7
                    r_ *= 1 - 0.40 * f_; g_ *= 1 - 0.30 * f_; b2 *= 1 - 0.42 * f_
            if 0 < dz_ < 90 and dy_ < 30:
                f_ = (1 - dz_ / 90.0) * (1 - dy_ / 30.0)
                r_ *= 1 - 0.05 * f_; g_ *= 1 - 0.20 * f_; b2 *= 1 - 0.36 * f_
        DPP = globals().get("DOWNPIPE")
        if DPP and vertical and (n.x if "face_x" in DPP else n.y) < -0.9 and abs((pv.x if "face_x" in DPP else pv.y) - DPP["y"]) < 3:   # the downpipe's own water: rust run down from the
            dx_ = abs((pv.y if "face_x" in DPP else pv.x) - DPP["x"])                                                                     # hopper and each holderbat, damp round the gully
            dz_ = DPP["z_hopper"] - pv.z
            if 0 < dz_ < 240:
                spread = 9 + dz_ * 0.07
                if dx_ < spread:
                    f_ = (1 - dz_ / 240.0) ** 1.3 * (1 - dx_ / spread) ** 0.8
                    r_ *= 1 - 0.10 * f_; g_ *= 1 - 0.26 * f_; b2 *= 1 - 0.40 * f_
            for zb_ in DPP["brackets"]:
                dz_ = zb_ - 3 - pv.z
                if 0 < dz_ < 45 and dx_ < 11:
                    f_ = (1 - dz_ / 45.0) * (1 - dx_ / 11.0)
                    r_ *= 1 - 0.06 * f_; g_ *= 1 - 0.20 * f_; b2 *= 1 - 0.32 * f_
            hz_ = pv.z - DPP["z_foot"]
            if hz_ < 75 and dx_ < 85:
                f_ = (1 - max(0.0, hz_) / 75.0) * (1 - dx_ / 85.0) ** 0.8
                r_ *= 1 - 0.24 * f_; g_ *= 1 - 0.20 * f_; b2 *= 1 - 0.20 * f_
        if DPP and n.z > 0.9 and abs(pv.z - G) < 2 and DPP["y_in"] < pv.y < DPP["y_in"] + 80:   # the paving the terrace's
            dw_ = math.hypot(pv.x - DPP["x"], (pv.y - DPP["y_in"]) * 1.6)                       # water runs to: damp
            if dw_ < 70:                                                                         # round its drain
                f_ = (1 - dw_ / 70.0) ** 0.7
                r_ *= 1 - 0.20 * f_; g_ *= 1 - 0.18 * f_; b2 *= 1 - 0.16 * f_
        c = (min(1.0, max(0.3, r_)), min(1.0, max(0.3, g_)), min(1.0, max(0.3, b2)), 1.0)
        cache[ck] = c
        return c
    lum = lambda c: 0.3 * c[0] + 0.59 * c[1] + 0.11 * c[2]
    def simplify(prof, tol=0.05):
        """the indices to keep so that linear interpolation between kept profiles stays within tol of every profile;
        entries that are None (points nobody can see) do not count"""
        n_ = len(prof); keep = {0, n_ - 1}; stack = [(0, n_ - 1)]
        while stack:
            a, b = stack.pop()
            if b - a < 2: continue
            worst, wi = 0.0, -1
            for i in range(a + 1, b):
                f = (i - a) / (b - a); e = 0.0
                for j in range(len(prof[i])):
                    x, xa, xb = prof[i][j], prof[a][j], prof[b][j]
                    if x is None or xa is None or xb is None: continue
                    e = max(e, abs(x - (xa * (1 - f) + xb * f)))
                if e > worst: worst, wi = e, i
            if worst > tol: keep.add(wi); stack += [(a, wi), (wi, b)]
        return sorted(keep)
    def convex_ccw(q2):
        """a face's outline in its own (s, v) plane, counter-clockwise, if it is convex; else None"""
        out = []
        for q in q2:
            if not out or abs(q[0] - out[-1][0]) + abs(q[1] - out[-1][1]) > 0.05: out.append(q)
        if len(out) > 2 and abs(out[0][0] - out[-1][0]) + abs(out[0][1] - out[-1][1]) <= 0.05: out.pop()
        if len(out) < 3: return None
        ar = sum(out[i][0] * out[(i + 1) % len(out)][1] - out[(i + 1) % len(out)][0] * out[i][1] for i in range(len(out))) / 2
        if abs(ar) < 1.0: return None
        if ar < 0: out = out[::-1]
        for i in range(len(out)):
            a, b_, c = out[i], out[(i + 1) % len(out)], out[(i + 2) % len(out)]
            if (b_[0] - a[0]) * (c[1] - b_[1]) - (b_[1] - a[1]) * (c[0] - b_[0]) < -1e-6: return None
        return out
    def inside(C, s_, v_, eps=0.3):
        for i in range(len(C)):
            a, b_ = C[i], C[(i + 1) % len(C)]; ex_, ey_ = b_[0] - a[0], b_[1] - a[1]
            if (ex_ * (v_ - a[1]) - ey_ * (s_ - a[0])) / math.hypot(ex_, ey_) < -eps: return False
        return True
    def clip_to(subj, C):
        """Sutherland-Hodgman: the part of a cell (any winding, kept) inside the convex outline C"""
        out = list(subj)
        for i in range(len(C)):
            if not out: break
            a, b_ = C[i], C[(i + 1) % len(C)]; ex_, ey_ = b_[0] - a[0], b_[1] - a[1]; L_ = math.hypot(ex_, ey_)
            sd = [(ex_ * (q[1] - a[1]) - ey_ * (q[0] - a[0])) / L_ for q in out]
            inp, out = out, []
            for k in range(len(inp)):
                q, r = inp[k], inp[(k + 1) % len(inp)]; dq, dr_ = sd[k], sd[(k + 1) % len(inp)]
                if dq >= -0.01: out.append(q)
                if (dq >= -0.01) != (dr_ >= -0.01):
                    f_ = dq / (dq - dr_); out.append((q[0] + (r[0] - q[0]) * f_, q[1] + (r[1] - q[1]) * f_))
        res = []
        for q in out:
            if not res or abs(q[0] - res[-1][0]) + abs(q[1] - res[-1][1]) > 0.05: res.append(q)
        if len(res) > 1 and abs(res[0][0] - res[-1][0]) + abs(res[0][1] - res[-1][1]) <= 0.05: res.pop()
        return res
    def real_sides(C, s0, s1, v0, v1):
        """the sides of the bounding box along which the outline has an edge"""
        out = set()
        for i in range(len(C)):
            a, b_ = C[i], C[(i + 1) % len(C)]
            if abs(a[1] - v0) < 0.3 and abs(b_[1] - v0) < 0.3: out.add("b")
            if abs(a[1] - v1) < 0.3 and abs(b_[1] - v1) < 0.3: out.add("t")
            if abs(a[0] - s0) < 0.3 and abs(b_[0] - s0) < 0.3: out.add("l")
            if abs(a[0] - s1) < 0.3 and abs(b_[0] - s1) < 0.3: out.add("r")
        return out
    def affine_uv(q2, uvs):
        """the face's planar texture mapping: uv as an affine function of (s, v), from its widest corner triple"""
        best = None
        for i in range(len(q2)):
            for j in range(i + 1, len(q2)):
                for k in range(j + 1, len(q2)):
                    (sa, va), (sb, vb), (sc_, vc_) = q2[i], q2[j], q2[k]
                    det = (sb - sa) * (vc_ - va) - (sc_ - sa) * (vb - va)
                    if best is None or abs(det) > abs(best[0]): best = (det, i, j, k)
        det, i, j, k = best
        (sa, va), (sb, vb), (sc_, vc_) = q2[i], q2[j], q2[k]
        def coef(fa, fb, fc):
            ga = ((fb - fa) * (vc_ - va) - (fc - fa) * (vb - va)) / det
            gb = ((sb - sa) * (fc - fa) - (sc_ - sa) * (fb - fa)) / det
            return ga, gb, fa - ga * sa - gb * va
        cu = coef(uvs[i][0], uvs[j][0], uvs[k][0]); cv = coef(uvs[i][1], uvs[j][1], uvs[k][1])
        return lambda s_, v_: (cu[0] * s_ + cu[1] * v_ + cu[2], cv[0] * s_ + cv[1] * v_ + cv[2])
    def fill(C):
        """None entries of a probe grid take the colour of the nearest (grid steps) entry that is not None"""
        from collections import deque
        out = [row[:] for row in C]; ni, nj = len(C), len(C[0])
        dq = deque((i, j) for i in range(ni) for j in range(nj) if C[i][j] is not None)
        while dq:
            i, j = dq.popleft()
            for a, b in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
                if 0 <= a < ni and 0 <= b < nj and out[a][b] is None: out[a][b] = out[i][j]; dq.append((a, b))
        return out
    def vcol(F, q, s_, v_):
        """a vertex's colour: the face's own grid where it has a probe (a hidden one carries its neighbour's colour);
        a point a coplanar neighbour puts on the edge: its colour if seen, else the nearest probe's"""
        ss_, vs_ = F["ss"], F["vs"]
        i = min(range(len(ss_)), key=lambda k: abs(ss_[k] - s_)); j = min(range(len(vs_)), key=lambda k: abs(vs_[k] - v_))
        if abs(ss_[i] - s_) < 0.05 and abs(vs_[j] - v_) < 0.05: return F["grid"][i][j]
        return colour(q, F["n"], F["key"]) if seen(q, F["n"], F["t"]) else F["grid"][i][j]
    def seen(q, n, t):
        """can anybody see this point: above the ground, and one of four rays off its face runs 300 clear and ends under
        the open sky (a ray that runs clear inside the void under the terrace, an attic or the hall itself does not)"""
        if SITE and q.z < ground(q.x, q.y) - 2: return False
        o = q + n * 1.0
        for d in (n, (n + UP).normalized(), (n + t * 0.7).normalized(), (n - t * 0.7).normalized()):
            if bvh.ray_cast(o, d, 300.0)[0] is None and bvh.ray_cast(o + d * 300.0, UP, 4000.0)[0] is None: return True
        return False
    planes, newg, newc, SEEN_WALL = {}, {}, {}, []
    for (part, key), faces in list(GEO.items()):
        if key not in AGE_CELL: continue
        newg[(part, key)] = []; newc[(part, key)] = []
        for pts, uvs in faces:
            P = [Vector(q) for q in pts]
            n = (P[1] - P[0]).cross(P[2] - P[0])
            if n.length < 1e-9: newg[(part, key)].append((pts, uvs)); newc[(part, key)].append([(1.0, 1.0, 1.0, 1.0)] * len(pts)); continue
            n.normalize()
            if abs(n.z) > 0.97: t = (Vector((1, 0, 0)) - n * n.x).normalized(); b = n.cross(t).normalized()
            else: t = UP.cross(n).normalized(); b = n.cross(t).normalized()
            S = [q.dot(t) for q in P]; Wv = [q.dot(b) for q in P]
            flat = max(abs(n.dot(q) - n.dot(P[0])) for q in P) < 0.05   # a twisted quad (a mitred coping on a curve) is not
            s0, s1, v0, v1 = min(S), max(S), min(Wv), max(Wv)
            rect = (flat and len(P) == 4 and s1 - s0 > 1 and v1 - v0 > 1 and max(s1 - s0, v1 - v0) >= 40
                    and all(min(abs(x - s0), abs(x - s1)) < 0.3 for x in S) and all(min(abs(y - v0), abs(y - v1)) < 0.3 for y in Wv))
            clip = None                                            # a gable, a hip: the grid, clipped to it
            if not rect and flat and AGE_CELL[key] and len(P) >= 3 and max(s1 - s0, v1 - v0) >= 40:
                clip = convex_ccw(list(zip(S, Wv)))
            if (rect or clip) and AGE_CELL[key]:
                cen = sum(P, Vector()) / len(P)
                probes = [cen] + [q.lerp(cen, 0.15) for q in P]
                if all(bvh.ray_cast(q + n * 0.3, n, 8.0)[0] is not None for q in probes): rect = False; clip = None     # covered
            else: rect = False
            if not rect and not clip:
                cs_ = [colour(q, n, key) for q in P]
                if key == "break":                                  # (2026-11-03) a chip's scar: fresh stone (0.95, not the age pass's shade, which read
                    # its few units of recess as deep shadow and left it darker than the weathered face round it), and its hollow's shade on that
                    cs_ = [tuple(0.95 * SCAR_TONE.get(tuple(round(v, 1) for v in q), 1.0) for _ in cq[:3]) + tuple(cq[3:]) for q, cq in zip(P, cs_)]
                newg[(part, key)].append((pts, uvs)); newc[(part, key)].append(cs_); continue
            d = n.dot(P[0]); st = AGE_CELL[key] if not clip else max(AGE_CELL[key], 32)   # a slanting edge needs both
                                                                    # directions cut: a coarser grid is enough for its band
            ns = max(1, math.ceil((s1 - s0) / st)); nv = max(1, math.ceil((v1 - v0) / st))
            ss = [s0 + (s1 - s0) * i / ns for i in range(ns + 1)]; vs = [v0 + (v1 - v0) * j / nv for j in range(nv + 1)]
            at = lambda s_, v_, n=n, t=t, b=b, d=d: n * d + t * s_ + b * v_
            Cm = [[(colour(at(s_, v_), n, key) if (clip is None or inside(clip, s_, v_)) and seen(at(s_, v_), n, t) else None) for v_ in vs] for s_ in ss]
            if abs(n.z) < 0.35 and key in ("stone", "base", "trim", "stucco"):     # what a visitor sees of the walls
                SEEN_WALL.extend(lum(c) for row in Cm for c in row if c is not None)
            if all(x is None for row in Cm for x in row):          # nobody can see any of it: its corners are enough
                newg[(part, key)].append((pts, uvs)); newc[(part, key)].append([colour(q, n, key) for q in P]); continue
            Cm = fill(Cm)                                          # a hidden probe: its nearest visible probe's colour
            Lm = [[lum(c) for c in row] for row in Cm]
            sk = simplify(Lm); vk = simplify([[Lm[i][j] for i in range(ns + 1)] for j in range(nv + 1)])
            cuv = {}
            for q, uv in zip(P, uvs): cuv[(abs(q.dot(t) - s0) < 0.3, abs(q.dot(b) - v0) < 0.3)] = uv
            rec = {"part": part, "key": key, "n": n, "t": t, "b": b, "d": d, "s0": s0, "s1": s1, "v0": v0, "v1": v1, "at": at,
                   "sc": sorted({ss[i] for i in sk}), "vc": sorted({vs[j] for j in vk}), "uv": cuv, "ss": ss, "vs": vs, "grid": Cm,
                   "clip": clip, "sides": real_sides(clip, s0, s1, v0, v1) if clip else {"b", "t", "l", "r"},
                   "uvf": affine_uv(list(zip(S, Wv)), uvs) if clip else None}
            planes.setdefault((round(n.x, 3), round(n.y, 3), round(n.z, 3), round(d, 1)), []).append(rec)
    nrect = 0; ngon = 0
    if os.environ.get("AG_AGE_DEBUG"):                        # which faces take the most cells, and why
        allr = [F for recs in planes.values() for F in recs]
        allr.sort(key=lambda F: -(len(F["sc"]) * len(F["vc"])))
        for F in allr[:14]:
            cen = F["at"]((F["s0"] + F["s1"]) / 2, (F["v0"] + F["v1"]) / 2)
            print("  AGEDBG", F["part"], F["key"], "cells", (len(F["sc"]) - 1) * (len(F["vc"]) - 1), "| s", round(F["s0"]), round(F["s1"]), "v", round(F["v0"]), round(F["v1"]),
                  "| n", [round(x, 2) for x in F["n"]], "| centre", [round(x) for x in cen], "| cuts", len(F["sc"]), len(F["vc"]))
        byk = {}
        for F in allr: byk[(F["part"], F["key"])] = byk.get((F["part"], F["key"]), 0) + (len(F["sc"]) - 1) * (len(F["vc"]) - 1)
        print("  AGEDBG cells by part/key:", sorted(byk.items(), key=lambda kv: -kv[1])[:8], "| faces", len(allr))
    for recs in planes.values():
        for F in recs:                                       # points a coplanar neighbour puts on a shared edge
            ex = {"b": set(), "t": set(), "l": set(), "r": set()}
            for G2 in recs:
                if G2 is F: continue
                gs = set(G2["sc"]) | {G2["s0"], G2["s1"]}; gv = set(G2["vc"]) | {G2["v0"], G2["v1"]}
                fs_, gs_ = F["sides"], G2["sides"]
                if G2["s1"] > F["s0"] and G2["s0"] < F["s1"]:
                    if abs(G2["v1"] - F["v0"]) < 0.05 and "t" in gs_ and "b" in fs_: ex["b"] |= {x for x in gs if F["s0"] + 0.05 < x < F["s1"] - 0.05}
                    if abs(G2["v0"] - F["v1"]) < 0.05 and "b" in gs_ and "t" in fs_: ex["t"] |= {x for x in gs if F["s0"] + 0.05 < x < F["s1"] - 0.05}
                if G2["v1"] > F["v0"] and G2["v0"] < F["v1"]:
                    if abs(G2["s1"] - F["s0"]) < 0.05 and "r" in gs_ and "l" in fs_: ex["l"] |= {y for y in gv if F["v0"] + 0.05 < y < F["v1"] - 0.05}
                    if abs(G2["s0"] - F["s1"]) < 0.05 and "l" in gs_ and "r" in fs_: ex["r"] |= {y for y in gv if F["v0"] + 0.05 < y < F["v1"] - 0.05}
            sc = sorted(set(F["sc"]) | {F["s0"], F["s1"]}); vc = sorted(set(F["vc"]) | {F["v0"], F["v1"]})
            near = lambda x, xs_: any(abs(x - y) < 0.05 for y in xs_)
            exb = sorted(x for x in ex["b"] if not near(x, sc)); ext = sorted(x for x in ex["t"] if not near(x, sc))
            exl = sorted(y for y in ex["l"] if not near(y, vc)); exr = sorted(y for y in ex["r"] if not near(y, vc))
            u00, u10, u01, u11 = (F["uv"].get(k_, (0, 0)) for k_ in ((True, True), (False, True), (True, False), (False, False)))
            def uvat(s_, v_):
                if F["uvf"]: return F["uvf"](s_, v_)
                a_ = (s_ - F["s0"]) / (F["s1"] - F["s0"]); c_ = (v_ - F["v0"]) / (F["v1"] - F["v0"])
                lo_ = (u00[0] + (u10[0] - u00[0]) * a_, u00[1] + (u10[1] - u00[1]) * a_)
                hi_ = (u01[0] + (u11[0] - u01[0]) * a_, u01[1] + (u11[1] - u01[1]) * a_)
                return (lo_[0] + (hi_[0] - lo_[0]) * c_, lo_[1] + (hi_[1] - lo_[1]) * c_)
            flip = F["t"].cross(F["b"]).dot(F["n"]) < 0
            for i in range(len(sc) - 1):
                for j in range(len(vc) - 1):
                    sv_ = [(sc[i], vc[j])]
                    if j == 0: sv_ += [(x, vc[0]) for x in exb if sc[i] < x < sc[i + 1]]
                    sv_.append((sc[i + 1], vc[j]))
                    if i == len(sc) - 2: sv_ += [(sc[-1], y) for y in exr if vc[j] < y < vc[j + 1]]
                    sv_.append((sc[i + 1], vc[j + 1]))
                    if j == len(vc) - 2: sv_ += [(x, vc[-1]) for x in reversed(ext) if sc[i] < x < sc[i + 1]]
                    sv_.append((sc[i], vc[j + 1]))
                    if i == 0: sv_ += [(sc[0], y) for y in reversed(exl) if vc[j] < y < vc[j + 1]]
                    if flip: sv_ = sv_[::-1]
                    if F["clip"]:
                        sv_ = clip_to(sv_, F["clip"])
                        if len(sv_) < 3: continue
                    pts3 = [tuple(F["at"](s_, v_)) for s_, v_ in sv_]
                    newg[(F["part"], F["key"])].append((pts3, [uvat(s_, v_) for s_, v_ in sv_]))
                    newc[(F["part"], F["key"])].append([vcol(F, Vector(q), s_, v_) for q, (s_, v_) in zip(pts3, sv_)])
                    nrect += 1; ngon += len(sv_) > 4
    for k_ in newg: GEO[k_] = newg[k_]; COLS[k_] = newc[k_]
    # ---- wall moss along the line where a north face meets the terrain, traced by casting at the wall from outside
    def wall_moss(a2, b2, into, seed, hmin=45.0, hmax=120.0, step=22.0):
        A2, B2 = Vector((a2[0], a2[1], 0)), Vector((b2[0], b2[1], 0)); L = (B2 - A2).length; dv = (B2 - A2).normalized()
        k = max(1, math.ceil(L / step)); cols_ = []
        for i in range(k + 1):
            q = A2 + dv * (L * i / k); g = ground(q.x, q.y)
            h = hmin + (hmax - hmin) * _n1(i * step / 90.0, seed)
            col = []
            for fz, al in ((-12.0, 0.9), (0.45, 0.55), (1.0, 0.0)):
                z = g + (fz if fz < 0 else fz * h)
                o = Vector((q.x, q.y, z)) - Vector((into[0], into[1], 0)) * 140.0
                hit = bvh.ray_cast(o, Vector((into[0], into[1], 0)), 200.0)
                if hit[0] is None or hit[2] >= NHALL or abs(hit[1].z) > 0.6: col = None; break
                col.append((hit[0] + hit[1] * 0.6, al, hit[3]))
            cols_.append(col)
        nq = 0
        for i in range(k):
            c0, c1 = cols_[i], cols_[i + 1]
            if not c0 or not c1: continue
            if abs(c0[0][2] - c1[0][2]) > 12 or abs(c0[2][2] - c1[2][2]) > 12: continue      # a buttress steps the face: break
            for r in range(2):
                q4 = [c0[r], c1[r], c1[r + 1], c0[r + 1]]
                pts3 = [tuple(v[0]) for v in q4]; al4 = [v[1] for v in q4]
                nn = (Vector(pts3[1]) - Vector(pts3[0])).cross(Vector(pts3[2]) - Vector(pts3[0]))
                if nn.dot(Vector((-into[0], -into[1], 0))) < 0: pts3, al4 = pts3[::-1], al4[::-1]
                tdir = Vector((dv.x, dv.y, 0))
                GEO.setdefault(("site", "mosswall"), []).append((pts3, [(Vector(v).dot(tdir) / 200.0, Vector(v).z / 200.0) for v in pts3]))
                MOSS_A.setdefault(("site", "mosswall"), []).append(al4); nq += 1
        return nq
    WALL_MOSS = []
    if SITE and "courts" in globals():
        cx0_, cx1_ = courts[0]["x"]; cy0_ = courts[0]["y"][0]
        WALL_MOSS = [((-1590, -470), (cx0_ - 40, -470), (0, 1), 11.0, "the podium's north face, left of the forecourt"),
                     ((cx1_ + 40, -470), (1590, -470), (0, 1), 12.0, "the podium's north face, right of the forecourt"),
                     ((-640, cy0_ - 40), (cx1_ + 30, cy0_ - 40), (0, 1), 13.0, "the forecourt's front wall, north face")]
    nwm = 0
    for a2, b2, into, sd_, why in WALL_MOSS: nwm += wall_moss(a2, b2, into, sd_)
    for xa, sgn_ in ((915, 1), (1005, -1)):                 # up each inside angle of the front buttress, by the ferns
        g = ground(xa - sgn_ * 20, -480)
        pts3 = [(xa, -460.6, g - 10), (xa, -460.6, g + 150), (xa - sgn_ * 42, -460.6, g + 110), (xa - sgn_ * 42, -460.6, g - 10)]
        al4 = [0.9, 0.0, 0.0, 0.9]
        if (Vector(pts3[1]) - Vector(pts3[0])).cross(Vector(pts3[2]) - Vector(pts3[0])).y > 0: pts3, al4 = pts3[::-1], al4[::-1]   # facing -y
        GEO.setdefault(("site", "mosswall"), []).append((pts3, [(q[0] / 200.0, q[2] / 200.0) for q in pts3]))
        MOSS_A.setdefault(("site", "mosswall"), []).append(al4); nwm += 1
    DPP = globals().get("DOWNPIPE")
    if DPP:                                                  # algae down the wall behind the downpipe, where the hopper's
        x_, y_ = DPP["x"], DPP["y"] - 0.6                    # overflow runs: thin under the hopper, thick toward the foot
        rows = [DPP["z_hopper"] - 2 + (DPP["z_foot"] - 2 - DPP["z_hopper"]) * f_ for f_ in (0, 0.25, 0.5, 0.75, 1.0)]
        cols = [(-24, 0.0), (-7, 0.8), (7, 0.8), (24, 0.0)]
        for j in range(4):
            for i in range(3):
                (u0, a0), (u1, a1) = cols[i], cols[i + 1]; f0, f1 = 0.3 + 0.7 * j / 4, 0.3 + 0.7 * (j + 1) / 4
                pts3 = [(x_ + u0, y_, rows[j]), (x_ + u1, y_, rows[j]), (x_ + u1, y_, rows[j + 1]), (x_ + u0, y_, rows[j + 1])]
                if "face_x" in DPP: pts3 = [(y_, x_ + q_[0] - x_, q_[2]) for q_ in pts3]   # (the wall runs along y there: x_ is its place along it, y_ its face)
                al4 = [a0 * f0, a1 * f0, a1 * f1, a0 * f1]
                w_ = (Vector(pts3[1]) - Vector(pts3[0])).cross(Vector(pts3[2]) - Vector(pts3[0]))
                if (w_.x if "face_x" in DPP else w_.y) > 0: pts3, al4 = pts3[::-1], al4[::-1]
                # (u along the wall: on a face_x wall x is the same at all four corners, and u read from it smeared one texel column down the
                # strip: the streaks behind the pipe)
                GEO.setdefault(("site", "mosswall"), []).append((pts3, [((q[1] if "face_x" in DPP else q[0]) / 200.0, q[2] / 200.0) for q in pts3]))
                MOSS_A.setdefault(("site", "mosswall"), []).append(al4); nwm += 1
    print("WALL MOSS", nwm, "faces along the north faces' ground line, the buttress's inside angles and behind the downpipe")
    for k_, al in MOSS_A.items(): COLS[k_] = [[(1.0, 1.0, 1.0, 1.0)] * len(f_) for f_ in al]   # (moss and wall moss)
    lumv = [lum(c) for cl in newc.values() for fc in cl for c in fc]
    print("AGE %d faces (%d with a neighbour's points on an edge) in %ds | luminance mean %.2f, min %.2f (vanilla Bryling walls: 0.81, 0.24)"
          % (sum(len(v) for v in newg.values()), ngon, time.time() - t0, sum(lumv) / len(lumv), min(lumv)),
          "| visible walls: mean %.3f, darkest tenth below %.2f" % (sum(SEEN_WALL) / max(1, len(SEEN_WALL)), sorted(SEEN_WALL)[len(SEEN_WALL) // 10] if SEEN_WALL else 0))
age_pass()

# ---------------------------------------------------------------- export: the parts as JSON in the layout frame (front +x)
INTERIOR = False
if os.environ.get("AG_INTERIOR"):   # the inside instead (interior_gen.py): the exterior above is built for its numbers
    exec(open(os.path.join(os.getcwd(), "interior_gen.py"), encoding="utf-8").read())
if os.environ.get("AG_EXPORT"):
    import json
    ex = os.environ["AG_EXPORT"]; os.makedirs(ex, exist_ok=True)
    L = lambda p: (-p[1], p[0], p[2])                       # hall frame -> layout frame (a quarter turn)
    CHUNK = 512
    def dump(part):
        shapes = {}
        for (pt, key), faces in GEO.items():
            if pt != part: continue
            # (2026-10-26) inside, each material's faces go in cells about a room's size, each its own shape ("key@i_j_level"):
            # the engine lights a shape with the few lamps it picks for it, and one shape across the whole hall would leave
            # the new rooms to lamps far away
            groups = {}
            for i_, (pts, uvs) in enumerate(faces):
                sub = key
                if INTERIOR and part == "interior":
                    c_ = sum((Vector(p) for p in pts), Vector()) / len(pts)
                    sub = "%s@%d_%d_%d" % (key, (c_.x + 2048) // CHUNK, (c_.y + 1024) // CHUNK, 0 if c_.z < ZG - 10 else (1 if c_.z < T1 + 6 else 2))
                groups.setdefault(sub, []).append(i_)
            for sub, idx in groups.items():
                V, F, U = [], [], []
                for i_ in idx:
                    pts, uvs = faces[i_]
                    du, dv = math.floor(min(u for u, _ in uvs)), math.floor(min(v for _, v in uvs))   # small UVs: NIFs store halves
                    F.append(list(range(len(V), len(V) + len(pts)))); V += [L(p) for p in pts]; U.append([(u - du, v - dv) for u, v in uvs])
                shapes[sub] = {"v": V, "f": F, "uv": U}
                if (pt, key) in COLS: shapes[sub]["c"] = [[[round(x, 3) for x in c] for c in COLS[(pt, key)][i_]] for i_ in idx]
                if (pt, key) in MOSS_A: shapes[sub]["a"] = [[round(x, 3) for x in MOSS_A[(pt, key)][i_]] for i_ in idx]
        return {"shapes": shapes, "coll": [[L(p) for p in t] for t in COLL.get(part, [])]}
    name = {"body": "hall2_body", "roof": "hall2_roof", "site": "hall2_site" + (("_" + TAG) if TAG else ""), "interior": "hall2_interior",
            "lookout": "hall2_lookout", "basement": "hall2_basement"}
    INT_PARTS = ("interior",) + (("lookout",) if INTERIOR and any(pt == "lookout" for pt, _ in GEO) else ())   # (W: the lookout's cell)
    INT_PARTS += (("basement",) if INTERIOR and any(pt == "basement" for pt, _ in GEO) else ())               # (2026-10-28: the basement's)
    if INTERIOR:   # the inside, to walk: every solid face collides (not the windows' and doors'
        NOCOLL = ("win1", "win3", "win1i", "win3i", "win1d", "win3d", "door", "iron", "candle", "cork", "paper", "wframe", "sframe", "gpane", "gcoat", "glead")   # pictures, the iron work, the candles)
        for ip_ in INT_PARTS:
            COLL[ip_] = [[f_[0], f_[k_], f_[k_ + 1]] for (pt, key), faces in GEO.items() if pt == ip_ and key not in NOCOLL
                         for i_, (f_, _) in enumerate(faces) if (pt, key, i_) not in NOCOLL_IDS
                         for k_ in range(1, len(f_) - 1)] + COLL_ONLY.get(ip_, [])
    def piece_json(pl):
        """a placed piece, layout frame; a load door (W's ladder and hatch) also says its role and where one arriving
        through it stands; (2026-10-26) a piece whose fifth item is a dict names its record ("ed") and may give its
        reference a name, a role, the role of the load door it pairs with and where one arriving through it stands"""
        d_ = {"model": pl[0], "pos": L(pl[1]), "yaw": pl[2] - 90, "scale": pl[3]}
        if len(pl) > 4 and isinstance(pl[4], dict):
            x_ = dict(pl[4])
            if "arrive" in x_: x_["arrive"] = L(x_["arrive"]); x_["arrive_yaw"] = x_["arrive_yaw"] - 90
            d_.update(x_)
        elif len(pl) > 6: d_.update(role=pl[4], arrive=L(pl[5]), arrive_yaw=pl[6] - 90)
        return d_
    for part in (INT_PARTS if INTERIOR else ("body", "roof", "site")):
        d = dump(part)
        if part == "interior":   # its door and its lights, for the plugin (layout frame, like the site's pieces)
            # (2026-10-27, the clutter pass) a piece marked bake="name" is no reference of its own: its mesh is merged with the
            # rest of that name into one static (bake_clutter.py -> AGHall2Bake<name>.nif), as vanilla's bookcases carry their
            # books (WinterholdBookCase01); hundreds of books as references were two draw calls each. Each one goes out
            # with its whole transform, layout frame (the render's: z turn, then x tilt; a quarter turn to the layout)
            isbake = lambda pl: len(pl) > 4 and isinstance(pl[4], dict) and pl[4].get("bake")
            # (the theft rules) who owns what, by place and record: the guild
            # master's faction owns his office and bedroom (all of it: a future player guild master inherits them, as a new
            # Harbinger does Kodlak's), the weapons on show, the counter's purses and strongbox; and a "group" for each set
            # the NPC build gives to a person (hall-owners.json, written by Hall2.cs with the final IDs): each staff room's
            # pieces but its named bed and chest, the first five bunks' nightstands, the bar's stock, the kitchen's food
            ROOMS1 = {"room3": (1072, 134, 1452, 344), "room4": (1072, 356, 1452, 566), "room5": (1072, 578, 1452, 906),   # (plan D, 2026-11-06: walls y 344-356 and 566-578)
                      "room6": (416, 158, 760, 366), "room7": (416, 378, 760, 588)}
            GM1 = ((-1452, 134, -1092, 616), (-1452, 640, -1092, 906))
            GM_EDS = ("DisplayCaseLgAngled01", "NordHeroSword", "NordHeroWarAxe", "ArmorDragonplateShield",
                      "CoinPurseSmall", "StrongBox")
            BUNKS = [(1210, 719), (1000, 345), (1142, 345), (1330, 345), (784, 719)]   # bunks 1-5 (6-8 the guild's; bunk 1,
                                                                                     # Ghrulek's, at 1210 since 2026-10-27)
            inr = lambda p_, r_: r_[0] <= p_[0] <= r_[2] and r_[1] <= p_[1] <= r_[3]
            def own_group(pl):
                x_ = pl[4] if len(pl) > 4 and isinstance(pl[4], dict) else {}
                ed_, nm_, pos_ = x_.get("ed", ""), x_.get("name") or "", pl[1]
                lvl_ = 0 if pos_[2] < ZG - 10 else (1 if pos_[2] < T1 + 6 else 2)
                own_, grp_ = None, None
                if ed_ in GM_EDS and not (ed_ == "StrongBox" and lvl_ == 2): own_ = "gm"
                if lvl_ == 1 and any(inr(pos_, r_) for r_ in GM1): own_ = "gm"
                named_ = nm_.startswith(("AGHallBed", "AGHallChest")) or nm_.endswith("Door") or ed_ in ("SSingleDoorInt01L", "SSingleDoorInt01R")
                if lvl_ == 1 and not named_:
                    grp_ = next((g_ for g_, r_ in ROOMS1.items() if inr(pos_, r_)), None)
                if lvl_ == 2 and ed_ == "UpperNightstand01" and pos_[2] > T1:
                    k_, dd_ = min(enumerate(BUNKS), key=lambda kv: math.hypot(kv[1][0] - pos_[0], kv[1][1] - pos_[1]))
                    dd_ = math.hypot(BUNKS[k_][0] - pos_[0], BUNKS[k_][1] - pos_[1])
                    if dd_ < 135: grp_ = f"bunk{k_ + 1}"   # (Ghrulek's nightstand 131 from his bunk at 1210)
                food_ = ed_.startswith("Food") or ed_ in ("Garlic", "SaltPile", "Flagon", "BasicTankard01", "GlazedGoblet01",
                                                           "BasicWoodenPlate01", "BasicWoodenBowl01", "MeadBarrel01", "Rag01")
                if lvl_ == 0 and food_ and -800 <= pos_[0] <= -220 and 700 <= pos_[1] <= 970: grp_ = "tavern"
                # (the kitchen's food the guild's: kitchen clutter is free to take; the tavern's
                # tables' things the guild's too, only items still at the bar off limits: the bar's region above)
                return own_, grp_
            def piece_json2(pl):
                d_ = piece_json(pl); own_, grp_ = own_group(pl)
                if own_: d_["owner"] = own_
                if grp_: d_["group"] = grp_
                return d_
            d["pieces"] = [piece_json2(pl) for pl in PLACE if not isbake(pl)]
            bake_ = {}
            for pl in PLACE:
                if not isbake(pl): continue
                rx_ = pl[4].get("rx", 0)
                M_ = (Matrix.Rotation(math.radians(90), 4, 'Z') @ Matrix.Translation(pl[1]) @ Matrix.Rotation(math.radians(-pl[2]), 4, 'Z')
                      @ Matrix.Rotation(math.radians(-rx_), 4, 'X') @ Matrix.Scale(pl[3], 4))
                lvl_ = 0 if pl[1][2] < ZG - 10 else (1 if pl[1][2] < T1 + 6 else 2)
                bake_.setdefault(pl[4]["bake"], []).append({"model": pl[0], "m": [list(r) for r in M_], "level": lvl_})
            if bake_: d["bake"] = bake_
            print("BAKED", {k: len(v) for k, v in bake_.items()})
            # (2026-10-26, the fit-out) a light may name its kind (candle, lamp, fire, window...): Hall2.cs places vanilla's
            # light record for it; one without (the windows' glows) lights only the renders
            d["lights"] = [[list(L((x_, y_, z_))), w_, list(c_)] + list(k_[:3]) for x_, y_, z_, w_, c_, *k_ in INT_LIGHTS]   # (kind, then a trim: radius and fade offsets)
            d["variant"] = VARIANT
            if globals().get("FLIGHTS"):   # (2026-10-28) the spiral's flights, in the hall's frame, for navgen.py's ramps
                d["stair"] = {"centre": [SC.x, SC.y], "r": [SR0, SR], "steps": [list(s_) for s_ in STEPS + DOWN], "flights": FLIGHTS,
                              "rects": [[ZG, list(TSQ)], [1e9, list(TU)]] if globals().get("TSQ") else []}   # (the square treads' outlines: below ZG, above)
            if globals().get("MARKERS"): d["markers"] = [[mk_[0], mk_[1], list(L(mk_[2])), mk_[3] - 90] + list(mk_[4:5]) for mk_ in MARKERS]   # (a fifth item: the ref's settings, e.g. {"disabled": true})
            if globals().get("ARCHES"): d["arches"] = [[list(L(a_)), list(L(b_))] for a_, b_ in ARCHES]
            if "PATIO_LAND" in globals(): d["patio_land"] = [list(L(PATIO_LAND[0])), PATIO_LAND[1] - 90]   # (the back door's way in)
        if part == "lookout":
            d["pieces"] = [piece_json(pl) for pl in LOOK_PLACE]
            if globals().get("LOOK_MARKERS"): d["markers"] = [[n_, e_, list(L(p_)), y_ - 90] for n_, e_, p_, y_ in LOOK_MARKERS]
            d["lights"] = [[list(L((x_, y_, z_))), w_, list(c_)] + list(k_[:3]) for x_, y_, z_, w_, c_, *k_ in LOOK_LIGHTS]
        if part == "basement":   # (2026-10-28) as the lookout: its pieces, lights and markers (basement_gen.py)
            # Henriette's room off the cellar a group of its own, as the staff rooms upstairs:
            # its pieces but her named bed and chest (hall-owners.json; npcgen gives the group to her). Her room's walls: x -1465
            # (the cellar's west wall) to -1060, y -60 (the front) to 168 (the cellar's front wall); the landing's doorway stays out
            def base_json(pl):
                d_ = piece_json(pl); x_ = pl[4] if len(pl) > 4 and isinstance(pl[4], dict) else {}
                nm_, ed_ = x_.get("name") or "", x_.get("ed", "")
                named_ = nm_.startswith(("AGHallBed", "AGHallChest")) or nm_.endswith("Door") or ed_ in ("SSingleDoorInt01L", "SSingleDoorInt01R")
                if not named_ and -1465 <= pl[1][0] <= -1060 and -60 <= pl[1][1] <= 168: d_["group"] = "henriette"
                return d_
            d["pieces"] = [base_json(pl) for pl in BASE_PLACE]
            d["markers"] = [[n_, e_, list(L(p_)), y_ - 90] for n_, e_, p_, y_ in BASE_MARKERS]
            d["lights"] = [[list(L((x_, y_, z_))), w_, list(c_)] + list(k_[:3]) for x_, y_, z_, w_, c_, *k_ in BASE_LIGHTS]
            d["water"] = B_WATER
        if part == "site":
            d["pieces"] = [dict({"model": pl[0], "pos": L(pl[1]), "yaw": pl[2] - 90, "scale": pl[3]}, **({"ed": pl[4]} if len(pl) > 4 else {})) for pl in PLACE]
            json.dump({"openings": OPENINGS, "pieces": [{"model": pl[0], "pos": list(pl[1]), "yaw": pl[2], "scale": pl[3]} for pl in PLACE],
                       "roofs": [{"plan": [list(q) for q in pg], "z": zl} for pg, zl in ROOF_PLAN]},
                      open(os.path.join(ex, "hall2_checks.json"), "w"))
            d["clear"] = [(-y1, -y0, x0, x1, 0) for x0, x1, y0, y1 in CLEAR] + [(-y1, -y0, x0, x1, 1) for x0, x1, y0, y1 in CLEAR_ALL]   # layout frame (lx0, lx1, ly0, ly1, kind)
            d["stair_foot"] = L(STAIR_FOOT); d["site"] = SITE
            d["ramps"] = [[[list(L(a_)), list(L(b_))] for a_, b_ in rows_] for rows_ in RAMPS]   # (each stair's walking surface, rows foot to top)
            # (2026-11-05) the ground under the yard, as triangles every 32 (layout frame), for the site's placement check: the terrain
            # is not in the site's collision, so every yard piece read "nothing under it" and the check's exit was ignored
            if "ground" in globals() and PLACE:
                xs_ = [pl[1][0] for pl in PLACE]; ys_ = [pl[1][1] for pl in PLACE]
                gx0, gx1, gy0, gy1 = min(xs_) - 160, max(xs_) + 160, min(ys_) - 160, max(ys_) + 160
                nx_, ny_ = int((gx1 - gx0) / 32) + 1, int((gy1 - gy0) / 32) + 1
                G_ = [[list(L((gx0 + i_ * 32, gy0 + j_ * 32, ground(gx0 + i_ * 32, gy0 + j_ * 32)))) for j_ in range(ny_ + 1)] for i_ in range(nx_ + 1)]
                d["ground"] = [tri_ for i_ in range(nx_) for j_ in range(ny_) for tri_ in
                               ([G_[i_][j_], G_[i_ + 1][j_], G_[i_ + 1][j_ + 1]], [G_[i_][j_], G_[i_ + 1][j_ + 1], G_[i_][j_ + 1]])]
        json.dump(d, open(os.path.join(ex, name[part] + ".json"), "w"))
        print("EXPORTED", name[part], {k: len(v["f"]) for k, v in d["shapes"].items()}, "collision", len(d["coll"]))
    sys.exit(0)

# ---------------------------------------------------------------- build meshes
for (part, key), faces in GEO.items():
    me = bpy.data.meshes.new(key); bm = bmesh.new(); uvl = bm.loops.layers.uv.new("UV")
    cl = bm.loops.layers.color.new("VERTEX_COLOR") if (part, key) in COLS else None
    al_ = bm.loops.layers.float_color.new("VERTEX_ALPHA") if (part, key) in MOSS_A else None   # raw, as the game tests it
    # (VERTEX_COLOR stays a byte layer: read back gamma-decoded, its multiply in the render's linear space matches the
    # game's multiply of the raw value in gamma space)
    for fi, (pts, uvs) in enumerate(faces):
        vs = [bm.verts.new(p) for p in pts]
        try: f = bm.faces.new(vs)
        except ValueError: continue
        for l, uv in zip(f.loops, uvs): l[uvl].uv = uv
        if cl:
            for l, c in zip(f.loops, COLS[(part, key)][fi]): l[cl] = c
        if al_:
            for l, a_ in zip(f.loops, MOSS_A[(part, key)][fi]): l[al_] = (a_, a_, a_, 1.0)
    smooth = key in ("crest3d", "pipe")                     # welded and smooth, as hall_nif.py writes them for the game
    if smooth:
        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.001)
        if key == "pipe":
            bm.normal_update()
            bmesh.ops.split_edges(bm, edges=[e for e in bm.edges if len(e.link_faces) == 2 and e.calc_face_angle(0) > math.radians(40)])
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(key, me); scene.collection.objects.link(ob)
    me.materials.append(material(key))
    for p in me.polygons: p.use_smooth = smooth
print("FACES", sum(len(v) for v in GEO.values()))
addon_utils.enable("io_scene_nifly", default_set=True, persistent=True)
PIECES = {}  # each NIF imported once; every placement is a linked copy (a second import of the same file adds nothing)
def _fx(o):
    """a mesh Eevee cannot show as the game does: an effect shader's flames and glows, a fire's heat-haze card (they
    rendered as white sheets in the hearth, 2026-10-25); inside only, so the outside's renders stay as they were"""
    m_ = o.data.materials[0] if o.data.materials else None
    groups = [n_.node_tree.name for n_ in m_.node_tree.nodes if n_.type == 'GROUP'] if (m_ and m_.use_nodes) else []
    return any("Effect" in g_ for g_ in groups) or o.name.startswith("Plane03")
_PI = 0                                # each placement's number and record name on its objects, for the clip check
BAKED_DIR = os.environ.get("AG_BAKED")   # (2026-10-27) render the baked statics themselves in place of their pieces: the bake's
                                        # check (bake_clutter.py: each one's NIF, set in the cell as the game sets it)
for rel, pos, yaw, sc, *ex_ in PLACE + (LOOK_PLACE if INTERIOR and "LOOK_PLACE" in globals() else []) + (BASE_PLACE if INTERIOR and os.environ.get("AG_RENDER_BASEMENT") and "BASE_PLACE" in globals() else []):   # (AG_RENDER_BASEMENT: renders only, the basement's pieces too)   # (W: and the lookout's)
    if BAKED_DIR and any(isinstance(e_, dict) and e_.get("bake") for e_ in ex_): continue
    if rel not in PIECES:
        before = set(bpy.data.objects)
        bpy.ops.import_scene.pynifly(filepath=os.path.join(root, *rel.split("/")))
        new = [o for o in bpy.data.objects if o not in before]
        # the game sets a reference's root node to the reference's own transform, so the NIF's root transform never shows
        # in game (2026-10-26: BarLeft01/BarRight01's root turns them 90 degrees; the Bannered Mare's bar only lines up
        # without it); pynifly applies it, so it is taken off here
        roots_ = [o for o in new if o.parent is None and o.type == 'EMPTY' and o.name.endswith(":ROOT")]
        R_ = roots_[0].matrix_world.inverted() if len(roots_) == 1 else Matrix.Identity(4)
        if max(abs(R_[i][j] - (i == j)) for i in range(4) for j in range(4)) > 1e-3: print("ROOT TRANSFORM dropped", os.path.basename(rel))
        PIECES[rel] = [(o.data, R_ @ o.matrix_world) for o in new
                       if o.type == 'MESH' and "bhk" not in o.name and "MultiBound" not in o.name and not (INTERIOR and _fx(o))]
        for data, _ in PIECES[rel]:                          # trees keep wind weights in vertex alpha: the game does not fade
            for m_ in data.materials:                        # leaves by it, so the render must not either
                if not (m_ and m_.use_nodes): continue
                for n_ in m_.node_tree.nodes:
                    if n_.type == 'GROUP' and "Vertex Alpha" in n_.inputs:
                        for l_ in list(n_.inputs["Vertex Alpha"].links): m_.node_tree.links.remove(l_)
                        n_.inputs["Vertex Alpha"].default_value = 1.0
        for o in new: bpy.data.objects.remove(o, do_unlink=True)
    rx_ = next((e_.get("rx", 0) for e_ in ex_ if isinstance(e_, dict)), 0)   # a tilt about its own x (2026-10-26: a map on a
    M = (Matrix.Translation(pos) @ Matrix.Rotation(math.radians(-yaw), 4, 'Z')        # wall), the game's z then x, both negated
         @ Matrix.Rotation(math.radians(-rx_), 4, 'X') @ Matrix.Scale(sc, 4))
    ga_ = next((e_["ga"] for e_ in ex_ if isinstance(e_, dict) and e_.get("ga")), None)   # (2026-11-03, the overmantel's display) the game's own angles, in the
    if ga_:                                                  # cell's frame, as the plugin writes them: Rx(-X) Ry(-Y) Rz(-Z), turned into the hall's by -90 about z
        M = (Matrix.Translation(pos) @ Matrix.Rotation(math.radians(-90), 4, 'Z') @ Matrix.Rotation(math.radians(-ga_[0]), 4, 'X')
             @ Matrix.Rotation(math.radians(-ga_[1]), 4, 'Y') @ Matrix.Rotation(math.radians(-ga_[2]), 4, 'Z') @ Matrix.Scale(sc, 4))
    for data, mw in PIECES[rel]:
        o = bpy.data.objects.new(os.path.basename(rel), data); scene.collection.objects.link(o)
        o["ag_piece"] = _PI; o["ag_ed"] = next((e_.get("ed") for e_ in ex_ if isinstance(e_, dict) and e_.get("ed")), os.path.basename(rel))
        o["ag_rel"] = rel
        o.matrix_world = M @ mw
    print("PLACED", os.path.basename(rel), pos)
    _PI += 1

if BAKED_DIR:
    import glob as _glob
    for f_ in sorted(_glob.glob(os.path.join(BAKED_DIR, "AGHall2Bake*.nif"))):
        before = set(bpy.data.objects)
        bpy.ops.import_scene.pynifly(filepath=f_)
        for o in [o for o in bpy.data.objects if o not in before]:
            if o.parent is None: o.matrix_world = Matrix.Rotation(math.radians(-90), 4, 'Z') @ o.matrix_world   # (layout -> hall)
        print("BAKED PLACED", os.path.basename(f_))

# ---------------------------------------------------------------- render
ids = {i.identifier for i in scene.render.bl_rna.properties['engine'].enum_items}
scene.render.engine = 'BLENDER_EEVEE_NEXT' if 'BLENDER_EEVEE_NEXT' in ids else 'BLENDER_EEVEE'
if os.environ.get("AG_CULL"):         # as the game draws: one-sided (a face seen from behind is not drawn)
    for m_ in bpy.data.materials: m_.use_backface_culling = True
scene.render.resolution_x, scene.render.resolution_y = 1280, 800
scene.view_settings.view_transform = 'AgX' if not CLAY else 'Standard'
try: scene.eevee.use_shadows = True
except Exception: pass
w = bpy.data.worlds.new("sky"); scene.world = w; w.use_nodes = True
bg = w.node_tree.nodes["Background"]; bg.inputs[0].default_value = (0.6, 0.7, 0.85, 1); bg.inputs[1].default_value = 1.1
sd = bpy.data.lights.new("sun", 'SUN'); sd.energy = 4.0; sd.angle = math.radians(3)
sun = bpy.data.objects.new("sun", sd); scene.collection.objects.link(sun); sun.rotation_euler = (math.radians(50), 0, math.radians(-40))
if INTERIOR:                          # inside: no sun, a dim fill, the interior's own lights; windows and candles glow
    sun.hide_render = True; bg.inputs[0].default_value = (0.6, 0.55, 0.5, 1); bg.inputs[1].default_value = 0.55
    scene.view_settings.exposure = 0.6
    for x_, y_, z_, watts, colour, *_ in INT_LIGHTS + (LOOK_LIGHTS if "LOOK_LIGHTS" in globals() else []):
        ld = bpy.data.lights.new("lamp", 'POINT'); ld.energy = watts; ld.color = colour; ld.shadow_soft_size = 25
        lo_ = bpy.data.objects.new("lamp", ld); scene.collection.objects.link(lo_); lo_.location = (x_, y_, z_)
    for k_, st_ in (("win1", 1.6), ("win3", 1.6), ("candle", 12.0)):
        if k_ not in MATS: continue
        nt_ = MATS[k_].node_tree; b_ = nt_.nodes["Principled BSDF"]
        tex_ = [n_ for n_ in nt_.nodes if n_.type == "TEX_IMAGE"]
        if tex_: nt_.links.new(tex_[0].outputs["Color"], b_.inputs["Emission Color"])
        else: b_.inputs["Emission Color"].default_value = (1.0, 0.8, 0.5, 1)
        b_.inputs["Emission Strength"].default_value = st_
    try: scene.eevee.use_raytracing = True
    except Exception: pass
VIEW_LENS = {}
cd = bpy.data.cameras.new("cam"); cd.lens = 30; cd.clip_start = 10; cd.clip_end = 40000
cam = bpy.data.objects.new("cam", cd); scene.collection.objects.link(cam); scene.camera = cam
views = {"road": ((-2300, -3400, G - 40), (0, 300, 600)), "front": ((0, -3300, 500), (0, 300, 650)),
         "door": ((-500, -1250, G + 40), (0, 0, 520)), "aerial": ((2600, -3200, 2600), (0, 400, 400))}
tag = ("clay" if CLAY else "tex") + (("_" + TAG) if TAG else "")
if SITE:
    # the terrain, in the hall's frame: slope tints grass to rock, gravel near a road piece; trees as cones, except the
    # big ones inside the hall's clear box (the spike hides those at run time)
    roads = [world_to_hall(o[0], o[1]) for o in _M["objs"] if o[5] == 1]
    eds = _M["eds"]
    bigt = ("pine", "alder", "beech", "aspen", "birch", "oak", "maple", "willow", "fir", "spruce")
    trees = [(world_to_hall(o[0], o[1]), o[2]) for o in _M["objs"] if o[5] == 2 and any(b in eds[o[6]].lower() for b in bigt)]
    R = 5200; st = 128
    bmt = bmesh.new(); colt = bmt.loops.layers.color.new("Col"); vid = {}
    xs = range(-R, R + 1, st); ys = range(-R, R + 1, st)
    for j, y in enumerate(ys):
        for i, x in enumerate(xs):
            vid[(i, j)] = bmt.verts.new((x, y, ground(x, y)))
    for j in range(len(ys) - 1):
        for i in range(len(xs) - 1):
            f = bmt.faces.new([vid[(i, j)], vid[(i + 1, j)], vid[(i + 1, j + 1)], vid[(i, j + 1)]])
            v = f.verts; dz = max(abs(a.co.z - b.co.z) for a in v for b in v) / st
            cx, cy = f.calc_center_median().x, f.calc_center_median().y
            near = min((math.hypot(cx - rx, cy - ry) for rx, ry in roads), default=1e9)
            if near < 260: c = (0.42, 0.38, 0.33, 1)
            else:
                t = min(1, max(0, (dz - 0.35) / 0.5)); c = (0.23 + 0.13 * t, 0.33 + 0.02 * t, 0.16 + 0.17 * t, 1)
            for l in f.loops: l[colt] = c
    me = bpy.data.meshes.new("terrain"); bmt.to_mesh(me); bmt.free()
    tm = bpy.data.materials.new("terrain"); tm.use_nodes = True; vc = tm.node_tree.nodes.new("ShaderNodeVertexColor"); vc.layer_name = "Col"
    tm.node_tree.links.new(vc.outputs["Color"], tm.node_tree.nodes["Principled BSDF"].inputs["Base Color"]); me.materials.append(tm)
    for pp in me.polygons: pp.use_smooth = True
    scene.collection.objects.link(bpy.data.objects.new("terrain", me))
    trm = bpy.data.materials.new("tree"); trm.use_nodes = True; trm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.1, 0.26, 0.11, 1)
    plm = bpy.data.materials.new("plant"); plm.use_nodes = True; plm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.22, 0.42, 0.16, 1)
    rx, ry = min(roads, key=lambda r: math.hypot(r[0], r[1] + 900)) if roads else (0, -3000)
    road_cam = (rx * 1.6, (ry - 900) * 1.6) if math.hypot(rx, ry) < 2000 else (rx, ry)
    import json as _j
    RAWO = _j.load(open(os.environ["AG_RAW"]))["objects"] if os.environ.get("AG_RAW") else []
    bigt = ("pine", "alder", "beech", "aspen", "birch", "oak", "maple", "willow", "fir", "spruce")
    smallt = ("shrub", "stump", "fern", "clover", "thistle", "thicket", "flora", "typha", "dwarf", "low", "vine", "ivy")
    LAND = ("landscape\\rocks", "landscape\\boulder", "landscape\\trees", "landscape\\dirtcliffs")
    models = {}
    if os.environ.get("AG_FORMS"):
        for line in open(os.environ["AG_FORMS"], encoding="utf-8", errors="replace"):
            f = line.rstrip("\n").split("\t")
            if len(f) > 3 and f[3]: models.setdefault(f[0].lower(), (f[3], [float(v) for v in f[1].split("x")] if "x" in f[1] else None))
    inbox = lambda x, y, boxes: any(c0 <= x <= c1 and d0 <= y <= d1 for c0, c1, d0, d1 in boxes)
    objs = []
    for ob in RAWO:
        hx, hy = world_to_hall(ob[0], ob[1])
        if abs(hx) > R or abs(hy) > R or ob[7] not in ("Tree", "Static", "MoveableStatic"): continue
        ed = str(ob[8]); el = ed.lower()
        if any(k in el for k in ("marker", "fx", "dyndolod", "lod")): continue
        m = models.get(el, (None, None))
        kind = "tree" if ob[7] == "Tree" and any(b in el for b in bigt) and not any(t in el for t in smallt) else ("plant" if ob[7] == "Tree" else "static")
        landish = kind != "static" or (m[0] and any(k in m[0].lower() for k in LAND))
        objs.append({"hx": hx, "hy": hy, "z": ob[2] - SITE[2], "rot": ob[3], "tilt": (ob[10], ob[11]) if len(ob) > 11 else (0, 0), "w": ob[4], "l": ob[5], "ed": ed, "kind": kind, "model": m[0], "bd": m[1], "land": landish, "src": ob[9]})
    hid = set()
    for k, o in enumerate(objs):
        if not o["land"]: continue
        big = o["kind"] == "static" and max(o["w"], o["l"]) > 1000
        if inbox(o["hx"], o["hy"], CLEAR_ALL) or (not big and inbox(o["hx"], o["hy"], CLEAR)): hid.add(k)
    FORCE = set(e.strip().lower() for e in os.environ.get("AG_HIDE_EDS", "").split(",") if e.strip())
    for k, o in enumerate(objs):                     # named pieces the design hides outright (AG_HIDE_EDS)
        if o["ed"].lower() in FORCE: hid.add(k)
    deps = set()
    for k in list(hid):
        o = objs[k]
        if o["kind"] != "static": continue
        rad = max(o["w"], o["l"]) / 2
        for q, d in enumerate(objs):
            if q in hid or q == k: continue
            if d["kind"] == "static" and max(d["w"], d["l"]) > 600: continue
            if math.hypot(d["hx"] - o["hx"], d["hy"] - o["hy"]) <= rad and d["z"] > ground(d["hx"], d["hy"]) + 40: deps.add(q)
    hid |= deps
    print("HIDE", len(hid) - len(deps), "in the clear boxes,", len(deps), "standing on hidden ledges:",
          sorted(set(objs[q]["ed"] for q in deps)))
    if os.environ.get("AG_DEBUG_HIDE"):
        for q in sorted(hid, key=lambda q: (objs[q]["kind"], objs[q]["hx"])):
            o = objs[q]
            print("  HID", o["kind"], o["ed"], (round(o["hx"]), round(o["hy"]), round(o["z"])), "size", round(max(o["w"], o["l"])), "dep" if q in deps else "", o["src"])
    addon_utils.enable("io_scene_nifly", default_set=True, persistent=True)
    cache = {}; nt_ = placed = 0
    e0 = Vector(world_to_hall(SITE[0], SITE[1]) + (0,)); ex = Vector(world_to_hall(SITE[0] + 1, SITE[1]) + (0,)) - e0
    rot = math.atan2(ex.y, ex.x)
    for k, o in enumerate(objs):
        if k in hid: continue
        tx, ty = o["hx"], o["hy"]
        if o["kind"] in ("tree", "plant"):
            if o["kind"] == "tree" and math.hypot(tx - road_cam[0], ty - road_cam[1]) < 900: continue
            hgt, rad = (900, 110) if o["kind"] == "tree" else (70, 40)
            bmc = bmesh.new(); bmesh.ops.create_cone(bmc, cap_ends=True, segments=8, radius1=rad, radius2=0, depth=hgt)
            bmesh.ops.translate(bmc, verts=bmc.verts[:], vec=(tx, ty, o["z"] + hgt / 2))
            mc = bpy.data.meshes.new(o["kind"]); bmc.to_mesh(mc); bmc.free(); mc.materials.append(trm if o["kind"] == "tree" else plm)
            scene.collection.objects.link(bpy.data.objects.new(o["kind"], mc)); nt_ += 1
            continue
        if not o["model"]: continue
        rel = o["model"].lower().replace("\\", "/")
        rel = rel if rel.startswith("meshes/") else "meshes/" + rel
        if rel not in cache:
            path = os.path.join(root, *rel.split("/"))
            if not os.path.exists(path): cache[rel] = []; continue
            before = set(bpy.data.objects)
            try: bpy.ops.import_scene.pynifly(filepath=path)
            except Exception as e: print("OBJ IMPORT FAILED", rel, e); cache[rel] = []; continue
            new = [x for x in bpy.data.objects if x not in before]
            cache[rel] = [(x.data, x.matrix_world.copy()) for x in new if x.type == 'MESH' and "bhk" not in x.name and "MultiBound" not in x.name]
            for x in new: bpy.data.objects.remove(x, do_unlink=True)
        sc = 1.0
        if o["bd"] and max(o["bd"]) > 0 and max(o["w"], o["l"]) > 0: sc = max(o["w"], o["l"]) / max(o["bd"][:2])
        if not 0.2 < sc < 6: sc = 1.0
        M = (Matrix.Translation((tx, ty, o["z"])) @ Matrix.Rotation(rot, 4, 'Z') @ Matrix.Rotation(-o["tilt"][0], 4, 'X')   # the game's order:
             @ Matrix.Rotation(-o["tilt"][1], 4, 'Y') @ Matrix.Rotation(-o["rot"], 4, 'Z') @ Matrix.Scale(sc, 4))              # Z, then Y, then X, negated
        for data, mw in cache[rel]:
            x = bpy.data.objects.new(o["ed"], data); scene.collection.objects.link(x); x.matrix_world = M @ mw
        placed += 1
    print("TERRAIN trees and plants drawn", nt_, "| landscape pieces drawn", placed)
    gf = ground(0, -1400)
    rx, ry = min(roads, key=lambda r: math.hypot(r[0], r[1] + 900)) if roads else (0, -3000)
    views = {"approach": ((-900, -3400, ground(-900, -3400) + 130), (0, 300, 650)),
             "fromroad": ((rx * 1.6 if math.hypot(rx, ry) < 2000 else rx, (ry - 900) * 1.6 if math.hypot(rx, ry) < 2000 else ry, 0), (0, 400, 600)),
             "side": ((-4200, 300, ground(-4200, 300) + 300), (0, 300, 400)),
             "aerial": ((3000, -3800, 3000), (0, 300, 200))}
    if os.environ.get("AG_STAIR") == "approach":
        # close-ups of every fix of 2026-10-23, from where a player stands (eye 130-170 above the ground)
        E = lambda x, y, h=150: (x, y, ground(x, y) + h)
        views = {"road_axis": (E(150, -2900, 160), (0, -600, 150)),
                 "stair_foot": (E(-750, -2450, 160), (0, -2050, -400)),
                 "courts": ((250, -1350, 20), (0, -500, 150)),
                 "bed": ((-200, -400, 160), (900, -60, 40)),
                 "door_balcony": ((140, -430, 150), (0, -40, 430)),
                 "jetty_under": ((-900, -60, 150), (-900, 170, 430)),
                 "rear_door": (E(920, 1700, 220), (920, 930, 470)),
                 "rear": (E(-700, 2400, 420), (0, 900, 400)),
                 "left_side": (E(-2900, -900, 320), (-1200, 0, 0)),
                 "sign": (E(-480, -2620, 150), (-560, -2235, -360)),
                 "plan": ((0, -900, 6200), (0, -899, -300))}
    if os.environ.get("AG_STAIR") == "legs":
        views = {"left_up": ((-2300, -1900, ground(-2300, -1900) + 140), (-1300, -600, -250)),
                 "left_side": ((-3200, -700, ground(-3200, -700) + 200), (-1200, -650, -250)),
                 "right_up": ((2600, -1600, ground(2600, -1600) + 140), (1300, -600, -100)),
                 "front": ((0, -2600, ground(0, -2600) + 160), (0, 0, 300)),
                 "aerial": ((-900, -3600, 2200), (-200, -500, -200)),
                 "top": ((-300, -900, 3200), (-300, -800, -300))}
VIEW_OPTS = {}                   # per view: {"ortho": scale, "clip": near clip, "res": [w, h]} (a cutaway: ortho, clipped)
if os.environ.get("AG_VIEWS"):   # {"name": [[x, y, z, above_ground?], [x, y, z], lens, opts?]} - views for inspecting a design
    _vv = json.loads(os.environ["AG_VIEWS"]); views = {}
    for _k, _v in _vv.items():
        _e = _v[0]; _ez = ground(_e[0], _e[1]) + _e[2] if len(_e) > 3 and _e[3] else _e[2]
        views[_k] = ((_e[0], _e[1], _ez), tuple(_v[1]))
        if len(_v) > 2: VIEW_LENS[_k] = _v[2]
        if len(_v) > 3: VIEW_OPTS[_k] = _v[3]
if os.environ.get("AG_CLIPCHECK"):
    # the clip check (visually obvious clipping went unflagged: a crate ran 11 into the back counter's inner panel): every placed piece's real mesh against
    # every other piece's and the hall's own, triangle by triangle (BVH overlap). A pair of crossing triangles counts by
    # how far one pokes through the other's plane, the smaller of the two ways (a chair leg sunk 0.5 into the floor:
    # 0.5); faces lying on each other (contact: parallel, under 0.6 apart) don't count. Pieces deeper than CLIP_MIN are
    # reported, worst first, and each gets a close-up view from its most open side; AG_CLIPCHECK=only renders just those
    from mathutils.bvhtree import BVHTree
    CLIP_MIN = float(os.environ.get("AG_CLIPMIN", "1.5"))
    _items = []
    for o in scene.objects:
        if o.type != 'MESH' or o.hide_render or not o.data.polygons: continue
        if "trigger" in o.name.lower(): continue                 # (the racks' trigger volumes: never drawn)
        if "/effects/" in o.get("ag_rel", ""): continue          # (flames, embers, glows: drawn through things by design)
        mw_ = o.matrix_world; vs_ = [mw_ @ v.co for v in o.data.vertices]; ps_ = [tuple(p_.vertices) for p_ in o.data.polygons]
        lo_ = Vector([min(v[k] for v in vs_) for k in range(3)]); hi_ = Vector([max(v[k] for v in vs_) for k in range(3)])
        _items.append({"pc": o.get("ag_piece", -1), "ed": o.get("ag_ed", "hall:" + o.name.split(".")[0]), "vs": vs_, "ps": ps_,
                       "lo": lo_, "hi": hi_, "bvh": None})
    def _bvh(it):
        if it["bvh"] is None: it["bvh"] = BVHTree.FromPolygons(it["vs"], it["ps"], epsilon=0.0)
        return it["bvh"]
    def _plane(it, i):
        p_ = [it["vs"][k] for k in it["ps"][i]]; n_ = (p_[1] - p_[0]).cross(p_[2] - p_[0])
        return (n_.normalized() if n_.length > 1e-9 else None), p_
    def _poke(pa, n_, o_):
        d_ = [(v - o_).dot(n_) for v in pa]; return min(max(d_), -min(d_))
    # clips made on purpose, with why (the notice board, for one, clips on purpose); a pair matches when its two record names contain the two keys, either way round
    CLIP_ACCEPT = [
        ("AGHall2GuildBoard", "hall:", "the board stands off its wall over the arch's stub, by design"),
        ("AGHall2GuildBoard", "AGHall2GuildBoard", "the three postings share one spot, one shown at a time"),
        ("Bar", "hall:", "the bar kit's counters run into their walls: built in"),
        ("WRIntCastleWallStrChimney01", "hall:", "the great hearth backed into its mass, its base under the floor as vanilla sets it"),
        ("WRIntWallStrChimney02", "hall:", "the kitchen hearth set in its breast, its base under the floor"),
        ("WRIntWallStrChimney02", "FireplaceWood01Burning", "the kitchen fire in its firebox"),
        ("WRIntWallStrChimney02", "CraftingCookingPotSm", "the pot hung in the firebox"),
        ("RTBannerAnchor01", "hall:", "the banners' brackets anchored in the galleries' fronts"),
        ("trapdoorladder02", "hall:", "the tower's ladder up through its hatch"),
        ("winterholdtrapdoor01", "hall:", "the strongroom's hatch set in its floor"),
        ("FarmBTrapdoor", "hall:", "the library's ladder and hatch through their floor"),
        ("NobleShelf02", "hall:trim", "the library's cornice down over the cases' tops, by design"),
        ("NobleShelf02", "hall:base", "the library's frieze down over the cases' tops, by design"),
        ("SSingleDoorInt01L", "hall:planks2", "a door leaf's foot in the floor's boards"),
        ("SSingleDoorInt01R", "hall:planks2", "a door leaf's foot in the floor's boards"),
        ("FirewoodPileMedium01", "hall:floor", "logs settled on the dais"),
    ]
    def _accepted(ea, eb):
        for ka, kb, why in CLIP_ACCEPT:
            if (ka in ea and kb in eb) or (ka in eb and kb in ea): return why
        return None
    _found = {}; _acc = {}
    for a_i, A in enumerate(_items):
        for B in _items[a_i + 1:]:
            if A["pc"] == B["pc"]: continue                         # (one piece's own parts, or the hall's own walls)
            if any(A["lo"][k] > B["hi"][k] + 0.1 or B["lo"][k] > A["hi"][k] + 0.1 for k in range(3)): continue
            best_, cnt_, pts_ = 0.0, 0, []
            for i_, j_ in _bvh(A).overlap(_bvh(B)):
                na_, pa_ = _plane(A, i_); nb_, pb_ = _plane(B, j_)
                if na_ is None or nb_ is None: continue
                if abs(na_.dot(nb_)) > 0.98 and abs((pa_[0] - pb_[0]).dot(nb_)) < 0.6: continue   # (contact)
                d_ = min(_poke(pa_, nb_, pb_[0]), _poke(pb_, na_, pa_[0]))
                if d_ <= 0.05: continue
                cnt_ += 1; pts_.append((sum(pa_, Vector()) / len(pa_) + sum(pb_, Vector()) / len(pb_)) / 2)
                best_ = max(best_, d_)
            if best_ > CLIP_MIN and _accepted(str(A["ed"]), str(B["ed"])):
                _acc[_accepted(str(A["ed"]), str(B["ed"]))] = _acc.get(_accepted(str(A["ed"]), str(B["ed"])), 0) + 1; continue
            if best_ > CLIP_MIN:
                key_ = (A["ed"], B["ed"], A["pc"], B["pc"])
                if key_ not in _found or _found[key_][0] < best_: _found[key_] = (best_, cnt_, sum(pts_, Vector()) / len(pts_))
    _rep = sorted(_found.items(), key=lambda kv: -kv[1][0])
    with open(os.path.join(out, "clip_report.txt"), "w") as f_:
        f_.write(f"CLIP {len(_rep)} pairs deeper than {CLIP_MIN} (piece against piece or hall; hall frame)" + chr(10))
        for (ea_, eb_, pa_, pb_), (d_, c_, ctr_) in _rep:
            f_.write(f"  {d_:6.1f} deep  {c_:4d} crossings  {ea_} x {eb_}  at ({ctr_.x:.0f}, {ctr_.y:.0f}, {ctr_.z:.0f})" + chr(10))
    print(f"CLIP {len(_rep)} pairs deeper than {CLIP_MIN}; accepted {sum(_acc.values())}: " + "; ".join(f"{n} {w}" for w, n in _acc.items()))
    for (ea_, eb_, pa_, pb_), (d_, c_, ctr_) in _rep[:40]: print(f"CLIP {d_:6.1f} {c_:4d} {ea_} x {eb_} at ({ctr_.x:.0f}, {ctr_.y:.0f}, {ctr_.z:.0f})")
    _cv = {}
    for n_i, ((ea_, eb_, pa_, pb_), (d_, c_, ctr_)) in enumerate(_rep[:int(os.environ.get("AG_CLIPVIEWS", "12"))]):
        best_dir, best_free = None, -1
        for az_ in range(0, 360, 45):
            for el_ in (15, 40):
                dv_ = Vector((math.cos(math.radians(az_)) * math.cos(math.radians(el_)), math.sin(math.radians(az_)) * math.cos(math.radians(el_)), math.sin(math.radians(el_))))
                st_, free_ = ctr_ + dv_ * 2, 140                     # (through the two pieces themselves: the camera may
                for _k in range(12):                                  # stand inside neither)
                    hit_, loc_, _n, _i, ho_, _m = scene.ray_cast(bpy.context.evaluated_depsgraph_get(), st_, dv_, distance=140)
                    if not hit_: break
                    if ho_ is not None and ho_.get("ag_piece", -1) != -1 and ho_.get("ag_piece") in (pa_, pb_):
                        st_ = loc_ + dv_ * 0.5; continue
                    free_ = (loc_ - ctr_).length; break
                if free_ > best_free: best_dir, best_free = dv_, free_
        cl_ = ctr_ + best_dir * max(20, min(best_free - 4, 90))
        nm_ = f"clip{n_i:02d}_{str(ea_)[:18]}_{str(eb_)[:18]}".replace(":", "-").replace(" ", "")
        _cv[nm_] = (tuple(cl_), tuple(ctr_)); VIEW_LENS[nm_] = 28; VIEW_OPTS[nm_] = {"res": [800, 560], "clip": 2}
    views = _cv if os.environ["AG_CLIPCHECK"] == "only" else dict(views, **_cv)
RES0 = (scene.render.resolution_x, scene.render.resolution_y)
for name, (loc, tgt) in views.items():
    if SITE and name == "fromroad": loc = (loc[0], loc[1], ground(loc[0], loc[1]) + 130)
    cd.lens = VIEW_LENS.get(name, 30)
    _o = VIEW_OPTS.get(name, {})
    cd.type = 'ORTHO' if "ortho" in _o else 'PERSP'
    if "ortho" in _o: cd.ortho_scale = _o["ortho"]
    cd.clip_start = _o.get("clip", 10)
    scene.render.resolution_x, scene.render.resolution_y = _o.get("res", RES0)
    cam.location = Vector(loc); cam.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    scene.render.filepath = os.path.join(out, f"hall_{tag}_{name}.png")
    bpy.ops.render.render(write_still=True)
    print("RENDERED", name)
