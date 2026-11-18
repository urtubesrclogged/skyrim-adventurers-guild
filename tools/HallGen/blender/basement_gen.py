"""The basement: a cell of its own (AGHall2BasementCell), exec'd at the end of interior_gen.py (its helpers and globals),
exported by guildhall_gen.py as hall2_basement.json. Designed from plans/BASEMENT.md (and the mock-up
blender/basement_mock.py, whose geometry this is): the main hallway from the tower's basement door; the gaoler's post at
its east end beside the prison cell; the cell (as the town jails': 256 x 320, the Imperial kit); the secret room behind
its big locked door; the cellar under the kitchen, its ladder up to the kitchen's hatch; the bath three steps down, its
pool after the bathhouse mods; the training room three steps down the strip beside the bath, timber over its main area, a
plain vault over the archery range, two pillars and a rib across where they meet. Hall frame (x right, y back), z up.
Facings are measured, never guessed (targets once went in sideways): the archery target's painted face is its local -x (its mesh rendered from both sides); a chair's
backrest is at its local -y (it faces +y); the doors run along their records' bounds (SSingleDoorInt01Load,
ImpWoodDoorSingle01, the jail frame: local x; SSingleDoorInt01L: local y); a sconce faces its local -x (interior_gen's)."""

BASE_PLACE, BASE_LIGHTS, BASE_MARKERS = [], [], []
B_F0, B_F1, B_CEIL, B_WATER = ZB, ZB - 48, -12.0, ZB - 60   # the hallway's floor (the tower's), the training room's and the
B_RISE, B_TREAD, B_T = 16.0, 32.0, 32.0                      # bath's (three steps down), under the ground floor, the pool's water
B_HY0, B_HY1 = 791.0, 940.0                                  # the hallway (the overlay's 780 -> 791: a 32 wall to the training room)
B_CX0 = -1465.0                                              # the cellar's west wall: the ladder against it under the kitchen's hatch


def bplace(rel, ed, pos, yaw, scale=1.0, **extra):
    BASE_PLACE.append((rel, tuple(pos), yaw % 360, scale, dict(ed=ed, **extra)))


def bfloor(x0, y0, x1, y1, z): box("floor", (x0, y0, z - 12), (x1, y1, z))


def bwall(axis, at, a0, a1, z0, z1, gaps=(), finish="stone", th=B_T):
    """a wall centred on the line (axis "x": its plane x = at, running along y; "y": along x), th thick, with doorways
    (a, b, head over z0); stone (the upstairs wall did not suit the basement: the plaster over the hall's panelled base
    only where a finish is asked for)"""
    def seg(s0, s1, za, zb):
        if s1 - s0 < 0.5 or zb - za < 0.5: return
        if axis == "x": lo, hi = (at - th / 2, s0, za), (at + th / 2, s1, zb)
        else: lo, hi = (s0, at - th / 2, za), (s1, at + th / 2, zb)
        if finish == "stone": box("stone", lo, hi); return
        box("stucco", lo, hi)   # (plaster to the floor, no panelled band)
    s = a0
    for g0, g1, head in sorted(gaps):
        seg(s, g0, z0, z1); seg(g0, g1, z0 + head, z1); s = g1
    seg(s, a1, z0, z1)


def btimber(x0, y0, x1, y1):
    """boards under the ground floor, joists every 64 across x, 14 deep (the hall's upper floors' way)"""
    box("planks", (x0, y0, B_CEIL), (x1, y1, B_CEIL + 4))
    for x in range(int(x0) + 8, int(x1) - 8, 64): box("wood", (x, y0, B_CEIL - 14), (x + 12, y1, B_CEIL))


