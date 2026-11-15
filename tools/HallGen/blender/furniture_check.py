"""The Guild Hall's furniture check (the fit-out; prototyped as research/clearance, after hall2s turned out to have
rooms that could not be got round): can a player walk to and use every piece of furniture? For each floor of an exported
interior (guildhall_gen AG_EXPORT JSON): the walls from its collision (sliced at four heights over the floor), the floor
from its level faces, the vanilla pieces' footprints (measured from their meshes), the doors' swings. A player is a disc
of radius R; where the disc fits is walkable. Reports:
  UNUSABLE  a piece whose use spot (a bed's side, a chair's front, a chest's lid side...) no walkable spot reaches
  DOORWAY   a door with no way through it
  SWING     a door whose leaf would sweep through furniture
  POCKET    walkable floor cut off from the rest of its floor (but those in ACCEPTED: floor inside solid masses)
  PINCH     a squeeze between two open areas that a comfortable body (W_OK wide) cannot pass: circled with its width
  (orange in the pictures: ways narrower than W_OK)
A layout passes only with none of these (exit 1 otherwise): the rule since a 56 pinch turned up in a kitchen that
had passed because nothing was cut off. Run before every deploy, beside the leak check:
    python furniture_check.py <hall2_interior.json> <out dir> [--levels interior|lookout] [--r 22] [--ok 72]
                              [--edits proposal.json] [--crops crops.json]"""
import sys, os, json, math
import numpy as np
from scipy import ndimage
from PIL import Image, ImageDraw, ImageFont

args = sys.argv[1:]
def opt(k, d):
    if k in args: i = args.index(k); v = args[i + 1]; del args[i:i + 2]; return float(v)
    return d
R, W_OK = opt("--r", 22.0), opt("--ok", 72.0)
def sopt(k):
    if k in args: i = args.index(k); v = args[i + 1]; del args[i:i + 2]; return v
    return None
EDITS = json.load(open(sopt("--edits"))) if "--edits" in args else {}
CROPS = json.load(open(sopt("--crops"))) if "--crops" in args else {}
LEVEL_SET = sopt("--levels") or "interior"
src, out = args[0], args[1]
os.makedirs(out, exist_ok=True)
D = json.load(open(src))
H = lambda p: (p[1], -p[0], p[2])                    # layout -> hall
T = np.array([[H(p) for p in t] for t in D["coll"]], float)

