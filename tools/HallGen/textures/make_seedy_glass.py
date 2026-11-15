"""The hall's seedy glass: old window glass that lets light in and shows no real view, for the diamond lattice.
A pane is one flat polygon a layer, so each quarry's slight tilt lives in the normal map: LATTICE quarries square, every one its own tilt, tiling, laid out by
blender/window_lead.py's window_uv so the cells land inside the lead. Wherever it says "picture" it means the whole opening, 0..1 up the window.

  AGH2GlassDiamond_n   ripple, seeds and each quarry's tilt. Alpha: specular
  AGH2GlassDay_g       inside, an atlas with a cell for each size of opening (window_parts.SIZES): pale sky over a paler glow, and every quarry its own tint and strength,
                       darkening toward its lead. The quarries are real ones: this is what stops a bright window reading as lit paper. External Emittance and the reference's region make it day, dusk and night, as vanilla's windows
  AGH2GlassOut         outside: the panes' diffuse, a neutral grey. The glow is multiplied by it, and it is all a pane shows by day, under the reflection. No colour of its own: amber here, in the glow and in the region's light crushed the green against the red, and the windows came out pink in game
  AGH2GlassOut_g       outside after dark, the same atlas: the room behind the glass, every piece its own strength, only a pale warm because the region's light brings the amber. External Emittance switches it: Whiterun's inverted window region, dark by day
  AGH2GlassCoat        the reflection layer's diffuse: black, so the additive layer adds only reflection and highlights. Not vanilla's (0, 0.03, 0.01): a strong light turned that green in game.
  AGH2GlassWhite       the lit panes' diffuse, a mid grey for all its name (PANE): the game multiplies a glow by the diffuse, so black leaves a pitch-black window (seen in game); the atlases are divided by it
  AGH2GlassFlat_n      the panes' normal: flat, and turned to face into the wall, so no light in front of a pane lights it: a pane shows its glow and nothing else, and a fill light beside it leaves no spot.
                       No specular. The ripple is the reflection layer's
  AGH2GlassSky_e       outside: what the glass reflects, a cube of sky, tree line and ground, with a faint sun in the way the front looks. The game multiplies it by the light the pane gets, so a storm or the night puts it out by itself
  AGH2GlassRoom_e      inside: a cube of a dim room, soft shades and nothing bright. The game multiplies a cube by the light the pane receives, so anything bright in it turns into a sun in the glass
                       beside a strong light (seen in game), and both cubes dim at night by themselves

    python make_seedy_glass.py <out dir> [preview.png]"""
import os, struct, subprocess, sys
import numpy as np
from PIL import Image

TEXCONV = "C:/Games/steamapps/common/SkyrimVR/tools/texconv/texconv.exe"
OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "blender"))
import window_parts as wp
EMIT = 1.8                                 # the Glow shader's Emissive_Mult 2.0 by colour 0.9, from Bryling's window: the atlas is the wanted brightness over this
DAY = 1.375                                # on the region (the great hall's readings, 2026-11-02: 0.55 at diffuse 0.4 peaked near 100-113 at noon, the inn's panes 255): about 2.5 times as much on screen, the glow to near full and the rest by PANE, not by Emissive_Mult, unproven under External Emittance
PANE = 0.8                                 # the lit panes' diffuse, and the glow raised to match (the game multiplies a glow by it, seen in the first in-game test). Up from 0.4: under white it takes in the room's ambient, which whitened it in a bright room
SIZE = 1024; LATTICE = 6                   # keep equal to window_lead.TILE
TILT = 0.045                               # a quarry's lean as a slope, about 2.5 degrees: a reflection swings twice that, so neighbouring quarries show different sky
RIPPLE = 0.05; SEEDS = 700; rng = np.random.default_rng(1830)


def periodic(size, lo, hi, power=1.4):
    """tiling noise: white noise band-passed in frequency, wavelengths from size/lo to size/hi pixels"""
    f = np.fft.fftfreq(size) * size; fx, fy = np.meshgrid(f, f); r = np.hypot(fx, fy)
    spec = np.fft.fft2(rng.standard_normal((size, size))) * ((r >= lo) & (r <= hi)) / np.maximum(r, 1) ** power
    n = np.real(np.fft.ifft2(spec)); return (n - n.mean()) / n.std()