def bvault(x0, y0, x1, y1, fl, along, spring=150.0, crown=B_CEIL - 16, cut=None):
    """a segmental stone barrel vault over a rectangle (its axis along x or y), springing `spring` over the floor, its faces
    turned down into the room; cut: a rectangle left open (a shaft through it). The arc's points (across, z)"""
    s0, s1, l0, l1 = (y0, y1, x0, x1) if along == "x" else (x0, x1, y0, y1)
    zs = fl + spring; h = crown - zs; w = s1 - s0
    R = (h * h + (w / 2) ** 2) / (2 * h); c = (s0 + s1) / 2; zc0 = crown - R; a0 = math.asin((w / 2) / R)
    N = 20; M_ = max(2, int((l1 - l0) // 32))
    pts = [(c + R * math.sin(-a0 + 2 * a0 * i / N), zc0 + R * math.cos(-a0 + 2 * a0 * i / N)) for i in range(N + 1)]
    P = (lambda l, s_, z_: Vector((l, s_, z_))) if along == "x" else (lambda l, s_, z_: Vector((s_, l, z_)))
    for j in range(M_):
        la, lb = l0 + (l1 - l0) * j / M_, l0 + (l1 - l0) * (j + 1) / M_
        for i in range(N):
            (sa, za), (sb, zb) = pts[i], pts[i + 1]
            q = [P(la, sa, za), P(la, sb, zb), P(lb, sb, zb), P(lb, sa, za)]
            if cut and cut[0] <= sum(p.x for p in q) / 4 <= cut[2] and cut[1] <= sum(p.y for p in q) / 4 <= cut[3]: continue
            nz = (q[1] - q[0]).cross(q[2] - q[0]).z
            poly("stone", q if nz < 0 else q[::-1])
    box("stone", (x0, y0, B_CEIL), (x1, y1, B_CEIL + 4))       # (the stone over it, closing the space above)
    return pts


def brack_run(tag, x, y, z, yaw, weapons):
    """a run of player-usable weapon racks along the wall the racks' backs stand on: (x, y) the run's middle on the wall's
    face, yaw the racks' turn (their front, local +y, to the room); weapons: one per rack, (record, mesh) or None"""
    a = math.radians(yaw); along = (math.cos(a), -math.sin(a)); front = (math.sin(a), math.cos(a))   # (local +x, +y in the hall)
    n = len(weapons); offs = [32 * (k - (n - 1) / 2) for k in range(n)]
    for e_ in (offs[0] - 16, offs[-1] + 16):
        bplace("meshes/clutter/weaponrack/wrsingleendcap01.nif", "WeaponRackEndCap", (x + along[0] * e_, y + along[1] * e_, z), yaw)
    for k, (o_, w_) in enumerate(zip(offs, weapons)):
        px, py = x + along[0] * o_, y + along[1] * o_
        rk, ac, wn = f"AGHall2Rack{tag}{k}", f"AGHall2Rack{tag}{k}Activator", f"AGHall2Rack{tag}{k}Weapon"
        bplace("meshes/clutter/weaponrack/wrsingle01.nif", "WeaponRackMidPlayerHouse", (px, py, z), yaw, name=rk, persistent=True,
               links={"WRackActivator": ac})
        bplace("meshes/clutter/weaponrack/wrsingletrigger01.nif", "WeaponRackMidACTIVATORPlayerHouse", (px, py, z), yaw, name=ac,
               persistent=True,   # (its script and values on the base, as vanilla: Hall2.cs vmad)
               links=dict({"WRackTrigger": rk}, **({"": wn} if w_ else {})))
        if w_:
            bplace(w_[1], w_[0], (px + front[0] * 28, py + front[1] * 28, z + 55), yaw, name=wn, persistent=True, owner="guild",
                   settled=True)                              # (kept put until the rack's script hangs it, on attach)


def bsconce(x, y, z, n, lamp=None):
    """a wall sconce (interior_gen's: it faces its local -x, scaled 1.7) on the wall facing n, its candle's light"""
    bplace("meshes/clutter/imperial/impwallsconcecandle01.nif", "ImpWallSconceCandle01", (x + 2 * n[0], y + 2 * n[1], z),
           math.degrees(math.atan2(n[1], -n[0])) % 360, 1.7)
    # (lamp: the reach this fixture must light its share of a room with, instead of a candle's 128: light_check.py)
    BASE_LIGHTS.append((x + 26 * n[0], y + 26 * n[1], z + 30, 1.0e6, (1.0, 0.7, 0.42), "lamp", lamp - 512, 0.0) if lamp else
                       (x + 26 * n[0], y + 26 * n[1], z + 30, 1.0e6, (1.0, 0.7, 0.42), "candle"))


if NEWEL and os.environ.get("AG_BASEMENT", "1") == "1":
    PART = "basement"
    F0, F1, CEIL, T = B_F0, B_F1, B_CEIL, B_T
    HY0, HY1 = B_HY0, B_HY1
    # ---------------------------------------------------------------- floors and the timber ceilings
    bfloor(-1100, HY0, 256, HY1, F0); btimber(-1100, HY0, 256, HY1)          # the main hallway
    bfloor(0, HY1, 256, 1060, F0); btimber(0, HY1, 256, 1060)                # the gaoler's post
    bfloor(B_CX0, 200, -1100, 940, F0)                                        # the cellar
    bfloor(-266, HY1, 0, HY1 + 320, F0)                                       # the prison cell
    bfloor(-760, HY1, -420, 1260, F0)                                         # the secret room
    bfloor(-412, 318, -280, HY0, F1)                                          # the steps' strip, at its foot
    bfloor(-280, 51, 336, 759, F1); bfloor(336, 215, 1400, 759, F1)          # the training room
    btimber(-412, 51, 336, HY0 - T)
    # ---------------------------------------------------------------- the hallway and the gaoler's post
    HR_DOOR = (-1445, -1345)                                                  # (2026-11-06) the cellar's entryway to Henriette's room
    DH = 176                                                                  # (doorways 176 high under the 230 clear)
    # (the cell barred across its whole front, as the town jails' are: the kit's frame at 0.9 runs -266..-32 and is 230 tall,
    # wall to wall)
    bwall("y", HY1 + T / 2, -1100, 256, F0, CEIL, gaps=[(-266, -32, 999), (-685, -495, 230), (0, 256, 999)])
    bwall("y", HY0 - T / 2, -1100, 256, F1, CEIL, gaps=[(-902, -806, 176 + 48), (-412, -280, DH + 48)])
    bwall("x", -1100 - T / 2, HY0, HY1, F0, CEIL, gaps=[(812, 920, DH)], finish="stone")
    bwall("x", 256 + T / 2, HY0, 1060, F0, CEIL)
    bwall("y", 1060 + T / 2, 0, 256, F0, CEIL); bwall("x", -T / 2, HY1 + T, HY1 + 320, F0, CEIL)   # (the post's west wall, the
                                                                                                  # cell's east, behind the hallway's)
    # the load door up to the tower's basement (its pair in the tower: interior_gen's "base_down"), on the hallway's east end
    # (the door was broken here too: its origin is a corner (its record's bounds x 0..95, y -7..0, z 0..175), so
    # it ran from y 850 into the corner. Turned 90 it runs to -y from its origin and stands 7 into the room (-x): centred on the
    # hallway's end, y 865, in a timber frame its own size)
    # (the door looked shut with its prompt and collision elsewhere, so a different door: SHouseIntDoor02Load, Solitude's own, Castle
    # Dour's to its jail: its record's bounds x 0..8, y -56..56, z -128..63, the origin in its middle 128 over the floor. New references, so no saved door state comes with them)
    bplace("meshes/architecture/solitude/doors/shouseintdoor02load.nif", "SHouseIntDoor02Load", (256, 865, F0 + 128), 180,
           name="AGHall2BasementDoorUpB", role="base_up", pair="base_down", arrive=(190, 865, F0), arrive_yaw=270)
    for y_ in (865 - 56 - 7, 865 + 56 + 7): box("wood", (256 - 10, y_ - 7, F0), (256, y_ + 7, F0 + 191))
    box("wood", (256 - 10, 865 - 56 - 14, F0 + 191), (256, 865 + 56 + 14, F0 + 215))
    for x_ in (-900, -440):                                    # (clear of the doorways: the cell's -247..-13, the secret room's; the
                                                               # third, 110 from the second, went: too many lights
                                                               # in the hallway; the post's lantern lights the east end)
        bsconce(x_, HY1 - 0.5, F0 + 150, (0, -1))
    # the gaoler's post (vanilla's own furniture by its town jails' cells): a table
    # by the post's back wall, the gaoler's chair beside it facing the hallway and the cell's door (a chair faces its +y:
    # turned 180), a lantern and the cell's ledger on the table (63 high)
    bplace("meshes/clutter/common/commontablesquare01.nif", "CommonTableSquare01", (128, 990, F0), 0)
    # (the chair goes to the side of the table: 83 either side of the table is too little for a
    # chair facing it (it reaches 73 forward, 20 back), so beside its west side, facing the hallway as before)
    bplace("meshes/clutter/common/commonchair02.nif", "CommonChair02F", (43, 1030, F0), 180)
    bplace("meshes/clutter/common/candlelanternwithcandle01.nif", "CandleLanternwithCandle01", (100, 980, F0 + 63), 0)
    bplace("meshes/clutter/books/bookruined01.nif", "RuinedBook", (150, 985, F0 + 62.0 + 2.0 + 0.15), 20, owner="guild", settled=True)   # (its middle at
    # its origin, 2 under; the table's top measured at 62 by the placement gate, 2026-10-29: it sat 0.5 in, which physics ejects)
    # (the clutter plan, plans/BASEMENT.md: vanilla's guard posts keep their meal and their watch at the table)
    rg_ = random.Random("gaoler"); TT_ = F0 + 63 + 0.15
    bplace("meshes/clutter/dining set/basictankard01.nif", "BasicTankard01", (156 + rg_.uniform(-3, 3), 1012 + rg_.uniform(-3, 3), TT_),
           rg_.uniform(0, 360), owner="guild", settled=True)
    pl_ = (104 + rg_.uniform(-3, 3), 1008 + rg_.uniform(-2, 2)); pa_ = rg_.uniform(-25, 25)
    bplace("meshes/clutter/dining set/basicwoodenplate01.nif", "BasicWoodenPlate01", (pl_[0], pl_[1], TT_), pa_, owner="guild", settled=True)
    bplace("meshes/clutter/food/bread01a.nif", "FoodBread01A", (pl_[0] + rg_.uniform(-4, 4), pl_[1] + rg_.uniform(-2, 2), TT_ + 1 + 0.1),   # (in its dish)
           pa_ + rg_.uniform(-30, 30), owner="guild", settled=True)
    bplace("meshes/clutter/bucket01.nif", "Bucket01", (226 + rg_.uniform(-3, 3), 1038 + rg_.uniform(-2, 2), F0), rg_.uniform(0, 360),
           owner="guild", settled=True)
    brack_run("Post", 256 - 1, 985, F0, 270, [("IronSword", "meshes/weapons/iron/longsword.nif")])
    BASE_LIGHTS.append((100, 980, F0 + 100, 0.6e6, (1.0, 0.75, 0.5), "candle"))
    # ---------------------------------------------------------------- the prison cell
    CY1 = HY1 + 320
    bwall("x", -266 - T / 2, HY1 + T, CY1, F0, CEIL); bwall("y", CY1 + T / 2, -266 - T, 0, F0, CEIL)
    box("stone", (-266, HY1, CEIL), (0, CY1, CEIL + 8))
    # (the frame's run is its local +x from its origin, its inside its local -y: turned 180, the inside to +y, the origin at -13)
    bplace("meshes/dungeons/imperial/jail/impjaildoorframe01.nif", "ImpJailDoorframe01", (-32, HY1 + 8, F0), 180, 0.9)
    bplace("meshes/dungeons/imperial/jail/impjaildoor01.nif", "ImpJailDoor01", (-32, HY1 + 8, F0), 180, 0.9, name="AGHall2CellDoor")
    # the bedding as Windhelm's jail's (the town jail with this kit): the big hay bedroll alone in the cell, 3 over the floor,
    # its pile (213 x 307) filling it, here between the bars (952) and the back wall (1260)
    bplace("meshes/furniture/bedroll/bedrollhay01.nif", "BedrollHay01L", (-149, 1108.5, F0 + 3), 0)
    # (the clutter plan: Riften's and Solitude's cells keep a bucket and a meal)
    rcl_ = random.Random("cell")
    bplace("meshes/clutter/bucket01.nif", "Bucket01", (-60, 980, F0 + 0.15), rcl_.uniform(0, 360), owner="guild", settled=True)   # (by the bars: the hay stops short)
    # (on the floor inside the bars: the hay's pile, measured, stops short of them)
    bplace("meshes/clutter/dining set/basicwoodenbowl01.nif", "BasicWoodenBowl01", (-205 + rcl_.uniform(-4, 4), 974, F0 + 0.15), rcl_.uniform(0, 360),
           owner="guild", settled=True)
    bplace("meshes/clutter/dining set/basicwoodenplate01.nif", "BasicWoodenPlate01", (-168 + rcl_.uniform(-4, 4), 970, F0 + 0.15),
           rcl_.uniform(-30, 30), owner="guild", settled=True)
    # ---------------------------------------------------------------- the secret room: big, obvious and locked
    bwall("x", -760 - T / 2, HY1 + T, 1260, F0, CEIL); bwall("x", -420 + T / 2, HY1 + T, 1260, F0, CEIL)
    bwall("y", 1260 + T / 2, -760, -420, F0, CEIL, finish="stone")
    bvault(-760, HY1 + T, -420, 1260, F0, "y")
    # (vanilla's Imperial dungeon door, at 0.74 under the hallway's 244; locked, its key for the later quest). Its mesh is a
    # whole stone doorway, not a leaf: a wall section 256 x 310 x 37 with its sill and a 138-wide leaf, for the kit's 256
    # opening (the placement gate: hall2bi's opening, 120 wide, buried its stone 35 into the wall each side). The opening its
    # size at 0.74 (190 x 230), the unit in the wall's middle, its stone (6 over its origin) on the floor
    bplace("meshes/dungeons/imperial/door/impwooddoorsingle01.nif", "ImpDoorSingle01", (-590, HY1 + T / 2, F0 - 6 * 0.74), 0, 0.74,
           name="AGHall2SecretDoor", lock="key")
    # (gaps on each side of the door frame showed right into the unfinished room: Glorious
    # Doors of Skyrim's mesh has vanilla's bounds but not its stone to the edges) the opening backed with stone behind the
    # unit (its back 14 behind the wall's middle), the leaf's way (138 at 0.74) left clear, whatever door mesh an install has
    for a_, b_ in ((-685, -641), (-539, -495)): box("stone", (a_, HY1 + T - 1.5, F0), (b_, HY1 + T + 0.5, F0 + 230))
    box("stone", (-641, HY1 + T - 1.5, F0 + 190), (-539, HY1 + T + 0.5, F0 + 230))
    bsconce(-590, 1260, F0 + 150, (0, -1), lamp=280)   # (hang_check.py: under 228 of ceiling nothing hangs clear of a head)
    # (a single note in the secret room, reading that the room is still to be done: Hall2.cs's
    # AGHall2SecretRoomNote, vanilla's note with that text; on the floor, a little off the room's middle)
    bplace("meshes/clutter/books/note01.nif", "AGHall2SecretRoomNote", (-583, 1128, F0 + 0.3 + 0.15), 23, owner="guild", settled=True)
    # ---------------------------------------------------------------- the cellar, its ladder and the shaft through its vault
    bwall("x", B_CX0 - T / 2, 200, 940, F0, CEIL, finish="stone")
    # (2026-11-06) the front wall's left end open: the entryway to Henriette's room (below)
    bwall("y", 200 - T / 2, B_CX0, -1100, F0, CEIL, gaps=[(HR_DOOR[0], HR_DOOR[1], DH)], finish="stone")
    bwall("y", 940 + T / 2, B_CX0, -1100, F0, CEIL)
    bwall("x", -1080, 200 - T, HY0 - T, F1, CEIL, th=40)       # (the cellar's east wall and the bath's west wall are one)
    LSC_B = (CEIL - 2 - F0) / 197.0                           # (the trapdoor 2 under the kitchen's floor; the ladder's top 197)
    LXB = -1372 - 35 * LSC_B                                  # (the trapdoor at its local +y 35: under the kitchen's hatch at -1372)
    # (a vault with a timber shaft through it over the ladder looked wrong; so a flat ceiling on ribs:
    # a flat stone ceiling under the kitchen's floor on stone ribs across the cellar, 24 wide and 24 deep every 180,
    # laid so none crosses the ladder (its mesh, 140 across at its scale: y 321..461; the gate found the first rib in it))
    box("stone", (B_CX0, 200, CEIL), (-1100, 940, CEIL + 4))
    for y_ in (296, 476, 656, 836):
        box("stone", (B_CX0, y_ - 12, CEIL - 24), (-1100 if y_ < HY0 else -1100 - T, y_ + 12, CEIL))
    # (the ladder's back, its local -y, to the west wall: turned 90)
    bplace("meshes/dungeons/imperial/door/trapdoorladder02.nif", "TrapdoorLadder02", (LXB, 391, F0), 90, LSC_B,
           name="AGHall2CellarLadder", role="cellar_ladder", pair="kitchen_hatch", arrive=(LXB + 110, 391, F0), arrive_yaw=90)
    # the cellar's stores, as vanilla's cellars keep theirs (in hall2bm, three kegs on three barrels in a row, taps to
    # the wall, read as copy and paste, not a real cellar: no clutter aligned in grids). Researched (scratchpad cellar/): Nightgate's and the Frozen Hearth's inn cellars, Dushnikh
    # Yal's; large casks at 0.8 standing on their legs, their taps (local +y) to the room; kegs (MeadBarrel01, spout local -y)
    # never on a barrel: on the floor in pairs or on a shelf's boards (CommonShelf01's, 17/62/107, the shelf's open front its
    # local -y, the kegs within 10 degrees of it); barrels in loose clusters at any turn, scaled 0.95-1.1; crates stacked across
    # each other with a flat sack on top; a bucket. Every piece jittered from a seed, nothing in a row; 20 pieces (Nightgate's
    # cellar: 67). The middle kept clear from the hallway's door (east, y 812..920) to the ladder (west, y 321..461)
    rc_ = random.Random(1028); jit = lambda a: rc_.uniform(-a, a)
    G_ = dict(owner="guild")
    for y_ in (272, 404):                                     # the casks, backs to the east wall (their mesh at 0.8: x -62..72)
        bplace("meshes/clutter/brewerycasklargeclosed01.nif", "BreweryCaskLargeClosed01", (-1166 + jit(2), y_ + jit(4), F0 + 26.6 * 0.8),
               270 + jit(4), 0.8)
    for y_ in (503, 547):                                     # a pair of kegs on the floor beside them, spouts to the room
        bplace("meshes/clutter/meadery/meadbarrel01.nif", "MeadBarrel01", (-1125 + jit(3), y_ + jit(3), F0), 90 + jit(9))
    # crates: the long one on the floor along the wall (its length, 143, local y), a small one set on it toward one end and
    # turned across, a flat sack on that (the render of hall2bn's first try: the long crate balanced on the small one, 38 over
    # at each end)
    cr_ = (-1135 + jit(2), 652 + jit(3))
    bplace("meshes/clutter/common/cratesmalllong01.nif", "CrateSmallLong01", (cr_[0], cr_[1], F0 + 24.3), jit(3))
    sm_ = (cr_[0] - 6 + jit(1), cr_[1] + 30 + jit(4))           # (its corners turned: 7 off the wall)
    bplace("meshes/clutter/common/cratesmall04.nif", "CrateSmall04", (sm_[0], sm_[1], F0 + 48.6 + 25 + 0.1), 84 + jit(5))
    bplace("meshes/clutter/containers/miscsack02largeflat.nif", "MiscSack02LargeFlat", (sm_[0] + jit(5), sm_[1] + jit(5), F0 + 48.6 + 25 + 0.1 + 21.3 + 7.4 + 0.15),   # (on its top board, 21.3 over its middle: measured)
           rc_.uniform(0, 360), **G_)
    bplace("meshes/clutter/containers/miscsack02largeflat.nif", "MiscSack02LargeFlat", (-1150 + jit(4), 762 + jit(4), F0 + 7.4 + 0.2),
           rc_.uniform(0, 360), **G_)
    # the shelf against the west wall north of the ladder (its open front local -y: turned 270 its back is to the wall)
    sh_ = (-1435, 600 + jit(4)); sy_ = 270 + jit(1.5)
    bplace("meshes/clutter/common/commonshelf01.nif", "CommonShelf01", (sh_[0], sh_[1], F0), sy_)
    def on_shelf(rel, ed, lx, ly, board, yaw, **kw):
        a = math.radians(sy_); c, s = math.cos(a), math.sin(a)
        bplace(rel, ed, (sh_[0] + lx * c + ly * s, sh_[1] - lx * s + ly * c, F0 + board + 0.15), yaw, **kw)
    on_shelf("meshes/clutter/meadery/meadbarrel01.nif", "MeadBarrel01", -27 + jit(3), jit(2), 62, sy_ + jit(8))
    on_shelf("meshes/clutter/meadery/meadbarrel01.nif", "MeadBarrel01", 24 + jit(3), jit(2), 107, sy_ + jit(8))
    on_shelf("meshes/clutter/glazedjuglarge01.nif", "GlazedJugLarge01", 31 + jit(4), jit(3), 17, rc_.uniform(0, 360), settled=True, **G_)
    for lx_ in (6, 27, 48):                                   # (bottles left by the keg, loose: 17 across, 19 apart at least)
        on_shelf("meshes/clutter/wine/winebottle01b.nif", "FoodWineAlto", lx_ + jit(1), jit(5), 62, rc_.uniform(0, 360), settled=True, **G_)
    # the north-west corner: barrels as they were rolled in, one of food, a bucket
    # (barrels 56 across, 61 at their largest: their middles 64 apart at least, an uneven four, not a square)
    for (bx_, by_), ed_, m_ in (((-1428, 900), "Barrel02Static", "barrel02"), ((-1360, 905), "Barrel02Static", "barrel02"),
                                ((-1427, 826), "BarrelFood01_NoRespawn", "barrel01"), ((-1360, 842), "Barrel02Static", "barrel02")):
        sc_ = 1.0 + rc_.uniform(-0.05, 0.1)
        bplace(f"meshes/clutter/{m_}.nif", ed_, (bx_ + jit(1.5), by_ + jit(1.5), F0), rc_.uniform(0, 360), sc_,
               **(G_ if "Food" in ed_ else {}))
    bplace("meshes/clutter/bucket01.nif", "Bucket01", (-1298 + jit(3), 914 + jit(2), F0), rc_.uniform(0, 360), settled=True, **G_)
    # Henriette's larder, as vanilla's inn and palace cellars keep theirs (Nightgate's 67 pieces, the Bee and Barb's and the
    # Blue Palace's stores: potatoes, cabbages, carrots, leeks and apples in open baskets, cheese wheels stacked, salted meat and
    # fish in barrels, sacks of grain, herbs hung up to dry). Nothing over the way from the hallway's door to the ladder.
    def bsit(m, ed, x, y, z, yaw, rx=0.0, **kw):          # (sit(), for the basement: lifted by its mesh's measured base)
        foot_(m); b_ = _CB.get(m); lo_ = 0.0
        if b_:
            r_ = math.radians(rx)
            lo_ = min(-yy * math.sin(r_) + zz * math.cos(r_) for yy in (b_["lo"][1], b_["hi"][1]) for zz in (b_["lo"][2], b_["hi"][2]))
        bplace(m, ed, (x, y, z - lo_ + 0.15), yaw, rx=rx, owner="guild", settled=True, **kw)
    rl_ = random.Random("larder")
    # (no herbs hung up to dry: from the ceiling's ribs they hang 220 over the floor, out of a hand's reach (160), and under the
    # shelf's top they hang into its kegs; the cellar has no other wall for them)
    # (no second shelf: the cellar's walls are taken: the hallway's door and its swing, the ladder, Henriette's doorway in the
    # south wall, the three sconces) cheese on the long crate's free end, as vanilla's stores stack it on crates
    C_ = "meshes/clutter/food/"
    CT_ = F0 + 24.3 + 24.26                                # (the long crate's top; the small crate on its far end, y 650..714)
    for k_ in range(2):
        bsit(C_ + "cheesewheel01a.nif", "FoodCheeseWheel01A", cr_[0] + rl_.uniform(-2, 2), 606 + rl_.uniform(-2, 2), CT_ + 0.7 + 15.3 * k_, rl_.uniform(0, 360))
    bsit(C_ + "cheesewedge01.nif", "FoodCheeseWedge01", cr_[0] + 9, 634, CT_ + 0.7, rl_.uniform(0, 360))
    # salted meat and fish in barrels, rolled in north of the shelf by the food barrel's corner (Dragonborn's own, never refilling)
    for (bx_, by_), ed_ in (((-1430, 735), "BarrelMeat01_NoRespawn"), ((-1366, 764), "BarrelFish01_NoRespawn")):
        # (round: its turn shows nothing, so square-on within 3, its box no wider than the barrel for the placement gate)
        bplace("meshes/clutter/barrel01.nif", ed_, (bx_ + rl_.uniform(-1, 1), by_ + rl_.uniform(-1, 1), F0), rl_.choice((0, 90, 180, 270)) + rl_.uniform(-3, 3), owner="guild")
    # open baskets of the week's vegetables, on the floor where nobody walks: by the south wall between Henriette's doorway and
    # the casks, beside the kegs, by the north-west barrels and beside the long crate; each basket's few things on its floor
    # (0.8), set apart so none rests on another (the gates: produce stacked in a basket floats). No sacks: no floor left for them
    P_ = "meshes/plants/"
    def basket(x, y, m, ed, spots, thing, lying=False, tops=()):
        """a basket, its floor (0.8) covered as vanilla's are (the Bee and Barb's Basket05: eight apples), and heaped as its
        potatoes are (up to 26 over the floor) only where the game's own settle sets them (settle_check.py): tops, a second
        layer on the floor's (by index), unused until then (the placement gate reads produce on produce as floating); spots:
        (lx, ly) in the basket's own turn; lying: long things laid side by side"""
        yb_ = rl_.uniform(0, 360); a_ = math.radians(yb_)
        bplace(f"meshes/clutter/{m}.nif", ed, (x, y, F0), yb_, owner="guild", settled=True)
        foot_(thing[0]); h_ = _CB[thing[0]]["hi"][2] - _CB[thing[0]]["lo"][2]
        at_ = []
        for lx, ly in spots:
            wx_, wy_ = x + lx * math.cos(a_) + ly * math.sin(a_), y - lx * math.sin(a_) + ly * math.cos(a_)
            wx_, wy_ = wx_ + rl_.uniform(-0.6, 0.6), wy_ + rl_.uniform(-0.6, 0.6); at_.append((wx_, wy_))
            bsit(thing[0], thing[1], wx_, wy_, F0 + 0.8, (yb_ + rl_.uniform(-8, 8)) if lying else rl_.uniform(0, 360), rx=90 if lying else 0)
        for i_ in tops:
            bsit(thing[0], thing[1], at_[i_][0], at_[i_][1], F0 + 0.8 + h_, rl_.uniform(0, 360))
    ring = lambda r, n, t0=0.0: [(r * math.cos(t0 + 2 * math.pi * k / n), r * math.sin(t0 + 2 * math.pi * k / n)) for k in range(n)]
    # (2026-11-18: the baskets of loose produce were knocked about in game, their contents' Havok hulls inside the baskets'
    # (Basket01's is one solid hull): none for now) their draws kept, so the rest of the larder keeps its places: potatoes 22,
    # carrots 16, leeks 13, cabbages 7, apples 16
    for _ in range(22 + 16 + 13 + 7 + 16): rl_.random()
    # a salt pile on the shelf's lowest board by the jug (its mesh 2.7 under its origin)
    on_shelf("meshes/clutter/ingredients/saltpile.nif", "SaltPile", -8 + rl_.uniform(-2, 2), rl_.uniform(-3, 3), 17 + 2.9, rl_.uniform(0, 360), settled=True, **G_)
    # (the cellar's lights made no sense: two sconces bunched on one wall) spread for the room, 365
    # by 740: by the door on the east wall, across on the west, and on the south wall at the casks' end
    bsconce(-1100, 640, F0 + 150, (-1, 0), lamp=290); bsconce(-1465, 790, F0 + 150, (1, 0), lamp=290); bsconce(-1300, 200, F0 + 150, (0, 1), lamp=290)
    # ---------------------------------------------------------------- Henriette's room, off the cellar
    # (the staff rooms upstairs were too tight; the cook sleeps by her kitchen's cellar, a room
    # of her own in front of it, an entryway and a separate room for the nook, a step down allowed: through
    # a doorway with no door at the cellar front wall's left end, beside the ladder, a landing and one step down. Outside the hall's
    # footprint, as the secret room and the cell are (underground, nothing shows it). Her own
    # bed and chest from room 6 (their names kept: her schedule's bed), a nightstand with her sweetroll, a rug, the cellar's sconce
    # on the wall the plan puts it on (no candle: the room has no window)
    HF = F0 - 16                                                         # her floor, a step under the cellar's
    bfloor(B_CX0, -60, -1060, 168, HF)
    # the landing: through the doorway and on inside it, from her left wall to 22 past the opening, as a step in a doorway is built
    # (wider than the opening, leaving no tiny spot in the corner); its riser the one step down
    box("floor", (B_CX0, 128, HF), (HR_DOOR[1] + 22, 200, F0))         # (on her floor, not through it: their sides were in one plane)
    bwall("x", B_CX0 - T / 2, -60 - T, 200, HF, CEIL)                   # her left wall, to the cellar's corner
    bwall("y", -60 - T / 2, B_CX0, -1060, HF, CEIL)                     # the front
    # the cellar's front wall stands on the cellar's floor, a step over hers: under it, beside the landing, a slot 16 high showed the
    # void (the first render); the wall's foot carried down to her floor there
    box("stone", (HR_DOOR[1] + 22, 168, HF), (-1100, 200, F0))
    bwall("x", -1060 + T / 2, -60 - T, 168, HF, CEIL)                   # her right wall, to the bath's front wall
    box("stone", (B_CX0, -60, CEIL), (-1060, 168, CEIL + 4))            # a flat stone ceiling on two ribs, as the cellar's
    for x_ in (-1330, -1195): box("stone", (x_ - 12, -60, CEIL - 24), (x_ + 12, 168, CEIL))
    # the bed in the far right corner, its head (local -y) to the front wall, 9 off both walls; the nightstand by its head
    # against the front wall
    bplace("meshes/clutter/upperclass/upperbedsingle01.nif", "UpperBedSingle01", (-1121, 42, HF), 0, name="AGHallBedRoom6")
    bplace("meshes/clutter/upperclass/uppernightstand01.nif", "UpperNightstand01", (-1200, -31, HF), 0)
    bplace("meshes/clutter/ingredients/sweetroll01.nif", "FoodSweetroll", (-1197, -34, HF + 32), 20, settled=True)
    # (the room looked a little empty for its size: her chest moved under the sconce, small shelves in its place; a plainer
    # rug, rug01) her chest on the
    # back wall under the sconce, its lid (local +y) to the room; vanilla's low upperclass shelf (UpperShelf02, 135 x 54, its open
    # front local -y, its crested back +y) in the chest's corner against her left wall, opening to the room
    bplace("meshes/clutter/upperclass/upperchest01.nif", "AGHall2Chest", (-1247, 168 - 23 - 2, HF), 180, name="AGHallChestRoom6")
    bplace("meshes/clutter/upperclass/uppershelf02.nif", "UpperShelf02", (B_CX0 + 33 + 2, -60 + 2 + 67, HF), 270)
    bplace("meshes/clutter/common/rug01.nif", "Rug01", (-1285, 42, HF + 0.3), 0)
    # (the nook's shelves were empty: a few keepsakes and a basket)
    # its top (z 62, x -1457..-1403, y -59..77, its crest at the back by the wall): a jug, a wooden bowl, two books, one on the
    # other; its inner board (z 10.5): a basket. Strewn, not set in a row; hers, being in her room (the export's group)
    SH_ = HF + 62
    bplace("meshes/clutter/glazedjugsmall01.nif", "GlazedJugSmall01", (-1437, -36, SH_), 23, settled=True)
    bplace("meshes/clutter/dining set/basicwoodenbowl01.nif", "BasicWoodenBowl01", (-1423, 6, SH_), 0, settled=True)
    # (the lived-in pass, 2026-11-17) by the bowl, a horn cup: the two belonged to people of the first company who did not come
    # home (vanilla's drinking horn mesh as our own static: its record is a Thieves Guild quest item)
    bplace("meshes/clutter/quest/tgdrinkinghorn.nif", "AGHall2DrinkingHorn", (-1418, -18, SH_ + 0.1), 205)
    bplace("meshes/clutter/books/basicbook01.nif", "Book1CheapBriefHistoryoftheEmpirev1", (-1432, 48, SH_ + 2.01), 97, settled=True)
    bplace("meshes/clutter/books/basicbook04a.nif", "Book2CommonExplorersGuideToSkyrim", (-1430, 50, SH_ + 2.01 + 4.13), 81, settled=True)
    bplace("meshes/clutter/basket01.nif", "Basket01", (-1426, 26, HF + 10.5), 17, settled=True)
    bsconce(-1247, 168, HF + 150, (0, -1), lamp=400)                    # (its reach the room's far corner, the chest's: light_check)
    # ---------------------------------------------------------------- the bath: down three steps; the pool
    bwall("y", 200 - T / 2, -1060, -444, F1, CEIL)
    bwall("x", -428, 200 - T, HY0 - T, F1, CEIL)              # (the bath's east wall and the steps' strip's west wall are one)
    bvault(-1060, 200, -444, HY0 - T, F1, "y", spring=170)
    for k in range(3):                                        # (from the hallway's floor's edge: the first tread is the doorway's
        y1 = HY0 - k * B_TREAD                                # floor through the wall, as the strip's; navgen found the bath cut off)
        box("stone", (-903, y1 - B_TREAD, F1), (-805, y1, F0 - k * B_RISE))
    # (the door stood out of its doorway, placed by its middle; its origin is its hinge. As interior_gen's
    # door_leaf hangs it: the leaf along its local +x from the hinge, 8 thick over local y 0..8, opening toward local -y, so
    # hinged at the end that makes it open into the bath (-y), at that jamb, 4 toward the swing; the doorway the leaf's size,
    # 96 x 176, as vanilla's: on MGO a slit by the hinge showed through)
    sx_, sy_ = 0, -1; ax_, ay_ = -sy_, sx_
    hx_, hy_ = (-902 + sx_ * 4, HY0 - T / 2 + sy_ * 4)
    bplace("meshes/architecture/solitude/doors/ssingledoorint01l.nif", "SSingleDoorInt01L", (hx_, hy_, F0),
           math.degrees(math.atan2(-ay_, ax_)) % 360, name="AGHall2BathDoor")
    # the pool (the bathhouse mods' form: sunken, flush with a flagged floor, real water): 416 x 288, the water 72 deep, ledges
    # 32 wide on its long sides 33 under the water, steps down at the door's end; its water is the cell's (Hall2.cs: -316)
    PX0, PY0, PX1, PY1 = -960, 270, -544, 558
    PFL, LEDGE = B_WATER - 72, B_WATER - 33
    box("stone", (PX0, PY0, PFL - 12), (PX1, PY1, PFL))
    for lo_, hi_ in (((PX0 - 12, PY0 - 12, PFL - 12), (PX0, PY1 + 12, F1)), ((PX1, PY0 - 12, PFL - 12), (PX1 + 12, PY1 + 12, F1)),
                     ((PX0, PY0 - 12, PFL - 12), (PX1, PY0, F1)), ((PX0, PY1, PFL - 12), (PX1, PY1 + 12, F1))):
        box("stone", lo_, hi_)
    # (the steps must face the door: the steps down from the pool's north edge, under the bath's door
    # (x -854), 112 wide; the sitting ledge along the far, south side)
    box("stone", (PX0, PY0, PFL), (PX1, PY0 + 32, LEDGE))
    # (in hall2bl the pool's bench could not be sat on, where other mods' benches can: the ledge in the pool. Vanilla seats a stone ledge with an invisible chair the
    # player can use: InvisibleChairPlayerTriple, seven on the cells' ledges in Solitude's jail; its three seats 33.8 over its
    # origin, 46 apart, facing its local +y. Two along the ledge, the sitter's back to the pool's south wall, facing the pool)
    # (a seat in the water: that chair has no collision, so no crosshair ever finds it;
    # vanilla's NPCs use it by package. AGHall2PoolSeat is its form and markers with a collision slab on the seat line and a
    # name: blender/pool_seat_nif.py, Hall2.cs)
    for x_ in (-842, -662):
        bplace("meshes/adventurersguild/hall2/aghall2poolseat.nif", "AGHall2PoolSeat", (x_, PY0 + 15, LEDGE - 33.8), 0)
    for k in range(4):
        box("stone", (-910, PY1 - 32 * (k + 1), PFL), (-798, PY1 - 32 * k, F1 - (k + 1) * (F1 - PFL) / 5))
    for x0_, y0_, x1_, y1_ in ((-1060, 200, -444, PY0 - 12), (-1060, PY1 + 12, -444, HY0 - 3 * B_TREAD),
                               (-1060, PY0 - 12, PX0 - 12, PY1 + 12), (PX1 + 12, PY0 - 12, -444, PY1 + 12)):
        bfloor(x0_, y0_, x1_, y1_, F1)
    bfloor(-1060, HY0 - 3 * B_TREAD, -903, HY0 - T, F1); bfloor(-805, HY0 - 3 * B_TREAD, -444, HY0 - T, F1)
    # the water: vanilla's own way. Its interior pools are placed water planes, the cell flagged for water with no height of its
    # own (watersurvey: PurewaterRun01, ClearspringTarn01, AbandonedPrison01 ...; hall2bi's cell water
    # was invisible); vanilla's interior workhorse, Water1024DefaultIntWaistStill (71 placed, scaled 0.88 to 4.29), at 0.5: 512
    # square over the pool's 416 x 288, its overflow inside the decks' slab (-316..-304), the surface 6 under the deck
    bplace("meshes/water/water1024.nif", "Water1024DefaultIntWaistStill", ((PX0 + PX1) / 2, (PY0 + PY1) / 2, F1 - 6), 0, 0.5)
    # the benches, by their record (bounds x -83..83, y -73..15, the seat's front, its sitting room, to -y) and their mesh's
    # three sit markers (y 0, heading 180: facing local -y, entered from the front only). The first benches could not be
    # sat on: placed by their middle, one sat in the south wall, the other with no room before it. The
    # decks beside the pool are 88 wide, the bench and its room 88: only the north deck (y 570..759) holds one. One on the
    # north wall east of the doorway's steps facing the pool, one on the east wall in the north-east corner facing west
    bplace("meshes/furniture/common/commonbench01.nif", "CommonBench01", (-700, 759 - 17, F1), 0)
    bplace("meshes/furniture/common/commonbench01.nif", "CommonBench01", (-444 - 17, 665, F1), 90)
    # the braziers as vanilla stands WRBrazier01 (its bounds z -80..41: its origin 80 over its feet) and its fire (19.7 over
    # the origin, FXfireWithEmbers01 at 0.87); in three corners, the north-east one's corner now the bench's
    # (the clutter plan: the bathhouse's things that vanilla has: a wash stand (NobleWashBasin01, its backsplash, local +y, to the
    # wall), a bucket, jugs and a bottle of oil on a wall shelf (WRWallShelf01, its board 16 over its origin; turned 270 its
    # brackets to the wall, as the tavern's))
    rb_ = random.Random("bath")
    bplace("meshes/furniture/noble/noblewashbasin01.nif", "NobleWashBasin01", (-958, 759 - 24.2 - 1, F1), rb_.uniform(-2, 2))
    bplace("meshes/clutter/bucket01.nif", "Bucket01", (-770 + rb_.uniform(-3, 3), 602 + rb_.uniform(-3, 3), F1), rb_.uniform(0, 360),
           owner="guild", settled=True)
    SH_ = (-444 - 19.6 - 0.5, 420); SZ_ = F1 + 110                 # (under the vault's springing, 170; not over the bench)
    bplace("meshes/architecture/whiterun/wrinteriors/wrwallshelf01.nif", "WRWallShelf01", (SH_[0], SH_[1], SZ_), 270)
    for lx_, m_, e_ in ((-48, "glazedjuglarge01", "GlazedJugLarge01"), (-14, "glazedjugsmall01", "GlazedJugSmall01"),
                        (20, "glazedjugsmall01", "GlazedJugSmall01"), (50, "wine/winebottle01b", "FoodWineAlto")):
        lx_ += rb_.uniform(-3, 3); ly_ = rb_.uniform(-4, 4)          # (turned 270: its local x is the hall's +y, its local y -x)
        bplace(f"meshes/clutter/{m_}.nif", e_, (SH_[0] - ly_, SH_[1] + lx_, SZ_ + 16.2 + 0.15), rb_.uniform(0, 360), owner="guild", settled=True)
    for bx_, by_ in ((-1014, 248), (-490, 248)):                  # (the third, by the door, went)
        bplace("meshes/architecture/whiterun/wrclutter/wrbrazier01.nif", "WRBrazier01", (bx_, by_, F1 + 80), 0)
        bplace("meshes/effects/fxfirewithembers01_cheap.nif", "FXfireWithEmbers01_Cheap", (bx_, by_, F1 + 80 + 19.7), 0, 0.87)
        BASE_LIGHTS.append((bx_, by_, F1 + 140, 1.0e6, (1.0, 0.65, 0.35), "fire_small", -300, 0.0))
    # ---------------------------------------------------------------- the training room
    bwall("y", 318 - T / 2, -412, -280, F1, CEIL)
    for k in range(3):
        y1 = HY0 - k * B_TREAD
        box("stone", (-412, y1 - B_TREAD, F1), (-280, y1, F0 - k * B_RISE))
    bwall("x", -280, 51, 318 - T, F1, CEIL, th=28)
    bwall("y", 51 - T / 2, -280, 1400, F1, CEIL)
    box("stone", (336, 51, F1), (1400, 215, CEIL))             # (no room under the range's front: marked out on the plan)
    bwall("x", 1400 + T / 2, 215, 759, F1, CEIL)
    bwall("y", 759 + T / 2, 256, 1400, F1, CEIL)
    pts_ = bvault(336, 215, 1400, 759, F1, "x")
    for y0_, y1_ in ((215, 215 + 96), (759 - 96, 759)): box("stone", (336 - 16, y0_, F1), (336 + 16, y1_, CEIL))   # the pillars
    # the rib across between them: a band following the vault's curve 18 under it, 24 wide (narrower than the pillars and
    # stopping at their faces: none of its faces in one plane with theirs). Its underside and sides as the vault's own facets
    # (hall2bk's renders: a box per facet, each to the lower of its ends, made its underside a staircase)
    def zv(y_):                                               # the vault's height over y, between the arc's points
        for (ya, za), (yb, zb) in zip(pts_, pts_[1:]):
            if min(ya, yb) <= y_ <= max(ya, yb): return za + (zb - za) * (y_ - ya) / ((yb - ya) or 1)
        return pts_[0][1]
    ys_ = sorted({215 + 96, 759 - 96} | {y_ for y_, _ in pts_ if 215 + 96 < y_ < 759 - 96})
    for ya, yb in zip(ys_, ys_[1:]):
        za, zb = zv(ya) - 18, zv(yb) - 18
        poly_n("stone", [(336 - 12, ya, za), (336 - 12, yb, zb), (336 + 12, yb, zb), (336 + 12, ya, za)], (0, 0, -1))   # under
        for x_, nx_ in ((336 - 12, -1), (336 + 12, 1)):                                                                  # sides
            poly_n("stone", [(x_, ya, za), (x_, yb, zb), (x_, yb, CEIL), (x_, ya, CEIL)], (nx_, 0, 0))
    # (the clutter plan: vanilla's indoor training areas surround their dummies with wall weapon racks, hay, barrels, a bench;
    # the basement brief's repair corner: the grindstone and the armour workbench, usable, their working sides to the
    # room; the racks player-usable, with some weapons already stored, as Jorrvaskr's)
    rtr_ = random.Random("training")
    brack_run("West", -266 + 1, 182, F1, 90, [("IronGreatsword", "meshes/weapons/iron/ironclaymore.nif"), None,
                                              ("IronWarAxe", "meshes/weapons/iron/waraxe.nif")])
    brack_run("North", 62, 759 - 1, F1, 180, [("IronSword", "meshes/weapons/iron/longsword.nif"), ("IronMace", "meshes/weapons/iron/ironmace.nif"), None])
    bplace("meshes/furniture/common/commonbench01.nif", "CommonBench01", (-150 + rtr_.uniform(-3, 3), 759 - 15 - 2, F1), rtr_.uniform(-1.5, 1.5))
    # (the workbench is worked from its local -x (its sit marker, heading 90, entered from behind): its +x back to the north
    # wall, turned 270; the grindstone's user stands at its origin facing its local +y, the wheel 26..144 ahead: its far end
    # to the wall)
    bplace("meshes/furniture/blacksmithworkbench01.nif", "CraftingBlacksmithArmorWorkbench", (200, 759 - 1 - 26.4, F1), 270 + rtr_.uniform(-1, 1))
    bplace("meshes/furniture/clutter/blacksmithsharpeningwheelanimating.nif", "CraftingBlacksmithSharpeningWheel", (292, 759 - 2 - 143.6, F1),
           rtr_.uniform(-1.5, 1.5))
    for hx_, hy_, m_, e_ in ((-35, 140, "hayscatter02", "HayScatter02"), (150, 128, "hayscatter02", "HayScatter02"),
                             (1290, 494, "hayscatter04", "HayScatter04")):
        bplace(f"meshes/clutter/hay/{m_}.nif", e_, (hx_ + rtr_.uniform(-8, 8), hy_ + rtr_.uniform(-8, 8), F1 + 0.3), rtr_.uniform(0, 360))
    bplace("meshes/clutter/barrel02.nif", "Barrel02Static", (293 + rtr_.uniform(-2, 2), 87 + rtr_.uniform(-2, 2), F1), rtr_.uniform(0, 360))
    BK_ = (298 + rtr_.uniform(-3, 3), 152 + rtr_.uniform(-3, 3), F1)
    bplace("meshes/clutter/bucket01.nif", "Bucket01", BK_, rtr_.uniform(0, 360), owner="guild", settled=True)
    # (the lived-in pass, 2026-11-17) the water bucket's ladle laid across its rim (the bucket's rim at 30, its radius 17.6; the
    # ladle's bowl at its origin, its handle along -x, 3.5 under its origin); two practice swords leaned on the south wall behind
    # the dummies, between the middle and the east one, out of anyone's swing (the swords' blades along +y to 63, the pommel at
    # -11.7: tilted 72..78 so the tip stands on the floor and the hilt rests against the wall)
    bplace("meshes/clutter/kitchen/woodenladle01.nif", "WoodenLadle01", (BK_[0] + 7, BK_[1] + 1.5, F1 + 30 + 3.6), 14, owner="guild", settled=True)
    for sx_, tilt_, yw_ in ((106, 74, 3), (124, 77, 351)):
        bplace("meshes/weapons/iron/longsword.nif", "IronSword", (sx_, 51 + 7, F1 + 63.2 * math.sin(math.radians(tilt_)) + 0.3), yw_, rx=tilt_,
               owner="guild", settled=True)
    # the targets at the range's end (their painted face, local -x, to the shooters), the dummies along the main area's front
    rt_ = random.Random("range targets")                       # (not ruled out: the clutter audit, 2026-10-28)
    TARGETS_ = []
    for ty in (334, 494, 654):
        TARGETS_.append(((1350 + rt_.uniform(-6, 0), ty + rt_.uniform(-6, 6)), rt_.uniform(-4, 4)))
        bplace("meshes/clutter/common/archerytarget01.nif", "ArcheryTarget", (*TARGETS_[-1][0], F1), TARGETS_[-1][1])
    # the archers' table (a small table against the wall in a corner, with a regular bow, a training bow and a quiver of
    # arrows, and an open barrel or bucket beside it with loose arrows; the training bow the Long Bow): the range's south corner by the entrance pillar (x 320..352, y 215..311), out of the line to the
    # nearest target (y 334); the north side holds the workbench and the grindstone. As vanilla sets them (HallSpike `pairs`):
    # bows and the prop quiver (DummyArrow, vanilla's quiver on shelves and tables) flat, untilted, 1.3 and 3.4 over a
    # table's top (CommonTableSquare01's at 63: New Gnisis' Hunting Bow at 64.3); arrows in a bucket stood on their origin end,
    # tilted 70..82 about their x so their 58 along -y rises (vanilla's iron arrows in Dawnstar's bucket and Markarth's basket
    # stand up only when the game's angles are read X, then Y, then Z, clockwise: Hall2.cs's GameAngles)
    ra_ = random.Random("archers table")
    TX_, TY_ = 352 + 14 + 45 + ra_.uniform(0, 3), 215 + 45 + 1.5; ta_ = ra_.uniform(-1.5, 1.5)   # (14 off the pillar: a bow's 115
    # overhangs the table's 92)
    bplace("meshes/clutter/common/commontablesquare01.nif", "CommonTableSquare01", (TX_, TY_, F1), ta_)
    def on_t(lx, ly):                                          # (a point on the table's top, turned with it)
        c_, s_ = math.cos(math.radians(ta_)), math.sin(math.radians(ta_)); return (TX_ + lx * c_ + ly * s_, TY_ - lx * s_ + ly * c_)
    bplace("meshes/weapons/steel/steelbow.nif", "HuntingBow", (*on_t(ra_.uniform(-4, 4), 18 + ra_.uniform(-2, 2)), F1 + 64.3),
           ta_ + 90 + ra_.uniform(-6, 6), owner="guild", settled=True)   # (a bow's 115 runs along its local y: along the wall)
    bplace("meshes/weapons/wooden/woodenbow.nif", "LongBow", (*on_t(ra_.uniform(-4, 4), -10 + ra_.uniform(-2, 2)), F1 + 64.3),
           ta_ + 270 + ra_.uniform(-8, 8), owner="guild", settled=True)
    bplace("meshes/clutter/dummyitems/dummyquiver01.nif", "DummyArrow", (*on_t(30 + ra_.uniform(-2, 2), 26 + ra_.uniform(-2, 2)), F1 + 66.4),
           ta_ + 77 + ra_.uniform(-12, 12), owner="guild", settled=True)
    BX_, BY_ = TX_ + 45 + 22 + ra_.uniform(0, 4), 215 + 16 + ra_.uniform(0, 3)
    bplace("meshes/clutter/bucket01.nif", "Bucket01", (BX_, BY_, F1), ra_.uniform(0, 360), owner="guild", settled=True)
    for k_ in range(7):
        r_, t_ = ra_.uniform(0, 7), ra_.uniform(0, 2 * math.pi)
        bplace("meshes/weapons/iron/ironarrow.nif", "IronArrow", (BX_ + r_ * math.cos(t_), BY_ + r_ * math.sin(t_), F1 + 3.4),
               ra_.uniform(0, 360), rx=ra_.uniform(70, 82), owner="guild", settled=True)   # (+: our rx turns its -y up; the
                                                                                        # game reads X, Y, Z clockwise, KB)
    for i, dx in enumerate((-150, 0, 150)):
        bplace(f"meshes/clutter/practicedummy/practicedummy0{i + 1}.nif", f"PracticeDummy0{i + 1}", (40 + dx, 110, F1), 180)   # (their
        # front, the arms, is local -y (the mesh reaches 23 that way, 6 to the post's side): turned to the room; in
        # hall2bl they faced the wrong way)
    # (the training room had almost no light, and the hanging ring was in the way of swinging swords)
    # nothing hangs over the training floor or the range: lit sconces on the walls, facing what they light; the dummies from the
    # long wall across from them, the range from its sides, before the targets and at the shooting line
    # (the training room's sconces, all but the archery range's, hung too low: over a head and a swung sword)
    bsconce(-120, 759, F1 + 190, (0, -1), lamp=380); bsconce(190, 759, F1 + 190, (0, -1), lamp=380)
    # (the dummies stand by the south wall, facing the room: a light on that wall would backlight them, so from their sides, light_check.py: 35% of the floor)
    bsconce(-266, 270, F1 + 190, (1, 0), lamp=380); bsconce(336, 130, F1 + 190, (-1, 0), lamp=380)
    bsconce(430, 215, F1 + 100, (0, 1), lamp=320); bsconce(430, 759, F1 + 100, (0, -1), lamp=320)   # (the range's near end)
    bsconce(760, 215, F1 + 100, (0, 1), lamp=320); bsconce(760, 759, F1 + 100, (0, -1), lamp=320)
    bsconce(1230, 215, F1 + 100, (0, 1), lamp=320); bsconce(1230, 759, F1 + 100, (0, -1), lamp=320)     # (under the vault's springing; formerly on the end wall, at 1400,
                                                                                      # between the targets)
    BASE_MARKERS.append(("AGHall2BasementArrive", "XMarkerHeading", (190, 850, F0), 270))
    # the training routines' markers (the staff routines: the guild
    # master drills at a dummy, the archer shoots; their packages copies of vanilla's GuardRiftenPracticeDayDummy01_20x2 and
    # MQSkyHavenTempleArcheryPracticeA8x2: the stand is the Use Weapon location, the target the Target and Trigger Ref). A
    # set per dummy and per target, sets 2 and 3 for the residents later. As vanilla sets them (HallSpike `pairs`): a
    # dummy's target 37 before its front at 83 (the Thieves Guild's PracticeDummy03), its stand 130 before it (Riften's
    # guards 140-166 from theirs, Sky Haven 96); an archery target's 55 before its painted face at 56 (the Thieves Guild's,
    # Tamriel -35,1: 53-62 out, 55-58 up), its stand 410 down the lane (Sky Haven's 400-425), the lane clear
    for i, dx in enumerate((-150, 0, 150)):                   # (the dummies' fronts face +y: turned 180)
        BASE_MARKERS.append((f"AGHallTrainMeleeTarget{i + 1}", "XMarker", (40 + dx, 110 + 37, F1 + 83), 180))
        BASE_MARKERS.append((f"AGHallTrainMeleeStand{i + 1}", "XMarkerHeading", (40 + dx, 110 + 130, F1), 180))   # (facing -y)
    for i, ((tx_, ty_), tyaw_) in enumerate(TARGETS_):        # (a painted face is local -x: along -x, turned with the target)
        c_, s_ = math.cos(math.radians(tyaw_)), math.sin(math.radians(tyaw_))
        out_ = lambda d_: (tx_ - d_ * c_, ty_ + d_ * s_)       # (local (-d, 0) as the archers' table turns its points)
        BASE_MARKERS.append((f"AGHallTrainArcheryTarget{i + 1}", "XMarker", (*out_(55), F1 + 56), 90))
        BASE_MARKERS.append((f"AGHallTrainArcheryStand{i + 1}", "XMarkerHeading", (*out_(410), F1), (90 + tyaw_) % 360))   # (facing it)
    # (Marius the hall's combat trainer, standing by in the training
    # room 8-11 and 14-18, watching, not practising) vanilla's WallLeanMarker on the north wall, facing the dummies across the room:
    # between the bench (x -208..-88) and the weapon rack (14..110), under no sconce (-120 and 190 at 190 up), out of the dummies'
    # swings (their stands at y 240) and of the range's lane (x 336 on). 40 off the wall's face (759), as vanilla sets it (pairs:
    # a wall-mounted fish 40 behind the marker, a wall's cap 50-56); the marker's one position is its origin, facing its +y
    BASE_MARKERS.append(("AGHallTrainWatchMarker", "WallLeanMarker", (-37, 759 - 40, F1), 180))
    PART = "interior"
    print("BASEMENT", sum(len(v) for (pt_, _), v in GEO.items() if pt_ == "basement"), "faces,", len(BASE_PLACE), "pieces,",
          len(BASE_LIGHTS), "lights")