# footprints in the piece's own frame (x0, y0, x1, y1), measured from the meshes (research/footprints) or the records'
# bounds less their entry points; use spots: (x, y) in the same frame, any one reachable will do
import re as _re
SIDED = _re.compile(r"^(UpperChair01|CommonChair01|UpperBedSingle01|NobleBedSingle01|NobleBedDouble01|CommonBed01)")   # (whose FP spots are their records' sides)
FP = {
 "CommonBed01": ((-50, -89, 50, 89), [(-80, 0), (80, 0)]), "UpperBedSingle01": ((-52, -93, 52, 93), [(-82, 0), (82, 0)]),
 "NobleBedSingle01": ((-52, -101, 52, 101), [(-82, 0), (82, 0)]), "NobleBedDouble01": ((-82, -101, 82, 101), [(-112, 0), (112, 0)]),
 "PersonalChestSmall": ((-48, -25, 48, 24), [(0, 58)]), "NobleChest01": ((-68, -40, 68, 25), [(0, -74)]),   # (its lid opens to local -y)

 "WoodenChair01": ((-28, -28, 27, 27), [(0, 60), (58, 0), (-58, 0), (0, -58)]), "NobleChair01": ((-31, -31, 33, 33), [(0, 64), (62, 0), (-62, 0), (0, -62)]), "NobleChair02L": ((-31, -32, 32, 33), [(62, 0)]), "NobleChair02R": ((-32, -32, 31, 33), [(-62, 0)]),   # (2026-11-03: entered from one side, local +x / -x: their records' bounds)
 "WoodenBarStool": ((-16, -16, 16, 16), [(0, 48), (0, -48), (48, 0), (-48, 0)]),
 "CommonBench01": ((-83, -15, 83, 15), [(0, -48), (-46, -48), (46, -48), (112, 0), (-112, 0)]),
 "FarmTable01": ((-104, -53, 104, 51), []), "FarmTableBench02": (None, [(0, 134), (0, -134)]),
 "CommonTable01": ((-106, -51, 106, 51), []), "CommonTableRound01": ((-40, -40, 40, 40), []),
 "CommonTableThin01": ((-80, -19, 80, 20), [(0, -52), (0, 54)]), "CommonCounter01": ((-68, -21, 67, 33), [(0, -54)]),
 "CommonShelf01": ((-68, -27, 68, 27), [(0, -60)]), "UpperShelf01": ((-68, -27, 68, 27), [(0, -60)]),
 "NobleDesk02": ((-81, -49, 83, 13), []),
 "Barrel02Static": ((-27, -27, 27, 27), []), "BarrelFood01_NoRespawn": ((-27, -27, 27, 27), []),
 "MiscSackLarge_NoRespawn": ((-19, -26, 18, 29), []), "CommonCrate01": ((-64, -19, 64, 26), []), "CommonCrate02": ((-36, -19, 36, 26), []),
 "CraftingCookingPotSm": ((-32, 10, 32, 64), [(0, -24)]), "FarmBTrapdoor01": ((-37, -38, 38, 56), [(0, -70)]),
 "UpperTableRound01": ((-40, -40, 40, 40), []), "UpperEndTable01": ((-49, -27, 36, 27), []), "UpperNightstand01": ((-21, -19, 21, 19), []),
 # the one-sided chairs and beds, by their records' entry points. The meshes' furniture markers
 # all face local +y; vanilla's double bed settles the sides: its marker on local -x enters only from "Left", its +x one only "Right"
 # (and vanilla's L chairs keep a wall on +x, 42 to 27; R ones on -x, 41 to 25: Skyrim.esm's placements)
 "UpperChair01L": ((-30, -21, 33, 30), [(-58, 0)]), "UpperChair01R": ((-30, -21, 33, 30), [(58, 0)]),
 "UpperChair01FL": ((-30, -21, 33, 30), [(0, 60), (-58, 0)]), "UpperChair01FR": ((-30, -21, 33, 30), [(0, 60), (58, 0)]),
 "UpperBedSingle01L": ((-52, -93, 52, 93), [(-82, 0)]), "UpperBedSingle01R": ((-52, -93, 52, 93), [(82, 0)]),
 "NobleBedSingle01L": ((-52, -101, 52, 101), [(-82, 0)]), "NobleBedSingle01R": ((-52, -101, 52, 101), [(82, 0)]),
 "NobleBedDouble01L": ((-82, -101, 82, 101), [(-112, 0)]), "NobleBedDouble01R": ((-82, -101, 82, 101), [(112, 0)]),
 "NobleCornerShelf": ((-6, -56, 53, 6), []), "Glazed02Urn01": ((-16, -16, 16, 16), []), "AGHall2UrnStatic": ((-16, -16, 16, 16), []), "TreeSwordFern01": ((-61, -61, 61, 61), []),
 "TrollFat": None, "dunUniqueFireflyInJar": None, "dunUniqueButterflyInJar": None,   # (2026-11-12, the tavern's corners: the fern's own size, 17 in its urn at 0.28; the curio's things on its shelves)
 "UpperDresser01": ((-68, -28, 68, 27), [(0, -57)]), "UpperCupboard01": ((-68, -28, 68, 27), [(0, -57)]), "UpperChair01F": ((-30, -21, 33, 30), [(0, 60)]), "UpperChair01LR": ((-30, -21, 33, 30), [(58, 0), (-58, 0)]), "AGHall2WritingChair": ((-21, -20, 21, 22), [(58, 0), (-58, 0)]),
 "CommonChair02F": ((-30, -20, 32, 30), [(0, 60), (58, 0), (-58, 0)]), "NobleTableThin01": ((-78, -18, 78, 18), []),
 "TreasUpperChest": ((-48, -23, 48, 26), [(0, 58)]), "WRJorrvaskrRugStr01": None, "Rug06": None, "BarrelFood01": ((-27, -27, 27, 27), []),
 "HEARTH": ((-23, -45, 23, 45), []), "WinterholdBookCase01": ((-41, -16, 41, 16), [(0, -50)]), "UpperShelf01b": ((-67, -27, 67, 27), [(0, -60)]),
 # (the fit-out's, measured: research/footprints, fitout_assets/nifinfo.py)
 "StrongBox": ((-15, -10, 15, 10), [(0, 40), (0, -40), (40, 0), (-40, 0)]), "Basket02": ((-18, -18, 18, 18), []),
 "BasketClosed01": ((-18, -18, 18, 18), []), "FirewoodPileSmall01": ((-32, -34, 24, 34), []),
 "NobleNightTable01": ((-26, -27, 26, 13), [(0, -57)]), "NobleChestDrawers01": ((-45, -57, 45, 1), [(0, -87)]), "NobleChestDrawers02": ((-45, -49, 45, 12), [(0, -79)]), "BoneHumanSkullFullStatic": None,
 "SilverCandleStick01": None, "Rug03": None, "Rug01": None,
 "AGHall2Chest": ((-48, -26, 48, 24), [(0, 58)]), "AGHall2LegacyChest": ((-48, -26, 48, 24), [(0, 58)]), "UpperTableBench02": ((-98, -110, 98, 110), [(0, 135), (0, -135)]),
 "UpperTable01": ((-98, -57, 98, 56), []), "UpperShelf02": ((-67, -21, 68, 33), [(0, -54)]),
 "UpperBench01": ((-87, -18, 87, 18), [(0, -48), (0, 48)]), "NobleCrate01": ((-68, -24, 68, 24), []), "MeadBarrel01": ((-20, -25, 20, 25), []), "NobleWardrobe01": ((-42, -15, 42, 15), [(0, -45)]),
 # vanilla's bar kit, as the game draws it (its ends' root turn ignored): a module along local y, the ends past +-32 in y
 "BarStraight01": ((-32, -32, 32, 32), []), "BarRight01": ((-32, 32, 33, 65), []), "BarLeft01": ((-32, -65, 33, -32), []),
 # Hearthfire's library shelving (the library, 2026-10-26): open to local -y
 "NobleShelf02": ((-41, -10, 41, 18), [(0, -50)]), "NobleShelf03": ((-41, -10, 41, 18), [(0, -50)]),
 "NobleShelf04": ((-41, -10, 41, 18), [(0, -50)]), "NobleLectern01": ((-37, -21, 37, 14), [(0, -50)]), "NobleWallShelf02": None,
 "NobleDesk01": ((-45, -49, 45, 12), []), "AGHall2PatioDoorOut": None,
 # vanilla's manor fireplace as the game draws it (its hearth along local y 88..204), its fire; the tavern's mounted skull
 "SMdCFirePlace01": ((-112, 88, 112, 204), []), "FXfireWithEmbersHeavy": None, "WRDragonSkullMounted01": None,
 "DisplayCaseLgAngled01": ((-64, -35, 64, 30), [(0, -60)]), "NordHeroSword": None, "NordHeroWarAxe": None,
 "CivilWarMap01": None,
 # the great hall (2026-10-26): Dragonsreach's hearth wall (its pilasters forward to local y 49, its back 238); Hearthfire's
 # standing bear; its runner, banners, heads and shields lie flat or hang on the walls
 "WRIntCastleWallStrChimney01": ((-280, 49, 272, 238), []), "AGHall2Bear": ((-50, -36, 64, 77), []),
 "WRIntWallStrChimney02": ((-128, 81, 128, 184), []),   # Whiterun's wall fireplace (the kitchen's, since hall2z)
 "WRCastleRugEEndR": None, "WRCastleRugEMid01": None, "WRCastleRugEEndL": None, "WRJovaskrBanner02": None,
 # the services wing dressed (2026-10-26): its bench (seated from its front, local +y: its sit marker heads 0 and its record's bounds reach +68; -y here until 2026-11-03 made it read UNUSABLE), sideboard, stock; the rest set on
 # surfaces or hung
 "NobleBench04Front": ((-78, -17, 78, 18), [(0, 55)]), "NobleTableSquare01": ((-47, -47, 47, 47), []), "NobleSideBoard01": ((-45, -25, 45, 12), []),
 "CrateSmall01": ((-26, -38, 26, 39), []), "CrateSmall02": ((-27, -41, 27, 43), []), "MiscSack02Large": ((-9, -15, 10, 15), []),
 "CandleHornChandelier01": None, "FoodSweetroll": None, "Ale": None, "ingotSilver": None, "CoinPurseLarge": None, "GlazedCup01": None, "GlazedJugSmall01": None, "SilverPlate01": None, "Book1CheapBriefHistoryoftheEmpirev1": None, "Book4RarePostingoftheHunt": None, "Book2CommonBookofDaedra": None, "Book2CommonNordsOfSkyrim": None, "Book2CommonCatsOfSkyrim": None, "Book3ValuableSkyrimRuleOutsiderView": None, "AGHall2Book03a": None, "AGHall2Book04": None, "AGHall2Book04a": None, "AGHall2Book05": None, "AGHall2Book05a": None, "AGHall2BookLarge2": None, "SilverCandleStick03": None, "Book2CommonTrollSlaying": None, "Book2CommonGiantsAndMammoths": None, "Book2CommonHagravens": None, "Book2CommonOnIceWraiths": None, "Book3ValuableFalmer": None, "Book3ValuableDwarvenAutomatons": None, "Book1CheapNineHolds": None, "Book3ValuableThereBeDragons": None, "Book4RareLycanthropicLegendsOfSkyrim": None, "Book3ValuableAmongstTheDraugr": None, "Book2CommonExplorersGuideToSkyrim": None, "FoodCabbage": None, "FoodVenison": None, "CastIronPotMedium01": None, "SaltPile": None, "FoodSalmon": None, "BasicKnife01": None, "Garlic": None, "FoodLeek": None, "FoodCarrot": None, "BasicPlate02": None, "FoodCheeseWheel01A": None, "FoodCheeseWedge01": None, "Basket05": None, "FoodPotato": None, "FoodApple": None, "GlazedPot02": None, "MiscSackLarge": None, "Bucket01": None, "NobleWallShelf01": None, "HangingAnimalsRing02": None, "HangingRabbit01": None, "HangingRabbit02": None, "HangingPheasant02": None, "WRWallShelf01": None, "HangingGarlicBraid": None, "HangingFrostMirriam": None, "HangingElvesEar01": None, "BasicWoodenPlate01": None, "FoodBread01B": None, "FoodBread01A": None, "FoodCheeseWheel02A": None, "FoodWineBottle02": None, "FoodWineAlto": None, "FoodMead": None, "Rag01": None, "GlazedGoblet01": None, "FoodSalmonCooked01": None, "Flagon": None, "FoodCheeseWedge02": None, "CrateOpen": None, "Rug02": None, "WRCastleRugEFree01": None, "AGHall2Note01": None, "AGHall2Note02": None, "AGHall2Note03": None,
 "AGHall2Note04": None, "AGHall2Book01": None, "AGHall2Book03": None, "AGHall2Book06": None, "AGHall2BookLarge": None, "AGHall2Journal": None, "RTBannerAnchor01": None, "CityBannerSolitude01": None, "CityBannerHjaalmarch01": None,
 "CityBannerDawnstar01": None, "CityBannerWinterhold01": None, "CityBannerMarkarth01": None, "CityBannerFalkreath01": None,
 "CityBannerWhiterun01": None, "CityBannerRiften01": None, "CandleHornWall01": None, "CandleHornTable01": None, "Rug11": None, "Inkwell01": None, "Quill01": None, "PaperRoll": None,
 "TGRFOBusinessLedger": None, "CoinPurseSmall": None, "CandleLanternwithCandle01": None, "MiscSack02Small": None,
 "Basket03": None, "Basket01": None, "BasketClosed01": None, "BasicWoodenBowl01": None, "BasicTankard01": None, "CastIronPotSmall01": None,
 "AGHall2GuildBoard": None, "AGHall2GuildBoardB": None, "AGHall2GuildBoardC": None, "FXfireWithEmbers01_lite": None, "FXfireWithEmbersLight": None,
 "CraftingCookingFireSpit": ((-126, -43, 126, 43), [(0, -80)]), "PeltFloor01": None, "CandleHornFloor01": ((-26, -26, 26, 26), []),
 "FirewoodPileMedium01": ((-45, -48, 45, 48), []), "SilverCandleStick02": None, "SilverJug01": None, "SilverGoblet01": None,
 "GlazedJugLarge01": None, "WallMountedSabreCat01": None, "WallMountedBear01": None, "WRIntShield01": None, "WRIntShield03": None,
 # flat on the floor, up on a wall, or hung high: nothing to walk round
 "WRJorrvaskrRugSquare01": None, "WRJorrvaskrRugEndL01": None, "WRJorrvaskrRugEndR01": None, "CandleHornChandelier02": None,
 "ImpWallSconceCandle01": None, "WRIntShield05": None, "WRIntShield06": None, "WRJovaskrBanner01": None,
 "WeaponRackCOAMidPlayerHouse": None, "WeaponRackCOALeftPlayerHouse": None, "WeaponRackCOARightPlayerHouse": None,
 "WeaponRackCOAMidACTIVATORPlayerHouse": None, "WeaponRackCOALeftACTIVATORPlayerHouse": None,
 "WeaponRackCOARightACTIVATORPlayerHouse": None, "ArmorDragonplateShield": None, "FireplaceWood01Burning": None,
}
# floor cut off inside solid masses, known and harmless (hall2s, 2026-10-26): (level, x, y) within 90
ACCEPTED = [("ground floor", -280, 984, "inside the mirror mass, behind the niche"), ("ground floor", -2, 924, "the great hearth's firebox"),
            ("ground floor", -2, 1006, "behind the great hearth's firebox"), ("first floor", 327, 841, "inside the tower's foot"),
            ("first floor", -129, 1008, "the jetty strip behind the breast"), ("first floor", 124, 1008, "the jetty strip behind the breast"),
            ("first floor", -2, 1028, "the jetty strip behind the breast"), ("attic", 419, 806, "inside the tower")]