def save(a, name, fmt):
    png = os.path.join(OUT, name + ".png")
    Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA" if a.shape[2] == 4 else "RGB").save(png)
    subprocess.run([TEXCONV, "-nologo", "-y", "-f", fmt, "-m", "0", "-sepalpha", "-o", OUT, png], check=True, capture_output=True); os.remove(png)


# height: long soft waves, the glass drawn out in one direction, a finer shimmer over them
h = 1.0 * periodic(SIZE, 3, 9) + 0.32 * periodic(SIZE, 10, 26)
gy, gx = np.gradient(h, axis=(0, 1)); gx, gy = (np.roll(gx, 0) * RIPPLE * 8, gy * RIPPLE * 8)
# seeds: the small trapped bubbles that name this glass
yy, xx = np.mgrid[0:SIZE, 0:SIZE]; sx, sy = np.zeros((SIZE, SIZE)), np.zeros((SIZE, SIZE))
for _ in range(SEEDS):
    cx, cy, r = rng.integers(SIZE), rng.integers(SIZE), rng.uniform(1.2, 3.0)
    x0, x1, y0, y1 = cx - 6, cx + 7, cy - 6, cy + 7
    for j in range(y0, y1):
        for i in range(x0, x1):
            d = np.hypot(i - cx, j - cy)
            if 0 < d < r: k = (1 - d / r) * 0.22; sx[j % SIZE, i % SIZE] += k * (i - cx) / d; sy[j % SIZE, i % SIZE] += k * (j - cy) / d