# use spots accepted as they are (level, editor ID, x, y within 30, why)
ACCEPTED_USE = [("first floor", "NobleChestDrawers01", -1299, 904, "GM bedroom, under the back window: opened from beside the bed")]
EXTRA = {"FarmTableBench02": [(-59, 71, 60, 102), (-59, -102, 60, -71)]}       # two benches either side of the table's axis
BYMODEL = {"impwallsconce02candleon01.nif": None, "fireplacewood01burning.nif": None, "byohhousetrophydragon01.nif": None,
           "sdoubledoorint01.nif": None, "trapdoorladder02.nif": None, "winterholdtrapdoor01.nif": None}

def rot(yaw):
    a = math.radians(yaw); return (math.cos(a), -math.sin(a)), (math.sin(a), math.cos(a))   # local +x, local +y in hall
pieces = []
for p in D["pieces"]:
    ed = p.get("ed") or os.path.basename(p["model"])
    x, y, z = H(p["pos"]); yaw = p["yaw"] + 90; sc = p.get("scale", 1.0)
    pieces.append(dict(ed=ed, x=x, y=y, z=z, yaw=yaw, sc=sc, name=p.get("name", "")))

def _near(p, e):
    return p["ed"] == e[0] and abs(p["x"] - e[1]) < 3 and abs(p["y"] - e[2]) < 3
for e in EDITS.get("remove_pieces", []): pieces = [p for p in pieces if not _near(p, e)]
for (z0_, x0_, y0_, x1_, y1_) in EDITS.get("remove_pieces_in", []):
    pieces = [p for p in pieces if not (abs(p["z"] - z0_) < 60 and x0_ <= p["x"] <= x1_ and y0_ <= p["y"] <= y1_)]
for a in EDITS.get("add_pieces", []):
    pieces.append(dict(ed=a[0], x=a[1], y=a[2], z=a[3], yaw=a[4], sc=a[5] if len(a) > 5 else 1.0, name=a[6] if len(a) > 6 else "", new=True))
for d_ in EDITS.get("add_doors", []):          # door_leaf's own reckoning: [ax, ay, bx, by, z, swing x, swing y, name]
    ax, ay, bx, by, zz, sx_, sy_, nm = d_
    al = (-sy_, sx_); hx_, hy_ = (ax, ay) if (bx - ax) * al[0] + (by - ay) * al[1] > 0 else (bx, by)
    hx_, hy_ = hx_ + al[0] + sx_ * 4, hy_ + al[1] + sy_ * 4
    pieces.append(dict(ed="SSingleDoorInt01L", x=hx_, y=hy_, z=zz, yaw=math.degrees(math.atan2(-al[1], al[0])) % 360, sc=1.0, name=nm, new=True))