# each quarry leans its own way
cell = SIZE // LATTICE; lean = rng.uniform(-TILT, TILT, (LATTICE, LATTICE, 2))
cu, cv = (xx // cell).clip(0, LATTICE - 1), (yy // cell).clip(0, LATTICE - 1)
nx = -(gx + sx + lean[cv, cu, 0]); ny = -(gy + sy + lean[cv, cu, 1]); nz = np.ones_like(nx)
L = np.sqrt(nx * nx + ny * ny + nz * nz); n = np.dstack([nx / L, ny / L, nz / L])
spec = np.full((SIZE, SIZE), 0.85)
save(np.dstack([(n + 1) / 2, spec]), "AGH2GlassDiamond_n", "BC7_UNORM")

# the picture: sky over a pale glow, the ramp read through the ripple. No horizon line: nothing behind it to be wrong
P = 512; v = np.linspace(1, 0, P)[:, None] * np.ones((P, P))
warp = np.array(Image.fromarray(((h - h.min()) / np.ptp(h) * 255).astype(np.uint8)).resize((P, P), Image.BILINEAR), np.float32) / 255 - 0.5
s = np.clip(v + 0.13 * warp, 0, 1)[..., None]
top, mid, low = np.array((0.74, 0.85, 0.96)), np.array((0.90, 0.95, 0.98)), np.array((0.66, 0.72, 0.66))
day = np.where(s > 0.5, mid + (top - mid) * (s - 0.5) * 2, low + (mid - low) * s * 2) * (0.96 + 0.08 * warp[..., None])

A = 1024; atlas = np.zeros((A, A, 3), np.float32); warm_ = np.zeros((A, A, 3), np.float32); day_ = np.zeros((A, A, 3), np.float32)
big = np.array(Image.fromarray(((h - h.min()) / np.ptp(h) * 255).astype(np.uint8)).resize((A, A), Image.BILINEAR), np.float32) / 255 - 0.5
tints = rng.uniform(-1, 1, (64, 64, 3))
for kind, w, h_ in wp.SIZES:
    g = wp.inset(wp.outline(kind, w, h_), wp.STYLE[kind][1][1]); c = wp.centre(g); xs = [p[0] for p in g]; zs = [p[1] for p in g]
    a, b, c_, d = wp.cell(kind, w, h_); x0, y0, x1, y1 = int(a * A), int(b * A), int(c_ * A), int(d * A)
    # the margin too: a cell is painted to its edges, so mips and the UVs' ends see the same glass
    yy2, xx2 = np.mgrid[y0 - 6:y1 + 6, x0 - 6:x1 + 6]; yy2 = yy2.clip(0, A - 1); xx2 = xx2.clip(0, A - 1)
    U = (xx2 + 0.5 - x0) / (x1 - x0); V = (yy2 + 0.5 - y0) / (y1 - y0)
    X = min(xs) + U * (max(xs) - min(xs)); Z = max(zs) - V * (max(zs) - min(zs))
    q = np.vectorize(lambda x_, z_: wp.pane(kind, x_, z_, g, h_), otypes=[int, int, float])(X, Z)
    i_, j_, edge = q[0] % 64, q[1] % 64, q[2]
    s = np.clip(1 - V + 0.10 * big[yy2, xx2], 0, 1)[..., None]
    grade = lambda top, mid, low: np.where(s > 0.45, mid + (top - mid) * (s - 0.45) / 0.55, low + (mid - low) * s / 0.45)
    col = grade(np.array((0.66, 0.76, 0.86)), np.array((0.86, 0.89, 0.86)), np.array((0.52, 0.58, 0.50)))
    sky = grade(np.array((0.72, 0.81, 0.92)), np.array((0.92, 0.94, 0.94)), np.array((0.70, 0.75, 0.79)))   # by day (more daylight looking): all sky, no green low in the opening
    t = tints[i_, j_]                                                                            # each quarry from another pot: stronger or weaker, a little greener or bluer
    piece = (1 + 0.13 * t[..., 0:1]) * (1 + np.stack([-0.05 * t[..., 1], 0.04 * t[..., 1], 0.05 * t[..., 2]], 2)) * (1 + 0.09 * big[yy2, xx2][..., None]) * (1 - 0.20 * np.clip((edge - 0.7) / 0.3, 0, 1)[..., None] ** 2)
    atlas[yy2, xx2] = col * piece; day_[yy2, xx2] = sky * piece
    # the night's: lamplight, stronger low in the opening where the lamps are, each piece of glass its own strength
    w_ = (0.84 + 0.16 * t[..., 0:1]) * (0.90 + 0.14 * V[..., None]) * (1 + 0.10 * big[yy2, xx2][..., None]) * (1 - 0.24 * np.clip((edge - 0.7) / 0.3, 0, 1)[..., None] ** 2)
    warm_[yy2, xx2] = np.array((1.0, 0.85, 0.62)) * w_ * (1 + np.stack([0.0 * t[..., 1], 0.05 * t[..., 1], 0.10 * t[..., 2]], 2))
save(day_ * DAY / EMIT / PANE, "AGH2GlassDay_g", "BC1_UNORM")
save(np.full((4, 4, 3), 0.30), "AGH2GlassOut", "BC1_UNORM"); save(warm_, "AGH2GlassOut_g", "BC1_UNORM")
save(np.dstack([np.zeros((4, 4, 3)), np.ones((4, 4))]), "AGH2GlassCoat", "BC3_UNORM")
save(np.dstack([np.full((4, 4, 3), (0.5, 0.5, 0.0)), np.zeros((4, 4))]), "AGH2GlassFlat_n", "BC3_UNORM")
save(np.dstack([np.full((4, 4, 3), PANE), np.ones((4, 4))]), "AGH2GlassWhite", "BC3_UNORM")


def face_dirs(i, size):
    """Direct3D's cube faces, +X -X +Y -Y +Z -Z: the unit direction of each pixel. The game looks a cube up by world direction, so world up is +Z whatever the face's picture looks like"""
    t, s = np.mgrid[0:size, 0:size]; s = (s + 0.5) / size * 2 - 1; t = (t + 0.5) / size * 2 - 1; o = np.ones_like(s)
    d = [(o, -t, -s), (-o, -t, s), (s, o, t), (s, -o, -t), (s, -t, o), (-s, -t, -o)][i]
    L = np.sqrt(d[0] ** 2 + d[1] ** 2 + d[2] ** 2); return d[0] / L, d[1] / L, d[2] / L


def wrap_noise(az, z, seed, freq):
    """smooth noise over directions: a few sines, cheap, and no seam at the cube's edges"""
    r = np.random.default_rng(seed); n = 0
    for _ in range(14):
        k = r.integers(1, freq); ph = r.uniform(0, 6.28); kz = r.uniform(0, freq * 0.6)
        n = n + np.sin(k * az + kz * z * 3 + ph) / (1 + k * 0.4)
    return n / 4


SUN = np.array((0.906 * 0.866, 0.423 * 0.866, 0.5))     # the site's front (yaw 245, world +0.906,+0.423), 30 degrees up: where someone before the hall sees reflected in it


def sky(x, y, z):
    az = np.arctan2(y, x); h = np.abs(z)
    zen, hor = np.array((0.20, 0.27, 0.38)), np.array((0.46, 0.47, 0.45))                      # a window is no mirror: old glass gives back a fraction of the sky
    t = np.clip(z / 0.55, 0, 1)[..., None] ** 0.7; c = hor + (zen - hor) * t
    cloud = np.clip(wrap_noise(az, z * 2.2, 11, 7) * 1.1 + 0.15, 0, 1)[..., None]
    c = c + (np.array((0.52, 0.52, 0.50)) - c) * cloud * np.clip(z * 6, 0, 1)[..., None] * 0.7
    ridge = 0.05 + 0.04 * wrap_noise(az, 0, 12, 7)                                              # the far hills as a shade, never an edge: seedy glass shows no outline
    t = np.clip((ridge - z) / 0.42 + 0.5, 0, 1)[..., None]; land = t * t * (3 - 2 * t)          # wide: a quarry's tilt swings the reflection 5 degrees, and a narrow band turns that into a mosaic
    c = c + (np.array((0.13, 0.15, 0.13)) - c) * land
    off = np.degrees(np.arccos(np.clip(x * SUN[0] + y * SUN[1] + z * SUN[2], -1, 1)))         # wide, for a quarry's tilt as above; a few windows catch it, never one bright spot in each
    return c + np.array((1.0, 0.96, 0.86)) * (0.22 * np.exp(-(off / 9) ** 2 / 2) + 0.10 * np.exp(-(off / 24) ** 2 / 2))[..., None]


def room(x, y, z):
    az = np.arctan2(y, x); shade = 1 + 0.3 * np.clip(wrap_noise(az, z, 21, 4), -1, 1) + 0.3 * np.clip(z, -1, 1)          # broad shades only: enough for neighbouring quarries to differ
    return np.array((0.25, 0.20, 0.15)) * shade[..., None]


def cube(fn, name, size=256):
    """texconv builds no cube: each face to BC1 with its mips, their data end to end, and a DDS header saying so"""
    data = b""; head = None
    for i in range(6):
        c = np.clip(fn(*face_dirs(i, size)), 0, 1) ** (1 / 2.2); tmp = f"{name}_f{i}"
        save(c, tmp, "BC1_UNORM"); raw = open(os.path.join(OUT, tmp + ".dds"), "rb").read(); os.remove(os.path.join(OUT, tmp + ".dds"))
        assert raw[84:88] == b"DXT1", raw[84:88]; head = bytearray(raw[:128]); data += raw[128:]
    head[108:116] = struct.pack("<II", struct.unpack("<I", bytes(head[108:112]))[0] | 0x8, 0xFE00)   # complex, all six faces
    open(os.path.join(OUT, name + ".dds"), "wb").write(bytes(head) + data)


cube(sky, "AGH2GlassSky_e"); cube(room, "AGH2GlassRoom_e", 128)
print("GLASS", sorted(f for f in os.listdir(OUT) if "Glass" in f))
if len(sys.argv) > 2:
    sh = Image.new("RGB", (1536, 512))
    sh.paste(Image.fromarray((np.clip((n[:512, :512] + 1) / 2, 0, 1) * 255).astype(np.uint8)), (0, 0))
    sh.paste(Image.fromarray((np.clip(day, 0, 1) * 255).astype(np.uint8)), (512, 0))
    sh.paste(Image.fromarray((np.clip(warm_[:512, :512], 0, 1) * 255).astype(np.uint8)), (1024, 0)); sh.save(sys.argv[2])