pieces = [p for p in pieces if p["name"] not in EDITS.get("remove_doors", [])]

LEVELS = {"interior": [("ground floor", 0.0, (-1470, -40, 1470, 1180)), ("first floor", 418.0, (-1470, -40, 1470, 1180)),
                       ("attic", 670.0, (380, 100, 1470, 940))],
          "lookout": [("strongroom", 1080.0, (200, 700, 760, 1200))]}[LEVEL_SET]
FAILS = []                                             # the findings a layout may not ship with
G = 4.0
n_ = T[:, 1] - T[:, 0]; m_ = T[:, 2] - T[:, 0]
N = np.cross(n_, m_); NL = np.linalg.norm(N, axis=1) + 1e-9; NZ = np.abs(N[:, 2]) / NL
font = None
for f in ("arial.ttf", "DejaVuSans.ttf"):
    try: font = ImageFont.truetype(f, 13); fontb = ImageFont.truetype(f.replace(".ttf", "bd.ttf") if f == "arial.ttf" else f, 15); break
    except Exception: pass
if font is None: font = fontb = ImageFont.load_default()

report = []
for lname, zf, (X0, Y0, X1, Y1) in LEVELS:
    nx, ny = int((X1 - X0) / G), int((Y1 - Y0) / G)
    occ = np.zeros((ny, nx), bool); floor = np.zeros((ny, nx), bool); furn = np.zeros((ny, nx), bool)
    def cell(x, y): return int((x - X0) / G), int((y - Y0) / G)
    def poly_mask(pts):
        img = Image.new("1", (nx, ny), 0)
        ImageDraw.Draw(img).polygon([((px - X0) / G, (py - Y0) / G) for px, py in pts], fill=1, outline=1)
        return np.array(img, bool)
    # the floor: level faces at the floor's height (a step either way: the dais, thresholds)
    fl = (NZ > 0.7) & (np.abs(T[:, :, 2].mean(1) - zf) < 34)
    img = Image.new("1", (nx, ny), 0); dr = ImageDraw.Draw(img)
    for t in T[fl]: dr.polygon([((p[0] - X0) / G, (p[1] - Y0) / G) for p in t], fill=1, outline=1)
    floor = np.array(img, bool)
    # the walls: steep faces cut at four heights over the floor
    img = Image.new("1", (nx, ny), 0); dr = ImageDraw.Draw(img)
    st = NZ < 0.6
    for h in (20, 60, 100, 125):          # (a player stands about 128 tall)
        zc = zf + h
        for t in T[st]:
            zs = t[:, 2]
            if zs.min() > zc or zs.max() < zc: continue
            pts = []
            for i in range(3):
                a, b = t[i], t[(i + 1) % 3]
                if (a[2] - zc) * (b[2] - zc) < 0 or (a[2] == zc and b[2] != zc):
                    s = (zc - a[2]) / (b[2] - a[2]) if b[2] != a[2] else 0
                    pts.append((a[0] + s * (b[0] - a[0]), a[1] + s * (b[1] - a[1])))
            if len(pts) >= 2: dr.line([((pts[0][0] - X0) / G, (pts[0][1] - Y0) / G), ((pts[1][0] - X0) / G, (pts[1][1] - Y0) / G)], fill=1, width=1)
    occ = np.array(img, bool)
    def rect_mask(x0_, y0_, x1_, y1_):
        m = np.zeros((ny, nx), bool)
        i0, j0 = cell(min(x0_, x1_), min(y0_, y1_)); i1, j1 = cell(max(x0_, x1_), max(y0_, y1_))
        m[max(0, j0):max(0, j1 + 1), max(0, i0):max(0, i1 + 1)] = True; return m
    added = np.zeros((ny, nx), bool)
    for (z0_, *r_) in EDITS.get("clear", []):
        if abs(z0_ - zf) < 60: occ &= ~rect_mask(*r_)
    for (z0_, *r_) in EDITS.get("floor", []):
        if abs(z0_ - zf) < 60: floor |= rect_mask(*r_)
    for (z0_, *r_) in EDITS.get("wall", []):
        if abs(z0_ - zf) < 60: m_ = rect_mask(*r_); occ |= m_; added |= m_
    # the furniture
    here = [p for p in pieces if abs(p["z"] - zf) < 60 and X0 <= p["x"] <= X1 and Y0 <= p["y"] <= Y1]
    shapes, uses, doors, bad_doors, pinches = [], [], [], [], []
    for p in here:
        ex_, ey_ = rot(p["yaw"]); s_ = p["sc"]
        W_ = lambda lx, ly: (p["x"] + (lx * ex_[0] + ly * ey_[0]) * s_, p["y"] + (lx * ex_[1] + ly * ey_[1]) * s_)
        if p["ed"] in ("SSingleDoorInt01L", "SSingleDoorInt01R"):   # a leaf: hinged at its origin, 96 along +x, swinging to -y (R, its mirror: to +y)
            sw_ = -1 if p["ed"].endswith("L") else 1
            arc = [W_(0, 0)] + [W_(96 * math.cos(math.radians(a)), sw_ * 96 * math.sin(math.radians(a))) for a in range(0, 91, 6)]
            doors.append((p, arc)); continue
        fp = FP.get(p["ed"])
        if fp is None:                                # (a piece nobody measured is a finding, not a free pass)
            if p["ed"] not in FP and p["ed"] not in BYMODEL:
                report.append(f"UNKNOWN {lname}: {p['ed']} at ({p['x']:.0f},{p['y']:.0f}): no footprint measured"); FAILS.append(report[-1])
            continue
        rects = ([fp[0]] if fp[0] else []) + EXTRA.get(p["ed"], [])
        for (a0, b0, a1, b1) in rects:
            pts = [W_(a0, b0), W_(a1, b0), W_(a1, b1), W_(a0, b1)]
            m = poly_mask(pts); furn |= m; shapes.append((p, pts))
        if fp[1]: uses.append((p, [W_(ux, uy) for ux, uy in fp[1]]))
    block = occ | furn
    dist = ndimage.distance_transform_edt(~block) * G
    walk = floor & (dist > R)
    lab, nl = ndimage.label(walk, structure=np.ones((3, 3)))
    sizes = ndimage.sum(walk, lab, range(1, nl + 1)) if nl else []
    main = 1 + int(np.argmax(sizes)) if nl else 0
    reach = lab == main
    # findings
    for p, arc in doors:
        m = poly_mask(arc)
        hit = [q["ed"] for q, pts in shapes if (poly_mask(pts) & m).sum() > 4]
        if hit: report.append(f"SWING   {lname}: {p['name'] or p['ed']} at ({p['x']:.0f},{p['y']:.0f}) sweeps through {', '.join(sorted(set(hit)))}"); FAILS.append(report[-1])
    for p, arc in doors:
        ex_, ey_ = rot(p["yaw"]); s_ = p["sc"]
        cx_, cy_ = p["x"] + ex_[0] * 48, p["y"] + ex_[1] * 48         # the doorway's middle
        ends = [(cx_ + ey_[0] * d_, cy_ + ey_[1] * d_) for d_ in (-52, 52)]
        ok_ = []
        for ux, uy in ends:
            i, j = cell(ux, uy); rr = int(math.ceil((R + 6) / G))
            ok_.append(0 <= i < nx and 0 <= j < ny and reach[max(0, j - rr):j + rr + 1, max(0, i - rr):i + rr + 1].any())
        if not all(ok_):
            side = "the swing side" if not ok_[0] else "the far side"
            report.append(f"DOORWAY {lname}: {p['name'] or p['ed']} at ({cx_:.0f},{cy_:.0f}): no way through ({side} blocked or cut off)")
            bad_doors.append(((cx_, cy_), ends)); FAILS.append(report[-1])
    bad_use = []
    def _reachable(ux, uy):
        i, j = cell(ux, uy)
        if not (0 <= i < nx and 0 <= j < ny): return False
        rr = int(math.ceil((R + 10) / G))
        return bool(reach[max(0, j - rr):j + rr + 1, max(0, i - rr):i + rr + 1].any())
    for p, pts in uses:
        # (2026-11-12) a chair or a bed: every side its record allows must be reachable, or the engine may pick the blocked one
        # (Uthgerd's chair, the tavern's corner chair: they stood up into the wall). Other pieces: any one of their spots
        every_ = bool(SIDED.match(p["ed"] or ""))
        ok = False if not every_ else all(_reachable(ux, uy) for ux, uy in pts)
        for ux, uy in ([] if every_ else pts):
            i, j = cell(ux, uy)
            if not (0 <= i < nx and 0 <= j < ny): continue
            rr = int(math.ceil((R + 10) / G))
            win = reach[max(0, j - rr):j + rr + 1, max(0, i - rr):i + rr + 1]
            if win.any(): ok = True; break
        if not ok:
            why = next((w_ for l_, e_, ax_, ay_, w_ in ACCEPTED_USE if l_ == lname and e_ == p["ed"] and math.hypot(p["x"] - ax_, p["y"] - ay_) < 30), None)
            sides_ = ""
            if every_:   # (which of its record's sides is blocked, in its own frame: L is local -x, R +x, F +y)
                lo_ = FP.get(p["ed"], (None, []))[1]
                sides_ = " blocked: " + ", ".join(("L" if lx_ < 0 else "R") if abs(lx_) > abs(ly_) else ("F" if ly_ > 0 else "B")
                                                  for (lx_, ly_), (ux, uy) in zip(lo_, pts) if not _reachable(ux, uy))
            report.append(f"UNUSABLE {lname}: {p['ed']} at ({p['x']:.0f},{p['y']:.0f}) yaw {p['yaw'] % 360:.0f}" + sides_ + (f" (accepted: {why})" if why else ""))
            if not why: bad_use.append((p, pts)); FAILS.append(report[-1])
    pockets = [k for k in range(1, nl + 1) if k != main and sizes[k - 1] * G * G > 2500]
    for k in pockets:
        jj, ii = np.nonzero(lab == k); px_, py_ = X0 + ii.mean() * G, Y0 + jj.mean() * G
        why = next((w_ for l_, ax_, ay_, w_ in ACCEPTED if l_ == lname and math.hypot(px_ - ax_, py_ - ay_) < 90), None)
        report.append(f"POCKET  {lname}: {sizes[k - 1] * G * G / 1e4:.1f} sq.units x1e4 cut off near ({px_:.0f},{py_:.0f})"
                      + (f" (accepted: {why})" if why else ""))
        if not why: FAILS.append(report[-1])
    tight = reach & (dist < W_OK / 2)
    # pinch points: where a comfortable body (W_OK wide) can't go but a squeezing one can, between two open areas (or to a
    # use spot): label the comfortable walk, then every squeeze-only cluster that joins two of its parts is a pinch
    walk_ok = floor & (dist > W_OK / 2)
    lab_ok, n_ok = ndimage.label(walk_ok, structure=np.ones((3, 3)))
    near_ok = ndimage.binary_dilation(walk_ok, iterations=int(math.ceil((W_OK / 2 - R) / G)) + 1)
    squeeze = reach & ~near_ok
    lab_sq, n_sq = ndimage.label(squeeze, structure=np.ones((3, 3)))
    grown_ok = ndimage.grey_dilation(lab_ok, size=(2 * int(math.ceil((W_OK / 2 - R) / G)) + 5,) * 2)
    for k in range(1, n_sq + 1):
        m_ = lab_sq == k
        if m_.sum() * G * G < 300: continue
        ring_ = ndimage.binary_dilation(m_, iterations=2) & ~m_
        touch = set(np.unique(grown_ok[ring_])) - {0}
        jj, ii = np.nonzero(m_); cx_, cy_ = X0 + ii.mean() * G, Y0 + jj.mean() * G
        wide = 2 * dist[m_].max()
        if len(touch) >= 2:
            report.append(f"PINCH   {lname}: about {wide:.0f} wide near ({cx_:.0f},{cy_:.0f}), between two open areas")
            if wide < W_OK - 0.5: pinches.append((cx_, cy_, wide)); FAILS.append(report[-1])
        elif len(touch) == 0 and m_.sum() * G * G > 2000: report.append(f"PINCH   {lname}: a squeeze-only area about {wide:.0f} wide near ({cx_:.0f},{cy_:.0f})")
    # the picture (hall frame: x right, y up the page = into the building)
    S_ = 2                                                     # px per cell
    im = Image.new("RGB", (nx * S_, ny * S_ + 40), (24, 22, 20))
    rgb = np.zeros((ny, nx, 3), np.uint8); rgb[:] = (24, 22, 20)
    rgb[floor] = (88, 84, 78); rgb[walk] = (205, 196, 120); rgb[reach] = (96, 168, 98); rgb[tight] = (232, 150, 52)
    rgb[furn] = (140, 92, 54); rgb[occ] = (12, 12, 12); rgb[added] = (70, 40, 120)
    pic = Image.fromarray(rgb[::-1]).resize((nx * S_, ny * S_), Image.NEAREST)
    im.paste(pic, (0, 40)); dr = ImageDraw.Draw(im)
    P = lambda x, y: ((x - X0) / G * S_, 40 + (ny - (y - Y0) / G) * S_)
    for p, arc in doors: dr.line([P(*a) for a in arc[1:]], fill=(90, 160, 235), width=2); dr.line([P(*arc[0]), P(*arc[1])], fill=(90, 160, 235), width=3)
    for (px0, py0, wd_) in pinches:
        cx, cy = P(px0, py0); dr.ellipse([cx - 11, cy - 11, cx + 11, cy + 11], outline=(255, 70, 40), width=3)
        dr.text((cx + 13, cy - 8), f"{wd_:.0f}", fill=(255, 235, 220), font=fontb)
    for (cx_, cy_), ends in bad_doors:
        a_, b_ = P(*ends[0]), P(*ends[1]); dr.line([a_, b_], fill=(235, 60, 50), width=5)
    for p, pts in bad_use:
        for ux, uy in pts:
            cx, cy = P(ux, uy); dr.ellipse([cx - 7, cy - 7, cx + 7, cy + 7], outline=(235, 60, 50), width=3)
    for p, pts in shapes:
        if p["ed"] in ("FarmTableBench02",): continue
        cx = sum(a for a, b in pts) / 4; cy = sum(b for a, b in pts) / 4
    dr.text((10, 8), f"{lname} (floor {zf:.0f}): green walkable (a player r={R:.0f}), orange narrower than {W_OK:.0f}, yellow cut off, red circles unusable, blue door swings",
            fill=(235, 225, 205), font=fontb)
    for p, pts in shapes:
        if p.get("new") and p["ed"] not in ("FarmTableBench02",):
            cx = sum(a for a, b in pts) / len(pts); cy = sum(b for a, b in pts) / len(pts)
            px_, py_ = P(cx, cy); lab_ = p.get("label") or p["ed"].replace("01", "").replace("Common", "").replace("Upper", "").replace("Noble", "")[:12]
            dr.text((px_, py_), lab_, fill=(255, 245, 225), font=font, anchor="mm")
    fn = os.path.join(out, f"clearance_{lname.replace(' ', '_')}.png"); im.save(fn); print("saved", fn)
    for cname, (clev, cx0, cy0, cx1, cy1) in CROPS.items():
        if clev != lname: continue
        a_, b_ = P(cx0, cy1); c_, d_ = P(cx1, cy0)
        im.crop((int(a_), int(b_), int(c_), int(d_))).save(os.path.join(out, f"crop_{cname}.png")); print("crop", cname)

# (a survey of Skyrim.esm, after NPCs stood up onto the hall's round tables: Vanilla never
# turns a front-entry chair (F, FL, FR, Front) to a table: 0 of 75 within 110 of one; the side-entry ones (L, R, LR) face
# them. A front-entry chair facing a table has its sitter sit and stand in the gap between the two, and the stand lands
# them inside the table.) A front-entry chair whose front (its local +y) looks at a table or desk within 110 fails
import re as _re
for c_ in pieces:
    if not _re.search(r"Chair\d*(F|FL|FR|Front)$", c_["ed"]): continue
    _, fy_ = rot(c_["yaw"])
    for t_ in pieces:
        if t_ is c_ or abs(t_["z"] - c_["z"]) > 60 or not _re.search(r"Table|Desk", t_["ed"]): continue
        dx_, dy_ = t_["x"] - c_["x"], t_["y"] - c_["y"]; d_ = math.hypot(dx_, dy_)
        if 0 < d_ < 110 and (dx_ * fy_[0] + dy_ * fy_[1]) / d_ > 0.7:
            report.append(f"FACING  {c_['ed']} at ({c_['x']:.0f},{c_['y']:.0f},{c_['z']:.0f}) faces {t_['ed']} at ({t_['x']:.0f},{t_['y']:.0f}) {d_:.0f} away: a front-entry chair at a table (vanilla sets its side-entry LR there)"); FAILS.append(report[-1])
print("\n".join(report) if report else "no findings")
open(os.path.join(out, f"report_{LEVEL_SET}.txt"), "w").write("\n".join(report) + "\n")
print(f"FURNITURE {LEVEL_SET}: {len(FAILS)} findings a layout may not ship with, {len(pieces)} pieces on {len(LEVELS)} floors"
      + ("" if not FAILS else ":\n  " + "\n  ".join(FAILS)))
sys.exit(1 if FAILS else 0)
