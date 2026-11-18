# The Guild Hall's interior, built from the exterior's own numbers. Run by guildhall_gen.py when AG_INTERIOR is set, after
# the exterior: its constants (PX0.., S1, T1, T2, J, ridge), its helpers (poly, box, beam, ATLAS, outline) and its register
# of openings (OPENINGS) are what the inside is made from, so a window inside stands where the window outside does.
# Phase 1 (a separate plugin, the great hall open to the roof): the great hall, for
# comparing the grand stair, AG_STAIRS =
#   A  twin flights along the side walls up to a gallery across the back, over the counter (the second reference)
#   B  one wide flight along the right wall; a gallery down the left side joins the back gallery to the office
#   C  galleries on all four sides; the stair rises in the right wing, seen through a wide arch
#   T  C's galleries with the stair in the tower instead: a newel stair from an arch at
#      the great hall's back-right corner up to a door onto the back gallery, and on up to the lookout; the right wing
#      gets back the room C's stair hall took, and its side of the hall an arcade like the left's
#   D  T with the first-floor plan: the left wing's middle open over the tavern to its roof,
#      galleries along its front and back walls joined to the ring, two rooms left in the cross gable's bay, and the
#      office's back-left corner given to the gallery
#   U  the tower plan: the stair entered from the guild services, out onto a lobby by the patio
#      door, the tower enlarged (run with AG_TOWER_BOX) and filled by square-ended steps
#   V  D with the tower at the planned line (the exterior's own box: x 216..720, y 732..1160): its foot takes
#      the great hall's back-right corner beside the counter, the back gallery goes (the hall open to its back wall),
#      and an open-well stair (Fort Dawnguard's kind) turns clockwise from an arch on the front's right part, off the
#      guild services, to an opening onto the lobby beside the gallery's door, the attic door and
#      a top landing under the lookout's hatch
#   W  V with the choices from the Great Hall Layout study: the great hearth in
#      the back bay between the tower's foot and its mirror (a stone mass in the back-left corner up to the roof), one
#      step up as a dais; the counter under the right gallery; the galleries on carved brackets off the arcades' stone
#      piers, with two tall posts where the front landing meets them, floor to truss; the arcades round stone arches; the
#      library loft on the office's roof, reached by a small newel stair inside the office
# Hall frame: +x right as seen from the road, +y back, z up from the hall's floor (G = 0); game units.

INTERIOR = True
VARIANT = os.environ.get("AG_STAIRS", "A").upper()
TOWER_STAIR, TAVERN_OPEN = VARIANT in ("T", "D", "U", "V", "W"), VARIANT in ("D", "V", "W")
TOWER2 = VARIANT in ("U", "V", "W")   # the stair from the guild services, out onto the lobby by the patio door
TOWER3 = VARIANT in ("V", "W")        # the tower at the planned line, an open-well stair turning clockwise
HEARTH = VARIANT == "W"               # the great hearth, its mirror mass, the counter on the right, bracketed galleries
for k_ in [k_ for k_ in GEO if k_[0] != "interior"]: del GEO[k_]   # the exterior was built for its numbers only
COLL.clear(); COLL_KEY.clear(); AGE_CELL.clear()                                     # no baked age inside (yet)
SITE = None                                                        # no terrain round an interior
PART = "interior"
if HEARTH:   # W, the fit-out (palette C): the renders in Solitude's interior kit, as hall_nif.py's
             # INT_MAP builds the cells (outside nothing changes; the windows' and doors' pictures stay as they are)
    FILES.update({"stucco": "sstuccowallint01", "wood": "swoodbeam02", "planks": "swoodfloor01", "floor": "sfloorhouse01",
                  "stone": "sintcoloumn01", "trim": "strims02", "base": "sslatebaseint01"})
    # (since the hall2t walk, 2026-10-26: our own graded copies, palette 1 with palette 2's woods; hall_nif.py's INT_MAP)
    FILES.update({k_: "../../adventurersguild/hall2/" + v_ for k_, v_ in (
        ("stucco", "AGH2Plaster"), ("wood", "AGH2Beam"), ("planks", "AGH2Boards"), ("floor", "AGH2Blocks"), ("stone", "AGH2Blocks"),
        ("trim", "AGH2Trim"), ("base", "AGH2Panel"), ("wood2", "AGH2Beam2"), ("planks2", "AGH2Planks2"))})
FILES.update(json.loads(os.environ.get("AG_FILES", "{}")))         # (renders only: a palette study's textures, by key)
FIX_FACES = True                                                   # poly's outline normal, beam's outward faces (guildhall_gen)
_wall_beam_ext = wall_beam
def wall_beam(W, a, b, w=18, deep=8, d0=0, key="wood", back=False):
    """the exterior's wall timber, stopped 0.5 short of both ends and 1 narrower: inside, timbers end at walls and floors
    and stand in corners, and with the full size their ends and edges lay in those surfaces' planes (z-fighting: 299 of the
    896 overlaps the interior's flicker check found, 2026-10-25)"""
    du, dz = b[0] - a[0], b[1] - a[1]; L_ = math.hypot(du, dz)
    up_ = abs(du) < 1e-6
    # (since the hall2bd walk, 2026-10-28: the beams beside a window flickered: a rail run to a wall's
    # end stopped 0.5 short, where the end post's outer side stands too, the two end faces in one plane; a horizontal
    # timber now stops 1.5 short, its end inside the post)
    # (since the MGO walk of 2026-11-05: bright seams all over the hall: a post 0.5 short of the floor and
    # the head and 1 narrower than its place left a strip of plaster showing down every doorpost and corner, 0.5 wide, its
    # edge lit like a crack. A post now runs 0.4 past its place every way: into the floor and the timber or ceiling over
    # it, 0.4 over the opening's or corner's edge. Its faces still lie in nobody's plane, the reason for the old cut
    # (0.4, not 0.5: the window frames and much else stand on the half units, and at 0.5 a post's side met theirs)
    cut_ = -0.4 if up_ else 1.5
    if L_ > 3 * abs(cut_):
        tu, tz = du / L_ * cut_, dz / L_ * cut_
        a, b = (a[0] + tu, a[1] + tz), (b[0] - tu, b[1] - tz)
                                                           # a post stands 1 proud of the rails it crosses: at the same depth
    if up_:   # (2026-11-06: running 0.4 over an opening's edge, a doorpost's open back showed there from the far side, through the
              # doorway: the leak check's faces seen from behind, 61 -> 163) a doorpost has its back (back=True: door_head's), in the wall's
              # plane facing into it; the others none, as before (their backs in that plane met the floors' and the other posts' edges)
        o_, r_, n_ = W
        beam(o_ + r_ * a[0] + UP * a[1] + n_ * d0, o_ + r_ * b[0] + UP * b[1] + n_ * d0, w + 0.8, deep + 1, n_, key=key, back=back or d0 > 0)
        return
    _wall_beam_ext(W, a, b, w=w - 1, deep=deep, d0=d0, key=key)   # their faces met in one plane, grain crossing
def wall_rail(W, u0, u1, zz, doors=(), w=24, deep=8):
    """a horizontal wall timber from u0 to u1 at zz, stopped at the posts of every door it would cross (doors: (u0, u1, z0,
    z1), holes and shut doors alike; until 2026-10-25 the rails at the floor ran on across the doorways: a sill to step
    over in each, its open back seen from the far side)"""
    if "ZG" in globals() and ZG + 8 <= zz <= ZG + 14:   # a floor rail, the baseboard: drawn at the end by baseboards()
        BASE_RUNS.append({"W": W, "u0": u0, "u1": u1, "deep": deep, "part": PART, "frame": FRAME, "band": (ZG - 0.5, ZG + 23),
                          "holes": sorted((min(h[0], h[1]), max(h[0], h[1])) for h in doors if h[2] <= ZG + 23 and h[3] >= ZG + 1)})
        return
    # (the test walk of 2026-11-06, another corner gap: the upper rooms' ceiling rails stopped 0.5 short of every end as the
    # floor rails did before 11-05, open at each outside corner) the rail under the first storey's ceiling, through the same
    # solver: mitred where two meet, stopped in a post, square against a wall
    if "T1" in globals() and abs(zz - (T1 - 12)) < 0.6:
        b_ = (zz - (w - 1) / 2, zz + (w - 1) / 2)
        BASE_RUNS.append({"W": W, "u0": u0, "u1": u1, "deep": deep, "part": PART, "frame": FRAME, "band": b_,
                          "holes": sorted((min(h[0], h[1]), max(h[0], h[1])) for h in doors if h[2] <= b_[1] and h[3] >= b_[0])})
        return
    a_ = u0 + 0.5; u1 = u1 - 0.5   # (0.5 short of the corners: the ends lay in the next wall's posts' faces, 2026-10-27)
    for d0, d1 in sorted((min(h[0], h[1]) - 7, max(h[0], h[1]) + 7) for h in doors if h[2] - w / 2 <= zz <= h[3] + w / 2):
        if d0 > a_ + 1: wall_beam(W, (a_, zz), (min(d0, u1), zz), w=w, deep=deep)
        a_ = max(a_, d1)
    if u1 > a_ + 1: wall_beam(W, (a_, zz), (u1, zz), w=w, deep=deep)

NOCOLL_BANDS = set()   # bands drawn without collision (tavern_panelling's rails)
BAND_KEY = {}          # a band's material, if not timber (tavern_panelling's)
BASE_RUNS = []   # the upper floors' baseboards (wall_rail at the floor), each wall's run less its doorways
BASE_LOG = []    # what baseboards() made of each end, for the gate (baseboard_check.py) and the renders
def baseboards():
    """each band's runs on their own (the floor's baseboards; the ceiling rails since 2026-11-06), one solve each"""
    global BASE_RUNS
    all_ = BASE_RUNS
    for band_ in sorted({r_["band"] for r_ in all_}):
        BASE_RUNS = [r_ for r_ in all_ if r_["band"] == band_]
        if band_ in NOCOLL_BANDS: drawn_only(_boards, *band_)   # (the tavern's panelling: drawn, no collision, so no walkway narrows)
        else: _boards(*band_)
    BASE_RUNS = all_

def _boards(Z0, Z1):
    """The baseboards, drawn once every wall is built (the MGO walk of 2026-11-05: misaligned all over the hall). Until then each wall drew its own floor rail, 0.5 short of its ends and 7 short of
    every doorway: right where a post stood in the corner or by the door, a gap of bare plaster at every outside corner,
    a run stopping short of a doorway with no post, and a stub left where a doorway stood near a corner. Now, in plan:
    runs on one line that touch are one run; where two runs meet at a corner, inside or outside, both are mitred to it
    (their back lines meet at the walls' corner, their fronts at the boards' own corner); a run that ends against
    another wall's face stops square at that wall's board; an end at a doorway stops in its post if it has one, else at
    the opening's edge; any other end is closed square; a piece under 12 long that joins nothing is dropped. One section
    for all (its foot 0.5 into the floor, 23 over it); each wall keeps its depth (5 where the wall's posts are 8)."""
    if not BASE_RUNS: return
    global PART, FRAME
    from mathutils.bvhtree import BVHTree
    keep_ = (PART, FRAME)
    ZM_ = (Z0 + Z1) / 2          # (the floor's band: its foot 0.5 into the floor, ZG - 0.5..ZG + 23; lifted 1 over it, a line of plaster showed under it)
    # the floor's posts and wood (doorposts, wall posts) to stop a board in: inside test by ray parity against the part's wood
    solids_ = {}
    def solid(part_):
        if part_ not in solids_:
            vs_, ps_ = [], []
            for (pt_, k_), fs_ in GEO.items():
                if pt_ != part_ or k_ not in ("wood", "wood2", "trim"): continue
                for pts_, _ in fs_:
                    o_ = len(vs_); vs_ += [Vector(p_) for p_ in pts_]; ps_.append(list(range(o_, len(vs_))))
            solids_[part_] = BVHTree.FromPolygons(vs_, ps_, epsilon=0.0) if ps_ else None
        return solids_[part_]
    def inside(part_, p, out_):
        """p inside a timber: looking out into the room (out_), the first face met looks away (its front, from behind)"""
        t_ = solid(part_)
        if t_ is None: return False
        d_ = Vector((out_.x, out_.y, 0.0)).normalized()
        hit_ = t_.ray_cast(Vector(p), d_, 40)
        return hit_[0] is not None and hit_[1].dot(d_) > 0.5
    # the pieces: each run cut at its doorways, in plan (x, y): back line from A to B, front out along n, depth d
    segs = []
    for R_ in BASE_RUNS:
        o_, r_, n_ = R_["W"]
        P_ = lambda u_: Vector((o_.x + r_.x * u_, o_.y + r_.y * u_))
        out_ = []
        a_, ka_ = R_["u0"], "wall"
        for h0_, h1_ in R_["holes"]:
            if h1_ <= a_ or h0_ >= R_["u1"]: continue
            if h0_ > a_: out_.append((a_, ka_, min(h0_, R_["u1"]), ("door", h0_, -1)))
            a_, ka_ = max(a_, h1_), ("door", h1_, 1)
        if R_["u1"] > a_: out_.append((a_, ka_, R_["u1"], "wall"))
        for ua_, ka_, ub_, kb_ in out_:
            segs.append({"A": P_(ua_), "B": P_(ub_), "r": Vector((r_.x, r_.y)), "n": Vector((n_.x, n_.y)), "d": R_["deep"],
                         "ka": ka_, "kb": kb_, "part": R_["part"], "frame": R_["frame"], "W": R_["W"]})
    # one run on one line: same plane, same facing, ends touching (a wall built in two pieces)
    merged = True
    while merged:
        merged = False
        for i_, s_ in enumerate(segs):
            for j_, t_ in enumerate(segs):
                if i_ == j_ or s_["part"] != t_["part"] or s_["n"].dot(t_["n"]) < 0.999 or s_["r"].dot(t_["r"]) < 0.999: continue
                if abs((t_["A"] - s_["A"]).dot(s_["n"])) > 0.3 or s_["d"] != t_["d"]: continue
                if s_["kb"] == "wall" and t_["ka"] == "wall" and (t_["A"] - s_["B"]).length < 2.0:
                    s_["B"], s_["kb"] = t_["B"], t_["kb"]; del segs[j_]; merged = True; break
            if merged: break
    for s_ in segs:   # each end: the point, the direction out of the piece along its line
        s_["end"] = {"a": None, "b": None}
    def plane_hit(s_, which):
        """the other board whose wall's plane this end meets: (t, its end there or None, inside corner?)"""
        p_ = s_["A"] if which == "a" else s_["B"]
        out_ = -s_["r"] if which == "a" else s_["r"]
        best_ = None
        for t_ in segs:
            if t_ is s_ or t_["part"] != s_["part"] or abs(t_["n"].dot(s_["n"])) > 0.01: continue
            off_ = (p_ - t_["A"]).dot(t_["n"])                  # this end's distance off t's wall plane
            # (on it; or short of it, by up to t's depth, the board running on toward it: a wall's run that starts a post's
            # width from its corner, the tower door's notch, 2026-11-05)
            if abs(off_) > 2.5 and not (abs(off_) <= t_["d"] + 2.5 and (-t_["n"] * off_).dot(out_) > 0): continue
            along_ = (p_ - t_["A"]).dot(t_["r"]); L_ = (t_["B"] - t_["A"]).dot(t_["r"])
            if along_ < -t_["d"] - 2.5 or along_ > L_ + t_["d"] + 2.5: continue
            da_, db_ = abs(along_), abs(along_ - L_)          # (its nearer end: a short board has both within reach)
            te_ = ("a" if da_ <= db_ else "b") if min(da_, db_) < t_["d"] + 2.5 else None
            if te_ is not None and t_["k" + te_] != "wall": te_ = None
            X_ = p_ - t_["n"] * off_
            ms_, mt_ = (s_["A"] + s_["B"]) / 2, (t_["A"] + t_["B"]) / 2
            fs_, ft_ = (ms_ - X_).dot(t_["n"]), (mt_ - X_).dot(s_["n"])
            if te_ is not None and not ((fs_ > 0 and ft_ > 0) or (fs_ < 0 and ft_ < 0)): te_ = None   # (a corner: each in front of
            if te_ is None and fs_ <= 0: continue                     # the other's wall, or each behind; else the board on a thin
            rank_ = (0 if te_ is not None else 1, abs(off_))          # wall's far face, in the same plane, was taken for its partner)
            if best_ is None or rank_ < best_[0]: best_ = (rank_, t_, te_)
        return best_
    for s_ in segs:
        for which in ("a", "b"):
            k_ = s_["k" + which]
            if k_ != "wall": continue
            h_ = plane_hit(s_, which)
            if h_ is None: continue
            _, t_, te_ = h_
            p_ = s_["A"] if which == "a" else s_["B"]
            # the walls' corner: this back line meets t's
            X_ = p_ - t_["n"] * (p_ - t_["A"]).dot(t_["n"])
            if te_ is not None:
                s_["end"][which] = ("mitre", X_, X_ + s_["n"] * s_["d"] + t_["n"] * t_["d"])
            elif (((s_["A"] + s_["B"]) / 2) - X_).dot(t_["n"]) > 0:   # against t's face, in front of it: square at t's board
                s_["end"][which] = ("butt", X_ + t_["n"] * t_["d"])
    # a mitre stands only with its partner's: the other board mitred at the same corner (else that end is left to the
    # post or closed-end rules below)
    corners_ = {}
    for s_ in segs:
        for which in ("a", "b"):
            e_ = s_["end"][which]
            if e_ and e_[0] == "mitre": corners_.setdefault((round(e_[1].x, 1), round(e_[1].y, 1)), []).append((s_, which))
    for k_, v_ in corners_.items():
        if len(v_) != 2 or v_[0][0] is v_[1][0]:
            for s_, which in v_: s_["end"][which] = None
    drawn_ = 0
    for s_ in segs:
        PART, FRAME = s_["part"], s_["frame"]
        r_, n_, d_ = s_["r"], s_["n"], s_["d"]
        ends_ = {}
        for which, p_, sgn_ in (("a", s_["A"], -1), ("b", s_["B"], 1)):
            k_, e_ = s_["k" + which], s_["end"][which]
            if e_ and e_[0] == "mitre":
                ends_[which] = (e_[1], e_[2], "joined"); continue
            if e_ and e_[0] == "butt":
                q_ = e_[1]; u_ = (q_ - s_["A"]).dot(r_)
                bp_ = s_["A"] + r_ * u_
                ends_[which] = (bp_, bp_ + n_ * d_, "butt"); continue
            # a post at this end (a doorway's, or the wall's own in its corner or by an opening): the board ends in its
            # middle, hidden (posts stand deeper than boards). Looked for up to 24 back along the board from the end
            in_ = [k * 0.5 for k in range(0, 49) if inside(s_["part"], tuple(p_ + r_ * (-sgn_ * k * 0.5) + n_ * (d_ / 2)) + (ZM_,), n_)]
            if in_:
                run_ = [in_[0]]
                for v_ in in_[1:]:
                    if v_ - run_[-1] > 0.6: break
                    run_.append(v_)
                bp_ = p_ + r_ * (-sgn_ * (run_[0] + run_[-1]) / 2)
                ends_[which] = (bp_, bp_ + n_ * d_, "post"); continue
            if isinstance(k_, tuple):                         # at an opening's edge with no post: 0.3 over it (in its plane
                q_ = p_ + r_ * (sgn_ * 0.3)                   # a sill's or reveal's side would meet the board's end)
                ends_[which] = (q_, q_ + n_ * d_, "edge"); continue
            ends_[which] = (p_, p_ + n_ * d_, "free")         # any other end: closed square
        (a0_, a1_, ta_), (b0_, b1_, tb_) = ends_["a"], ends_["b"]
        L_ = max((b0_ - a0_).dot(r_), (b1_ - a1_).dot(r_))
        joined_ = "joined" in (ta_, tb_)
        mid_ = (a0_ + b0_) / 2
        BASE_LOG.append({"part": s_["part"], "a": [a0_.x, a0_.y], "b": [b0_.x, b0_.y], "n": [n_.x, n_.y], "d": d_, "ends": [ta_, tb_],
                         "len": round(L_, 1), "z": round(ZM_, 1), "dropped": L_ < 12 and not joined_})
        if L_ < 0.5 or (L_ < 12 and not joined_): continue
        V3 = lambda p_, z_: Vector((p_.x, p_.y, z_))
        plan_ = [a0_, b0_, b1_, a1_]                           # back a, back b, front b, front a
        top_ = [V3(p_, Z1) for p_ in plan_]; bot_ = [V3(p_, Z0) for p_ in plan_]
        r3_, n3_ = Vector((r_.x, r_.y, 0)), Vector((n_.x, n_.y, 0))
        uvl = lambda p_: (p_ - V3(s_["A"], 0)).dot(r3_) / S
        def put(q_, want_, uv_):
            """a face wound to look along want_ (every shape is one-sided in game)"""
            nn_ = Vector((0, 0, 0))
            for i_ in range(len(q_)): nn_ += q_[i_ - 1].cross(q_[i_])
            if nn_.dot(want_) < 0: q_ = q_[::-1]
            poly(BAND_KEY.get((Z0, Z1), "wood"), q_, [uv_(p_) for p_ in q_])
        put([bot_[3], bot_[2], top_[2], top_[3]], n3_, lambda p_: (uvl(p_), (p_.z - (Z0 + Z1) / 2) / S))   # (as a beam's: across from its middle)                          # the front
        dn_ = lambda p_: (uvl(p_), (p_ - V3(s_["A"], 0)).dot(n3_) / S)
        put([top_[0], top_[3], top_[2], top_[1]], UP, dn_)                                                      # the top
        for t_, i0_, i1_ in ((ta_, 0, 1), (tb_, 1, 0)):   # (an end 0.3 over an opening showed its open back from the far side: the leak
            if t_ != "edge": continue                       # check, 2026-11-06) its back there, its last 0.5, in the wall's plane facing in
            e0_ = bot_[i0_]; e1_ = e0_ + (bot_[i1_] - bot_[i0_]).normalized() * 0.5
            put([e0_, e1_, Vector((e1_.x, e1_.y, Z1)), Vector((e0_.x, e0_.y, Z1))], -n3_, lambda p_: (uvl(p_), (p_.z - (Z0 + Z1) / 2) / S))
        put([bot_[0], bot_[1], bot_[2], bot_[3]], -UP, dn_)                                                     # underneath (a rail over the
        # tavern's open middle has air under it: from that floor one saw into it, 2026-11-06; elsewhere it lies 0.5 under the floor)
        for t_, i0_, i1_, out_ in ((ta_, 0, 3, -r3_), (tb_, 1, 2, r3_)):                                       # the ends
            if t_ == "joined": continue
            q_ = [bot_[i0_], bot_[i1_], top_[i1_], top_[i0_]]
            e3_ = (q_[1] - q_[0]); e3_ = UP.cross(e3_).normalized()                                             # its own
            put(q_, e3_ if e3_.dot(out_) > 0 else -e3_, lambda p_: (Vector((p_.x - q_[0].x, p_.y - q_[0].y)).length / S, p_.z / S))
        drawn_ += 1
    PART, FRAME = keep_
    from collections import Counter as _C
    print("BASEBOARDS", drawn_, "pieces of", len(segs), "ends", dict(_C(e_ for b_ in BASE_LOG for e_ in b_["ends"])),
          "dropped", sum(1 for b_ in BASE_LOG if b_["dropped"]))
CLAYCOL.update({"candle": (1.0, 0.86, 0.62), "cork": (0.46, 0.33, 0.21), "paper": (0.88, 0.84, 0.72), "iron": (0.12, 0.12, 0.12)})
INT_LIGHTS = []                                                    # (x, y, z, watts, (r, g, b)) for the render
ARCHES = []                                                        # (a surround's outer edge, its opening's edge), 3 proud, for frame_check.py
PLAN = []                                                          # what is built, as the floor plans draw it
NEW_LIGHTS = []         # (2026-10-26, the working rooms) their lamps, after every lamp the last build had (Hall2.cs keeps
MARKERS = []            # named, persistent markers for the NPC session (COORDINATION.md): (name, record, hall pos, yaw)
NEW_PLACE = []          # those records); their vanilla pieces, each naming its record ("ed"), after every piece it had

def drawn_only(fn, *a, **k):
    """draw with fn, its faces kept out of the collision (theirs is built apart: the tower stair's treads and risers)"""
    before = {gk: len(v) for gk, v in GEO.items()}
    r_ = fn(*a, **k)
    for gk, v in GEO.items():
        NOCOLL_IDS.update((gk[0], gk[1], i_) for i_ in range(before.get(gk, 0), len(v)))
    return r_

def coll_only(q):
    """a collision quad that is not drawn"""
    q = [tuple(p) for p in q]
    COLL_ONLY.setdefault(PART, []).extend([[q[0], q[1], q[2]], [q[0], q[2], q[3]]])
    COLL_ONLY_KEY.setdefault(PART, []).extend(["stairs:" + str(LAST_KEY[0])] * 2)   # every caller lays a stair's walking ramp under its drawn tread

# the carved brackets under the galleries (the great hall's and the tavern's): their size (the hall2t walk, 2026-10-26: shrunk,
# all of them including the tavern's, as they read too large); AG_BRACKET for the renders of sizes
BR = dict(reach=1.0, drop=0.7, thick=20, t=16)            # (B of the three rendered)
BR.update(json.loads(os.environ.get("AG_BRACKET", "{}")))
DOOR_W, DOOR_H = 96, 176   # vanilla's Solitude interior door (SSingleDoorInt01L), and its doorway (SMdBDorInt01): the opening
                           # the leaf's own size, 96 x 176, the leaf shut flush to the posts and the head (the MGO walk, 2026-11-04:
                           # a small gap in the closed door on the hinge side: ours were 98 x 178, the leaf hung 1 in, a slit each side)
INT_CS = 70                # the wings' casements' sill over the first floor, inside (outside: guildhall_gen's CS)
DOOR_HW, DOOR_TOP = 182 * DSC / 2 + 0.5, 175 * DSC + 0.5   # the front doors' half width and top, inside, with 0.5 to spare
FAN_IN = os.environ.get("AG_FANLIGHT_IN", "1") == "1"     # (2026-11-14) the door's fanlight from inside; FAN_DZ: inside only, under the
FAN_DZ = -11.0                                            # joists' ledge (the chosen one of the rendered options)
def door_leaf(a, b, z, swing, name=None, right=False, **extra):
    """vanilla's SSingleDoorInt01L in the doorway from a to b (2D points on the wall's middle line, DOOR_W apart). Its leaf
    lies along its local +x from the hinge at its origin, 8 thick over local y 0..8, and opens a quarter turn toward local
    -y (its Open animation); so it is hinged at whichever end makes it open toward `swing` (2D unit), at that
    jamb, its leaf centred in the wall. right: its mirror, SSingleDoorInt01R, whose leaf opens toward local +y: the same swing
    hinged on the other jamb. extra: the piece's other keys (lock, lock_key, owner)"""
    sx_, sy_ = swing; ax_, ay_ = (sy_, -sx_) if right else (-sy_, sx_)   # along the leaf, hinge to free edge
    dx_, dy_ = b[0] - a[0], b[1] - a[1]
    hx_, hy_ = a if dx_ * ax_ + dy_ * ay_ > 0 else b
    hx_, hy_ = hx_ + sx_ * 4, hy_ + sy_ * 4
    yaw_ = math.degrees(math.atan2(-ay_, ax_)) % 360                 # (placed yaws turn clockwise)
    hand_ = "R" if right else "L"
    NEW_PLACE.append((f"meshes/architecture/solitude/doors/ssingledoorint01{hand_.lower()}.nif", (hx_, hy_, z), yaw_, 1.0,
                      dict(ed="SSingleDoorInt01" + hand_, **({"name": name} if name else {}), **extra)))
    PLAN.append({"t": "door", "level": 0 if z < ZG - 50 else (1 if z < 600 else 2), "a": list(a), "b": list(b), "real": True})

import random, json, os
# loose seats stand a little off square, as people leave them (a chair in each dormer looked fake, perfectly
# aligned): each one turned and shifted by a small amount drawn from its own place (the same every
# build), at most (shift, turn); exact=True places one as given
LOOSE = {"UpperChair01F": (3, 7), "UpperChair01LR": (3, 7), "NobleChair01": (3, 6), "NobleChair02L": (2, 4), "NobleChair02R": (2, 4), "WoodenBarStool": (4, 15),
         # (the clutter rules: things that should be aligned, such as tables and chairs, are a degree or two off in
         # real rooms: the dormitories' beds, chests and nightstands were in rows at one turn)
         "UpperBedSingle01": (1.5, 1.5), "AGHall2Chest": (2, 2), "UpperNightstand01": (2, 3)}

# a quill stands in its inkwell as vanilla stands one (2026-10-29: a quill floated; HallSpike
# `pairs` over Skyrim.esm: of 78 quills by an inkwell 72 lie flat beside it, the 6 standing are 19.7..20.6 over the well's
# foot, untilted, held by "don't havok settle". At +15 its nib (15.9 under its middle) was 0.9 into the desk, and the game
# pushed it out: it fell against the wall)
QUILL_Z = 19.7
# (a quill lying beside the ink) as vanilla's 72: tilted 90 about its x (its 31.7 along its own z
# then lies along its local y, its vane 5.5 tall on edge), its middle 2.77 + 0.15 over the desk, 15..25 from the well
QUILL_LIE_Z = 2.77 + 0.15
SQUARE_JIT = {"PaperRoll", "Inkwell01", "SilverCandleStick01", "SilverCandleStick02", "SilverCandleStick03", "CandleHornTable01",
              "CandleLanternwithCandle01", "CoinPurseSmall", "CoinPurseMedium", "CoinPurseLarge", "Book3ValuableAmongstTheDraugr"}

# (2026-11-12, after the tavern's corner chair stood its sitter up into the wall) chairs and beds whose
# record lets the engine use a side that is blocked take vanilla's one-sided record of the same piece (same mesh): L enters from
# local -x, R from +x (the meshes' markers; vanilla's double bed's two). furniture_check's UNUSABLE ... blocked: lists them.
# (record, hall x, y as the code places it) -> the record that leaves out the blocked side
SIDE_FIX = {("UpperChair01LR", -925, 835): "UpperChair01R",                     # the tavern's corner table, by the wall
            ("UpperChair01LR", 450, 480): "UpperChair01R", ("UpperChair01LR", 520, 550): "UpperChair01L",   # the attic's table
            ("UpperChair01F", 565, 260): "UpperChair01LR",                     # the attic's dormer seat: its front is the dormer's wall
            ("NobleBedSingle01", -1334.5, 790): "NobleBedSingle01R",           # the guild master's
            ("UpperBedSingle01", 520, 219): "UpperBedSingle01L",               # room 4's, under its window
            ("UpperBedSingle01", 1142, 345): "UpperBedSingle01R", ("UpperBedSingle01", 994, 345): "UpperBedSingle01L",   # the attic's bunks,
            ("UpperBedSingle01", 780, 719): "UpperBedSingle01R", ("UpperBedSingle01", 903, 719): "UpperBedSingle01L",   # each to its open side
            ("UpperBedSingle01", 1210, 719): "UpperBedSingle01L", ("UpperBedSingle01", 1397, 719): "UpperBedSingle01R"}
def side_fix(ed, pos):
    return next((v_ for (e_, x_, y_), v_ in SIDE_FIX.items() if e_ == ed and abs(pos[0] - x_) < 2 and abs(pos[1] - y_) < 2), ed)
def piece(rel, ed, pos, yaw, scale=1.0, **extra):
    """a vanilla piece by its record's name (Hall2.cs places them after every record the last build had)"""
    fixed_ = side_fix(ed, pos)                                  # (its place and turn drawn as the record it replaces: nothing moves)
    if ed in LOOSE and not extra.pop("exact", False):
        r_ = random.Random(f"{ed} {pos[0]:.1f} {pos[1]:.1f} {pos[2]:.1f}"); d_, a_ = LOOSE[ed]
        lat_, fwd_ = r_.uniform(-d_, d_), r_.uniform(0, d_)   # (sideways, or toward what it faces: never back into a way)
        t_ = math.radians(yaw)
        pos = (pos[0] + lat_ * math.cos(t_) + fwd_ * math.sin(t_), pos[1] - lat_ * math.sin(t_) + fwd_ * math.cos(t_), pos[2])
        yaw += r_.uniform(-a_, a_)
    # (2026-10-28, the clutter audit: small loose things placed here directly, not by sit(), were left exactly square: one set
    # down by hand is turned a little, from its place, the same every build; a stack's own turns, off square, are kept)
    if ed in SQUARE_JIT and min(yaw % 90, 90 - yaw % 90) < 0.01 and not extra.pop("square", False):
        r_ = random.Random(f"piece {ed} {pos[0]:.1f} {pos[1]:.1f} {pos[2]:.1f}"); yaw += r_.choice((-1, 1)) * r_.uniform(3, 12)
    extra.pop("square", None)
    NEW_PLACE.append((rel, tuple(pos), yaw % 360, scale, dict(ed=fixed_, **extra)))

_CB = None
def sit(m, ed, x, y, zs, yaw=0, scale=1.0, **kw):
    """a small thing set on a surface at height zs: lifted by its own mesh's measured base (clutter_bounds.json, from the
    NIF: some sit on their origin, some straddle it), so it neither floats nor sinks; the guild's, kept put (the clutter
    pass, 2026-10-27: clutter fitting each area and room)"""
    global _CB
    if _CB is None:
        _CB = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "clutter_bounds.json")))
    lo_ = 0.0
    if m in _CB:                                                # (laid over by rx, as the render tilts it: z' = -y sin + z cos)
        b_ = _CB[m]; r_ = math.radians(kw.get("rx", 0))
        lo_ = min(-yy * math.sin(r_) + zz * math.cos(r_) for yy in (b_["lo"][1], b_["hi"][1]) for zz in (b_["lo"][2], b_["hi"][2]))
    kw.setdefault("owner", "guild"); kw.setdefault("settled", True)
    # (the clutter rules: random variation is required: the clutter audit found 107 loose pieces turned
    # exactly square to the cell; one set down by hand is never square: a turn of 3..12 either way, from its place, the same
    # every build; a turn already off square was given on purpose and is kept)
    if min(yaw % 90, 90 - yaw % 90) < 0.01 and not kw.pop("square", False):
        r_ = random.Random(f"sit {ed} {x:.1f} {y:.1f} {zs:.1f}"); yaw += r_.choice((-1, 1)) * r_.uniform(3, 12)
    kw.pop("square", None)
    piece(m, ed, (x, y, zs - lo_ * scale + 0.15), yaw, scale, exact=True, **kw)

def foot_(m):
    """a small thing's footprint radius on a board, from its measured bounds"""
    global _CB
    if _CB is None:
        _CB = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "clutter_bounds.json")))
    b_ = _CB.get(m)
    if b_ is None: return 6.0
    return max(abs(b_["lo"][0]), b_["hi"][0], abs(b_["lo"][1]), b_["hi"][1])

LIE_OK = ("wine/", "ingredients/mead01", "glazedgoblet01", "basictankard01")   # what vanilla leaves knocked over now and then
def strew(a, b, z, groups, seed, depth=0.0, lie=0.12, **kw):
    """small things left on a board as people leave them (the pantry's and the bar's shelves were in neat rows, which
    no real shelf is: uneven and natural instead; and sparse, as vanilla stocks them: the Bannered Mare's under-bar shelves hold one book, its counter's
    food sits in a few clumps with long bare runs). a, b: the board's usable line (hall 2D, at its middle depth); z its top;
    groups: (mesh, record, how many) kept together, each a clump in its own place; depth: how far off the line a thing may
    stand (half the board's usable depth); lie: the chance a bottle or cup lies on its side. What the few things leave
    of the run is bare, in uneven stretches. Turns, gaps and places drawn from the seed: the same every build"""
    global _CB
    if _CB is None:
        _CB = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "clutter_bounds.json")))
    rnd = random.Random(seed)
    L = math.hypot(b[0] - a[0], b[1] - a[1]); ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
    clumps = []
    for m_, e_, n_ in groups:
        r_ = foot_(m_); b_ = _CB.get(m_)
        half_ = (b_["hi"][2] - b_["lo"][2]) / 2 if b_ else r_      # (laid over, it lies along the board: its half-length)
        lies_ = [any(k in m_ for k in LIE_OK) and r_ < 9 and rnd.random() < lie for _ in range(n_)]
        ext_ = [half_ + 1 if l_ else r_ for l_ in lies_]
        steps_ = [(ext_[j] + ext_[j + 1]) * rnd.uniform(1.04, 1.4) for j in range(n_ - 1)]
        clumps.append((m_, e_, n_, ext_[0], steps_, ext_[0] + ext_[-1] + sum(steps_), lies_))
    rnd.shuffle(clumps)
    used_ = sum(c_[5] for c_ in clumps)
    spare_ = max(0.0, L - used_)
    w_ = [rnd.random() ** 1.6 for _ in range(len(clumps) + 1)]           # (uneven: one long bare run, short ones elsewhere)
    gaps_ = [spare_ * x_ / sum(w_) for x_ in w_]
    t_ = gaps_[0]
    for k_, (m_, e_, n_, r_, steps_, len_, lies_) in enumerate(clumps):
        u_ = t_ + r_
        for j_ in range(n_):
            if j_: u_ += steps_[j_ - 1]
            off_ = rnd.uniform(-depth, depth) if depth else 0.0
            x_, y_ = a[0] + ux * u_ - uy * off_, a[1] + uy * u_ + ux * off_
            if lies_[j_]:                                             # (laid over, along the board, its neck either way)
                yaw_ = (math.degrees(math.atan2(ux, uy)) + rnd.choice((0, 180)) + rnd.uniform(-12, 12)) % 360
                sit(m_, e_, x_, y_, z, yaw_, rx=90, **kw)
            else:
                sit(m_, e_, x_, y_, z, rnd.uniform(0, 360), **kw)
        t_ += len_ + gaps_[k_ + 1]

def pile(m, ed, x, y, z, n, seed, step=None, spin=25, drift=0.8, **kw):
    """a stack of plates, bowls or cheeses as it is left: each a little off the one under it and turned"""
    rnd = random.Random(seed)
    foot_(m); b_ = _CB[m]
    h_ = max(step or 0.0, (b_["hi"][2] - b_["lo"][2]) * 1.02)
    for k_ in range(n):
        sit(m, ed, x + rnd.uniform(-drift, drift), y + rnd.uniform(-drift, drift), z + h_ * k_, rnd.uniform(-spin, spin) + k_ * rnd.uniform(0, 40), **kw)

LIB_BOOKS = {"Book01": "basicbook01", "Book03": "basicbook03", "Book03a": "basicbook03a", "Book04": "basicbook04", "Book04a": "basicbook04a",
             "Book05": "basicbook05", "Book05a": "basicbook05a", "Book06": "basicbook06", "BookLarge": "book02lowpoly02", "BookLarge2": "book02lowpoly"}
def shelf_books(a, b, z, yaw, seed, room=40, fill=0.8, real=(), only_real=False, bake="library"):
    """a shelf's board filled as a library's are (the clutter pass, 2026-10-27: the Arcanaeum's cases, Proudspire's study):
    runs of books stood spine out, a gap now and then, a short stack laid flat, a large volume where the board's height
    allows. a, b: the board's ends in the hall (x, y), at the books' depth; z its top; yaw the books' turn (0: spines to -x,
    the row along y; 90: to +y, the row along x; 270: to -y); room the height over the board. The shelves' books are the
    guild's own statics (AGHall2Book*: not to be taken); real: readable vanilla books (ed, mesh) set first, in order;
    only_real: nothing after them (a shelf of readable books only, so none of its books is a dummy); bake: the static the
    guild's books are merged into (their own references only for the render and the checks)"""
    rnd = random.Random(seed)
    L = math.hypot(b[0] - a[0], b[1] - a[1]); ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
    fx, fy = -math.cos(math.radians(yaw)) * 2.8, math.sin(math.radians(yaw)) * 2.8   # (the large volumes, 24 deep to the
                                                                                       # others' 19, stood out to the front)
    small = [k for k in LIB_BOOKS if not k.startswith("BookLarge")]
    t = 1.0; real = list(real)
    if only_real:                                               # (centred on its board)
        t = max(1.0, (L - sum((6.8 if "lowpoly" in m_ else 4.2) + 0.3 for _, m_ in real)) / 2)
    while t < L - 3:
        if real:                                                # (a real book: stood like the rest)
            ed_, m_ = real.pop(0); th_ = 6.8 if "lowpoly" in m_ else 4.2
            if t + th_ > L: break
            c_ = t + th_ / 2
            big_ = "lowpoly" in m_
            piece(f"meshes/clutter/books/{m_}.nif", ed_, (a[0] + ux * c_ + (fx if big_ else 0), a[1] + uy * c_ + (fy if big_ else 0), z + (15.3 if big_ else 11.8)),
                  yaw + rnd.uniform(-2, 2), rx=90, exact=True, owner="guild", settled=True)
            t += th_ + 0.3
            continue
        if only_real: break
        r_ = rnd.random()
        if r_ > fill + 0.1 and t > 6:                           # a gap
            t += rnd.uniform(6, 16)
        elif r_ > fill and t + 25 < L:                         # a short stack laid flat
            c_ = t + 12.5
            for k_ in range(rnd.randint(2, 4)):
                bk_ = rnd.choice(small)
                piece(f"meshes/clutter/books/{LIB_BOOKS[bk_]}.nif", "AGHall2" + bk_, (a[0] + ux * c_, a[1] + uy * c_, z + 2.15 + 4.15 * k_),
                      yaw + rnd.uniform(-6, 6), exact=True, bake=bake)
            t += 26
        else:                                                   # a run stood up
            for k_ in range(rnd.randint(4, 12)):
                big_ = room > 34 and rnd.random() < 0.15
                bk_ = rnd.choice(("BookLarge", "BookLarge2")) if big_ else rnd.choice(small)
                th_ = 6.8 if big_ else 4.2
                if t + th_ > L - 1: break
                c_ = t + th_ / 2
                piece(f"meshes/clutter/books/{LIB_BOOKS[bk_]}.nif", "AGHall2" + bk_,
                      (a[0] + ux * c_ + (fx if big_ else 0), a[1] + uy * c_ + (fy if big_ else 0), z + (15.3 if big_ else 11.8)),
                      yaw + rnd.uniform(-2.5, 2.5), rx=90, exact=True, bake=bake)
                t += th_ + 0.3

def niche_dress(T_):
    """the back bar's niche (reworked 2026-10-27: furniture, shelves, everything), from vanilla's back bars
    (research/backbar; of a tap counter, a bottle shelf and a cask store, the tap counter). Its chamber x -340..-228 (back), y 768..960, seen through
    the arch y 772..886 (crown 240); vanilla pieces 4 off its stone; all of it faces the barkeep's lane (-x)"""
    XB = -228                                                       # its back wall
    WINE = (("wine/winebottle02b", "FoodWineBottle02"), ("wine/winebottle01b", "FoodWineAlto"))
    MEAD = (("ingredients/mead01", "FoodMead"),)
    def herbs(x, ys):                                               # bundles hung from its ceiling (240), tops at 236
        for k_, y_ in enumerate(ys):
            m_, e_ = (("plants/hanginggarlicbraid01", "HangingGarlicBraid"), ("plants/hangingfrostmirriam01", "HangingFrostMirriam"),
                      ("plants/hangingelvesear01", "HangingElvesEar01"))[k_ % 3]
            top_ = (0.18, 8.45, 15.1)[k_ % 3]
            piece("meshes/" + m_ + ".nif", e_, (x, y_, 236 - top_), (k_ * 67) % 360, exact=True)
    # the tap: the bar's kit as a back counter (its shelves to
    # the lane), three kegs on it, a wall shelf over, herbs. One module and both ends, as the bar itself is closed (the
    # counter base's sides were missing): the ends 33 past the module (y 772..902, the far one
    # behind the jamb); each placed on the module, as the bar's are
    for m_, e_ in (("barstraight01", "BarStraight01"), ("barright01", "BarRight01"), ("barleft01", "BarLeft01")):
        piece(f"meshes/clutter/barset/{m_}.nif", e_, (XB - 4 - 33, 837, 0), 180)   # (BarRight01 the -y end at 180)
    # (the module's shelves, 55 and 16: two tankards above, a wine and a mead below, strewn, not set out in a row)
    strew((XB - 4 - 32 - 12, 804), (XB - 4 - 32 - 12, 870), 55, ((T_ + "dining set/basictankard01.nif", "BasicTankard01", 2),), "niche 55", depth=3)
    strew((XB - 4 - 32 - 6, 804), (XB - 4 - 32 - 6, 870), 16, ((T_ + WINE[0][0] + ".nif", WINE[0][1], 1), (T_ + MEAD[0][0] + ".nif", MEAD[0][1], 1)),
          "niche 16", depth=4, lie=0.3)
    rk_ = random.Random("tavern kegs")                         # (their spouts, local -y, to the lane; not in a perfect row:
    # (the walk of 2026-11-01: too offset, minor clipping, an unconvincing turn: 40 wide on the bar's 130, so 44 apart, and what a hand leaves when it sets them square)
    for y_ in (793, 837, 881):                                  # the clutter audit, 2026-10-28)
        piece("meshes/clutter/meadery/meadbarrel01.nif", "MeadBarrel01", (XB - 4 - 30 + rk_.uniform(-1.5, 1.5), y_ + rk_.uniform(-0.8, 0.8), 78),
              90 + rk_.uniform(-3, 3), exact=True)
    piece("meshes/architecture/whiterun/wrinteriors/wrwallshelf01.nif", "WRWallShelf01", (XB - 4 - 19.7 * 0.9, 837, 150), 270, 0.9)   # (its brackets
                                                                                       # to the wall: it stood backwards, 2026-10-27)
    strew((XB - 4 - 17, 776), (XB - 4 - 17, 888), 150 + 16.23 * 0.9,     # (the shelf at 0.9: 135 wide, the niche 138)
          ((T_ + "dining set/basictankard01.nif", "BasicTankard01", 2), (T_ + WINE[1][0] + ".nif", WINE[1][1], 1), (T_ + MEAD[0][0] + ".nif", MEAD[0][1], 1)),
          "niche wall shelf", depth=3)
    # (2026-10-29, the rule from the kitchen's: herbs hung high out of anyone's reach go to a wall-mounted
    # shelf within reach, or are removed: these hung from the niche's ceiling (236); under its shelf they would hang into the
    # kegs, so they are gone. herbs() is kept for a reachable place)
    # a broom stood in the niche's corner against the pier's stone side (its face x -340, from y 886 to the back wall at 906),
    # out of the lane: leaning 3 toward the stone, its head against it and its handle's top 2 off it. Placed by its Havok hull
    # (one convex body, a loose item): the hull and its 2.0 skin 0.5 short of the stone and of the back wall: in the corner, so
    # nothing pushes it on load
    sit("meshes/clutter/common/broom.nif", "Broom01", -332.1, 897.6, 0, 270 + random.Random("tavern broom").uniform(-3, 3), rx=3)
    # the first company's tankards: a second shelf high in the niche (its board 214.6, 25 under the chamber's ceiling), a few
    # left up there and never taken down, set as hands leave things (a row of eight, set straight, read as staged)
    piece("meshes/architecture/whiterun/wrinteriors/wrwallshelf01.nif", "WRWallShelf01", (XB - 4 - 19.7 * 0.9, 837, 200), 270, 0.9)
    strew((XB - 4 - 17, 776), (XB - 4 - 17, 888), 200 + 16.23 * 0.9,
          ((T_ + "dining set/basictankard01.nif", "BasicTankard01", 2), (T_ + "dining set/basictankard01.nif", "BasicTankard01", 1)),
          "first company", depth=5, lie=0)

def poly_n(key, pts, nrm):
    """poly(), wound to face nrm"""
    pts = [Vector(p) for p in pts]; n = Vector((0, 0, 0))
    for i in range(len(pts)):
        a_, b_ = pts[i - 1], pts[i]
        n += Vector(((a_.y - b_.y) * (a_.z + b_.z), (a_.z - b_.z) * (a_.x + b_.x), (a_.x - b_.x) * (a_.y + b_.y)))
    poly(key, pts if n.dot(Vector(nrm)) > 0 else pts[::-1])


def frame_timbers(W, u0, u1, z0, z1, key="wood"):
    """a doorway's lintel and posts on a wall face whose other face draws its reveals (opening_frame)"""
    door_head(W, u0, u1, z0, z1, key)

def partition(x0, y0, x1, y1, z0, z1, holes=(), key="stucco", rails=(), arches=(), ends=(False, False), timbers=True, level=None):
    """an interior wall, the box (x0, y0)..(x1, y1) from z0 to z1, along x or y: both faces less its openings (holes:
    (s0, s1, hz0, hz1) in the wall's own x or y), each opening's reveals from the first face and its timbers on both (none
    for arches: (s0, s1, crown) among the holes, round-headed with their spandrels), rails at `rails` on both faces,
    and its end faces where it stops free (ends: at its low and high end)"""
    alx = (x1 - x0) >= (y1 - y0)
    if alx:
        Ws = [((Vector((x0, y0, 0)), Vector((1, 0, 0)), Vector((0, -1, 0))), lambda s_: s_ - x0),
              ((Vector((x1, y1, 0)), Vector((-1, 0, 0)), Vector((0, 1, 0))), lambda s_: x1 - s_)]
        L_, th_ = x1 - x0, y1 - y0
    else:
        Ws = [((Vector((x0, y1, 0)), Vector((0, -1, 0)), Vector((-1, 0, 0))), lambda s_: y1 - s_),
              ((Vector((x1, y0, 0)), Vector((0, 1, 0)), Vector((1, 0, 0))), lambda s_: s_ - y0)]
        L_, th_ = y1 - y0, x1 - x0
    arch_set = {(a_, b_) for a_, b_, c_ in arches}
    allh = list(holes) + [(a_, b_, z0, c_) for a_, b_, c_ in arches]
    for k_, (W, U) in enumerate(Ws):
        hs = [tuple(sorted((U(h[0]), U(h[1])))) + (h[2], h[3]) for h in allh]
        face(key, W, 0, L_, z0, z1, hs)
        for zz in rails: wall_rail(W, 0, L_, zz, hs, w=22)
        for h, hu in zip(allh, hs):
            # (the spandrels in the face's own finish: a full-height "stone" wall is plaster over a slate base (face()), and they
            # stood in bare stone, two dark corners over the clerks' arch: the walk of 2026-11-03)
            if (h[0], h[1]) in arch_set: arch_head(W, hu[0], hu[1], h[3], th_ if k_ == 0 else 0, key="stucco" if HEARTH and key == "stone" and z0 < 30 and z1 >= 300 else key)
            elif k_ == 0: opening_frame(W, hu[0], hu[1], h[2], h[3], th_, timbers=timbers)
            elif timbers: frame_timbers(W, hu[0], hu[1], h[2], h[3])
    for e_, at_ in zip(ends, (0, 1)):
        if not e_: continue
        if alx:
            xe = x0 if at_ == 0 else x1; nx = -1 if at_ == 0 else 1
            W = (Vector((xe, y1 if nx < 0 else y0, 0)), Vector((0, -1 if nx < 0 else 1, 0)), Vector((nx, 0, 0)))
        else:
            ye = y0 if at_ == 0 else y1; ny = -1 if at_ == 0 else 1
            W = (Vector((x0 if ny < 0 else x1, ye, 0)), Vector((1 if ny < 0 else -1, 0, 0)), Vector((0, ny, 0)))
        face(key, W, 0, th_, z0, z1)
    PLAN.append({"t": "wall", "level": level if level is not None else (0 if z0 < ZG - 50 else 1), "a": [x0, y0], "b": [x1, y1],
                 "gaps": [[h[0], h[1]] for h in allh], "th": th_})

TOWER_TOP = TT                                   # the exterior's tower top (1400), before TT is reused just below
TS, TT = 40, 24                                  # wall thickness: the stone storey, the timber storeys
BRF = 1078                                       # the services' backroom's partition's backroom face (24 thick from the hall's face at 1054 since the trim walk of 2026-11-07: it was 40, the outer walls', and read too thick)
XG, YF, YB = PX1 - TS, PY0 + TS, PY1 - TS        # the pavilion's ground storey, inside: |x| 340, y 40..1060
FRONT_WIN_X = (DOOR_HW + 21 + XG) / 2                   # the great hall's front windows' axes inside: midway, frame to wall
XU, YFU, YBU = PX1 + J - TT, PY0 - J + TT, PY1 - TT   # its jettied storeys above, inside: |x| 392, y -12..1076
ZG = S1 + 18                                     # the first floor: gallery and office (418)
TP = math.tan(math.radians(54))                  # the pavilion roof's pitch
ZR = lambda x_: ridge - abs(x_) * TP - 18        # the roof's underside inside, over x
ZWP = ZR(XU)                                     # where it meets the side walls (927)
GB0 = 856                                        # the back gallery's front edge
JX = TX0 if TOWER3 else (XU - 36 if TOWER2 else XU)   # U: along the tower the jettied wall moves 36 into the gallery's
                                                 # corner; V: the tower's own wall is the hall's there, flush with the void
STAIR_W = 140
SW0, SW1 = PX1 + 180, PX1 + 180 + STAIR_W        # C: the stair in the right wing, 180 in from the hall's wall

def room_walls(x0, y0, x1, y1):
    """the four walls of a room, each (origin, right, normal into the room) and its length"""
    return {"front": ((Vector((x1, y0, 0)), Vector((-1, 0, 0)), Vector((0, 1, 0))), x1 - x0),
            "back": ((Vector((x0, y1, 0)), Vector((1, 0, 0)), Vector((0, -1, 0))), x1 - x0),
            "left": ((Vector((x0, y0, 0)), Vector((0, 1, 0)), Vector((1, 0, 0))), y1 - y0),
            "right": ((Vector((x1, y1, 0)), Vector((0, -1, 0)), Vector((-1, 0, 0))), y1 - y0)}

PLASTER_BASE = 44          # (W, 2026-10-26: palette C) the stone storey's walls plastered over a slate base
def face(key, W, u0, u1, z0, z1, holes=()):
    """a wall face from u0 to u1, z0 to z1, less rectangular holes (u0, u1, z0, z1): rows between every hole edge. W: a
    stone storey's wall (from the floor, 300 or more tall) is plaster over a slate base inside, but for the tower's own
    stone walls round its stair; the arches' heads, the hearths, the niche and the piers' dressed blocks stay stone"""
    bare_ = key.endswith("!"); key = key.rstrip("!")                  # (a wall that stays bare stone: the fireplaces' breasts, 2026-11-03)
    if HEARTH and key == "stone" and z0 < 30 and z1 >= 300 and not bare_:
        c_ = W[0] + W[1] * ((u0 + u1) / 2)
        if not (TOWER3 and 254 <= c_.x <= 682 and 770 <= c_.y <= 1122):
            # (plaster to the floor since the MGO walk of 2026-11-04: the wood bottom band on the plastered walls looked poor
            # and caused problems: the band ran from the wall's foot, half buried beside a raised floor)
            face("stucco", W, u0, u1, z0, z1, holes); return
    o, r, n = W
    zs = sorted({z0, z1} | {h[k_] for h in holes for k_ in (2, 3) if z0 < h[k_] < z1})
    for za, zb in zip(zs, zs[1:]):
        runs = [(u0, u1)]
        for ha, hb, hz0, hz1 in holes:
            if hz0 <= za and hz1 >= zb:
                runs = [q for a_, b_ in runs for q in ((a_, min(b_, ha)), (max(a_, hb), b_)) if q[1] - q[0] > 0.5]
        for a_, b_ in runs:
            poly(key, [o + r * a_ + UP * za, o + r * b_ + UP * za, o + r * b_ + UP * zb, o + r * a_ + UP * zb])

def shut_door(W, u0, u1, z0, z1, kind="archdoor"):
    """a door that stays shut: its picture 1 proud of the wall face, no hole (the wall behind it collides; in the first walk
    such doors were holes into the void), with an opening's lintel and posts round it"""
    quad_on(W, u0, z0, u1, z1, 1.0, *ATLAS[kind], kind=kind)
    door_head(W, u0, u1, z0, z1)

def opening_frame(W, u0, u1, z0, z1, depth, key="wood", timbers=True, rev="stucco", both=False, near=True):
    """a doorway through a wall `depth` thick: its reveals, a lintel and two posts on the room side (timbers=False: the
    reveals only, where the wall's own posts already frame it)"""
    o, r, n = W
    for ua in (u0, u1):                                           # the jambs, facing into the opening (until 2026-10-25
        p = [o + r * ua + UP * z0, o + r * ua + UP * z0 - n * depth, o + r * ua + UP * z1 - n * depth, o + r * ua + UP * z1]
        poly(rev, p if ua == u0 else p[::-1])                     # they faced into the wall: one-sided, one saw through them)
    p = [o + r * u0 + UP * z1, o + r * u0 + UP * z1 - n * depth, o + r * u1 + UP * z1 - n * depth, o + r * u1 + UP * z1]
    poly(rev, p)                                                  # its head, facing down (rev: stone through a stone wall, the tower's)
    if not timbers: return
    if near: door_head(W, u0, u1, z0, z1, key)                      # (near=False: the far face's alone, 2026-11-07)
    # (the test walk of 2026-11-06: many doorways were framed on one side only; a doorway's casing
    # stands on both faces of its wall) both: its lintel and posts on the far face too, where no partition draws them
    if both: door_head((o - n * depth, -r, -n), -u1, -u0, z0, z1, key)


def door_head(W, u0, u1, z0, z1, key="wood"):
    """a doorway's lintel and posts. (The walk of 2026-11-03, the back office door, misaligned: the lintel stopped 1.5 short
    of the posts' outer sides (wall_beam's cut), which stand 1 prouder, so the posts poked out past its ends. It runs 3.5 past
    them now, as a real door head's horns do; no end face shares a post's plane)"""
    wall_beam(W, (u0 - 19, z1 + 12), (u1 + 19, z1 + 12), w=24, deep=10, key=key)
    for ua in (u0 - 7, u1 + 7): wall_beam(W, (ua, z0), (ua, z1), w=14, deep=10, key=key, back=True)

def arch_head(W, u0, u1, z_crown, depth=0, key="stucco", n_=10, ring=14, ring_key="stone"):
    """a round-headed arch in a wall face whose hole is the rectangle (u0, u1, 0, z_crown): the two spandrels that close
    the rectangle's top corners down to the semicircle (key: the wall's own, so the face reads whole); with depth, the
    reveals below the springing and the curved soffit through the wall, facing into the opening (one face of the wall
    builds those), in ring_key, the texture running on round the curve; and a dressed surround `ring` wide, 1.5 proud of
    the face, up the jambs and round the head (the palette study's renders, 2026-10-26: "the arches appear to have broken
    textures": the soffit's segments each took their own texture direction, and the stone spandrels made a band thick at
    the corners and thin at the crown, on the hall's side only)"""
    o, r, n = W
    R = (u1 - u0) / 2; uc = (u0 + u1) / 2; zs = z_crown - R
    P = lambda u, z: o + r * u + UP * z
    arc = [(uc - R * math.cos(math.pi * k / (2 * n_)), zs + R * math.sin(math.pi * k / (2 * n_))) for k in range(n_ + 1)]
    poly(key, [P(u0, z_crown), P(u0, zs)] + [P(u, z) for u, z in arc[1:]])            # left: corner, springing, arc to the crown
    arc_r = [(2 * uc - u, z) for u, z in reversed(arc)]
    poly(key, [P(u1, z_crown)] + [P(u, z) for u, z in arc_r])                         # right: corner, crown, arc to the springing
    line_ = [(u0, 0)] + arc + arc_r[1:] + [(u1, 0)]                                   # up one jamb, over, down the other
    s_ = [0.0]
    for (ua, za), (ub, zb) in zip(line_, line_[1:]): s_.append(s_[-1] + math.hypot(ub - ua, zb - za))
    if depth:
        for i_, ((ua, za), (ub, zb)) in enumerate(zip(line_, line_[1:])):
            a_, b_ = P(ua, za), P(ub, zb)
            poly(ring_key, [a_, a_ - n * depth, b_ - n * depth, b_],                  # (wound into the wall until 2026-10-25)
                 [(s_[i_] / S, 0), (s_[i_] / S, depth / S), (s_[i_ + 1] / S, depth / S), (s_[i_ + 1] / S, 0)])
    if ring:
        def outward(i_):                                                              # away from the opening, in (u, z)
            u_, z_ = line_[i_]
            if z_ <= zs + 1e-6: return (-1.0, 0.0) if u_ < uc else (1.0, 0.0)
            d_ = math.hypot(u_ - uc, z_ - zs); return ((u_ - uc) / d_, (z_ - zs) / d_)
        for i_, (u_, z_) in enumerate(line_):
            if z_ > 0: ARCHES.append((tuple(P(u_ + outward(i_)[0] * ring, z_ + outward(i_)[1] * ring) + n * 3), tuple(P(u_, z_) + n * 3)))
        for i_ in range(len(line_) - 1):
            (ua, za), (ub, zb) = line_[i_], line_[i_ + 1]
            oa, ob = outward(i_), outward(i_ + 1)                                     # (radial at the springing is square
                                                                                      # to the jamb; squaring the whole first
                                                                                      # segment left a notch at its far end)
            q_ = [P(ua, za) + n * 1.5, P(ub, zb) + n * 1.5, P(ub + ob[0] * ring, zb + ob[1] * ring) + n * 1.5,
                  P(ua + oa[0] * ring, za + oa[1] * ring) + n * 1.5]
            poly(ring_key, q_, [(s_[i_] / S, 0), (s_[i_ + 1] / S, 0), (s_[i_ + 1] / S, ring / S), (s_[i_] / S, ring / S)])   # (counter-
                                                                                  # clockwise in (u, z): facing n, into the room)
            # its two edges, 1.5 deep: open, its back showed from inside the arch's passage (leak_check, 2026-10-26: 236
            # faces seen from behind)
            def edge_n(pa_, pb_, away):                                               # square to the edge, toward the
                du_, dz_ = (pb_ - pa_).dot(r), pb_.z - pa_.z                          # opening's middle (or away)
                pu_, pz_ = -dz_, du_
                mu_, mz_ = ((pa_ + pb_) / 2).dot(r) - o.dot(r), (pa_.z + pb_.z) / 2
                if (pu_ * (uc - mu_) + pz_ * (zs - mz_) > 0) == away: pu_, pz_ = -pu_, -pz_
                return r * pu_ + UP * pz_
            poly_n(ring_key, [P(ua, za), P(ub, zb), P(ub, zb) + n * 1.5, P(ua, za) + n * 1.5], edge_n(P(ua, za), P(ub, zb), False))
            poly_n(ring_key, [q_[3] - n * 1.5, q_[2] - n * 1.5, q_[2], q_[3]], edge_n(q_[3], q_[2], True))

def curved_brace(p0, h, L, dz, w=16, d=20, n=8, key="wood"):
    """a curved timber brace in the upright plane through p0 along h (unit 2D): from p0 on a post it rises dz while reaching
    L out, upright at the post and level where it meets the beam above (Dragonsreach's pillars carry their beams so)"""
    hx, hy = h; side = Vector((-hy, hx, 0))
    pts = [Vector((p0[0] + hx * L * (1 - math.cos(t)), p0[1] + hy * L * (1 - math.cos(t)), p0[2] + dz * math.sin(t)))
           for t in (math.pi / 2 * k / n for k in range(n + 1))]
    for a_, b_ in zip(pts, pts[1:]): beam(a_ - side * (d / 2), b_ - side * (d / 2), w, d, side, key=key)

# the windows whose daylight is a light in game too (vanilla's window fill), not only the renders' glow. (2026-11-02, the daylight plan) every room with windows, about one
# fill for two panes, vanilla's measured 0.4-0.7: 26 of 52, cell frame, as each opening's point 120 off its glass; a value moves one off a lamp's patch of wall (light_check's 130), as a cell offset
WINDOW_FILL = {(-161, -240, 175): None, (-161, 240, 175): None, (-955, 140, 550): None, (-955, -140, 550): None, (-109, 0, 1154): None,    # the great hall (and its bounce light)
               (-331, -571, 183): None, (-331, -881, 183): None, (-769, -881, 183): None, (-769, -571, 183): None, (-279, -571, 544): None,  # the tavern (its back two on the front's axes inside: guildhall_gen's WING_BACK_L)
               (-769, -1250, 183): None, (-290, -1279, 183): None,                                                                          # the kitchen (its back one centred inside: guildhall_gen's WING_BACK_LG)
               (-109, -36, 530): None, (-109, 280, 550): None, (-285, 571, 749): None, (-255, 1318, 736): None,                              # the library, the attic
               (-255, -1256, 544): None, (-790, -1331, 544): (90, -49, 0),                                                                   # the GM's office, his bedroom (off the lamp)
               (-290, 1279, 183): None, (-331, 571, 183): None, (-283, 1331, 544): None, (-505, 1331, 544): None, (-720, 1331, 544): None,   # back room, services, rooms 3, 4, 5 (plan D)
               (-279, 571, 544): None, (-279, 881, 544): (14, -6, 0), (-1015, 468, 664): None,                       # room 6, the common room (off the lamp), the tower
               (-946, 575, 1250): "glow"}   # the strongroom (2026-11-05): its glow card only, no fill: in a room 300 across no fill stands 130 off both its chandelier and its candle (light_check)
def window_wall(n, plane):
    """the wall face an exterior window's picture lies on, inside: (origin, right, normal into the room) as room_walls gives
    them, its origin on the axis so that u is the point's offset along `right`"""
    n = Vector(n); ax = 0 if abs(n.x) > 0.5 else 1
    into = Vector((-round(n.x), -round(n.y), 0)); o = Vector((0, 0, 0)); o[ax] = plane
    return (o, UP.cross(into), into)

TOWER_WIN_UP = 16
def window_inside(op, plane):
    """an exterior window, seen from inside: the same picture, mirrored, 1 in front of the inner face (`plane`: its x or
    y, along the window's outward normal)"""
    global PART
    kind = op["kind"]; key, rect = ATLAS[kind]
    n = Vector(op["n"]); ax = 0 if abs(n.x) > 0.5 else 1
    # the wings' casements sit INT_CS over the first floor inside (2026-10-26: they stood too low; moved inside, barely
    # nudged outside): outside their sill is CS, so inside
    # they stand a little higher than out, which no one can see from either side
    z0_ = min(p[2] for p in op["c"])
    dz_ = (ZG + INT_CS - z0_) if (HEARTH and kind == "grid" and ZG <= z0_ < ZG + 100) else 0
    if op["what"].startswith("tower") and z0_ < ZLK: dz_ += TOWER_WIN_UP   # (2026-10-30: one met the step, so shifted up a little: inside only)
    if kind == "fan": dz_ += FAN_DZ                            # (2026-11-14: the door's fanlight, under the front wall's ledge at ZG - 46 inside)
    # the great hall's two front windows stand 45.5 from the door's frame and from the side walls inside (after
    # the hall2t walk, 2026-10-26: moved slightly, inside only; outside the facade keeps them at +-280, 5 off the
    # side walls' inner faces, which read as windows pushed into the corners)
    dx_ = 0.0
    if HEARTH and kind == "arched" and op["what"].startswith("pavilion ground front"):
        cx_ = sum(p[0] for p in op["c"]) / 4
        dx_ = math.copysign(FRONT_WIN_X, cx_) - cx_
    c = []
    for p in op["c"]:
        q = Vector(p); q[ax] = plane - n[ax] * 1; q.z += dz_; q.x += dx_; c.append(q)
    w, h = (c[1] - c[0]).length, (c[3] - c[0]).length
    shape = outline(kind, w, h); a, b, cc, e = rect
    pts = [c[0] + (c[1] - c[0]) * fx + (c[3] - c[0]) * fy for fx, fy in shape][::-1]
    uvs = [(a + fx * (cc - a), 1 - e + fy * (e - b)) for fx, fy in shape][::-1]
    # start at the corner with the largest first triangle: poly() takes its normal from the first three points and drops
    # the face when they lie in a line, and the small casement's traced outline does (the back gable's two were never
    # drawn inside, 2026-10-25)
    i0 = max(range(len(pts)), key=lambda i: (pts[(i + 1) % len(pts)] - pts[i]).cross(pts[(i + 2) % len(pts)] - pts[i]).length)
    # (2026-10-30: windows that read as glass letting light through, as the Bannered Mare's do; the windows dark at night) inside the hall a
    # window follows vanilla's region, one pane, by day and by night (2026-11-02)
    if glazed(op["what"]):
        Wg = window_wall(n, plane); ug_ = sum(c_.dot(Wg[1]) for c_ in c) / 4; zg_ = min(c_.z for c_ in c)
        glaze(Wg, ug_, zg_, w, h, kind, 1.0, "in", "cross_diamond" if op["what"].startswith("dormer") else None)
    elif PART == "interior":
        poly(key + "i", pts[i0:] + pts[:i0], uvs[i0:] + uvs[:i0])
    else: poly(key, pts[i0:] + pts[:i0], uvs[i0:] + uvs[:i0])
    if HEARTH and kind in ("grid", "small"):   # W: a timber frame round the casements (the hall2t walk, 2026-10-26: all of them
        Wf = window_wall(n, plane)                 # looked clipped: their pictures are the atlas' square bodies, the heads
        us_ = [c_.dot(Wf[1]) for c_ in c]          # cropped mid-rail; outside the wall's timber covers that edge, inside nothing
        ua_, ub_ = min(us_), max(us_)              # did): a head over the cut, sides, and a sill standing out under it
        za_, zb_ = min(c_.z for c_ in c), max(c_.z for c_ in c)
        wall_beam(Wf, (ua_ - 8, zb_ - 3), (ub_ + 8, zb_ - 3), w=20, deep=9)
        for u_ in (ua_ + 1, ub_ - 1): wall_beam(Wf, (u_, za_), (u_, zb_ - 13), w=10, deep=7)
        wall_beam(Wf, (ua_ - 10, za_ - 2), (ub_ + 10, za_ - 2), w=10, deep=12)
    lp_ = sum(c, Vector()) / 4 - n * 120; lk_ = (round(-lp_.y), round(lp_.x), round(lp_.z))
    if HEARTH and lk_ in WINDOW_FILL:
        glow_only_ = WINDOW_FILL[lk_] == "glow"
        if WINDOW_FILL[lk_] and not glow_only_: lp_ = lp_ + Vector((WINDOW_FILL[lk_][1], -WINDOW_FILL[lk_][0], WINDOW_FILL[lk_][2]))
        if not glow_only_: INT_LIGHTS.append((*lp_, 2.0e5, (0.75, 0.85, 1.0), "window"))
        else: INT_LIGHTS.append((*lp_, 2.0e5, (0.75, 0.85, 1.0)))   # (the renders' glow only)
        # (2026-11-05, Option A: the hall was as dim at midday as at midnight) a
        # window's daylight haze as vanilla's Solitude houses have it (Erikur's House: 15 FXGlowFillRoundBrt at its windows, 0.37-0.8,
        # each on the region with the window fills): one at each window with a fill, 60 in from its glass at its middle, on the region
        gp_ = sum(c, Vector()) / 4 - n * 60; gs_ = 0.69 if w >= 100 else 0.48
        gl_ = ("meshes/effects/ambient/fxglowfillrndlitbrt.nif", "FXGlowFillRoundBrt")
        if PART == "lookout": LOOK_PLACE.append((*gl_[:1], tuple(gp_), 0, gs_, dict(ed=gl_[1], region=True)))
        else: piece(*gl_, tuple(gp_), 0, gs_, region=True)
    else: INT_LIGHTS.append((*lp_, 2.0e5, (0.75, 0.85, 1.0)))

def gallery(x0, x1, y0, y1, open_edges, posts=(), fascia=46, fw=8, joist_at=None):
    """a gallery floor at ZG: planks on joists, a fascia and a balustrade along its open edges, posts down to the floor.
    open_edges: [((x, y), (x, y))] along the void; fascia, fw: the edge beam's depth under the floor and half width (W: a
    heavy beam, since brackets and posts carry it)"""
    box("planks", (x0, y0, ZG - 4), (x1, y1, ZG)); box("wood", (x0, y0, ZG - 18), (x1, y1, ZG - 4))
    PLAN.append({"t": "gallery", "level": 1, "r": [x0, y0, x1, y1]})
    PLAN.extend({"t": "rail", "level": 1, "a": list(a_), "b": list(b_)} for a_, b_ in open_edges)
    PLAN.extend({"t": "post", "p": list(p_)} for p_ in posts)
    along_x = (x1 - x0) >= (y1 - y0)                              # joists across the short way, every 64
    a0, a1 = (x0, x1) if along_x else (y0, y1)
    q = a0 + 32
    if joist_at is not None: q = joist_at - 64 * math.floor((joist_at - a0 - 16) / 64)   # (one over a bracket: the hall2t walk,
    while q < a1 - 16:                                                                 # a board under the gallery was out of line)
        if along_x: box("wood", (q - 7, y0, ZG - 40), (q + 7, y1, ZG - 18))
        else: box("wood", (x0, q - 7, ZG - 40), (x1, q + 7, ZG - 18))
        q += 64
    for (ax, ay), (bx, by) in open_edges:
        L = math.hypot(bx - ax, by - ay); dx, dy = (bx - ax) / L, (by - ay) / L
        ex, ey = (8 if dx == 0 else 0), (8 if dy == 0 else 0)
        sx_, sy_ = (0.5 if dx != 0 else 0), (0.5 if dy != 0 else 0)  # (0.5 short of its ends: not in the plane of the floor or
        lo, hi = (min(ax, bx) - ex + sx_, min(ay, by) - ey + sy_), (max(ax, bx) + ex - sx_, max(ay, by) + ey - sy_)   # wall it meets)
        fx, fy = (fw if dx == 0 else 0), (fw if dy == 0 else 0)
        box("wood", (min(ax, bx) - fx + sx_, min(ay, by) - fy + sy_, ZG - fascia), (max(ax, bx) + fx - sx_, max(ay, by) + fy - sy_, ZG + 2))   # the fascia beam
        box("wood", (lo[0], lo[1], ZG + 80), (hi[0], hi[1], ZG + 90))                # the handrail, 90 over the floor
        box("wood", (lo[0], lo[1], ZG + 8), (hi[0], hi[1], ZG + 16))                 # the bottom rail
        for i in range(int(L // 16) + 1):                         # balusters every 16, a newel every 128
            s_ = min(i * 16, L); px, py = ax + dx * s_, ay + dy * s_
            big = i % 8 == 0 or s_ >= L
            hw = 6 if big else 2.5
            box("wood", (px - hw, py - hw, ZG), (px + hw, py + hw, ZG + 80 + (14 if big else 0)))
    for px, py in posts:                                          # posts down to the floor, on stone bases
        box("wood", (px - 11, py - 11, 14), (px + 11, py + 11, ZG - 40.5))   # (on its base, not through it)
        box("trim", (px - 16, py - 16, 0), (px + 16, py + 16, 14))

def stair(x0, x1, y_bot, y_top, rails=("in",), side=-1):
    """a straight flight from the floor at y_bot up to ZG at y_top: oak treads and risers on two stringers"""
    n_ = 22; rise = ZG / n_; run = (y_top - y_bot) / n_
    PLAN.append({"t": "stair", "r": [x0, min(y_bot, y_top), x1, max(y_bot, y_top)], "up_from": y_bot, "up_to": y_top})
    for i in range(n_):
        ya, yb = sorted((y_bot + run * i, y_bot + run * (i + 1)))
        zt = rise * (i + 1)
        box("planks", (x0, ya, zt - 4), (x1, yb, zt))
        box("wood", (x0, ya if run > 0 else yb - 2, zt - rise), (x1, (ya if run > 0 else yb - 2) + 2, zt - 4))
    for sx in (x0, x1):                                           # the stringers
        beam((sx, y_bot, -6), (sx, y_top, ZG - 6), 30, 8, (1 if sx == x1 else -1, 0, 0))
    for which in rails:                                           # the handrail on the open side, on newel posts
        rx = x1 if (which == "in") == (side < 0) else x0
        beam((rx, y_bot, 96), (rx, y_top, ZG + 90), 10, 8, (1 if rx == x1 else -1, 0, 0))
        for yy, zz in ((y_bot, 0), (y_top, ZG)):
            box("wood", (rx - 8, yy - 8, zz), (rx + 8, yy + 8, zz + 104))
        for i in range(0, n_, 2):
            yy = y_bot + run * (i + 0.5); zz = rise * (i + 1)
            box("wood", (rx - 2.5, yy - 2.5, zz), (rx + 2.5, yy + 2.5, zz + 90))

def timber(a, b, side, w, t, key="wood", ch=2.5):
    """a hewn timber from a to b, w across (along side) and t thick, its long edges chamfered by ch, the grain along its
    length on every face (2026-11-13, the trusses' king posts read as stacked slices rather than one beam stood
    upright: box() maps the grain level, so an upright box showed it in rings). Every face looks out."""
    a, b = Vector(a), Vector(b); ax = b - a; L = ax.length
    if L < 1e-6: return
    ax.normalize(); s = Vector(side); s = (s - ax * s.dot(ax)).normalized(); n = ax.cross(s).normalized()
    hw, ht = w / 2, t / 2; c = min(ch, hw * 0.4, ht * 0.4)
    ring = [(hw - c, -ht), (hw, -ht + c), (hw, ht - c), (hw - c, ht), (-hw + c, ht), (-hw, ht - c), (-hw, -ht + c), (-hw + c, -ht)]
    G2 = S / 2                                                # (the grain at twice the walls' timbers' density, as in the approved mock-up)
    def put(pts, uvs, out_):
        if (pts[1] - pts[0]).cross(pts[2] - pts[0]).dot(out_) < 0: pts, uvs = pts[::-1], uvs[::-1]
        poly(key, pts, uvs)
    per = 0.0
    for k in range(8):
        (x0, y0), (x1, y1) = ring[k], ring[(k + 1) % 8]; seg = math.hypot(x1 - x0, y1 - y0)
        p = [a + s * x0 + n * y0, b + s * x0 + n * y0, b + s * x1 + n * y1, a + s * x1 + n * y1]
        put(p, [(0, per / G2), (L / G2, per / G2), (L / G2, (per + seg) / G2), (0, (per + seg) / G2)], s * ((x0 + x1) / 2) + n * ((y0 + y1) / 2))
        per += seg
    for e, sg in ((a, -1), (b, 1)):
        put([e + s * x + n * y for x, y in ring], [(0.5 + x / G2, 0.5 + y / G2) for x, y in ring], ax * sg)

def timber_curve(pts, side, w, t, key="wood", ch=2.5):
    """a curved timber through pts, one swept piece: its rings joined face to face, the grain running on unbroken (straight
    lengths overlapped at the joints showed each one's end and a restart of the grain there, in the first render)"""
    pts = [Vector(p) for p in pts]; hw, ht = w / 2, t / 2; c = min(ch, hw * 0.4, ht * 0.4); G2 = S / 2
    ring = [(hw - c, -ht), (hw, -ht + c), (hw, ht - c), (hw - c, ht), (-hw + c, ht), (-hw, ht - c), (-hw, -ht + c), (-hw + c, -ht)]
    frames, run, along = [], [], 0.0
    for i, p in enumerate(pts):
        tg = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        s = Vector(side); s = (s - tg * s.dot(tg)).normalized(); n = tg.cross(s).normalized()
        if i: along += (p - pts[i - 1]).length
        frames.append((p, s, n, tg)); run.append(along)
    def put(q, uvs, out_):
        if (q[1] - q[0]).cross(q[2] - q[0]).dot(out_) < 0: q, uvs = q[::-1], uvs[::-1]
        poly(key, q, uvs)
    for i in range(len(pts) - 1):
        (p0, s0, n0, _), (p1, s1, n1, _) = frames[i], frames[i + 1]; per = 0.0
        for k in range(8):
            (x0, y0), (x1, y1) = ring[k], ring[(k + 1) % 8]; seg = math.hypot(x1 - x0, y1 - y0)
            q = [p0 + s0 * x0 + n0 * y0, p1 + s1 * x0 + n1 * y0, p1 + s1 * x1 + n1 * y1, p0 + s0 * x1 + n0 * y1]
            put(q, [(run[i] / G2, per / G2), (run[i + 1] / G2, per / G2), (run[i + 1] / G2, (per + seg) / G2), (run[i] / G2, (per + seg) / G2)],
                (s0 + s1) * ((x0 + x1) / 4) + (n0 + n1) * ((y0 + y1) / 4))
            per += seg
    for (p, s, n, tg), sg in ((frames[0], -1), (frames[-1], 1)):
        put([p + s * x + n * y for x, y in ring], [(0.5 + x / G2, 0.5 + y / G2) for x, y in ring], tg * sg)

TRUSS_JOINTS = os.environ.get("AG_TRUSS_JOINTS", "1") == "1"   # (the joints, 2026-11-13, as in the mock-up; AG_TRUSS_JOINTS=0 the old braces)
PENDANT_B = [(2, 12.0), (-3, 14.5), (-7, 14.5), (-9, 9.0), (-15, 8.0), (-21, 13.0), (-29, 14.0), (-37, 11.0), (-44, 5.0), (-50, 0.0)]
def turned_drop(c_, X_, Y_, prof, n=16, key="wood"):
    """a turned piece under c_ (a drop or pendant): the profile [(z, radius)] down from c_, revolved round the upright through it
    in n facets, its grain along its length; every face looks out"""
    run = [0.0]
    for (za, ra), (zb, rb) in zip(prof, prof[1:]): run.append(run[-1] + math.hypot(za - zb, ra - rb))
    X_, Y_ = Vector(X_).normalized(), Vector(Y_).normalized()
    P_ = lambda r, a, z: c_ + X_ * (r * math.cos(a)) + Y_ * (r * math.sin(a)) + UP * z
    for i in range(len(prof) - 1):
        (za, ra), (zb, rb) = prof[i], prof[i + 1]
        for k in range(n):
            a0, a1 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
            q = [P_(ra, a0, za), P_(ra, a1, za), P_(rb, a1, zb), P_(rb, a0, zb)]
            uv = [(k / n * 0.5, run[i] / 128), ((k + 1) / n * 0.5, run[i] / 128), ((k + 1) / n * 0.5, run[i + 1] / 128), (k / n * 0.5, run[i + 1] / 128)]
            if rb < 1e-6: q, uv = q[:3], uv[:3]
            mid_ = sum(q, Vector((0, 0, 0))) / len(q); out_ = mid_ - (c_ + UP * ((za + zb) / 2))
            if (q[1] - q[0]).cross(q[2] - q[0]).dot(out_) < 0: q, uv = q[::-1], uv[::-1]
            poly(key, q, uv)

def arch_truss(P, H, zroof, tie_bot, tie_top, post_bot, brace_z, brace_in, collar_z, crown_brace_z, rake_u, rake_z, foot=None, braces=True, pendant=None):
    """an arch-braced truss with a crown post (2026-11-13, after the references, York's Merchant Adventurers' Hall and
    fantasy guild halls: more diagonal braces, the trusses and their curved lower braces as mocked up): wall posts with curved arch braces up under a cambered tie beam, principals, a
    collar, a crown post braced to the collar, raking struts from the tie beam to the principals. P(u, z, t): the point u
    across the span from its middle, z up, t along the room. H: wall to middle. zroof(u): the boards' underside. foot: the
    principals' foot at the wall when it stands over the tie beam (a span narrower than the roof's; the posts rise to it)"""
    V_ = lambda u, z, t=0.0: Vector(P(u, z, t))
    ALONG = V_(0, 0, 1) - V_(0, 0); UPV = V_(0, 1) - V_(0, 0); ACROSS = V_(1, 0) - V_(0, 0)
    camber = lambda u: 7 * (1 - (u / H) ** 2)
    tc_, th_ = (tie_bot + tie_top) / 2, tie_top - tie_bot
    us_ = [-H - 2 + (2 * H + 4) * k / 10 for k in range(11)]                              # the tie beam, cambered, 2 into each wall
    timber_curve([V_(u, tc_ + camber(u)) for u in us_], UPV, th_, 30)
    zf = tie_top - 4 if foot is None else foot; zt_ = zroof(0) - 8
    pu = lambda z: (zt_ - z) * (H - 6) / (zt_ - zf)                                       # the principal's u at height z
    for sg in (-1, 1):
        timber(V_(sg * (H - 6), zf), V_(0, zt_), V_(-sg, 1) - V_(0, 0), 32, 18)          # the principal
        if braces:   # (braces=False: no wall post and arch brace; the tavern's truss, 2026-11-13)
          timber(V_(sg * (H - 12.6), post_bot - 0.4), V_(sg * (H - 12.6), (tie_bot + 2) if foot is None else foot + 8), ACROSS, 26, 22)   # the wall post
          if pendant: turned_drop(V_(sg * (H - 12.6), post_bot), ACROSS, ALONG, pendant)   # (its foot carved: option B, 2026-11-13)
          if not TRUSS_JOINTS:
            cu, au, bz = sg * (H - brace_in), sg * (brace_in - 26), tie_bot - brace_z + 1     # the arch brace, a quarter ellipse
            timber_curve([V_(cu + au * math.cos(math.radians(9 * k)), brace_z + bz * math.sin(math.radians(9 * k))) for k in range(11)], ALONG, 18, 18)
          else:
            # (2026-11-13, the curved braces looked disconnected: the brace's
            # ends were square cuts, half of its foot standing proud of the post and its head short of the cambered tie. Now its
            # centre line runs 9 inside both, so its inner edge leaves the post's face and meets the tie's underside as tangents,
            # and its ends (swept 9 degrees past both) lie hidden in them. And the joints the references dress: a capital on the
            # post under the brace's spring, a corbel under the tie's end, a boss under the tie at the crown post)
            zt_b = tie_bot + camber(H - brace_in)
            cu, au, bz = sg * (H - brace_in), sg * (brace_in - 17), zt_b + 9 - brace_z
            timber_curve([V_(cu + au * math.cos(math.radians(9 * k)), brace_z + bz * math.sin(math.radians(9 * k))) for k in range(-1, 12)], ALONG, 18, 18)
            pu_ = sg * (H - 12.6)
            timber(V_(pu_, brace_z - 16), V_(pu_, brace_z - 6), ACROSS, 30, 26, ch=3)        # the capital: its bed ...
            timber(V_(pu_, brace_z - 6.5), V_(pu_, brace_z), ACROSS, 34, 30, ch=2)           # ... and its abacus, the brace springing off it
            # (a corbel under the tie's end was mocked up and dropped)
        timber(V_(sg * rake_u, tie_top - 2), V_(sg * pu(rake_z), rake_z), ALONG, 20, 16)  # the raking strut
        timber(V_(0, crown_brace_z), V_(sg * 95, collar_z - 10), ALONG, 16, 16)          # the crown post's brace
    uc = pu(collar_z)
    timber(V_(-uc - 6, collar_z), V_(uc + 6, collar_z), UPV, 24, 15)                      # the collar (thinner than the principals: at
                                                                                          # their 18 its sides lay in theirs and flickered)
    timber(V_(0, tie_top + camber(0) - 2), V_(0, collar_z - 10), ACROSS, 26, 26)          # the crown post, its grain upright
    if TRUSS_JOINTS and braces:   # a small plain block under the tie where the crown post stands (the mock-up's carved boss with a drop
        # was too big and ornamental): the post's tenon end, 16 square, 5 under the tie, chamfered
        timber(V_(0, tie_bot + camber(0) - 5), V_(0, tie_bot + camber(0) + 1), ACROSS, 16, 16, ch=1.5)

def truss(y, xr=None, xl=None):
    """the great hall's truss at y (xr, xl: its right and left walls where they stand further in than the roof's; both do
    together, so the narrower span is the hall's middle). Over the library loft (y 150: its tie beam 172 over the loft's
    floor) the posts stand on that floor (the walk of 2026-11-13) and the braces are short knee braces near the walls, clear of the loft's walkway;
    over the narrower span (the tower's foot, the hearth's mirror) the posts rise to the principals' feet"""
    xr = XU if xr is None else xr; xl = XU if xl is None else xl; H = min(xr, xl)
    P = lambda u, z, t=0.0: (u, y + t, z)
    if y < 270:      arch_truss(P, H, ZR, 862, 900, T1 + 34, 815, 70, 1232, 1075, 125, 1100)   # (270: the loft's back edge, OFF1 + 10. The posts stand
                                                                                                 # on its floor, 2026-11-13; the chest slid clear)
    elif H < XU - 1:
        ft_ = ZR(H - 6) - 18
        arch_truss(P, H, ZR, 862, 900, 728, 745, 120, 1232, 1075, 70, ft_ + 40, foot=ft_, pendant=PENDANT_B)
    else:            arch_truss(P, H, ZR, 862, 900, 728, 745, 205, 1232, 1075, 125, 1100, pendant=PENDANT_B)
    # (2026-11-13, the truss posts' flat bottoms wanted ornament; of the three drops rendered,
    # B, the turned acorn, with the post shortened as it came down too far: the posts end 28 higher, at 728, 17 under where
    # the arch brace meets them, the drop's point at 678. Not on the loft's truss, whose posts stand on its floor)

def purlin(sx, y0, y1):
    """a purlin along the great hall's slope on side sx, from y0 to y1 (2026-11-13: support timbers under the roof,
    no plaster and no curved pieces): straight, hard up against
    the boards, 3 into them (its chamfers too: the first hung under the rafters with a gap to the roof), so the rafters run into it as if notched over it; through the principals as a butt purlin is tenoned through
    them. 24 deep against the rafters' 17: their undersides 4 apart, not in one plane"""
    u_ = sx * 262; nrm_ = Vector((sx * TP, 0, 1)).normalized(); c_ = Vector((u_, 0, ZR(u_))) - nrm_ * 9
    timber(Vector((c_.x, y0, c_.z)), Vector((c_.x, y1, c_.z)), Vector((-sx, 0, TP)), 22, 24)

DRAGON_S = 0.69
def wall_sconce(x, y, z, n, lamp=None):
    """a wall candle (2026-10-30, in place of a chandelier in a 238-high room): vanilla's, at 1.7 as the attic's, on the
    wall facing n; lamp: the reach it lights its share of a room with, instead of a candle's 128"""
    piece("meshes/clutter/imperial/impwallsconcecandle01.nif", "ImpWallSconceCandle01", (x + 2 * n[0], y + 2 * n[1], z), math.degrees(math.atan2(n[1], -n[0])) % 360, 1.7)
    INT_LIGHTS.append((x + 45 * n[0], y + 45 * n[1], z + 30, 1.0e6, (1.0, 0.7, 0.42), "lamp", lamp - 512, -0.6) if lamp else (x + 26 * n[0], y + 26 * n[1], z + 30, 1.0e6, (1.0, 0.7, 0.42), "candle"))


def chandelier(x, y, z, hang_to, gather=None, low=False):
    """a lit chandelier (2026-10-30, none of the hall's fixtures looked lit: the stand-in iron ring, no
    flames, replaced by vanilla's). ImpChandellierCandle01: an iron ring of lit candles 132 across, its origin at its foot, its
    own chains 280 tall, then a chain to hang_to. low: under a low ceiling CandleHornChandelier02 hard up to it, 79 tall"""
    rel, ed, at = (("meshes/clutter/candles/candlehornchandelier02.nif", "CandleHornChandelier02", hang_to - 49.7) if low else
                   ("meshes/clutter/imperial/impchandelliercandle01.nif", "ImpChandellierCandle01", z))
    if PART == "basement": bplace(rel, ed, (x, y, at), 0)
    elif PART == "lookout": LOOK_PLACE.append((rel, (x, y, at), 0, 1.0, dict(ed=ed)))
    else: piece(rel, ed, (x, y, at), 0)
    if not low and hang_to > at + 281:    # (the walk of 2026-10-30: the extension did not match the chain: a bar; now the ring's own chain, carried on: chain_nif.py, a mesh per length)
        l_ = math.ceil(hang_to - (at + 280)); r_ = f"meshes/adventurersguild/hall2/aghall2chain{l_}.nif"; e_ = f"AGHall2Chain{l_}"
        if PART == "basement": bplace(r_, e_, (x, y, at + 280), 0)
        elif PART == "lookout": LOOK_PLACE.append((r_, (x, y, at + 280), 0, 1.0, dict(ed=e_)))
        else: piece(r_, e_, (x, y, at + 280), 0, exact=True)
    INT_LIGHTS.append((x, y, at + 30, 9.0e6, (1.0, 0.72, 0.42), "candle"))   # (in game: vanilla's inn candle light, 2026-10-26)

# ---------------------------------------------------------------- the great hall
if TOWER3:                                                                   # stone flags (V: not under the tower's foot)
    box("floor", (-XG, YF, -12), (XG, TY0, 0)); box("floor", (-XG, TY0, -12), (TX0, YB, 0))
else: box("floor", (-XG, YF, -12), (XG, YB, 0))
DAIS = 20
if HEARTH:   # W: the back bay between the tower's foot and its mirror, one step up: the dais before the great hearth
    box("floor", (-TX0, TY0, 0), (TX0, YB, DAIS))
    PLAN.append({"t": "dais", "r": [-TX0, TY0, TX0, YB], "z": DAIS})
RW = room_walls(-XG, YF, XG, YB)
side_holes = {"left": [], "right": []}                                       # doorways into the wings: (y0, y1, z1)
ARCADE = [(300, 420, 330), (450, 570, 330), (600, 720, 330), (750, 850, 330)]   # under a side gallery, into the wing
UNDER = [(680, 850, 250)]                     # under a stair's upper end (its underside is 280 up there)
TOWER_ARCH = (800, 920, 240)                  # T: the way into the tower, beside the counter's end (the tower's inside starts at y 800)
# W: the arcades either side of the great hall. Since the hall2aa walk (2026-10-26: 3 arches to 2, more open
# with fewer columns in the way, both sides, the brace moved with them): two round arches over
# the same run (300..720) on one pier, 50 like the old ones, at 485..535; their crown 350 (springing 257.5; the ring's
# top 364, under the ledge at 372). AG_ARCADE=three: the three of 110 and 100 at crown 330
W_ARCS = ([(300, 410, 330), (460, 560, 330), (610, 720, 330)] if os.environ.get("AG_ARCADE", "two") == "three"
          else [(300, 485, 350), (535, 720, 350)])
W_PIER = 435 if os.environ.get("AG_ARCADE", "two") == "three" else 510   # the pier the galleries' brackets stand on
side_holes = {"A": {"left": UNDER, "right": UNDER}, "B": {"left": ARCADE, "right": UNDER},
              "C": {"left": ARCADE, "right": [(380, 760, 340)]},
              "T": {"left": ARCADE, "right": ARCADE[:3] + [TOWER_ARCH]},
              "D": {"left": ARCADE, "right": ARCADE[:3] + [TOWER_ARCH]},
              "U": {"left": ARCADE, "right": ARCADE[:3]}, "V": {"left": ARCADE, "right": ARCADE[:3]},
              # W: three round arches a side with solid piers (they carry the galleries' brackets); on the right they open
              # into the guild services (the clerks' two doors became arches like the left's, 2026-10-26: a
              # passthrough; no fourth opening: the mirror is solid below, chosen after the renders)
              "W": {"left": W_ARCS, "right": W_ARCS}}[VARIANT]   # (a wing
ARCHED = {(s_, a_, b_) for s_ in ("left", "right") for a_, b_, c_ in W_ARCS} if HEARTH else set()
for side, (W, L) in RW.items():                                              # stands behind y 230..870 only)
    if side in ("left", "right"):
        to_u = (lambda y_: y_ - YF) if side == "left" else (lambda y_: YB - y_)
        holes = [tuple(sorted((to_u(a_), to_u(b_)))) + (0, zt_) for a_, b_, zt_ in side_holes[side]]
        arched = [(side, a_, b_) in ARCHED for a_, b_, zt_ in side_holes[side]]
    else:
        holes, arched = [], []
    u0_, u1_ = (YB - TY0, L) if (TOWER3 and side == "right") else ((0, XG + TX0) if (TOWER3 and side == "back") else (0, L))
    if HEARTH and side == "left": u1_ = TY0 - YF                             # (W: the mirror stands in the other corner,
    if HEARTH and side == "back": u0_ = XG - TX0                             # solid: the walls stop at it)
    face("stone", W, u0_, u1_, 0, ZG - 18, holes)                            # (V: the tower's foot stands in its corner)
    for h, ar in zip(holes, arched or [False] * len(holes)):
        if ar: arch_head(W, h[0], h[1], h[3], TS)                            # (W: stone arches, no timber posts in front)
        else: opening_frame(W, h[0], h[1], 0, h[3], TS, both=True)
    if side in ("left", "right"):                                            # a stone threshold through each opening
        for a_, b_, zt_ in side_holes[side]:
            box("floor", ((-XG - TS, a_, -12) if side == "left" else (XG, a_, -12)), ((-XG, b_, 0) if side == "left" else (XG + TS, b_, 0)))
        PLAN += [{"t": "opening", "level": 0, "x": (-1 if side == "left" else 1) * (XG + TS / 2), "y": [a_, b_], "z": [0, zt_]}
                 for a_, b_, zt_ in side_holes[side]]
XB_ = TX0 if TOWER3 else XG                     # V: the hall's back wall and its ledge stop at the tower's foot
ZL_ = ZG - 19 if HEARTH else ZG - 18           # (W: the ledges' tops 1 under the floors over them, out of their plane)
# the ledge where the jetty steps out. Each run stops at the next one's face, not on it (2026-10-27, coplanar_check on
# the interior: the side runs' ends lay in the front and tower ledges' faces, the back run's in the tower's, and flickered)
# (2026-11-12, the ledges beside the main hall's hearth showed an odd wood texture: the trim key is
# the interior's carved trim sheet, AGH2Trim, a sheet of rows, and a box's world-projected UVs gave each ledge whatever row its height
# met: at 372..399 the end-grain tiles, an empty black one among them, and the iron strip. From the renders: the carved molding
# only works as trim, and the wood strip reads better as the edge of a brace, so each is used where it fits:
# the masses' string courses, trim on dressed stone beside the hearth, wear the sheet's carved row fitted to them; the ledges under
# the galleries, the edge of their framing, are timber (the wood key))
TRIM_ROW = (0.572, 0.862)                                   # the carved row, in the sheet's own v (top down)
def carved_box(lo, hi):
    """a box in the trim sheet's carved row, fitted: on its long faces the row's full height over the face's, the carving's
    proportions kept along it; on its ends the same across them; on top and underneath the row's plain lower edge"""
    x0, y0, z0 = lo; x1, y1, z1 = hi
    along = 0 if (x1 - x0) >= (y1 - y0) else 1
    n0, n1 = TRIM_ROW; H_ = z1 - z0; UPT = H_ / (n1 - n0)       # units per sheet width, the row's height over the face's
    v = [Vector((x, y, z)) for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)]
    for f in [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (3, 2, 6, 7), (2, 0, 4, 6), (1, 3, 7, 5)]:
        pts = [v[i] for i in f]; uvs = []
        nrm = (pts[1] - pts[0]).cross(pts[2] - pts[0])
        for p_ in pts:
            if abs(nrm.z) < 1e-6 * max(1, nrm.length):              # a side: the row's height up it (v: bottom n1, top n0)
                t_ = (p_.z - z0) / H_; u_ = (p_[along] if abs(nrm[1 - along]) > abs(nrm[along]) else p_[1 - along]) / UPT
                uvs.append((u_, 1 - (n1 + (n0 - n1) * t_)))
            else:                                                    # top, underneath: the row's lower edge, along the box
                uvs.append((p_[along] / UPT, 1 - (n1 - 0.004 - 0.004 * ((p_[1 - along] - (y0 if along == 0 else x0)) / max(1e-6, (y1 - y0) if along == 0 else (x1 - x0))))))
        poly("trim", pts, uvs)
box("wood", (-XG, YF, ZG - 46), (XG, YF + 12, ZL_))
box("wood", ((-TX0 + 8 if HEARTH else -XG), YB - 12, ZG - 46), (XB_ - (8 if TOWER3 else 0), YB, ZL_))
for sx in (-1, 1): box("wood", (sx * XG - (12 if sx > 0 else 0), YF + 12, ZG - 46), (sx * XG + (0 if sx > 0 else 12), (TY0 - 8) if (TOWER3 and (sx > 0 or HEARTH)) else YB - 12, ZL_))
if TOWER3:   # V: the tower's foot in the hall's back-right corner: its stone faces up to the gallery's floor, a string course
    for W, L in (((Vector((TX0, TY0, 0)), Vector((1, 0, 0)), Vector((0, -1, 0))), XG - TX0),     # (normal = right x up)
                 ((Vector((TX0, YB, 0)), Vector((0, -1, 0)), Vector((-1, 0, 0))), YB - TY0)):
        face("stone", W, 0, L, 0, ZG - 4)   # (to the gallery's planks at 414, 2026-11-08: stopped at 400, a 19-high slot over the string course showed the timber behind)
    carved_box((TX0, TY0 - 8, ZG - 46), (XG, TY0, ZL_)); carved_box((TX0 - 8, TY0 - 8, ZG - 46), (TX0, YB, ZL_))
    PLAN.append({"t": "foot", "r": [TX0, TY0, XG, YB]})
if HEARTH:   # W: the tower's foot mirrored in the back-left corner: stone to the gallery's
             # floor and a string course on the hall's side, solid below (chosen after the renders: no door onto
             # the dais, so two blank stone faces flank the hearth); the passage is upstairs only
    MX = -TX0
    WMF = (Vector((-XG, TY0, 0)), Vector((1, 0, 0)), Vector((0, -1, 0)))       # its front to the hall
    WMS = (Vector((MX, TY0, 0)), Vector((0, 1, 0)), Vector((1, 0, 0)))         # its side to the dais (over the dais' step)
    face("stone", WMF, 0, XG + MX, 0, ZG - 4)     # (to the gallery's planks at 414, as the tower's foot: 2026-11-08, the slot over its string course)
    face("stone", WMS, 0, YB - TY0, DAIS, ZG - 4)
    carved_box((-XG, TY0 - 8, ZG - 46), (MX, TY0, ZL_)); carved_box((MX, TY0 - 8, ZG - 46), (MX + 8, YB, ZL_))
    PLAN.append({"t": "foot", "r": [-XG, TY0, MX, YB], "mirror": True})
if HEARTH:   # W: the office, the galleries and the masses' floors cover the jetty's strips; two floors in one plane
    box("wood", (-TX0, YB, ZG - 18), (TX0, YBU, ZG))     # flicker (the walk of 2026-10-25), so only the back bay's is built
else:
    box("wood", (-XU, YFU, ZG - 18), (-XG, YBU, ZG))                                                             # the jetty's floor inside
    if TOWER2: box("wood", (XG, YFU, ZG - 18), (XU, TY0, ZG))                                                    # (U, V: not into the tower)
    if TOWER2 and not TOWER3: box("wood", (XG, TY0, ZG - 18), (PX1, YBU, ZG))
    if not TOWER2: box("wood", (XG, YFU, ZG - 18), (XU, YBU, ZG))
    box("wood", (-XU, YFU, ZG - 18), (XU, YF, ZG)); box("wood", (-XU, YB, ZG - 18), (TX0 if TOWER3 else (PX1 if TOWER2 else XU), YBU, ZG))
# above the stone: the timber storeys' inner walls, plaster between posts and plates, up to the roof
RU = room_walls(-XU, YFU, XU, YBU)
TOWER_DOORS = [(YBU - 740, YBU - 620, ZG, ZG + 202),          # to the staff quarters and the patio door
               (YBU - 1000, YBU - 880, ZG, ZG + 202)]          # into the tower
UPPER_HOLES = {"C": {"right": [(YBU - 870, YBU - 770, ZG, ZG + 202)]},   # (u along the right wall: YBU - y; the left: y - YFU)
               "T": {"right": TOWER_DOORS},
               "D": {"right": TOWER_DOORS,                     # and from the ring onto the tavern's two galleries
                     "left": [(172 - YFU, 292 - YFU, ZG, ZG + 202), (776 - YFU, 896 - YFU, ZG, ZG + 202)]},
               "U": {"right": [(YBU - 724, YBU - 604, ZG, ZG + 202)]},       # U: to the stair's lobby (no door into the
               "V": {"right": [(YBU - 724, YBU - 604, ZG, ZG + 202)],       # tower from the gallery); V: and D's two
                     "left": [(172 - YFU, 292 - YFU, ZG, ZG + 202), (776 - YFU, 896 - YFU, ZG, ZG + 202)]}}
UPPER_HOLES["W"] = UPPER_HOLES["V"]                                          # (W: the back one inside the mirror's passage)
UPPER_HOLES = UPPER_HOLES.get(VARIANT, {})
for side, (W, L) in RU.items():                                             # (onto the tavern's galleries)
    u0_, u1_ = (YBU - TY0, L) if (TOWER2 and side == "right") else ((XU - TX0 if HEARTH else 0, XU + JX) if (TOWER2 and side == "back") else (0, L))
    face("stucco", W, u0_, u1_, ZG, ZWP, UPPER_HOLES.get(side, ()))
    for h in UPPER_HOLES.get(side, ()):
        opening_frame(W, h[0], h[1], h[2], h[3], TT, both=True)
        if side == "right": PLAN.append({"t": "door", "level": 1, "a": [XU + TT / 2, YBU - h[1]], "b": [XU + TT / 2, YBU - h[0]]})
        else: PLAN.append({"t": "door", "level": 1, "a": [-XU - TT / 2, YFU + h[0]], "b": [-XU - TT / 2, YFU + h[1]]})
    o, r, n = W
    # (the walk of 2026-11-13: the trim heights differed between the window walls and the walls opposite: under the
    # loft's floor, in the library, the outer walls' rail at T1 stood 9 under the library's own walls' (T1 + 8, 22 tall, under the
    # ceiling). There it runs at their height: the whole front wall, and each side wall from the front to a wall that hides the step
    # (the left: the alcove wall's middle, y 148; the right: the office wall's middle, y 248). The gallery's stay at T1)
    lib_ = {"front": [(u0_, u1_, True)], "left": [(u0_, 148 - YFU, True), (148 - YFU, u1_, False)],
            "right": [(u0_, YBU - 248, False), (YBU - 248, u1_, True)]}.get(side, [(u0_, u1_, False)]) if HEARTH else [(u0_, u1_, False)]
    for zz in (ZG + 13, T1, ZWP - 14):
        for ua_, ub_, in_lib_ in (lib_ if zz == T1 else [(u0_, u1_, False)]):
            if in_lib_: wall_rail(W, ua_, ub_, T1 + 8, UPPER_HOLES.get(side, ()), w=22, deep=5)
            else: wall_rail(W, ua_, ub_, zz, UPPER_HOLES.get(side, ()), deep=5)   # (13: its underside 1 over the floors,
    # not in their plane; 5 deep since the hall2ac walk: at 8 they ran 1 behind the posts' faces and showed through them, flickering
    # in an upright strip beside the window)
                                                                                    # not in their plane)
    # its windows' spans along it (W, after the hall2t walk, 2026-10-26: timbers stood in front of the windows: the
    # posts every 136 skipped doorways only, so some crossed the glass; now they skip windows too and stand either side)
    wins_ = []
    if HEARTH:
        for op_ in OPENINGS:
            if (op_["what"].startswith("pavilion") and "ground" not in op_["what"] and op_["kind"] in ("arched", "leaded", "grid", "small", "gothic", "door leaf")
                    and Vector(op_["n"]).dot(n) < -0.5 and ZG <= min(p_[2] for p_ in op_["c"]) < ZWP):
                us_ = [(Vector(p_) - o).dot(r) for p_ in op_["c"]]
                if min(us_) < u1_ and max(us_) > u0_: wins_.append((min(us_), max(us_)))
    # (the hall2bf walk, 2026-10-28: the boards framing the library's window flickered: its window and the loft's
    # over it, 3 narrower each side, each got its own full-height post either side, two posts 3 apart in one plane; windows
    # whose spans overlap, stacked in one bay, are one span, its posts outside the wider)
    merged_ = []
    for wa_, wb_ in sorted(wins_):
        if merged_ and wa_ < merged_[-1][1] + 16: merged_[-1] = (merged_[-1][0], max(merged_[-1][1], wb_))
        else: merged_.append((wa_, wb_))
    wins_ = merged_
    k_ = 0
    while u0_ + k_ * 136 <= u1_:                                               # posts, and a brace in every other bay
        u = min(u0_ + k_ * 136, u1_ - 9) if k_ else u0_ + 9
        if not any(h[0] - 16 < u < h[1] + 16 for h in list(UPPER_HOLES.get(side, ())) + [w_ + (0, 0) for w_ in wins_]):   # (none in
            wall_beam(W, (u, ZG), (u, ZWP), w=18, deep=8)                        # a doorway: the first walk found one in the
        k_ += 1                                                                  # tavern gallery's)
    for wa_, wb_ in wins_:
        for u in (wa_ - 10, wb_ + 10):
            if u0_ + 9 <= u <= u1_ - 9 and not any(h[0] - 16 < u < h[1] + 16 for h in UPPER_HOLES.get(side, ())):
                wall_beam(W, (u, ZG), (u, ZWP), w=18, deep=8)
if TOWER2 and not TOWER3:   # U: along the tower the jettied wall stands 36 into the gallery's corner, up to the roof; a
    WJ = (Vector((JX, YBU, 0)), Vector((0, -1, 0)), Vector((-1, 0, 0)))    # short return at the tower's front
    face("stucco", WJ, 0, YBU - TY0, ZG, ZR(JX))
    for zz in (ZG + 12, T1): wall_beam(WJ, (0, zz), (YBU - TY0, zz), w=24, deep=8)
    for u in (9, (YBU - TY0) / 2, YBU - TY0 - 9): wall_beam(WJ, (u, ZG), (u, ZR(JX)), w=18, deep=8)
    face("stucco", (Vector((JX, TY0, 0)), Vector((1, 0, 0)), Vector((0, -1, 0))), 0, XU - JX, ZG, ZR(JX))
if TOWER3:   # V: the tower's timber storeys over its foot, flush with the void, up to the roof; its front over the gallery's
    WJ = (Vector((JX, YBU, 0)), Vector((0, -1, 0)), Vector((-1, 0, 0)))    # end, under the roof's slope
    LJ = YBU - TY0
    face("stucco", WJ, 0, LJ, ZG - 18, ZR(JX))
    for zz in (ZG + 13, T1, T2 - 14): wall_beam(WJ, (0.5, zz), (LJ - 0.5, zz), w=24, deep=8)   # the tower's own storey lines
    for u in (9, LJ / 3, 2 * LJ / 3, LJ - 9): wall_beam(WJ, (u, ZG - 18), (u, ZR(JX)), w=18, deep=8)
    WR = (Vector((JX, TY0, 0)), Vector((1, 0, 0)), Vector((0, -1, 0)))
    xs_ = [JX + (XU - JX) * k_ / 8 for k_ in range(9)]
    for xa, xb in zip(xs_, xs_[1:]):                                          # its top follows the roof's underside
        poly("stucco", [Vector((xa, TY0, ZG)), Vector((xb, TY0, ZG)), Vector((xb, TY0, ZR(xb))), Vector((xa, TY0, ZR(xa)))])
    for zz in (ZG + 13, T1): wall_beam(WR, (0, zz), (XU - JX, zz), w=24, deep=8)
    wall_beam(WR, (9, ZG), (9, ZR(JX + 9)), w=18, deep=8)
    PLAN.append({"t": "wall", "level": 1, "a": [JX + TT / 2, TY0], "b": [JX + TT / 2, YBU], "gaps": []})
if HEARTH:   # W: the mirror's timber storeys, the tower's mirrored: its side to the dais up to the roof, its front over the left
             # gallery's end with the door into its passage, which runs through to the tavern's back-gallery door (776..896)
    MX = -TX0
    WMS = (Vector((MX, TY0, 0)), Vector((0, 1, 0)), Vector((1, 0, 0)))
    LJ = YBU - TY0
    face("stucco", WMS, 0, LJ, ZG - 18, ZR(MX))
    for zz in (ZG + 13, T1, T2 - 14): wall_beam(WMS, (0.5, zz), (LJ - 0.5, zz), w=24, deep=8)
    for u in (9, LJ / 3, 2 * LJ / 3, LJ - 9): wall_beam(WMS, (u, ZG - 18), (u, ZR(MX)), w=18, deep=8)
    MGD = (-380, -260)                                                        # the door from the left gallery's end
    WMF = (Vector((-XU, TY0, 0)), Vector((1, 0, 0)), Vector((0, -1, 0)))
    xs_ = [-XU + (XU + MX) * k_ / 8 for k_ in range(9)]
    for xa, xb in zip(xs_, xs_[1:]):                                          # over the door's head, its top following
        poly("stucco", [Vector((xa, TY0, ZG + 202)), Vector((xb, TY0, ZG + 202)), Vector((xb, TY0, ZR(xb))), Vector((xa, TY0, ZR(xa)))])   # the roof
    face("stucco", WMF, 0, XU + MX, ZG, ZG + 202, [(MGD[0] + XU, MGD[1] + XU, ZG, ZG + 202)])
    opening_frame(WMF, MGD[0] + XU, MGD[1] + XU, ZG, ZG + 202, TT, both=True)
    for zz in (ZG + 13, T1): wall_rail(WMF, 0, XU + MX, zz, [(MGD[0] + XU, MGD[1] + XU, ZG, ZG + 202)])
    wall_beam(WMF, (XU + MX - 9, ZG), (XU + MX - 9, ZR(MX + 9)), w=18, deep=8)
    # the passage inside, floor to ceiling at T1: its two inner walls (the hall's left and back walls are its others)
    box("planks", (-XU, TY0, ZG - 4), (MX - 0.5, YBU, ZG)); box("wood", (-XU, TY0, ZG - 18), (MX - 0.5, YBU, ZG - 4))
    box("planks", (-XU, TY0 + TT, T1), (MX - TT, YBU, T1 + 14))
    for W, L, hs in (((Vector((MX - TT, YBU, 0)), Vector((0, -1, 0)), Vector((-1, 0, 0))), YBU - TY0 - TT, []),
                     ((Vector((MX - TT, TY0 + TT, 0)), Vector((-1, 0, 0)), Vector((0, 1, 0))), XU + MX - TT,
                      [(MX - TT - MGD[1], MX - TT - MGD[0], ZG, ZG + 202)]),
                     ((Vector((-XU, YBU, 0)), Vector((1, 0, 0)), Vector((0, -1, 0))), XU + MX - TT, [])):   # (and its back:
                                                                                         # the hall's back wall stops at the mirror)
        face("stucco", W, 0, L, ZG, T1, hs)
        for zz in (ZG + 12, T1 - 12): wall_rail(W, 0, L, zz, hs, w=22)
    # the passage's dead end past the tavern gallery's door, the guild's display (a trophy or display
    # case): vanilla's angled display case against the back wall (its viewer at local -y, its back at +30, 8.5 off the
    # wall for its rails), two of vanilla's weapons made for display laid in it about 57 over its foot as vanilla sets a
    # case's contents (each lies along its local y from its grip: the greatsword -27..87, the warhammer -37..58), and a
    # candle sconce over it
    YDC = YBU - 8.5 - 30
    # (2026-10-29, a locked display case with valuable weapons inside: the Nord Hero Sword and War Axe, locked, the GM
    # holding the key (Expert, as Jorrvaskr's cases, the guild's), the
    # Ebony greatsword and Glass warhammer removed). The real weapons, takeable once open, lie where the display pair lay, on
    # the case's bed (54 over its foot, by the old pair's own measured undersides): the sword (-14.8..64.5 along its local
    # y, 1.6 under its middle) in front, the axe (-13.2..39.5, 1.8) behind it, each centred on the case and a little off
    # square; "don't havok settle", as vanilla's cased weapons
    piece("meshes/clutter/displaycases/displaycaselgangled01.nif", "DisplayCaseLgAngled01", (-316, YDC, ZG), 0,
          owner="gm", lock="Expert", lock_key="AGHall2DisplayCaseKey")   # (the weapons on show are the guild master's: the hall's
                                                                                    # theft rules, 2026-10-27)
    # (2026-10-29: an exception to the rule of natural misalignment for clutter: weapons on display are placed
    # meticulously) square to the case, each centred on its length
    # (the sword's 79, the axe's 53) and the pair spaced evenly about the case's middle (2 before YDC)
    piece("meshes/weapons/nordhero/nordherosword.nif", "NordHeroSword", (-316 - 24.9, YDC - 14, ZG + 54 + 1.6 + 0.15), 90,
          owner="gm", settled=True)
    piece("meshes/weapons/nordhero/nordherohandaxe.nif", "NordHeroWarAxe", (-316 - 13.2, YDC + 10, ZG + 54 + 3 + 1.8 + 0.15), 90,
          owner="gm", settled=True)
    piece("meshes/clutter/imperial/impwallsconcecandle01.nif", "ImpWallSconceCandle01", (-316, YBU - 2, ZG + 150), 270, 1.7)
    NEW_LIGHTS.append((-316, YBU - 26, ZG + 180, 1.0e6, (1.0, 0.7, 0.42), "candle", 0, -0.8))   # (the walk of 2026-10-30, a bit too bright: a candle's 1.7 in a plaster box of three walls)
    PLAN.append({"t": "wall", "level": 1, "a": [MX - TT / 2, TY0], "b": [MX - TT / 2, YBU], "gaps": []})
    PLAN.append({"t": "door", "level": 1, "a": [MGD[0], TY0], "b": [MGD[1], TY0]})
    PLAN.append({"t": "corridor", "level": 1, "r": [-XU, TY0 + TT, MX - TT, YBU]})
gw = room_walls(-XU, YFU, XU, YBU)
for (W, L), yy in ((gw["front"], YFU), (gw["back"], YBU)):                  # the gable ends, up to the roof's underside
    o, r, n = W
    xe_ = JX if (TOWER2 and n.y < 0) else XU                                  # (U: the back one stops at the tower)
    x0_ = -TX0 if (HEARTH and n.y < 0) else -XU                               # (W: and at the mirror)
    xs = [x0_ + i * (xe_ - x0_) / 24 for i in range(25)]
    for xa, xb in zip(xs, xs[1:]):
        za, zb = ZR(xa), ZR(xb)
        pts = [Vector((xa, yy, ZWP)), Vector((xb, yy, ZWP)), Vector((xb, yy, zb)), Vector((xa, yy, za))]
        poly("stucco", pts if n.y < 0 else [pts[1], pts[0], pts[3], pts[2]])
    box("wood", (x0_, yy - 10 if n.y < 0 else yy, ZWP - 14), (xe_, yy + 10 if n.y > 0 else yy, ZWP + 14))   # (2 proud of the rail under it)
# the roof's underside: boards on rafters, the trusses and a ridge beam: the hall's ceiling, open to the ridge
CHW, CHY0 = 64, YB - 70          # W: the great hearth's chimney breast, its half width and its face (it rises to the ridge)
for sx in (-1, 1):
    a_, b_ = Vector((sx * XU, YFU, ZWP)), Vector((0, YFU, ridge - 18))
    spans = [(YFU, TY0, XU), (TY0, YBU, JX)] if (TOWER2 and (sx > 0 or HEARTH)) else [(YFU, YBU, XU)]   # (U: the tower's corner is not the hall's)
    for ya_, yb_, xe_ in spans:
        pts = [Vector((sx * xe_, ya_, ZR(xe_))), Vector((sx * xe_, yb_, ZR(xe_))), Vector((0, yb_, ridge - 18)), Vector((0, ya_, ridge - 18))]
        poly("planks", pts if sx < 0 else [pts[1], pts[0], pts[3], pts[2]])
    for k_ in range(0, 12):
        yy = YFU + 40 + k_ * (YBU - YFU - 80) / 11
        # (the walk of 2026-11-13: the rearmost sat oddly offset from the trim and the chimney stack, so it goes flush
        # against the wall and on to the stack: it stood 40 off the back wall and stopped at the breast's half width
        # (64), 23-36 short of the stack, which up here is 28 a side. Now against the wall, 0.5 into it, and run into the stack, 14 inside
        # its face, so its square-cut end, slanted across the slope, is buried in the stone)
        if HEARTH and k_ == 11: yy = YBU - 6 + 0.5
        xe_ = JX if (TOWER2 and (sx > 0 or HEARTH) and yy > TY0) else XU
        p0_, p1_ = Vector((sx * xe_, yy, ZR(xe_) - 2)), Vector((0, yy, ridge - 20))
        if HEARTH and yy > CHY0: p1_ = p0_ + (p1_ - p0_) * ((xe_ - (14 if k_ == 11 else CHW)) / xe_)   # (W: it stops at the chimney breast)
        beam(p0_, p1_, 12, 16, (-sx * TP / math.hypot(1, TP), 0, -1 / math.hypot(1, TP)))
box("wood", (-16, YFU, ridge - 60), (16, CHY0 if HEARTH else YBU, ridge - 18))
for yy in (150, 420, 690, 960): truss(yy, JX if (TOWER2 and yy > TY0) else XU, TX0 if (HEARTH and yy > TY0) else None)
if os.environ.get("AG_PURLINS", "1") == "1":     # (front wall to the tower's front wall, where the slope's own corner ends)
    # (their front ends flush with the front wall, not 2 into it: navgen's grid starts at the cell's outermost face, and that 2 moved
    # every vertex of the navmesh, narrowing the tower stair's top and the basement door's landing under the connect gate's 40)
    for sx in (-1, 1): purlin(sx, YFU, (TY0 + 2) if (TOWER2 and (sx > 0 or HEARTH)) else YBU + 2)
# the office over the entrance: its wall to the hall, its door, its flat roof (a loft over it)
OFF1 = 260
LDX = (113, 209) if HEARTH else (-60, 60)       # the library's door, hall x (W, 2026-10-26: from the wall's middle to the
                                                # landing's right end, so the room makes sense
                                                # and its walls can take bookshelves)
PLAN.append({"t": "room", "level": 1, "name": "office", "r": [-XU, YFU, XU, OFF1]})
PLAN.append({"t": "door", "level": 1, "a": [LDX[0], OFF1], "b": [LDX[1], OFF1]})
box("planks", (-XU, YFU, ZG - 4), (XU, OFF1, ZG)); box("wood", (-XU, YFU, ZG - 18), (XU, OFF1, ZG - 4))
if HEARTH:   # W: joists under it too, on the landing's lines, and a beam under its wall carrying both (the timbers on the
             # ceiling over the main doors looked like unfinished floor joists: only the galleries had
             # them, so the landing's stopped in mid-air where this floor began)
    for k_ in range(-3, 10):
        q_ = -TX0 + 32 + 64 * k_
        if -XG + 16 <= q_ <= XG - 16: box("wood", (q_ - 7, YF + 12.5, ZG - 40), (q_ + 7, OFF1 - 8, ZG - 18))   # (in the walls' span)
    box("wood", (-XG + 0.5, OFF1 - 8, ZG - 56), (XG - 0.5, OFF1 + 8, ZG - 18.5))
oW = (Vector((XU, OFF1, 0)), Vector((-1, 0, 0)), Vector((0, 1, 0)))
OW1 = XU + 216 if TAVERN_OPEN else 2 * XU                 # D: the wall stops at the left gallery's edge; the corner behind is gallery
ODH = (XU - LDX[1], XU - LDX[0], ZG, ZG + DOOR_H) if HEARTH else (XU - 60, XU + 60, ZG, ZG + 200)   # (u = XU - x)
DCU = (ODH[0] + ODH[1]) / 2
face("stucco", oW, 0, OW1, ZG, T1 + 20, [ODH])            # (W: the library's door a real one since 2026-10-26; its painted
if not HEARTH: quad_on(oW, XU - 60, ZG, XU + 60, ZG + 200, 1.0, *ATLAS["archdoor"], kind="archdoor")   # one was see-through
# (the trim walk of 2026-11-07: the door's posts stood 15 out from its opening, the wall's own posts at its middle +-72 with a
# lintel between; now a door frame at the opening's edges as every other door's, the wall's posts at its ends only)
for u in ((9, OW1 - 9) if HEARTH else (9, DCU - 72, DCU + 72, OW1 - 9)): wall_beam(oW, (u, ZG), (u, T1 + 20), w=18, deep=8)            # from inside)
for zz in (ZG + 10, T1 + 10): wall_rail(oW, 0, OW1, zz, [ODH], w=22, deep=10)   # (stopped at the door: a sill crossed it)
if HEARTH:
    door_head(oW, ODH[0], ODH[1], ODH[2], ODH[3])                       # its frame at the opening's edges (2026-11-07)
    door_leaf((LDX[0], OFF1 - TT / 2), (LDX[1], OFF1 - TT / 2), ZG, (0, -1), "AGHall2LibraryDoor")
if TAVERN_OPEN:                                           # the notch: the office's corner given to the gallery (y 160..260)
    NOTCH = (-XU, 160, -216, OFF1)
    for W, L in (((Vector((-216, OFF1, 0)), Vector((0, -1, 0)), Vector((-1, 0, 0))), OFF1 - 160),
                 ((Vector((-216, 160, 0)), Vector((-1, 0, 0)), Vector((0, 1, 0))), XU - 216)):
        face("stucco", W, 0, L, ZG, T1 + 20)
        for zz in (ZG + 10, T1 + 10): wall_beam(W, (0, zz), (L, zz), w=22, deep=10)
        wall_beam(W, (L - 9, ZG), (L - 9, T1 + 20), w=18, deep=8)
    # (the walk of 2026-11-13, from the gallery: two trim gaps here. Under the loft's floor the notch's ceiling is low (T1 + 20),
    # and the hall's left wall's rail at T1 (5 deep, its top T1 + 11.5) left a strip of plaster 8.5 tall under it, seen as a light line
    # along the rail; the back rail's end, 1.5 short of that wall, left a slit over it. A wall plate from the rail to the ceiling, the
    # notch's depth and the loft floor's edge (y 160..OFF1 + 11), closes both; its top 0.4 into the floor's slab)
    box("wood", (-XU, 160, T1 + 11.5), (-XU + 5, OFF1 + 11, T1 + 20.4))
    # (2026-11-13, the gap's other side: the notch's outside corner at (-216, OFF1), where the
    # notch wall's rails end 1.5 short (y 258.5) and the office's hall-side head beam starts 2 short (x -214): an open pocket at the
    # corner at both rails' heights. A block at each returns the rail round the corner, abutting both ends)
    for z0_, z1_ in ((ZG - 0.5, ZG + 20.5), (T1 - 0.5, T1 + 20.5)):
        box("wood", (-226, OFF1 - 1.5, z0_), (-214, OFF1 + 10, z1_))
    PLAN.append({"t": "notch", "level": 1, "r": list(NOTCH)})
if HEARTH:   # W: the office's walls from inside, TT behind their hall and notch faces (the first walk: the guild master's office
             # was broken: its walls had faces on the hall's side only, so from inside one saw through them), and the door's reveals
    OFI = OFF1 - TT
    for W, L, hs in (((Vector((-216 + TT, OFI, 0)), Vector((1, 0, 0)), Vector((0, -1, 0))), XU + 216 - TT,
                      [(216 - TT + LDX[0], 216 - TT + LDX[1], ZG, ODH[3])]),   # (u = x + 216 - TT)
                     ((Vector((-216 + TT, 160 - TT, 0)), Vector((0, 1, 0)), Vector((1, 0, 0))), OFI - 160 + TT, []),
                     ((Vector((-XU, 160 - TT, 0)), Vector((1, 0, 0)), Vector((0, -1, 0))), XU - 216 + TT, [])):
        face("stucco", W, 0, L, ZG, T1 + 20, hs)
        for zz in (ZG + 13, T1 + 8): wall_rail(W, 0, L, zz, hs, w=22)
        for h in hs: frame_timbers(W, h[0], h[1], h[2], h[3])
    # (the walk of 2026-11-13: another trim gap at the top of a corner: the alcove's outside corner at (-192, 136),
    # where the alcove wall's rails end 2 short of it and the library wall's start 2 past it, each 8 deep: a 10 x 10 notch
    # open at both rails. A corner block returns each rail round it, abutting both ends, its top and foot in their planes but
    # beside them, not over them)
    for zz in (ZG + 13, T1 + 8):
        box("wood", (-216 + TT - 2, 160 - TT - 8, zz - 10.5), (-216 + TT + 8, 160 - TT + 2, zz + 10.5))
    opening_frame(oW, ODH[0], ODH[1], ZG, ODH[3], TT, timbers=False)   # (the hall side's posts already frame it)
ZL = T1 + 34                                      # the loft's floor on the office's roof (W: the library; whole since its
box("planks", (-XU, YFU, T1 + 20), (XU, OFF1 + (11 if HEARTH else 10), ZL))   # small stair went for a ladder, 2026-10-26:
                                                  # its edge 1 past the wall's beam)
if not HEARTH:
    # the counter against the blind back wall, with shelves behind it; the quest board between it and the door
    CX = 200 if VARIANT == "A" else (TX0 - 6 if TOWER3 else 270)   # (V: its right end against the tower's foot)
    box("wood", (-CX, 930, 0), (CX, 975, 72)); box("trim", (-CX - 6, 924, 72), (CX + 6, 981, 80))
    PLAN.append({"t": "counter", "r": [-CX, 924, CX, 981]}); PLAN.append({"t": "shelves", "r": [-CX, YB - 40, CX, YB]})
    for zz in (40, 110, 180, 250): box("wood", (-CX, YB - 40, zz), (CX, YB, zz + 6))
    for sx in (-1, 1): box("wood", (sx * CX - 6, YB - 40, 0), (sx * CX + 6, YB, 300))
def board(x0, x1, y):
    """the quest board's stand-in, its notices on the side toward -y (the door): two posts, cork, a cap"""
    box("wood", (x0, y, 0), (x0 + 10, y + 10, 230)); box("wood", (x1 - 10, y, 0), (x1, y + 10, 230))
    box("cork", (x0 - 10, y + 2, 90), (x1 + 10, y + 8, 240)); box("wood", (x0 - 16, y, 240), (x1 + 16, y + 10, 252))
    per = max(1, int((x1 - x0 - 20) // 30))                                # notices a row, 30 apart (none overlapping)
    for i in range(2 * per):
        px = x0 + 10 + (i % per) * 30 + (i // per) * 8; pz = 110 + (i // per) * 60 + (i % 3) * 6
        box("paper", (px, y - 1, pz), (px + 22, y + 1, pz + 30))
    PLAN.append({"t": "board", "r": [x0, y, x1, y + 10]})
if os.environ.get("AG_BOARD"): board(-120, 120, 560)   # the board's stand-in (W: out of the great hall since the hall2r
                                                        # walk, its home a question for later, 2026-10-26)
# chandeliers under the trusses' tie beams
# (W since 2026-10-27, a chandelier clipped the gallery: hung low, the one on the truss at 420 met
# the front landing's edge and fascia; both now hang from the ridge beam, clear of the landing, at 540 and 790)
for yy in ((540, 790) if HEARTH else (420, 690)) + ((960,) if (TOWER3 and not HEARTH) else ()):   # (V: a third over the
    if HEARTH and os.environ.get("AG_CHAND", "low") == "low":            # counter; W: the hearth's breast is there) (W: hung
        chandelier(0, yy, 340, ridge - 60, gather=90)                    # low as the tavern's, under the galleries' eye level,
    else: chandelier(0, yy, 640, ZWP - 60)                               # as in the tavern, 2026-10-26)
    PLAN.append({"t": "chandelier", "p": [0, yy]})
if HEARTH:
    # W: (the counter under the right gallery went into the guild services room after the hall2r walk, 2026-10-26)
    # the great hearth on the back wall, one step up; its hood narrows to a breast that rises between the back windows
    # (their inner edges are 144 apart) to the ridge and out as the stack. Everything that meets the wall runs 4 into it,
    # so no face lies in the wall's plane.
    GH = os.environ.get("AG_GREAT_HEARTH", "castle")
    if GH == "castle":   # since the hall2y round (2026-10-26: real fireplace assets in place of the built
        # hearths, the main hall's first): Dragonsreach's hearth wall
        # (WRIntCastleWallStrChimney01: Whiterun's castle woods, slate and stone, 552 x 544; its face, the panels' plane, at
        # local y 118, its firebox back to 238, facing -y), at 0.76 the most the dais's bay (432) holds. It stands its back
        # on the hall's wall; a stone mass fills behind its face, round the firebox, up to the hood
        GSC, GOFF = 0.76, 4.0; yo_ = YB - GOFF - 238 * GSC   # (GOFF: its firebox back 4 off the wall: on it, the two
                                                             # flickered in game, the walk of 2026-10-26)
        piece("meshes/architecture/whiterun/wrinteriors/wrcastle/wrintcastlewallstrchimney01.nif", "WRIntCastleWallStrChimney01",
              (0, yo_, DAIS), 0, GSC)
        HW, HD = 205, GOFF + 238 * GSC - 120 * GSC + 2   # the mass: hidden behind the piece's frame, 2 behind its face
        FX0, FX1, FZ = -187, 181, DAIS + 232 * GSC + 1   # the firebox's mouth (its walls are the piece's)
        box("stone", (-HW, YB - HD, DAIS - 2), (FX0, YB + 4, DAIS + 512 * GSC)); box("stone", (FX1, YB - HD, DAIS - 2), (HW, YB + 4, DAIS + 512 * GSC))
        box("stone", (FX0, YB - HD, FZ), (FX1, YB + 4, DAIS + 512 * GSC))
        zh0, zh1 = DAIS + 512 * GSC, 440
        # its fire and its dressing as Dragonsreach has them round this hearth (research/dragonsreach: the castle kitchen's
        # refs; after the hall2ab walk the fire did not fit the fireplace, it wanted a spit or grate in front, and the
        # hearth stood empty): low fires
        # spread along the grate (its local y 133..223), not one log pile; vanilla's cooking spit across the firebox's
        # mouth (local y 75); on the mantel shelf (local y 49..100, its top at local z 249) candlesticks and a few vessels
        L_ = lambda lx, ly, lz=0: (lx * GSC, yo_ + ly * GSC, DAIS + lz * GSC)
        for ed_, (lx, ly, lz), s_ in (("FXfireWithEmbers01_lite", (-90, 161, -9), 1.51), ("FXfireWithEmbers01_lite", (14, 177, -9), 1.51),
                                      ("FXfireWithEmbers01_lite", (70, 187, -8), 1.2), ("FXfireWithEmbersLight", (-160, 176, 0), 1.7),
                                      ("FXfireWithEmbersLight", (-48, 181, -4), 1.48), ("FXfireWithEmbersLight", (150, 190, -16), 1.7)):
            piece("meshes/effects/fxfirewithembers01_lite.nif" if "lite" in ed_ else "meshes/effects/fxfirewithembers02.nif",
                  ed_, L_(lx, ly, lz), 0 if "lite" in ed_ or lx > 100 else 270, s_ * GSC, exact=True)
        piece("meshes/furniture/firespitcooking.nif", "CraftingCookingFireSpit", L_(-7, 75), 0, GSC)
        zm_ = DAIS + 249 * GSC + 0.3                                       # the mantel shelf's top
        # (2026-10-30: a few plain candles on the mantel, no candelabra or sconces: the Bannered Mare's shelf candles)
        # (2026-11-02, the front elevation plan: the left candle pair and the jug and goblet trade places, each keeping its order; the right plate
        # 26 in from the shelf's end, the candles off its very edges)
        for x_, ed_, m_, yaw_ in ((-95, "GlazedCandlesStatic02", "clutter/glazedcandlesstatic02", 30), (-69, "GlazedCandlesStatic", "clutter/glazedcandles01", 0), (150, "GlazedCandlesStatic02", "clutter/glazedcandlesstatic02", 200),
                                  (-151, "SilverJug01", "clutter/silver/silverjug01", 331), (-125, "SilverGoblet01", "clutter/silver/silvergoblet01", 6),
                                  (64, "SilverJug01", "clutter/silver/silverjug01", 191), (96, "SilverGoblet01", "clutter/silver/silvergoblet01", 200)):
            piece(f"meshes/{m_}.nif", ed_, (x_, yo_ + 74 * GSC, zm_), yaw_, owner="guild", settled=True)   # (the guild's; kept put)
        NEW_LIGHTS += [(-82, yo_ + 74 * GSC - 16, zm_ + 26, 0.6e6, (1.0, 0.72, 0.45), "candle_small"), (150, yo_ + 74 * GSC - 16, zm_ + 26, 0.6e6, (1.0, 0.72, 0.45), "candle_small")]
        # (2026-11-03, the textures session's overmantel display: a fixed weapon display, dragonbone) vanilla's plaques for a shield
        # and two swords, as WeaponRackPlaque's pivots hold them, every piece a static at 1.2 on the breast's centre panel; the textures session
        # gave them in the cell's frame with the game's own angles ("ga", as Hall2.cs writes them): the plaques' face at cell x -964.28 (hall y
        # 964.28), the swords' hilts 4 under the beam's underside (398). The yaw here is the plaques' (ga Z + 90), for the gates that read only it
        for hx_, hy_, z_, ed_, m_, ga_ in ((0, 964.28, 336, "AGHall2PlaqueShield", "clutter/weaponrack/wrplaqueshield01", (0, 0, 90)),
                                           (0, 964.28, 336, "AGHall2PlaqueLeft", "clutter/weaponrack/wrplaqueleft01", (0, 0, 90)),
                                           (0, 964.28, 336, "AGHall2PlaqueRight", "clutter/weaponrack/wrplaqueright01", (0, 0, 90)),
                                           (0, 959.16, 336, "AGHall2DisplayShield", "armor/dragonbone/dragonboneshield", (270, 90, 0)),
                                           (-24.0, 960.5, 374.11, "AGHall2DisplaySword", "dlc01/weapons/dragonbone/sword", (56.25, 270, 0)),
                                           (24.0, 960.5, 374.11, "AGHall2DisplaySword", "dlc01/weapons/dragonbone/sword", (123.75, 270, 0))):
            piece(f"meshes/{m_}.nif", ed_, (hx_, hy_, z_), ga_[2] + 90, 1.2, ga=list(ga_), owner="guild", settled=True)
        # the dais before it: a pelt on the floor before the fire (nothing to sit on: no seats by a hearth),
        # firewood on one front corner
        piece("meshes/clutter/pelts/peltfloor01.nif", "PeltFloor01", (8, 818, DAIS + 0.2), 7, 0.85)
        # (the horn candelabra on the other corner gone since the hall2bd walk: the fireplace already lights
        # that corner well)
        piece("meshes/clutter/firewood/firewoodpilemedium01.nif", "FirewoodPileMedium01", (166, 786, DAIS), 74)
    else:
        HW, HD, HO, ZM = 160, 100, 112, 340          # the surround's half width, its depth; the opening's half width; the mantel
        box("trim", (-HW, YB - HD, DAIS - 2), (-HO, YB + 4, ZM)); box("trim", (HO, YB - HD, DAIS - 2), (HW, YB + 4, ZM))   # dressed
        box("trim", (-HO, YB - HD, DAIS + 210), (HO, YB + 4, ZM))               # stone cheeks and lintel, against the rubble wall
        box("stone", (-HO, YB - 6, DAIS - 2), (HO, YB + 2, DAIS + 210))         # the firebox's back
        box("wood", (-HW - 16, YB - HD - 22, ZM), (HW + 16, YB + 4, ZM + 22))   # the mantel: one oak beam
        box("trim", (-HW - 20, YB - HD - 70, DAIS - 2), (HW + 20, YB - HD, DAIS + 4))   # the hearthstone
        zh0, zh1 = ZM + 22, 440                                                 # the hood, mantel to breast: it ends under the
                                                                            # first floor's back windows (sills 454)
    hb_ = YBU + 4
    poly("stone", [Vector((-HW, YB - HD, zh0)), Vector((HW, YB - HD, zh0)), Vector((CHW, CHY0, zh1)), Vector((-CHW, CHY0, zh1))])
    poly("stone", [Vector((-HW, hb_, zh0)), Vector((-HW, YB - HD, zh0)), Vector((-CHW, CHY0, zh1)), Vector((-CHW, hb_, zh1))])
    poly("stone", [Vector((HW, YB - HD, zh0)), Vector((HW, hb_, zh0)), Vector((CHW, hb_, zh1)), Vector((CHW, CHY0, zh1))])
    box("stone", (-CHW, CHY0, zh1), (CHW, hb_, T2 - 40))                   # the breast, up between the back windows,
    CW2 = 28                                                               # then set in at the gable (its two small
    poly("stone", [Vector((-CHW, CHY0, T2 - 40)), Vector((CHW, CHY0, T2 - 40)), Vector((CW2, CHY0, T2)), Vector((-CW2, CHY0, T2))])   # windows
    poly("stone", [Vector((-CHW, hb_, T2 - 40)), Vector((-CHW, CHY0, T2 - 40)), Vector((-CW2, CHY0, T2)), Vector((-CW2, hb_, T2))])   # are 64
    poly("stone", [Vector((CHW, CHY0, T2 - 40)), Vector((CHW, hb_, T2 - 40)), Vector((CW2, hb_, T2)), Vector((CW2, CHY0, T2))])       # apart)
    box("stone", (-CW2, CHY0, T2), (CW2, hb_, ridge))                      # and on through the roof as the stack
    # (the fourth report of 2026-11-01, proven in game by switching it off: the crescent on the stair's wall was this light, its shadow failing behind the wall at 291 from it; its shadows stay,
    # short of that wall, and a soft fire without them carries the hall's warmth)
    INT_LIGHTS.append((0, YB - 285, DAIS + 90, 6.0e6, (1.0, 0.55, 0.25), "fire_small", -100, 0.0))
    INT_LIGHTS.append((0, YB - 150, DAIS + 90, 6.0e6, (1.0, 0.55, 0.25), "fire", -483, -0.5))   # (its fade 2.5 since the hall2bd walk:
                                                                                          # the corner by it washed out)
    PLAN.append({"t": "hearth", "r": [-HW, YB - HD, HW, YB], "breast": [-CHW, CHY0, CHW, YBU]})
    # the fit-out (2026-10-26: the floating dragon skull replaced by a shield rack on the chimney
    # column with a dragonbone shield on it, the rack a working one): vanilla's coat-of-arms rack as the Hearthfire houses
    # wire it (measured: research/rack, `links`): the shield plaque, its trigger, the crossed-weapon plaques either side
    # with theirs, all six at one point and angle (the plaques' offsets are in their meshes), persistent; each rack links
    # [WRackActivator] to its trigger, each trigger [WRackTrigger] back, and the shield's trigger, unkeyworded, to the
    # starting item, which its script hangs on ShieldPivot01 on cell attach: the Dragonplate Shield (Skyrim's dragon-bone
    # one), the guild's. The plaques face their local +y: on the breast's face, centred over the hood
    RACK = (0, CHY0 - 0.5, 500)
    if os.environ.get("AG_GREAT_HEARTH", "castle") == "castle":   # (since the hall2ae walk, 2026-10-27: it hung too high
        # and came down, the rack with sconces at its sides: on the overmantel's centre panel
        # (the hearth's panels at local y 118, 2 off them), the panel's middle height)
        RACK = (0, YB - GOFF - 238 * 0.76 + 118 * 0.76 - 2, 320)
    # (the rack itself gone since 2026-10-27: once its shield went, an empty plaque was left: nothing on the overmantel's
    # centre panel now; its six references are retired, disabled)
    if os.environ.get("AG_GREAT_HEARTH", "castle") == "castle":
        # (2026-10-30: a striking piece over the fireplace, a dragon head properly mounted, not floating: Dragonsreach's mount in the
        # niche over the hood: its stone panel faces its local +y, its back at local y -20, flush on the niche's back at 990)
        piece("meshes/architecture/whiterun/wrclutter/wrdragonskullmounted01.nif", "WRDragonSkullMounted01", (0, 990 - 20 * DRAGON_S, 650), 180, DRAGON_S, exact=True)   # (the plan of 2026-10-30: its 183 of panel in to the stack's 127, x -63.5..63.5, centred where it was)
        box("wood", (-66, 975.5, 650 - 245.5 * DRAGON_S - 5), (66, 990, 650 - 245.5 * DRAGON_S + 0.2))   # (the walk of 2026-11-01, from below: its trim has no underside, made for eye level: a sill closes it)
    # the great hall dressed (2026-10-26: the main hall and its hearth, banners and the like for some life,
    # a bear), all vanilla and of the hearth's Whiterun family:
    # Dragonsreach's runner (its ends join its middle at their origins: EndR runs local -y from it, EndL +y) from the doors
    # to the dais; Hearthfire's standing bear (it faces its local +y) by the right wall's front
    # bay, turned toward the doors; a mounted bear's head (it faces its local -y, its back at 1) on the mirror's face,
    # across the dais from the guild board
    for ed_, dy_ in (("WRCastleRugEEndR", -128), ("WRCastleRugEMid01", 0), ("WRCastleRugEEndL", 128)):   # (E: the red one, 240
        piece(f"meshes/architecture/whiterun/wrclutter/{ed_.lower()}.nif", ed_, (0, 380 + dy_, 0.2), 0)    # wide, 554 long)
    # (Jorrvaskr's long banners stood either side of the front door until 2026-11-01: 49 wide, across the windows' frames once the windows had real ones, the door's frame and the window's 45 apart, so they went)
    piece("meshes/_byoh/architecture/byohhouse/trophy/byohhousetrophybear2ft01.nif", "AGHall2Bear", (280, 220, 0), 238)
    # (the left wall's sabre cat between two shields went after the hall2ab walk: they did not fit here)
    piece("meshes/clutter/deadanimals/wallmountedbear01.nif", "WallMountedBear01", (-278, TY0 - 1.5, 252), 0)
    # the guild board (the board session's v1, 2026-10-26): on the tower foot's face where the plan puts it, across the
    # right arcade's last stub (its stand-off frame clears the stub); its origin on the wall plane at its bottom middle,
    # its front toward its local -y. Its bottom at 64 for now (64, or the plan's 85)
    # Its postings rotate (the board session's v4: three variants, rotated on the hour for
    # testing): the three on one spot, B and C disabled until AGHallBoardRotate (on the marker beside them) shows the
    # hour's (Hourly; the design is a day each)
    zb_ = float(os.environ.get("AG_BOARD_Z", "64"))
    piece("meshes/adventurersguild/board/agguildboard.nif", "AGHall2GuildBoard", (358.5, TY0, zb_), 0, name="AGHall2GuildBoardRefA", persistent=True)
    for v_ in ("B", "C"):
        piece(f"meshes/adventurersguild/board/agguildboard_{v_.lower()}.nif", "AGHall2GuildBoard" + v_, (358.5, TY0, zb_), 0,
              name="AGHall2GuildBoardRef" + v_, persistent=True, disabled=True)
    # (2026-11-04: the adventurers, Caralion among them, looking the board over in the mornings; RENOWN_PLAN F) three of vanilla's idle
    # markers before it, its face at y TY0 - 21, the outer two turned in toward its middle (each faces its local +y)
    MARKERS += [("AGHallGuildBoardReadMarker1", "DBExamineIdleMarker", (292, TY0 - 76, 0), 15),
                ("AGHallGuildBoardReadMarker2", "StudyMarker", (358.5, TY0 - 80, 0), 0),
                ("AGHallGuildBoardReadMarker3", "DBExamineIdleMarker", (425, TY0 - 76, 0), 345)]
    # the daily routines' activity spots (2026-10-28, the NPC session's list from the approved schedules): the centres
    # of vanilla Sandbox packages, on the navmesh where each activity happens (their radius the NPC session's)
    MARKERS += [("AGHallSpotLibrary", "XMarkerHeading", (0, 130, ZG), 0),            # the library's floor (~300)
                ("AGHallSpotLibraryLoft", "XMarkerHeading", (0, 170, T1 + 34), 180),  # the loft, before its cases (~200)
                ("AGHallSpotGreatHall", "XMarkerHeading", (0, 450, 0), 0),         # the great hall's middle (~500)
                ("AGHallSpotDais", "XMarkerHeading", (0, 800, 20), 180),           # Willem's, on the dais (~200)
                ("AGHallSpotHearth", "XMarkerHeading", (-120, 680, 0), 0),         # the hearth's side of the hall (~300)
                ("AGHallSpotTavern", "XMarkerHeading", (-720, 616, 0), 0),         # the tavern's aisle beside its long tables (~450; between
                                                                                    # them until 2026-11-12, where the re-laid tables now stand)
                ("AGHallSpotCardTable", "XMarkerHeading", (-571, 320, 0), 180),    # by the round table under the window (~120)
                ("AGHallSpotCommonRoom", "XMarkerHeading", (916, 520, ZG), 180),   # the first floor's common room (~250)
                ("AGHallSpotAtticTable", "XMarkerHeading", (590, 480, T1 + 14), 270),   # by the attic's table (~250)
                ("AGHallSpotGallery", "XMarkerHeading", (-300, 520, ZG), 90)]      # the left gallery, at its rail (~250)
    # (the rotator dropped 2026-10-27, the board session's report after hall2ax: the script's properties live in a save,
    # so an older save's still named the board refs hall2ax dropped and never rotated the live ones; the single 3D board
    # replaces the rotation. Its marker retires, and AGHallBoardRotate.pex is no longer shipped, so a save's old instance
    # cannot bind and is cleared)
    # (2026-10-29: the rotation is a required feature and was not to be dropped) the
    # rotation is back, in AG's DLL (GuildBoard.cpp, Rotate): the day's arrangement enabled when the board loads

    def rail(a, b, z, gaps=()):
        """a balustrade from a to b (2D) on a floor at z: handrail, bottom rail, balusters every 16, newels every 128;
        gaps: (from, to) distances along it left open"""
        L = math.hypot(b[0] - a[0], b[1] - a[1]); dx, dy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        runs, s0 = [], 0.0
        for g0, g1 in sorted(gaps): runs.append((s0, g0)); s0 = g1
        runs.append((s0, L))
        for r0, r1 in runs:
            if r1 - r0 < 8: continue
            p, q = (a[0] + dx * r0, a[1] + dy * r0), (a[0] + dx * r1, a[1] + dy * r1)
            ex, ey = (5 if dx == 0 else 0), (5 if dy == 0 else 0)
            lo, hi = (min(p[0], q[0]) - ex, min(p[1], q[1]) - ey), (max(p[0], q[0]) + ex, max(p[1], q[1]) + ey)
            box("wood", (lo[0], lo[1], z + 80), (hi[0], hi[1], z + 90)); box("wood", (lo[0], lo[1], z + 8), (hi[0], hi[1], z + 16))
            n = int((r1 - r0) // 16)
            for i in range(n + 1):
                s_ = r0 + (r1 - r0) * i / max(1, n); px, py = a[0] + dx * s_, a[1] + dy * s_
                big = i % 8 == 0 or i == n; hw = 6 if big else 2.5
                box("wood", (px - hw, py - hw, z), (px + hw, py + hw, z + 80 + (14 if big else 0)))

    # W: the library loft on the office's roof, under the great window (the exterior's own "library under the great
    # window"): a balustrade to the hall, shelves along the gable wall between the second storey's windows (x +-235), and
    # since the hall2r walk a ladder up from the office's alcove (its small newel stair broke the one-stair rule: a
    # clickable ladder and hatch in this corner niche instead, 2026-10-26)
    rail((-XU + 6, OFF1 + 4), (XU - 6, OFF1 + 4), ZL)
    yb_ = YFU + 1                                                          # (1 off the wall: no face in its plane)
    for x0_, x1_ in ((-220, -8), (8, 220)):                                # two bookcases, books on the shelves left to dressing
        box("wood", (x0_ + 8, yb_, ZL), (x1_ - 8, yb_ + 6, ZL + 214))   # (between its sides)
        for xs_ in (x0_, x1_ - 8): box("wood", (xs_, yb_, ZL), (xs_ + 8, yb_ + 40, ZL + 214))
        for zz in (ZL + 4, ZL + 56, ZL + 108, ZL + 160, ZL + 206): box("wood", (x0_ + 8, yb_ + 6, zz), (x1_ - 8, yb_ + 40, zz + 8))
    INT_LIGHTS.append((236, YFU + 24, ZL + 30, 1.5e6, (1.0, 0.78, 0.55), "lamp"))   # (the lantern's, on the floor by the right case since 2026-11-13)
    PLAN.append({"t": "loft", "level": 2, "r": [-XU, YFU, XU, OFF1 + 10], "z": ZL})
    # the ladder: vanilla's farmhouse cellar ladder (FarmBTrapdoor01, a load door: a ladder up to a trapdoor, 232 to the
    # trapdoor's top) in the alcove, scaled so the trapdoor meets the office's ceiling (258 up); its own floor hatch
    # (FarmBTrapdoor02) over that trapdoor on the loft. Hall2.cs links the two, each sending one to where the other's
    # "arrive" says. Back 88 from the front wall: the window at x -328..-232 stays clear. The mesh's ladder leans from its
    # foot at local -y (-27) up to its trapdoor at +y (0..52, the middle at 26), so it is climbed from its -y side: yaw 270
    # puts the trapdoor 45 off the alcove's end wall and the foot out toward the room (until the 2026-10-26 walk it stood
    # the other way round, its rungs to the wall, facing the wrong way)
    LSC = (T1 + 20 - ZG) / 232.0
    LTX, LY = -XU + 45 + 12, 80                               # the trapdoor's middle (2026-11-03, the known faults: 8 nearer the front wall, its trapdoor
                                                              # had run 2 into the office ceiling's beam at y 128..136; 12 off the loft's side wall, its
                                                              # hatch frame had tucked 10 under the sill at x -392)
    LX = LTX + 26 * LSC                                       # the ladder's origin (its local +y is hall -x)
    piece("meshes/architecture/farmhouse/interior/basement/farmbtrapdoor01.nif", "FarmBTrapdoor01", (LX, LY, ZG), 270, LSC,
          name="AGHall2LibraryLadder", role="lib_ladder", pair="lib_hatch", arrive=(LX + 28 * LSC + 66, LY, ZG), arrive_yaw=90)
    # (the hatch sunk into the loft's floor, 2026-10-26, after the hall2t walk: it stood too proud and blocky; flush with the
    # floor now: the mesh is 18 tall from its origin; its foot now 0.5 over the library's ceiling,
    # inside the floor's 14, so 4.5 of it stands proud)
    piece("meshes/architecture/farmhouse/interior/basement/farmbtrapdoor02.nif", "FarmBTrapdoor02", (LTX, LY, T1 + 20.5), 270, 1.0,
          name="AGHall2LibraryHatch", role="lib_hatch", pair="lib_ladder", arrive=(LTX + 100, LY, ZL), arrive_yaw=90)
    PLAN.append({"t": "ladder", "p": [LX, LY], "a": 180, "to": "library"})
    # the library (the old office, 2026-10-26: its door at the landing's right end frees its walls). Since the hall2t walk
    # (six matching bookcases, the side table used as a table, no room; built-in and
    # intentional instead): Hearthfire's library shelving (NobleShelf02/03/04: one bookcase at 202, 160 and 117 high, 82 wide, 28
    # deep, open to its local -y) built in, the middle of the room left open. Everything stands 8.5 off its wall: the
    # walls' rails and posts are 8 deep
    NS_ = "meshes/furniture/noble/"
    def frieze_panels(o_, n_, u0_, u1_, z0_, z1_):
        """(2026-11-13: the built-in shelves stay, the wood texture at their top changes; of four options, C: the tavern's
        panelling) the frieze's face from z0_ to z1_ framed and panelled as the
        tavern's walls: one frame (stiles 5 wide, rails top and bottom), each panel bevelled down from it, the frame 1.6 and the field
        0.6 proud of the frieze's face; panels about 26 wide, all one width in the run. Drawn only: the frieze's box collides"""
        r_ = UP.cross(n_); W_ = (o_ + n_ * 1.6, r_, n_); SW2, BV2 = 5.0, 1.4
        m_ = max(1, round((u1_ - u0_ - SW2) / (26.0 + SW2))); pw_ = (u1_ - u0_ - SW2 * (m_ + 1)) / m_
        za_, zb_ = z0_ + SW2, z1_ - SW2
        holes_ = [(u0_ + SW2 + k_ * (pw_ + SW2), u0_ + SW2 + k_ * (pw_ + SW2) + pw_, za_, zb_) for k_ in range(m_)]
        def draw():
            face("wainframe", W_, u0_, u1_, z0_, z1_, holes_)
            # (its back, 0.05 behind it, and its two ends down to the frieze's face, as the tavern's: the leak gate saw the frame from
            # behind past the study run's end, through the 1.6 it stands proud)
            face("wainframe", (o_ + n_ * 1.55, -r_, -n_), -u1_, -u0_, z0_, z1_, [(-ub_, -ua_, za0_, zb0_) for ua_, ub_, za0_, zb0_ in holes_])
            for ue_, sg_ in ((u0_, -1), (u1_, 1)):
                q_ = [o_ + r_ * ue_ + n_ * -0.5 + UP * z0_, o_ + r_ * ue_ + n_ * 1.6 + UP * z0_, o_ + r_ * ue_ + n_ * 1.6 + UP * z1_, o_ + r_ * ue_ + n_ * -0.5 + UP * z1_]
                poly("wainframe", q_ if sg_ < 0 else q_[::-1])
            A_ = lambda u_, d_, z_: o_ + r_ * u_ + n_ * d_ + UP * z_
            for ua_, ub_, z0b_, z1b_ in holes_:
                P0 = [A_(ua_, 1.6, z0b_), A_(ub_, 1.6, z0b_), A_(ub_, 1.6, z1b_), A_(ua_, 1.6, z1b_)]
                P1 = [A_(ua_ + BV2, 0.6, z0b_ + BV2), A_(ub_ - BV2, 0.6, z0b_ + BV2), A_(ub_ - BV2, 0.6, z1b_ - BV2), A_(ua_ + BV2, 0.6, z1b_ - BV2)]
                for k_ in range(4): poly("wainframe", [P0[k_], P1[k_], P1[(k_ + 1) % 4], P0[(k_ + 1) % 4]][::-1])
                poly("wainpanel", P1)
        drawn_only(draw)
    # the right wall: one run, wall to wall (231 between the front wall's corner post and the back wall's rail: the three
    # units at 0.939), tall, low, tall; a panelled frieze over it to the ceiling, a carved cornice at its foot; over the
    # low one a recess, panelled at its back, with two shelves
    s_ = 231 / 246; xb_ = XU - 8.5; xk_ = XU - 13; xf_ = xk_ - 28 * s_    # the frieze's back, the cases' backs, their front: the
    # panelled back 2 before the wall's posts (9 deep) and the cases 2 before it (the hall2ac walk: the panel lay in the
    # posts' plane and 0.5 behind the cases' own backs, and flickered with both)
    for k_, (m_, e_) in enumerate((("nobleshelf02", "NobleShelf02"), ("nobleshelf04", "NobleShelf04"), ("nobleshelf02", "NobleShelf02"))):
        piece(NS_ + m_ + ".nif", e_, (xk_ - 18 * s_, YFU + 8.5 + 41 * s_ + 82 * s_ * k_, ZG), 90, s_)
    ya_, yb_ = YFU + 8.5, OFI - 8.5                                         # the run's ends (y -3.5, 227.5)
    # (since the hall2u walk, 2026-10-26: a back on these side shelves so they read as built in - the installs' cases are
    # open-backed, the wall showed through - and a small gap at the top closed: the frieze and cornice now come down 4 over the
    # cases' tops, and a panelled back runs behind the whole run, right behind the cases, before the wall's posts)
    box("wainframe", (xf_, ya_, ZG + 202 * s_ - 4), (xb_, yb_, T1 + 19.5))   # the frieze (the panelling's wood since 2026-11-13), panelled over its cornice
    frieze_panels(Vector((xf_, 0, 0)), Vector((-1, 0, 0)), -yb_, -ya_, ZG + 202 * s_ + 8, T1 + 19.5)
    box("trim", (xf_ - 3, ya_, ZG + 202 * s_ - 4.5), (xf_ + 2, yb_, ZG + 202 * s_ + 8))   # its cornice
    box("base", (XU - 11, ya_, ZG), (XU - 10.5, yb_, ZG + 202 * s_ - 3))      # the back, 2 before the wall's posts
    yr0_, yr1_ = ya_ + 82 * s_, ya_ + 164 * s_                              # the recess over the low unit
    box("base", (XU - 11.5, yr0_, ZG + 117 * s_ + 0.5), (XU - 10.5, yr1_, ZG + 202 * s_ + 0.5))
    for zz in (ZG + 117 * s_ + 30, ZG + 117 * s_ + 56): box("wood", (xf_ + 1, yr0_ + 0.5, zz), (XU - 12, yr1_ - 0.5, zz + 3))
    # the back wall: the study, a second run from the corner: a tall case, a desk in a niche (NobleDesk01, 90 wide: the
    # niche's width) with two shelves over it on a panelled back, a tall case; one frieze over all three; a chair
    yc_ = OFI - 13 - 18                                                     # (the cases' origins: their backs 2 before the panel)
    for x_ in (-142.5, 29.5): piece(NS_ + "nobleshelf02.nif", "NobleShelf02", (x_, yc_, ZG), 0)
    box("wainframe", (-183.5, OFI - 41, ZG + 198), (70.5, OFI - 8.5, T1 + 19.5))     # (down over the cases' tops, as the right
    frieze_panels(Vector((0, OFI - 41, 0)), Vector((0, -1, 0)), -183.5, 70.5, ZG + 210, T1 + 19.5)
    box("trim", (-183.5, OFI - 44, ZG + 197.5), (70.5, OFI - 39, ZG + 210))     # wall's; a back behind the run)
    box("base", (-183.5, OFI - 11, ZG), (70.5, OFI - 10.5, ZG + 199))
    piece(NS_ + "nobledesk01.nif", "NobleDesk01", (-56.5, OFI - 13 - 12, ZG), 0)    # (its back at local +12)
    box("base", (-101.5, OFI - 11, ZG + 63.5), (-11.5, OFI - 10.5, ZG + 202.5))     # the niche's back
    for zz in (ZG + 120, ZG + 160): box("wood", (-101, OFI - 39, zz), (-12, OFI - 11.5, zz + 3))
    # (side-entry at the desk: 2026-11-07, front-entry chairs facing tables stand their sitters up into them. 2026-11-13, for
    # the NPC session, so Merila and Zhasim use the library: vanilla's writing chair, its keyword isWritingChair, so whoever
    # sits here writes; the same side-entry, spot and facing)
    piece("meshes/furniture/common/commonchair01.nif", "AGHall2WritingChair", (-56.5, 136, ZG), 0, name="AGHallLibraryDeskChair")   # (Hall2.cs: CommonWritingChair01LR named)
    # and things to use (the same request): vanilla's browse markers before the two tall cases flanking the desk, each 8-10 further out
    # than first planned so it stands 31-35 off the writing chair's side entries (x -118.5, 5.5), and a study marker at the lectern; each facing
    # what it serves (layout yaw 0 faces +y)
    MARKERS += [("AGHallLibraryBrowseA", "BrowseIdleMarker", (-150, 170, ZG), 0), ("AGHallLibraryBrowseB", "BrowseIdleMarker", (40, 170, ZG), 0),
                ("AGHallLibraryBrowseC", "BrowseIdleMarker", (150, 55, ZG), 180), ("AGHallLibraryStudyD", "StudyMarker", (-150, 55, ZG), 180)]
    # the front wall, between the balcony door and the windows (126 each side): a low case on the right, a lectern on the
    # left, its reader facing the wall and the window's light
    piece(NS_ + "nobleshelf04.nif", "NobleShelf04", (150, YFU + 13 + 18, ZG), 180)
    box("base", (109, YFU + 10.5, ZG), (191, YFU + 11, ZG + 116))       # (its back, as the runs': 2 before the posts)
    piece(NS_ + "noblelectern01.nif", "NobleLectern01", (-150, YFU + 17 + 14, ZG), 180)
    # its books and its study (the clutter pass, 2026-10-27), as vanilla's libraries keep theirs: the cases full but not
    # packed (research/library: the Arcanaeum's bookcases are meshes with their books in them; its readable books lie on
    # its tables), so the cases hold the guild's own unreadable books, and the low case by the lectern is the reading
    # shelf: vanilla's field guides, readable, the guild's (the beasts and the places its work takes it to). Every board
    # measured from its mesh (NobleShelf02's at 15.5, 61, 103.7, 146.4, local x +-34, y -7..14.5; NobleShelf04's at 15.5,
    # 61; the right wall's at 0.939)
    LS = s_                                                   # (the right wall's run: its cases at y 35, 112, 189)
    for k_, yc2_ in enumerate((35.0, 112.0, 189.0)):
        zs_ = (15.5, 61, 103.7, 146.4) if k_ != 1 else (15.5, 61, 117.1)
        for j_, zb_ in enumerate(zs_):
            if k_ == 1 and j_ == 2: break                     # (the low case's top: in the recess, below)
            room_ = ((zs_[j_ + 1] if j_ + 1 < len(zs_) else 202) - zb_) * LS - 3
            shelf_books((366, yc2_ - 30), (366, yc2_ + 30), ZG + zb_ * LS, 0, f"R{k_}{j_}", room=room_)
    shelf_books((366, 80), (366, 144), ZG + 117.1 * LS, 0, "Rtop", room=26, fill=0.6)   # (the low case's top, under the recess)
    # the recess's boards (x 354..380, y 74..150; 23 and 17 clear: too low for books stood): a stack, a journal and notes
    # below, a rolled map above (55 long: along the recess)
    for k_, bk_ in enumerate(("Book05a", "Book03", "Book01")):
        piece(f"meshes/clutter/books/{LIB_BOOKS[bk_]}.nif", "AGHall2" + bk_, (367, 92, ZG + 142.9 + 2.15 + 4.15 * k_), (k_ * 7) % 9 - 4, exact=True, bake="library")
    piece("meshes/clutter/books/journallowpoly01.nif", "AGHall2Journal", (367, 122, ZG + 142.9 + 1.0), 6, exact=True, bake="library")
    for k_ in range(2):
        piece(f"meshes/clutter/books/note0{k_ + 3}.nif", f"AGHall2Note0{k_ + 3}", (366 + k_ * 0.8, 139, ZG + 142.9 + 0.35 + 0.3 * k_), 92 + k_ * 5, exact=True, bake="library")
    piece("meshes/clutter/quest/tgparchment01.nif", "PaperRoll", (367, 112, ZG + 168.9 + 2.8), 90, owner="guild", settled=True)
    for xc2_ in (-142.5, 29.5):                               # the back wall's two cases (books to -y)
        for j_, zb_ in enumerate((15.5, 61, 103.7, 146.4)):
            room_ = ((15.5, 61, 103.7, 146.4, 202)[j_ + 1] - zb_) - 3
            shelf_books((xc2_ - 31, 208.5), (xc2_ + 31, 208.5), ZG + zb_, 270, f"B{xc2_}{j_}", room=room_)
    for j_, zb_ in enumerate((123, 163)):                     # the desk niche's two shelves
        shelf_books((-99, 211), (-14, 211), ZG + zb_, 270, f"N{j_}", room=(37, 32)[j_], fill=0.7)
    # the reading shelf (the front wall's low case, books to +y): the field guides, readable
    # (only readable books on it: a dummy among them would be one a player tries to read)
    FIELD = [("Book2CommonTrollSlaying", "basicbook03"), ("Book2CommonGiantsAndMammoths", "basicbook03"), ("Book2CommonHagravens", "basicbook03"),
             ("Book2CommonOnIceWraiths", "basicbook06"), ("Book3ValuableFalmer", "basicbook06"), ("Book3ValuableDwarvenAutomatons", "basicbook03"),
             ("Book4RarePostingoftheHunt", "basicbook01"), ("Book4RareLycanthropicLegendsOfSkyrim", "book02lowpoly02"),
             ("Book1CheapNineHolds", "basicbook03"), ("Book3ValuableThereBeDragons", "basicbook06"), ("Book2CommonBookofDaedra", "book02lowpoly"),
             ("Book2CommonNordsOfSkyrim", "basicbook06"), ("Book2CommonCatsOfSkyrim", "basicbook03"), ("Book3ValuableSkyrimRuleOutsiderView", "book02lowpoly02")]
    shelf_books((122, 15.5), (180, 15.5), ZG + 61, 90, "F1", room=50, real=FIELD[:8], only_real=True)
    shelf_books((122, 15.5), (180, 15.5), ZG + 15.5, 90, "F0", room=42, real=FIELD[8:], only_real=True)
    piece("meshes/clutter/silver/silvercandlestick03.nif", "SilverCandleStick03", (175, 14, ZG + 117.1), 0)
    # the lectern: Amongst the Draugr laid open to the reader... closed, on its slope (30 deg, rising away from the reader:
    # local y -20.6..12.2, z 89.4..106.7; the book on its middle, its back on the slope)
    piece("meshes/clutter/books/book02lowpoly02.nif", "Book3ValuableAmongstTheDraugr", (-150, YFU + 31 + 5.3, ZG + 100.8), 180, rx=330,
          exact=True, owner="guild", settled=True)
    # the study's desk (NobleDesk01: its top 63.3, x -101..-12, y 162..223.5; its reader on the chair at y 136): a candle at
    # the back, the Explorer's Guide out, a journal open with notes beside it, ink and quill, a pile of books, papers
    DZ = ZG + 63.3
    piece("meshes/clutter/silver/silvercandlestick01.nif", "SilverCandleStick01", (-91, 211, DZ), 0)
    NEW_LIGHTS.append((-91, 211, DZ + 52, 0.4e6, (1.0, 0.72, 0.45), "candle_small"))
    piece("meshes/clutter/books/basicbook04a.nif", "Book2CommonExplorersGuideToSkyrim", (-84, 182, DZ + 2.2), 15, exact=True, owner="guild", settled=True)
    piece("meshes/clutter/books/journallowpoly01.nif", "AGHall2Journal", (-62, 182, DZ + 1.0), 4, exact=True, bake="library")
    for k_ in range(3):
        piece(f"meshes/clutter/books/note0{k_ + 1}.nif", f"AGHall2Note0{k_ + 1}", (-43 + k_ * 0.8, 184 + k_ * 0.6, DZ + 0.35 + 0.3 * k_), 80 + k_ * 5, exact=True, bake="library")
    piece("meshes/clutter/common/inkwell01.nif", "Inkwell01", (-21, 180, DZ), 0, owner="guild", settled=True)
    piece("meshes/clutter/common/quill01.nif", "Quill01", (-31, 169.5, DZ + QUILL_LIE_Z), 84, owner="guild", settled=True, rx=90)   # (along
    # the desk's front, between the notes and the well: x -47..-15 of its -101..-12, y 169.5 of its 162..223.5)
    for k_, bk_ in enumerate(("BookLarge2", "Book04", "Book05a")):   # (a pile at the back, 3 short of the case and the niche's back)
        piece(f"meshes/clutter/books/{LIB_BOOKS[bk_]}.nif", "AGHall2" + bk_, (-32, 209, DZ + (3.4 if k_ == 0 else 6.9 + 4.15 * (k_ - 1) + 2.1)), 90 + (k_ * 7) % 9, exact=True, bake="library")
    # the loft's two cases (boards at ZL + 12, 64, 116, 168, their tops ZL + 214; x -212..-16 and 16..212; open to +y):
    # its older stock
    for x0_, x1_ in ((-210, -18), (18, 210)):
        for j_, zb_ in enumerate((12, 64, 116, 168)):
            shelf_books((x0_, 18), (x1_, 18), ZL + zb_, 90, f"L{x0_}{j_}", room=41, fill=0.75)
    # its light (2026-10-27: the lanterns that stood on the cases' tops were out of anyone's reach, so the loft is lit
    # another way, a hanging lantern): a candle lantern on a chain from the ridge
    # beam, before the cases, its top under the truss's tie beam's level (that beam, at y 150, is only 177 over the floor
    # and hid a lantern hung higher), its foot 148 up, over heads; the chain an iron rod to the ridge beam's underside.
    # (Since the hall2bd walk's rule, hang_check.py: over the loft's walkway its foot is 200 up, clear of every head; the tie
    # beam at y 150 hides it from the far end of the loft, which is the trade the rule makes)
    # (the walk of 2026-11-13: the hanging lantern read wrong here, so it sits on the floor as a person would have left
    # it: set down on the boards by the right case's end, against the front wall, a little turned, off the walkway: its
    # box (18 x 18, 43 tall, its foot 1.7 under its origin; turned 23, 11.8 from its middle each way) 4 off the case's side, 12 off the wall: its record's bounds, taller than the mesh, reached 7 into the wall at 4)
    piece("meshes/clutter/common/candlelanternwithcandle01.nif", "CandleLanternwithCandle01", (236, YFU + 24, ZL + 1.66 + 0.15), 23, owner="guild")
    # the loft's chest at its empty end (x 220..392): a retired member's armour and letter (Hall2.cs's
    # AGHall2LegacyChest: the guild's, so a member takes from it freely), its back to the end wall (its lid opens to
    # its local +y, as the attic's chests stand: here toward the loft, -x), under the end's window
    # (2026-11-13: slid 28 toward the window so the truss's post at y 150, now to the floor, stands clear: its 98 along the wall, y 35..133)
    piece("meshes/clutter/upperclass/upperchest01.nif", "AGHall2LegacyChest", (XU - 8.5 - 26.5, 84, ZL), 270, name="AGHall2LegacyChestRef", owner="guild")

# ---------------------------------------------------------------- galleries and stairs, by variant
gal = []
if VARIANT == "A":
    gallery(-XU, XU, GB0, YBU, [((-XG + STAIR_W, GB0), (XG - STAIR_W, GB0))], posts=[(-150, GB0), (150, GB0)])
    stair(-XG, -XG + STAIR_W, 236, GB0, side=-1)
    stair(XG - STAIR_W, XG, 236, GB0, side=1)
elif VARIANT == "B":
    gallery(-XU, XU, GB0, YBU, [((-216, GB0), (XG - STAIR_W, GB0))], posts=[(-216, GB0), (60, GB0)])
    gallery(-XU, -216, OFF1, GB0, [((-216, OFF1), (-216, GB0))], posts=[(-216, OFF1 + 20), (-216, 560)])
    stair(XG - STAIR_W - 50, XG, 236, GB0, side=1)
elif HEARTH:   # W: the galleries end at the tower and the mirror. Carved brackets off the arcades' piers carry them (the
               # third reference): two a side since the hall2r walk (2026-10-26: the posts replaced by a second
               # set of the same side-wall braces), on the piers either side of the middle arch
    FL = OFF1 + 160                                           # the front landing, 160 deep (to the truss at 420)
    for sx in (-1, 1):
        x0_, x1_ = sorted((sx * TX0, sx * XU))
        gallery(x0_, x1_, OFF1, TY0, [((sx * TX0, FL), (sx * TX0, TY0))], fascia=64, fw=12, joist_at=W_PIER)   # (a joist over its bracket)
    gallery(-TX0, TX0, OFF1, FL, [((-TX0, FL), (TX0, FL))], fascia=64, fw=12)
    for sx in (-1, 1):
        # (OFF1: the plan of 2026-10-30, one put back since the arches went from 3 to 2: on the side wall under the cross beam, before the first arch)
        for yb_ in (W_PIER, OFF1):                            # the pier between the arches (two arches: 485..535; three: 410..460, (560..610's went after the
                                                              # palette study: 2 of the four braces dropped)
            bracket((sx * (XG - 0.5), yb_), (-sx, 0), (0, 1), ZG - 40.5, (XG - TX0 + 6) * BR["reach"], 250 * BR["drop"],
                    thick=BR["thick"], t=BR["t"], pendant=True)
            PLAN.append({"t": "bracket", "p": [sx * XG, yb_]})
    PLAN.append({"t": "void", "level": 1, "r": [-TX0, FL, TX0, YBU]})
else:
    FL = OFF1 + 128                                           # the front landing, before the office door
    if TOWER3:   # V: no back gallery (the tower's foot is its right end): the left one runs on to the back wall, the
        gallery(-XU, -216, OFF1, YBU, [((-216, FL), (-216, YBU))], posts=[(-216, FL), (-216, 622), (-216, GB0)])   # hall
        gallery(216, XU, OFF1, TY0, [((216, FL), (216, TY0))], posts=[(216, FL), (216, 622)])   # opens to its back wall
    else:
        gallery(-XU, JX, GB0, YBU, [((-216, GB0), (216, GB0))], posts=[(-216, GB0), (216, GB0)])   # (U: JX, the moved wall)
        gallery(-XU, -216, OFF1, GB0, [((-216, FL), (-216, GB0))], posts=[(-216, FL), (-216, 622)])
    if TOWER3: pass
    elif TOWER2:
        gallery(216, XU, OFF1, TY0, [((216, FL), (216, TY0))], posts=[(216, FL), (216, 622)])
        gallery(216, JX, TY0, GB0, [((216, TY0), (216, GB0))])
    else: gallery(216, XU, OFF1, GB0, [((216, FL), (216, GB0))], posts=[(216, FL), (216, 622)])
    gallery(-216, 216, OFF1, FL, [((-216, FL), (216, FL))])
    PLAN.append({"t": "void", "level": 1, "r": [-216, FL, 216, YBU if TOWER3 else GB0]})

# ---------------------------------------------------------------- the wings' ground floors, seen through the doorways
NICHE_W = (772, 886, 240)                               # W: the back bar's niche through the hall's wall: y, its crown (the
                                                        # lane's full width since the hall2ad walk; was 784..874)
for sx, name in ((-1, "L"), (1, "R")):
    x0, x1 = sorted((sx * PX1, sx * (PX1 + 1060 - TS)))
    tower = TOWER_STAIR and sx > 0                       # T, D: the tower's foot stands in this wing's back corner, x 380..680, y 760..
    CGX = BRF if HEARTH else None                        # W: the cross gables' bays are rooms now (the kitchen, the services'
                                                         # backroom, 2026-10-26): inside they reach the cross gable's front, y 186
    if tower:
        box("planks", (x0, 210, -4), (x1, TY0, 0)); box("planks", (TX1, TY0, -4), (x1, 890, 0))
        if CGX: box("planks", (CGX, 186, -4), (x1, 210, 0))
    elif HEARTH and sx < 0:                              # W: the kitchen's stone flags behind the tavern's partition
        box("planks", (-1100, 210, -4), (x1, 890, 0)); box("floor", (x0, 186, -12), (-1100, 890, 0))
    else: box("planks", (x0, 210, -4), (x1, 890, 0))
    cx0, cx1 = x0, x1                                    # the ceiling's extent (W: it stops where the galleries over the
    if HEARTH: cx0, cx1 = (x0, -XU) if sx < 0 else (XU, x1)   # wall's top begin: they shared their planes; ending 0.5 short
                                                              # left a slot over the wall, 2026-10-25: their ends meet back to back)
    well = (SW0, SW1, 300, 860) if (VARIANT == "C" and sx > 0) else ((PX1, TX1, TY0, 890) if tower else None)   # C: the stair's well
    if TAVERN_OPEN and sx < 0: well = (-1068, -XU - TT, 210, 890)    # D: open above the tavern; its galleries' floors are its low ceilings
    if well:
        for a_, b_, c_, d_ in ((cx0, max(cx0, well[0]), 210, 890), (min(cx1, well[1]), cx1, 210, 890), (max(cx0, well[0]), min(cx1, well[1]), 210, well[2]), (max(cx0, well[0]), min(cx1, well[1]), well[3], 890)):
            if b_ - a_ > 1 and d_ - c_ > 1: box("wood", (a_, c_, 400), (b_, d_, 414))
    else: box("wood", (cx0, 210, 400), (cx1, 890, 414))
    if CGX: box("wood", (x0, 186, 400), (-1100, 210, 414)) if sx < 0 else box("wood", (CGX, 186, 400), (x1, 210, 414))   # (W: over the bays)
    for k_ in range(int((cx1 - cx0) // 128) + 1):
        xx = cx0 + 64 + 128 * k_
        if xx >= cx1: continue
        ya_ = 186.5 if (CGX and (xx + 12 <= -1100 or xx - 12 >= CGX)) else 210.5   # (W: on over the bays)
        if well and well[0] - 12 <= xx <= well[1] + 12:
            if well[2] > 212: box("wood", (xx - 12, ya_, 370), (xx + 12, well[2] - 0.5, 399.5))   # (none where the well
            if well[3] < 888: box("wood", (xx - 12, well[3] + 0.5, 370), (xx + 12, 889.5, 399.5))   # runs wall to wall: 1 long, inside out)
        else: box("wood", (xx - 12, ya_, 370), (xx + 12, 889.5, 399.5))   # (0.5 short of the walls and the floor over them)
    WW = room_walls(x0, 210, x1, 890)
    for side, (W, L) in WW.items():
        if (side == "right" and sx < 0) or (side == "left" and sx > 0):          # the pavilion's wall, its wing side
            to_u = (lambda y_: 890 - y_) if side == "right" else (lambda y_: y_ - 210)
            hall_side = "left" if sx < 0 else "right"
            hs = [tuple(sorted((to_u(a_), to_u(b_)))) + (0, zt_) for a_, b_, zt_ in side_holes[hall_side]
                  if not (tower and a_ >= TY0)]                                  # (the tower's arch opens into the tower)
            NICHE = NICHE_W if (HEARTH and sx < 0) else None                     # W: the back bar's niche, through this
            if NICHE: hs.append((890 - NICHE[1], 890 - NICHE[0], 0, NICHE[2]))   # wall into the mirror's mass (the
            face("stone", W, 0, TY0 - 210 if tower else L, 0, 400, hs)           # tavern plan, 2026-10-26)
            for a_, b_, zt_ in side_holes[hall_side]:                            # (W: the arches' heads on this side too)
                if (hall_side, a_, b_) in ARCHED: arch_head(W, *sorted((to_u(a_), to_u(b_))), zt_)
            # (a thin frame since the walk of 2026-11-01: 4 from the back wall, the usual 14 lay 10 inside it on one jamb and showed whole on the other; even and centred: 4 each side)
            if NICHE: arch_head(W, 890 - NICHE[1], 890 - NICHE[0], NICHE[2], TS, ring=4)  # (a round arch with a jamb each side since
                                                                                  # the fit-out, centred on the barkeep's lane:
                                                                                  # it ran into the back wall's corner, askew)
        elif tower and side == "back":
            face("stone", W, TX1 - x0, L, 0, 400)
        elif HEARTH and side == "front":                 # W: the front breaks forward into the cross gable at its bay
            if sx < 0:
                face("stone", W, 0, -380 + 1060, 0, 400)                         # the tavern's (u = -380 - x)
                face("stone", (Vector((-1100, 186, 0)), Vector((-1, 0, 0)), Vector((0, 1, 0))), 0, 300, 0, 400)   # the kitchen's
            else:
                face("stone", W, 1400 - 1054, L, 0, 400)                         # the guild services' (u = 1400 - x)
                face("stone", (Vector((1400, 186, 0)), Vector((-1, 0, 0)), Vector((0, 1, 0))), 0, 1400 - CGX, 0, 400)   # the backroom's
        elif HEARTH and side == ("left" if sx < 0 else "right"):   # the outer end, on into the cross gable
            if sx < 0: face("stone", (Vector((x0, 186, 0)), Vector((0, 1, 0)), Vector((1, 0, 0))), 0, 890 - 186, 0, 400)
            else: face("stone", W, 0, 890 - 186, 0, 400)
        else:
            face("stone", W, 0, L, 0, 400)
    if tower:                                            # the tower's foot, as the wing's room sees it: its front and right walls
        SV_ARCH = (530, 670, 260) if TOWER3 else (450, 610, 260)   # U: the way into the stair, from the guild services
                                                         # (V: on the front's right part, 2026-10-25)
        for W, L in (room_walls(PX1, 210, TX1, TY0)["back"], room_walls(TX1, TY0, x1, 890)["left"]):
            hs = [(SV_ARCH[0] - PX1, SV_ARCH[1] - PX1, 0, SV_ARCH[2])] if (TOWER2 and W[2].y < 0) else []
            face("stone", W, 0, L, 0, 400, hs)
            for h in hs: opening_frame(W, h[0], h[1], 0, h[3], TS, rev="stone")   # (the walk of 2026-11-06: the way into the tower by the counter, its reveals the tower's stone, not plaster)
        if TOWER2: PLAN.append({"t": "arch", "level": 0, "a": [SV_ARCH[0], TY0 + TS / 2], "b": [SV_ARCH[1], TY0 + TS / 2]})
    if sx < 0 and not TAVERN_OPEN:
        box("wood", (-1300, 300, 0), (-1000, 380, 72)); box("wood", (-1300, 520, 0), (-1000, 600, 72))   # tavern tables, stand-ins
        INT_LIGHTS.append((-900, 560, 300, 5.0e6, (1.0, 0.7, 0.4)))
    elif sx < 0: INT_LIGHTS.append((-760, 530, 230, 4.0e6, (1.0, 0.7, 0.4), "lamp"))
    else:
        # (2026-10-30, the SE test install's run: the upstairs hall by Room 5's wall far too bright: measured with Actor.GetLightLevel,
        # lights off in halves: 66 there, 25 with no lights, this lamp 18 of it through the floor at its full 512, the
        # hall's own lamp 23) a light passes through floors: trimmed to stop 60 over the floor above it, as the upper rooms' stop
        # 60 under theirs
        pass   # (gone with its fixture, 2026-10-30: 10 off a wall; the services have their chandeliers, the counter its candlestick)
if VARIANT == "C":           # the stair in the right wing, behind a passage from the arch, rising to the back: its landing
    stair(SW0, SW1, 300, 860, side=1)      # reaches the right gallery (a door through the jettied wall) and the patio door
    LND = (PX1 + J, 760, SW1, 890)
    box("planks", (LND[0], LND[1], ZG - 4), (LND[2], LND[3], ZG)); box("wood", (LND[0], LND[1], ZG - 18), (LND[2], LND[3], ZG - 4))
    PLAN.append({"t": "landing", "level": 1, "r": list(LND)})
    sh = room_walls(PX1 + J, 210, SW1, 890)["right"]                         # the stair hall's wall to the services room,
    face("stucco", sh[0], 0, sh[1], 0, 400, [(890 - 350, 890 - 230, 0, 240)])  # both faces, a doorway by the stair's foot
    sv = room_walls(SW1 + 24, 210, PX1 + 1060 - TS, 890)["left"]
    face("stucco", sv[0], 0, sv[1], 0, 400, [(230 - 210, 350 - 210, 0, 240)])
    PLAN.append({"t": "wall", "level": 0, "a": [SW1 + 12, 210], "b": [SW1 + 12, 890], "gap": [230, 350]})
    # its upper storey (418 to 656), so it reads as a room: walls, the partition going on up with the corridor's doorway
    # to the patio door, a ceiling; the stairwell stays open below
    up = room_walls(PX1 + J, 210, SW1, 890)
    for side, (W, L) in up.items():
        hs = {"right": [(0, 890 - 760, ZG, ZG + 200)],                         # to the corridor and the patio door
              "left": [(770 - 210, 870 - 210, ZG, ZG + 202)]}.get(side, [])     # into the right gallery
        face("stucco", W, 0, L, ZG, T1, hs)
        for zz in (ZG + 12, T1 - 12): wall_beam(W, (0, zz), (L, zz), w=22, deep=8)
    box("planks", (PX1 + J, 210, T1), (SW1, 890, T1 + 14))
    PLAN.append({"t": "wall", "level": 1, "a": [SW1 + 12, 210], "b": [SW1 + 12, 890], "gap": [760, 890]})

if TOWER_STAIR:
    # The stair in the tower: a newel stair (stone steps wound round a stone column) rising counter-clockwise from the arch
    # at the great hall's back-right corner to a landing at the door onto the back gallery, then on up to the lookout's
    # floor. Inside the tower: its stone foot x 380..640, y 800..1072; the timber storeys above it x 416..656 (the
    # pavilion's jettied wall is their left wall), y 784..1088; the lookout x 364..656. The stair fits the narrowest of
    # them: centre x 528, the steps' ends 110 out (2 clear of the walls at x 416 and 640), y 826..1046.
    TG = (TX0 + TS if TOWER3 else PX1, TY0 + TS, TX1 - TS, TY1 - TS)   # 380, 800, 640, 1072 (U: 380, 772, 680, 1072;
                                                              # V: 256, 772, 680, 1120: its own stone walls all round)
    TU = (JX + TT if TOWER2 else PX1 + J, TY0 + TT, TX1 - TT, TY1 - TT)   # 416, 784, 656, 1088 (U: 380, 756, 696, 1088)
    TL = (TX0 + TT, TY0 + TT, TX1 - TT, TY1 - TT)             # 364, 784, 656, 1088
    ZLK = 1080                                                # the lookout's floor: its windows' sills (1170) 90 over it
    SC = Vector(((TG[0] + TG[2]) / 2, (TG[1] + TG[3]) / 2, 0)) if TOWER2 else Vector((528, (TY0 + TY1) / 2, 0))   # the stair's centre
    NEWEL = HEARTH                                            # W: a solid stone newel instead of V's open well (fully
                                                              # enclosed), a level landing inside
                                                              # the arch, a flight down to a basement landing, the lookout its own cell
    SR, SR0, STH = 110, (24 if NEWEL else 64) if TOWER3 else 16, 30   # the steps' outer ends, their inner ends (in the column; V: at
                                                              # the open well's rail, Fort Dawnguard's is about 80), depth under a top
    ZB = -256                                                 # W: the basement's floor, 16 steps of 16 down
    pol = lambda r_, a_, z_: Vector((SC.x + r_ * math.cos(math.radians(a_)), SC.y + r_ * math.sin(math.radians(a_)), z_))
    STEPS = []                                                # (from, to: degrees counter-clockwise from +x; top; rise)
    DOWN = []                                                 # (W: the flight down to the basement, the same form)
    FLIGHTS = []   # (2026-10-28, the follower who could not climb it) each flight: its first step's index in STEPS + DOWN,
                   # its steps, whether its last is a landing; exported for navgen.py, which lays the flight a ramp as vanilla
    def flight(a_from, z_from, z_to, n_, da):
        FLIGHTS.append([len(STEPS), n_, False])
        h_ = (z_to - z_from) / n_
        STEPS.extend((a_from + da * i, a_from + da * (i + 1), z_from + h_ * (i + 1), h_) for i in range(n_))
        return a_from + da * n_
    def landing(extra):                                       # the last step runs on past its door
        FLIGHTS[-1][2] = True
        STEPS[-1] = (STEPS[-1][0], STEPS[-1][1] + extra, STEPS[-1][2], STEPS[-1][3]); return STEPS[-1][1]
    if TOWER3:
        # V: the steps run from the well out to every wall, turning clockwise (angles run down; the tower plan,
        # 2026-10-25): in through the arch on the front's right part (from the guild services), out onto the lobby through
        # an opening on the front's left part beside the gallery's door, on to the attic door on the front's right part,
        # then a top landing under the lookout's hatch. Each landing is the flight's last step run on across its door.
        ang = lambda x_, y_: math.degrees(math.atan2(y_ - SC.y, x_ - SC.x)) % 360
        V_OPEN, ATTIC_DOOR, LOBBY_DOOR = (430, 550), (540, 660), None   # x on the front wall
        ZAT, ZTOP = T1 + 12, 880                              # the attic's floor (668); the top landing (182 clear under the lookout's floor)
        span = lambda d_, yw: (ang(d_[1], yw), ang(d_[0], yw))    # a door's angles on the front wall: its right edge, its left
        a_ = ang(sum(SV_ARCH[:2]) / 2, TG[1])                     # the first step, at the arch's middle (307)
        if NEWEL:   # W: a level landing behind the arch (the first step clipped the arch), from
                    # 3 degrees past its left jamb to 3 past its right; up from its left end, down from its right
            ARCH_L = (ang(SV_ARCH[0], TG[1]) - 3, ang(SV_ARCH[1], TG[1]) + 3)   # (287, 322)
            a_ = ARCH_L[0]
        o0, o1 = (v_ - 360 for v_ in span(V_OPEN, TU[1]))          # the opening, a turn on (293, 259)
        flight(a_, 0, ZG, 26, (o0 + 2 - a_) / 26); a_ = landing(o1 - 4 - (o0 + 2))
        t0, t1 = (v_ - 720 for v_ in span(ATTIC_DOOR, TU[1]))     # the attic door, two turns on (315, 291)
        n_ = round((a_ - (t0 + 2)) / 16.0); flight(a_, ZG, ZAT, n_, (t0 + 2 - a_) / n_)
        if NEWEL:   # W since the hall2t walk (2026-10-26: the stair ends lower, the ladder hatch moves to another corner,
                    # and the open drop at the stair's end is walled up):
                    # the stair ends at the attic door's landing, run on clockwise along the front wall to 252 degrees (past
                    # that, the flight under it would have less than 200 clear); the tower's ceiling comes down over it
            A_END = 291 - 720   # (2026-11-03, more steps: the landing's step runs round to 291, where the ray meets
                                # the front wall at the attic doorway's edge (x 541); four steps go on up from there across the corner, below)
            a_ = landing(A_END - (t0 + 2)); ZTOP = ZAT; ZC = ZAT + 200   # the ceiling's underside (868)
        else:
            a_ = landing(t1 - 4 - (t0 + 2))
            flight(a_, ZAT, ZTOP, 13, -16.36); a_ = landing(-44)
        HATCH_A = (STEPS[-1][0] + STEPS[-1][1]) / 2           # the hatch over the top landing, by the wall
        if NEWEL:   # W: the flight down, counter-clockwise from the landing's right end: 15 steps of 16 and the floor's
            n_up = len(STEPS)                                 # 16th, about 0.6 of a turn, under the flight up
            flight(ARCH_L[1], 0, ZB + 16, 15, 14.3)
            DOWN = STEPS[n_up:]; del STEPS[n_up:]
    elif TOWER2:
        # U: in through an arch from the guild services (the front wall, 270 degrees), out through the right wall onto the
        # lobby by the patio door, on to a door in the front wall into the attic over the staff quarters, then a top
        # landing under a hatch into the lookout. About 22 steps a turn, each turn climbing 320-360.
        ang = lambda x_, y_: math.degrees(math.atan2(y_ - SC.y, x_ - SC.x)) % 360
        LOBBY_DOOR, ATTIC_DOOR = (776, 896), (470, 590)       # y on the right wall; x on the front wall
        ZAT, ZTOP = T1 + 12, 880                              # the attic's floor (668); the top landing (182 clear under the lookout's floor)
        a_ = 270.0
        A_OUT = ang(TU[2], sum(LOBBY_DOOR) / 2) + 360
        flight(a_, 0, ZG, 26, (A_OUT - a_) / 26); a_ = landing(20)
        A_AT = 270 + 360 * math.ceil((a_ - 270) / 360)
        n_ = round((A_AT - a_) / 16.36); flight(a_, ZG, ZAT, n_, (A_AT - a_) / n_); a_ = landing(20)
        flight(a_, ZAT, ZTOP, 13, 16.36); a_ = landing(44)
        HATCH_A = (STEPS[-1][0] + STEPS[-1][1]) / 2           # the hatch over the top landing, by the wall
    else:
        A0 = math.degrees(math.atan2(860 - SC.y, PX1 - SC.x)) % 360           # the first step, at the arch's middle (207)
        A1 = 720 + math.degrees(math.atan2(940 - SC.y, PX1 + J - SC.x)) % 360  # the landing, at the gallery door's middle (178)
        a_end = flight(A0, 0, ZG, 31, (A1 - A0) / 31)        # 31 steps of 13.5, 1.92 turns
        LAND = 32                                             # the landing: the top step runs on past the door
        landing(LAND)
        flight(a_end + LAND, ZG, ZLK, 41, 22.5)               # 41 steps of 16.1, 2.56 turns, to the lookout

    def tread(a0, a1, zt, h_, key="steps"):
        """one stone step: its top, its riser at a0, its outer end and its underside, which slopes down a rise across it"""
        n_ = max(2, math.ceil((a1 - a0) / 8))
        arc = [a0 + (a1 - a0) * k_ / n_ for k_ in range(n_ + 1)]
        poly(key, [pol(SR0, a0, zt)] + [pol(SR, b_, zt) for b_ in arc] + [pol(SR0, a1, zt)])
        poly(key, [pol(SR0, a0, zt - h_), pol(SR, a0, zt - h_), pol(SR, a0, zt), pol(SR0, a0, zt)])
        zb = lambda b_: zt - STH - h_ * (a1 - b_) / (a1 - a0)
        for b0, b1 in zip(arc, arc[1:]):
            poly(key, [pol(SR, b0, zb(b0)), pol(SR, b1, zb(b1)), pol(SR, b1, zt), pol(SR, b0, zt)])
            poly(key, [pol(SR0, b0, zb(b0)), pol(SR0, b1, zb(b1)), pol(SR, b1, zb(b1)), pol(SR, b0, zb(b0))])
    # AG_TOWER_STEPS=square: the steps run out to the walls, as Fort Dawnguard's tower stair does (2026-10-25). Below
    # the first floor they stop at the timber wall's line on the left (416), so none pass under its
    # jetty; the last turn stays round, because the lookout's floor needs a ring round its well.
    SQUARE = TOWER2 or os.environ.get("AG_TOWER_STEPS") == "square"
    TSQ = TG if TOWER2 else (PX1 + J, TG[1], TG[2], TG[3])    # 416, 800, 640, 1072 (U: no jetty over the foot, so all of it)
    LAST = ZLK + 1 if TOWER2 else ZLK - 216                   # (U: no round last turn: the lookout is reached by a hatch)
    def reach(rect, a_):
        """how far the ray from the stair's centre at a_ degrees runs before it meets rect's walls"""
        c_, s_ = math.cos(math.radians(a_)), math.sin(math.radians(a_))
        return min(t_ for t_ in ((rect[2] - SC.x) / c_ if c_ > 1e-9 else None, (rect[0] - SC.x) / c_ if c_ < -1e-9 else None,
                                 (rect[3] - SC.y) / s_ if s_ > 1e-9 else None, (rect[1] - SC.y) / s_ if s_ < -1e-9 else None) if t_ is not None)
    def corners_in(rect, a0, a1):
        """the angles of rect's corners strictly between a0 and a1 (in a0's turn)"""
        out_ = []
        for cx_, cy_ in ((rect[0], rect[1]), (rect[2], rect[1]), (rect[2], rect[3]), (rect[0], rect[3])):
            ca = math.degrees(math.atan2(cy_ - SC.y, cx_ - SC.x)) % 360
            ca += 360 * math.ceil((a0 - ca) / 360)
            if a0 < ca < a1: out_.append(ca)
        return out_
    def tread_sq(a0, a1, zt, h_, rect, key="steps", last=False, first=False):
        """one stone step out to the walls: its top, its riser at its front (a0), its underside sloping a rise across it
        (its end is against the wall). Clockwise steps (a1 < a0) have their riser at the larger angle. V: the top in a quad
        per segment (an open well's inner edge is an arc, not a chord) and the step's end at the well"""
        cw = a1 < a0; lo, hi = (a1, a0) if cw else (a0, a1)
        bs = sorted(set([lo, hi] + corners_in(rect, lo, hi) + [lo + (hi - lo) * k_ / 3 for k_ in (1, 2)]
                        + ([lo + (hi - lo) * k_ / math.ceil((hi - lo) / 8) for k_ in range(1, math.ceil((hi - lo) / 8))] if TOWER3 else [])))
        draw_ = drawn_only if NEWEL else (lambda fn, *a: fn(*a))   # (W: the top and the riser collide as coll_tread builds them)
        if TOWER3:
            for b0, b1 in zip(bs, bs[1:]):
                draw_(poly, key, [pol(SR0, b0, zt), pol(reach(rect, b0), b0, zt), pol(reach(rect, b1), b1, zt), pol(SR0, b1, zt)])
        else: poly(key, [pol(SR0, lo, zt)] + [pol(reach(rect, b_), b_, zt) for b_ in bs] + [pol(SR0, hi, zt)])
        rs = hi if cw else lo
        rq = [pol(SR0, rs, zt - h_), pol(reach(rect, rs), rs, zt - h_), pol(reach(rect, rs), rs, zt), pol(SR0, rs, zt)]
        draw_(poly, key, rq[::-1] if cw else rq)
        low_lo = cw == (h_ < 0)                               # its underside drops a rise toward its lower neighbour (W's flight
        zb = ((lambda b_: zt - STH - abs(h_) * (hi - b_) / (hi - lo)) if low_lo   # down: until 2026-10-25 it sloped up, above the
              else (lambda b_: zt - STH - abs(h_) * (b_ - lo) / (hi - lo)))       # step's own top)
        if NEWEL:                                             # W: the lowest steps stand on the basement's floor (their
            zb_raw = zb; zb = lambda b_: max(ZB, zb_raw(b_))  # undersides ran on below it)
        if first:                                             # a flight's first step: its front under the riser, open under
            zr = min(zt, zt - h_)                             # the arch's landing (12 thick) until 2026-10-25
            fq = [pol(SR0, rs, zb(rs)), pol(reach(rect, rs), rs, zb(rs)), pol(reach(rect, rs), rs, zr), pol(SR0, rs, zr)]
            poly(key, fq[::-1] if cw else fq)
        if last:                                              # a flight's last step: its far end, which no next step's riser
            re = lo if cw else hi                             # covers (the top landing's edge, the basement's last riser)
            q_ = [pol(SR0, re, zb(re)), pol(reach(rect, re), re, zb(re)), pol(reach(rect, re), re, zt), pol(SR0, re, zt)]
            poly(key, q_ if cw else q_[::-1])
        for b0, b1 in zip(bs, bs[1:]):
            poly(key, [pol(SR0, b0, zb(b0)), pol(SR0, b1, zb(b1)), pol(reach(rect, b1), b1, zb(b1)), pol(reach(rect, b0), b0, zb(b0))])
            # (the walk of 2026-10-30, the stairs' underside could be walked through: since the tower stair's faces came out of the collision (2026-10-29: the walkers' steps are coll_tread's)
            # its undersides had none, and one-sided faces stop nothing from behind. Facing down, under the tread, they touch no one going up or down)
            if NEWEL:
                q_ = [pol(SR0, b0, zb(b0)), pol(SR0, b1, zb(b1)), pol(reach(rect, b1), b1, zb(b1)), pol(reach(rect, b0), b0, zb(b0))]
                if (q_[1] - q_[0]).cross(q_[2] - q_[0]).z > 0: q_ = q_[::-1]
                coll_only(q_)
            if TOWER3: poly(key, [pol(SR0, b1, zb(b1)), pol(SR0, b0, zb(b0)), pol(SR0, b0, zt), pol(SR0, b1, zt)])
    # (2026-10-29, the stair the NPCs cannot climb: the export's tower collision held 475 faces steeper than 60 degrees, the
    # drawn treads' own risers and undersides, under the chamfered collision laid over them (hall2r's fix): a wall every 16 of
    # rise. The treads are drawn only now; their collision is built apart below)
    for i_, st_ in enumerate(STEPS + DOWN):
        if SQUARE and st_[2] <= LAST: drawn_only(tread_sq, *st_, TSQ if st_[2] < ZG else TU, last=i_ in ((() if NEWEL else (len(STEPS) - 1,)) + (len(STEPS) + len(DOWN) - 1,)),   # (W: the attic landing's
                                                                                                                   # far end runs on into the slab: no end face there)
                                                 first=NEWEL and i_ in (0, len(STEPS)))
        else: drawn_only(tread, *st_)
    if NEWEL:   # W: the stair's collision as vanilla's (the hall2r walk: going up, the collision bumped
                # and paused on each step). Fort Dawnguard's tower stair has the same 16 steps; measured along its walking
                # line (stair_profile.py, 2026-10-26) its collision keeps flat treads, each riser upright for its lower 10 and
                # chamfered at 45 degrees over its top 6, which eats 6 into the tread above. Ours collided with whole 16 risers.
        CH, DA = 6.0, math.degrees(6.0 / 80)                  # (the chamfer's run: 6 at r 80, the walking line; longer further out)
        def span_(x0, x1, rect):
            lo_, hi_ = min(x0, x1), max(x0, x1)
            n_ = max(1, math.ceil((hi_ - lo_) / 8))
            return sorted(set([lo_, hi_] + corners_in(rect, lo_, hi_) + [lo_ + (hi_ - lo_) * k_ / n_ for k_ in range(1, n_)]))
        def strip_(b0, b1, z0, z1, rect):                     # collision from the newel to the walls, z0 at angle b0 to z1 at b1
            zf = lambda b_: z0 + (z1 - z0) * (b_ - b0) / (b1 - b0)
            bs_ = span_(b0, b1, rect)
            for c0, c1 in zip(bs_, bs_[1:]):
                coll_only([pol(SR0, c0, zf(c0)), pol(reach(rect, c0), c0, zf(c0)), pol(reach(rect, c1), c1, zf(c1)), pol(SR0, c1, zf(c1))])
        def ramp_strip_(b0, b1, z0, z1, rect):                 # strip_ in rings: a spiral's surface twists, and one quad from
            zf = lambda b_: z0 + (z1 - z0) * (b_ - b0) / (b1 - b0)   # the newel to the wall split in two left a 70-degree sliver
            bs_ = span_(b0, b1, rect)                          # along the newel (the export's tower collision, 2026-10-29)
            for c0, c1 in zip(bs_, bs_[1:]):
                R0, R1 = reach(rect, c0), reach(rect, c1)
                for f0, f1 in ((0, 1 / 3), (1 / 3, 2 / 3), (2 / 3, 1)):
                    ra0, rb0 = SR0 + (R0 - SR0) * f0, SR0 + (R0 - SR0) * f1
                    ra1, rb1 = SR0 + (R1 - SR0) * f0, SR0 + (R1 - SR0) * f1
                    coll_only([pol(ra0, c0, zf(c0)), pol(rb0, c0, zf(c0)), pol(rb1, c1, zf(c1)), pol(ra1, c1, zf(c1))])
        def coll_tread(a0, a1, zt, h_, rect, below=None):
            lo_, hi_ = (a1, a0) if a1 < a0 else (a0, a1)
            front, far = (hi_, lo_) if a1 < a0 else (lo_, hi_)
            low = front if h_ > 0 else far                    # the side the next step down is on
            into = 1 if low == lo_ else -1
            cut = low + into * DA
            strip_(cut, hi_ if into > 0 else lo_, zt, zt, rect)   # the tread, less the chamfer
            strip_(low, cut, zt - CH, zt, rect)               # the chamfer
            zl = zt - abs(h_) if below is None else below
            coll_only([pol(SR0, low, zl), pol(reach(rect, low), low, zl), pol(reach(rect, low), low, zt - CH), pol(SR0, low, zt - CH)])
        # (2026-10-29, tried as a test: a smooth ramp as vanilla's stair helpers are,
        # in place of the chamfered treads: on the navmesh's own surface (navgen.py's ramps), through each tread's middle, half
        # a riser under its nosing and over its back; from the floor at each flight's first riser; level on a landing step)
        STAIR_RAMP = True
        if STAIR_RAMP:
            ALL_ = STEPS + DOWN
            for i0_, n_, land_ in FLIGHTS:
                fl_ = ALL_[i0_:i0_ + n_]; h_ = fl_[0][3]; zf_ = fl_[0][2] - h_
                zb_ = [zf_] + [zf_ + h_ * (k_ + 0.5) for k_ in range(1, n_)] + [fl_[-1][2]]
                if land_: zb_[n_ - 1] = fl_[-1][2]
                for k_, (a0, a1, zt, hh_) in enumerate(fl_):
                    ramp_strip_(a0, a1, zb_[k_], zb_[k_ + 1], TSQ if zt < ZG else TU)
        else:
            for st_ in STEPS + DOWN:
                coll_tread(*st_, TSQ if st_[2] < ZG else TU)
    ZCOL = ZC if NEWEL else (ZLK - 18 if TOWER2 else ZLK + 110)   # the column: up through the lookout's floor as its rail's post
                                                              # (U: to its floor; W: to the tower's ceiling)
    for k_ in range(16 if (NEWEL or not TOWER3) else 0):      # (V: none, the middle is an open well; W: the newel, from the
        b0, b1 = 22.5 * k_, 22.5 * (k_ + 1)                  # basement's floor to the top landing's ceiling)
        z0_ = ZB if NEWEL else 0
        poly("trim", [pol(SR0 + 1 if NEWEL else SR0 + 3, b0, z0_), pol(SR0 + 1 if NEWEL else SR0 + 3, b1, z0_),
                      pol(SR0 + 1 if NEWEL else SR0 + 3, b1, ZCOL), pol(SR0 + 1 if NEWEL else SR0 + 3, b0, ZCOL)])
    if NEWEL: PLAN.append({"t": "newel", "c": [SC.x, SC.y], "r": SR0 + 1})
    if TOWER3 and not NEWEL:   # V: the well's rail: iron balusters on every step's end (every 15 degrees along a landing), an oak handrail
        tops = []                                             # 86 over the step at each step's middle (from the second step)
        for a0, a1, zt, h_ in STEPS[1:]:
            n_ = max(1, round(abs(a1 - a0) / 15))
            for k_ in range(n_):
                p_ = pol(SR0 + 4, a0 + (a1 - a0) * (k_ + 0.5) / n_, zt)
                box("iron", (p_.x - 2, p_.y - 2, zt), (p_.x + 2, p_.y + 2, zt + 86))
            tops.append(pol(SR0 + 4, (a0 + a1) / 2, zt + 86))
        for p0, p1 in zip(tops, tops[1:]):
            beam(p0, p1, 7, 5, Vector((p0.x - SC.x, p0.y - SC.y, 0)).normalized())
        PLAN.append({"t": "well", "c": [SC.x, SC.y], "r": SR0})
    if not TOWER2: box("trim", (SC.x - 26, SC.y - 26, ZLK + 110), (SC.x + 26, SC.y + 26, ZLK + 124))
    def railing(steps_, at=lambda a_: SR - 5):
        """iron balusters at the steps' open ends, an oak handrail on them (none across the landing or the arch)"""
        tops = []
        for a0, a1, zt, h_ in steps_:
            p_ = pol(at((a0 + a1) / 2), (a0 + a1) / 2, zt)
            box("iron", (p_.x - 2, p_.y - 2, zt), (p_.x + 2, p_.y + 2, zt + 86)); tops.append(p_ + UP * 86)
        for p0, p1 in zip(tops, tops[1:]):
            beam(p0, p1, 7, 5, Vector((p0.x - SC.x, p0.y - SC.y, 0)).normalized())
    if not SQUARE: railing(STEPS[1:30]); railing(STEPS[31:])
    elif not TOWER2:                                          # square: a rail only where the steps leave a gap (the strip below
        ca0 = math.degrees(math.atan2(TSQ[3] - SC.y, TSQ[0] - SC.x)); ca1 = math.degrees(math.atan2(TSQ[1] - SC.y, TSQ[0] - SC.x)) % 360
        railing([s_ for s_ in STEPS[:30] if s_[2] > 100 and ca0 < ((s_[0] + s_[1]) / 2) % 360 < ca1], at=lambda a_: reach(TSQ, a_) - 4)
        railing([s_ for s_ in STEPS if s_[2] > LAST])        # the jetty, by the arch) and round the last, round turn

    def ring(z_, th_, rect, key="planks", seg=48):
        """a floor at z_ over rect, less a round hole for the stair"""
        x0_, y0_, x1_, y1_ = rect; rh = SR + 2
        def edge(a_):                                         # where the ray from the stair's centre leaves rect
            c_, s_ = math.cos(math.radians(a_)), math.sin(math.radians(a_))
            ts_ = [t_ for t_ in ((x1_ - SC.x) / c_ if c_ > 1e-9 else None, (x0_ - SC.x) / c_ if c_ < -1e-9 else None,
                                 (y1_ - SC.y) / s_ if s_ > 1e-9 else None, (y0_ - SC.y) / s_ if s_ < -1e-9 else None) if t_ is not None]
            t_ = min(ts_); return Vector((SC.x + t_ * c_, SC.y + t_ * s_, 0))
        cang = sorted(((math.degrees(math.atan2(cy_ - SC.y, cx_ - SC.x)) % 360, Vector((cx_, cy_, 0)))
                       for cx_, cy_ in ((x0_, y0_), (x1_, y0_), (x1_, y1_), (x0_, y1_))), key=lambda t_: t_[0])
        for k_ in range(seg):
            a0, a1 = 360 * k_ / seg, 360 * (k_ + 1) / seg
            pts = [pol(rh, a0, 0), edge(a0)] + [v_ for ca_, v_ in cang if a0 < ca_ < a1] + [edge(a1), pol(rh, a1, 0)]
            poly(key, [Vector((p_.x, p_.y, z_)) for p_ in pts])
            poly(key, [Vector((p_.x, p_.y, z_ - th_)) for p_ in pts][::-1])
            poly(key, [pol(rh, a1, z_ - th_), pol(rh, a0, z_ - th_), pol(rh, a0, z_), pol(rh, a1, z_)])
    def sector(a0, a1, z_top, th, rect, key="floor", edges=(True, True)):
        """a floor over the part of rect between the rays at a0 and a1 (a0 < a1), from the newel out to the walls (edges: which
        ray's edge face to draw: none where a step's riser stands in its plane)"""
        bs = sorted(set([a0, a1] + corners_in(rect, a0, a1) + [a0 + (a1 - a0) * k_ / 4 for k_ in (1, 2, 3)]))
        top = [pol(SR0, a0, z_top)] + [pol(reach(rect, b_), b_, z_top) for b_ in bs] + [pol(SR0, a1, z_top)]
        poly(key, top); poly(key, [Vector((p_.x, p_.y, z_top - th)) for p_ in reversed(top)])
        for b_, e_ in zip((a0, a1), edges):                   # its edges along the rays, over the stairwell
            if not e_: continue
            q_ = [pol(SR0, b_, z_top - th), pol(reach(rect, b_), b_, z_top - th), pol(reach(rect, b_), b_, z_top), pol(SR0, b_, z_top)]
            poly(key, q_ if b_ == a0 else q_[::-1])
    TOWER_PLACE, LOOK_PLACE, LOOK_LIGHTS, LOOK_MARKERS = [], [], [], []         # W: pieces in the tower; the lookout cell's pieces and lights
    if NEWEL:   # W: the foot's flags only on the landing behind the arch (the rest is the stairwell, down and up); a stone
                # threshold through the arch (the services' floor stops at the wall's outer face, the foot's at its inner one:
                # 40 of nothing under the arch, in the first walk); the basement's floor
        drawn_only(sector, ARCH_L[0], ARCH_L[1], 0, 16, TG, edges=(True, False))   # (the first step down's riser is its right edge; 16
                                                              # thick, as tall as it: at 12 its foot showed its back from the basement)
        coll_tread(ARCH_L[0], ARCH_L[1], 0, -16, TG)          # (it collides as a step does: chamfered toward the flight down)
        box("floor", (SV_ARCH[0], TY0, -12), (SV_ARCH[1], TG[1], 0))   # (to the landing: 0.5 short, a slot; the wall is notched for its end)
        box("floor", (TG[0], TG[1], ZB - 12), (TG[2], TG[3], ZB))
        PLAN.append({"t": "basement", "r": list(TG), "z": ZB, "landing": list(ARCH_L)})
    else: box("floor", (TG[0], TG[1], -12), (TG[2], TG[3], 0))      # the foot's stone flags
    if not SQUARE: ring(ZG, 18, (XU, TU[1], TU[2], TU[3]))    # round the stair at the first floor (x < 392 is the jetty's floor)
    else:                                                     # square: only the ledges where the timber walls stand back
        for lo_, hi_ in (((TU[0] if TOWER3 else XU, TU[1]), (TSQ[0], TU[3])), ((TSQ[2], TU[1]), (TU[2], TU[3])), ((TSQ[0], TU[1]), (TSQ[2], TSQ[1])), ((TSQ[0], TSQ[3]), (TSQ[2], TU[3]))):
            if hi_[0] - lo_[0] > 1 and hi_[1] - lo_[1] > 1: box("stone", (lo_[0], lo_[1], ZG - 18), (hi_[0], hi_[1], ZG - (0.5 if NEWEL else 0)))   # (W: under the landing's step, not in its plane; stone since the walk of 2026-11-01: an odd wood strip inside the tower stair: planks while the walls were timber)
    if NEWEL:   # W: the lookout is a cell of its own (a clickable ladder and hatch, as vanilla uses, leading to
                # another cell): vanilla's TrapdoorLadder02 (a load door: a ladder up to a trapdoor, 197
                # tall) at a wall, its trapdoor 2 under the tower's ceiling; in the lookout, Winterhold's floor trapdoor over
                # the same spot leads back. Hall2.cs links the two. Since the hall2t walk (2026-10-26) the stair ends at the
                # attic landing: the ceiling comes down to 868 over the whole tower (200 over the landing, 213 over the last
                # step), the ladder (at 1.1) stands on the landing against the front wall left of the attic door, and a
                # partition walls up the landing's open end
        # (2026-11-03, the headroom under the landing; more steps, as planned: the stair goes
        # on up past the attic door's landing, four more steps across the corner, the ladder on a small top landing) the attic door's
        # landing ends on the ray at A_END; then three treads and the top landing, each straight across from the front wall to the end
        # wall's face, their risers on that ray and at x 456, 412 and 373 (the plan's), each a riser of the flight below higher
        # (AG_TOWER_RISE to try another); the ceiling raised over them, 200 over the top landing
        RISE_ = float(os.environ.get("AG_TOWER_RISE", "0")) or STEPS[-2][3]
        RC_ = SR0 + 1; YW0 = SC.y - RC_; YW1 = YW0 + 12                   # the end wall: its landing face (flush with the column's side), its stairwell face
        XS_ = (456.0, 412.0, 373.0)                                       # risers 2, 3 and 4
        ZS_ = [ZAT + RISE_ * k_ for k_ in (1, 2, 3, 4)]                   # treads 1..3 and the top landing
        US_ = [z_ - STH for z_ in ZS_]                                    # their undersides
        ZP_ = ZS_[3]; ZC2 = ZP_ + 200
        A_S = A_END % 360; dA_ = Vector((math.cos(math.radians(A_S)), math.sin(math.radians(A_S)), 0))
        XR0 = SC.x + dA_.x * (TU[1] - SC.y) / dA_.y; XR1 = SC.x + dA_.x * (YW0 - SC.y) / dA_.y   # the ray at the front wall, at the end wall's line
        V_ = lambda x_, y_, z_: Vector((x_, y_, z_))
        def ceil_(pts_, z_):                                              # planks 18 thick: their underside, their top
            poly("planks", [V_(x_, y_, z_) for x_, y_ in reversed(pts_)]); poly("planks", [V_(x_, y_, z_ + 18) for x_, y_ in pts_])
        ceil_([(TU[0], YW0), (TU[2], YW0), (TU[2], TU[3]), (TU[0], TU[3])], ZC)          # over the stairwell
        ceil_([(XR0, TU[1]), (TU[2], TU[1]), (TU[2], YW0), (XR1, YW0)], ZC)              # over the attic door's landing
        ceil_([(TU[0], TU[1]), (XS_[0], TU[1]), (XS_[0], YW0), (TU[0], YW0)], ZC2)       # over the steps and the top landing
        ceil_([(XS_[0], TU[1]), (XR0, TU[1]), (XR1, YW0), (XS_[0], YW0)], ZC2)
        # (the walk of 2026-11-03: a large clipping on the ceiling, a grey triangle: this face was wound toward the attic door's landing, where
        # it stands above that landing's ceiling; it is seen from under the raised ceiling, the steps' side, so it faces that way: the leak check's
        # one face seen from behind in the tower, 235 rays)
        poly("planks", [V_(XR0, TU[1], ZC2), V_(XR1, YW0, ZC2), V_(XR1, YW0, ZC), V_(XR0, TU[1], ZC)])   # the fascia where it steps, facing
        poly("planks", [V_(SC.x, YW0, ZC), V_(XR1, YW0, ZC), V_(XR1, YW0, ZC2), V_(SC.x, YW0, ZC2)])     # the attic door; beside the column
        WN = Vector((-1, 0, 0)); yaw_l = 90.0                              # (its back, local -y, to the left wall)
        HB_ = Vector((TU[0], 822, 0)); LS_ = (ZC2 - ZP_) / 182.0
        OUT_ = lambda d_, z_: Vector((HB_.x - WN.x * d_, HB_.y - WN.y * d_, z_))   # d_ in from the wall
        lp_ = OUT_(38, ZP_ - 2)                                           # (its ladder 4..31 behind it, scaled: 3 off the wall)
        HATCH = (lp_.x, lp_.y)
        # (where one coming down stands, facing the room; since 2026-10-29, through the NPC session, locked at Adept
        # on the Guild Hall Key, which the guild master, the one whose routine goes up, and the assistant carry; the hatch
        # back down stays open, as vanilla locks a load door on one side)
        TOWER_PLACE.append(("meshes/dungeons/imperial/door/trapdoorladder02.nif", tuple(lp_), yaw_l, LS_,
                            dict(role="ladder", arrive=tuple(OUT_(115, ZP_)), arrive_yaw=yaw_l, lock="Adept", lock_key="AGHall2DisplayCaseKey")))
        hp_ = OUT_(38 + 35 * LS_, ZLK + 0.5)                              # the trapdoor over the ladder's own (local y 35)
        LOOK_PLACE.append(("meshes/architecture/winterhold/winterholdtrapdoor01.nif", tuple(hp_), yaw_l, 1.0, "hatch",
                           tuple(OUT_(170, ZLK)), yaw_l))                 # (where one coming up stands)
        wall_sconce(696, 900, 818, (-1, 0), 260)   # (the walk of hall2bz: the landing's own, on its wall: 200 of headroom is no place to hang one)
        PLAN.append({"t": "ladder", "p": [lp_.x, lp_.y], "a": 180 if WN.x < 0 else 270, "to": "lookout"})
        # the steps: solid stone from the front wall to the end wall (their ends stand against the walls, undrawn); their tops and
        # risers drawn only (their collision is the ramp below), the risers facing the climb (from the attic door, leftward); under
        # them a stepped soffit over the stairwell, closed and colliding, as the spiral's undersides
        P1_ = [(XS_[0], TU[1]), (XR0, TU[1]), (XR1, YW0), (XS_[0], YW0)]
        TREADS_ = [P1_] + [[(xa_, TU[1]), (xb_, TU[1]), (xb_, YW0), (xa_, YW0)] for xa_, xb_ in ((XS_[1], XS_[0]), (XS_[2], XS_[1]), (TU[0], XS_[2]))]
        for k_, P_ in enumerate(TREADS_):
            drawn_only(poly, "steps", [V_(x_, y_, ZS_[k_]) for x_, y_ in P_])
            poly("steps", [V_(x_, y_, US_[k_]) for x_, y_ in reversed(P_)])
        ARC_ = [pol(SR0, A_S - (A_S - 270) * k_ / 6, 0) for k_ in range(7)]   # tread 1 on round the column from the ray to 270 (inside it): a fan
        FAN_ = [(XR1, YW0)] + [(v_.x, v_.y) for v_ in ARC_]
        for (xa_, ya_), (xb_, yb_) in zip(FAN_, FAN_[1:]):
            drawn_only(poly, "steps", [V_(SC.x, YW0, ZS_[0]), V_(xa_, ya_, ZS_[0]), V_(xb_, yb_, ZS_[0])])
            poly("steps", [V_(xb_, yb_, US_[0]), V_(xa_, ya_, US_[0]), V_(SC.x, YW0, US_[0])])
        ra_ = pol(SR0, A_S, 0)                                            # riser 1 on the ray, facing the attic door's landing, and under it
        drawn_only(poly, "steps", [V_(XR0, TU[1], ZAT), V_(ra_.x, ra_.y, ZAT), V_(ra_.x, ra_.y, ZS_[0]), V_(XR0, TU[1], ZS_[0])])
        poly("steps", [V_(ra_.x, ra_.y, ZAT - STH), V_(XR0, TU[1], ZAT - STH), V_(XR0, TU[1], US_[0]), V_(ra_.x, ra_.y, US_[0])])   # the soffit's step
        for i_, x_ in enumerate(XS_):                                     # risers 2..4, facing +x (back down the climb); the soffit's steps under them
            drawn_only(poly, "steps", [V_(x_, TU[1], ZS_[i_]), V_(x_, YW0, ZS_[i_]), V_(x_, YW0, ZS_[i_ + 1]), V_(x_, TU[1], ZS_[i_ + 1])])
            poly("steps", [V_(x_, YW0, US_[i_]), V_(x_, TU[1], US_[i_]), V_(x_, TU[1], US_[i_ + 1]), V_(x_, YW0, US_[i_ + 1])])
        # their collision: a ramp as the flights' (ramp_strip_; bare risers outside snagged the player): from the floor at riser
        # 1's foot through risers 2..4's middles, on to the top landing's level 20 past its riser, level after
        LINES_ = [((XR0, TU[1]), (XR1, YW0))] + [((x_, TU[1]), (x_, YW0)) for x_ in XS_] + [((XS_[2] - 20, TU[1]), (XS_[2] - 20, YW0))]
        ZL_ = [ZAT, ZAT + 1.5 * RISE_, ZAT + 2.5 * RISE_, ZAT + 3.5 * RISE_, ZP_]
        def up_(q_):
            if (q_[1] - q_[0]).cross(q_[2] - q_[0]).z < 0: q_ = q_[::-1]
            coll_only(q_)
        for (a0_, a1_), (b0_, b1_), za_, zb_ in zip(LINES_, LINES_[1:], ZL_, ZL_[1:]):
            up_([V_(a0_[0], a0_[1], za_), V_(b0_[0], b0_[1], zb_), V_(b1_[0], b1_[1], zb_), V_(a1_[0], a1_[1], za_)])
        up_([V_(TU[0], TU[1], ZP_), V_(XS_[2] - 20, TU[1], ZP_), V_(XS_[2] - 20, YW0, ZP_), V_(TU[0], YW0, ZP_)])
        # the end wall over them (2026-11-03, the spec after the two hatch options; the old partition ran on the ray at A_END and
        # its head rail crossed the ladder's trapdoor): straight across at 90 degrees from the left wall to the newel, its landing face
        # flush with the column's side, 12 thick on the stairwell side, its end cut to the column's curve; plaster on a timber frame,
        # its landing face up to the raised ceiling, its stairwell face to the stairwell's; its foot stepped under the treads, 10 under
        # each one's underside (tread 1's 12 under it share tread 2's, its edge closed below)
        XW1 = SC.x - math.sqrt(RC_ ** 2 - (SC.y - YW1) ** 2)              # where the stairwell face meets the column
        SEG_ = [(TU[0], XS_[2], US_[3] - 10), (XS_[2], XS_[1], US_[2] - 10), (XS_[1], SC.x, US_[1] - 10)]
        WL_ = (Vector((TU[0], YW0, 0)), Vector((1, 0, 0)), Vector((0, -1, 0)))   # the landing face, u = x - TU[0]
        WS_ = (Vector((XW1, YW1, 0)), Vector((-1, 0, 0)), Vector((0, 1, 0)))     # the stairwell face, u = XW1 - x
        for x0_, x1_, f_ in SEG_:
            face("stone!", WL_, x0_ - TU[0], x1_ - TU[0], f_, ZC2)   # (stone since 2026-11-03, a strip of plaster matched to the stone around it)
            # (its sill beams, one per step of its foot, stepped down beside the posts: the test walk of 2026-11-06, more broken
            # trim; no baseboard on the flight)
            if x0_ < XW1:
                face("stone!", WS_, XW1 - min(x1_, XW1), XW1 - x0_, f_, ZC)
        # (the trim walk of 2026-11-07: the top and back pieces dropped, the front trim up the central pillar kept, the
        # top and right side untrimmed: its head rails and its posts by the left wall gone,
        # its posts by the column kept, one on each face)
        wall_beam(WL_, (SC.x - TU[0] - 9, SEG_[2][2]), (SC.x - TU[0] - 9, ZC2), w=18, deep=8)   # (landing face: its side flush with the column's)
        wall_beam(WS_, (12, SEG_[2][2]), (12, ZC), w=18, deep=8)
        def far_(x_):                                                     # the wall's far side at x: its stairwell face, or the column
            return YW1 if x_ <= XW1 else SC.y - math.sqrt(max(0.0, RC_ ** 2 - (x_ - SC.x) ** 2))
        for x0_, x1_, f_ in SEG_:                                         # its foot
            xs_ = [x0_, x1_] if x1_ <= XW1 else [x0_, XW1] + [XW1 + (x1_ - XW1) * k_ / 6 for k_ in range(1, 7)]
            poly_n("stone", [V_(x_, YW0, f_) for x_ in xs_] + [V_(x_, far_(x_), f_) for x_ in reversed(xs_)], (0, 0, -1))   # (stone, the wall's: the trim walk of 2026-11-07)
        for (x0_, x1_, f_), (x2_, x3_, g_) in zip(SEG_, SEG_[1:]):           # where it steps down, facing the higher foot
            poly("stone", [V_(x1_, far_(x1_), g_), V_(x1_, YW0, g_), V_(x1_, YW0, f_), V_(x1_, far_(x1_), f_)])
        if SEG_[2][2] > US_[0]:                                           # tread 1's edge under the wall's foot there, facing the stairwell
            poly("steps", [V_(SC.x, YW0, US_[0]), V_(XS_[0], YW0, US_[0]), V_(XS_[0], YW0, SEG_[2][2]), V_(SC.x, YW0, SEG_[2][2])])
        PLAN.append({"t": "wall", "level": 2, "a": [TU[0], YW0 + 6], "b": [SC.x, YW0 + 6], "gaps": []})
        # the headroom under it all, checked point by point (every 4) over the attic door's landing, the treads, the top landing and
        # the end wall's foot: the underside there against the top of the step under it, a turn and two turns below
        def step_under_(x_, y_):
            if math.hypot(x_ - SC.x, y_ - SC.y) < RC_: return None
            a_ = math.degrees(math.atan2(y_ - SC.y, x_ - SC.x)) % 360; best_ = None
            for st_ in STEPS[:-1]:
                lo_, hi_ = min(st_[0], st_[1]), max(st_[0], st_[1])
                if any(lo_ <= a_ + 360 * k_ <= hi_ for k_ in range(-3, 4)) and st_[2] < ZAT - 50: best_ = st_[2] if best_ is None else max(best_, st_[2])
            return best_
        def under_at_(x_, y_):
            a_ = math.degrees(math.atan2(y_ - SC.y, x_ - SC.x)) % 360
            if y_ > YW0: return next((f_ for x0_, x1_, f_ in SEG_ if x0_ <= x_ <= x1_), None)
            if x_ <= XS_[2]: return US_[3]
            if x_ <= XS_[1]: return US_[2]
            if x_ <= XS_[0]: return US_[1]
            if x_ <= SC.x + dA_.x * (y_ - SC.y) / dA_.y: return US_[0]
            return ZAT - STH if A_S <= a_ <= 317 else None
        clr_ = (1e9, None)
        for x_ in range(int(TU[0]) + 2, int(TU[2]) - 1, 4):
            for y_ in range(int(TU[1]) + 2, int(YW1) - 1, 4):
                u_, s_ = under_at_(x_, y_), step_under_(x_, y_)
                if u_ is not None and s_ is not None and u_ - s_ < clr_[0]: clr_ = (u_ - s_, (x_, y_))
        print("TOWER W: the attic landing to", round(A_S, 1), "deg (the front wall at x", round(XR0, 1), "); risers of", round(RISE_, 2), "; treads at",
              [round(z_, 1) for z_ in ZS_[:3]], "; the top landing", round(ZP_, 1), "; the ceiling over them", round(ZC2, 1), "; least headroom under it all", round(clr_[0], 1), "at", clr_[1])
        print("TOWER W: ladder", [round(v_) for v_ in lp_], "yaw", round(yaw_l, 1), "scale", round(LS_, 3),
              "; landing behind the arch", [round(v_, 1) for v_ in ARCH_L], "; down to", round(DOWN[-1][1], 1) if DOWN else None)
    elif TOWER2:   # U: the lookout's floor is whole but for a hatch over the top landing; a ladder up to it from the landing
        hc = pol(reach(TU, HATCH_A) - 60, HATCH_A, 0); HATCH = (hc.x - 45, hc.y - 45, hc.x + 45, hc.y + 45)
        for lo_, hi_ in (((TL[0], TL[1]), (HATCH[0], TL[3])), ((HATCH[2], TL[1]), (TL[2], TL[3])),
                         ((HATCH[0], TL[1]), (HATCH[2], HATCH[1])), ((HATCH[0], HATCH[3]), (HATCH[2], TL[3]))):
            box("planks", (lo_[0], lo_[1], ZLK - 18), (hi_[0], hi_[1], ZLK))
        lt = pol(reach(TU, HATCH_A) - 22, HATCH_A, 0); lb = pol(reach(TU, HATCH_A) - 58, HATCH_A, 0)   # its foot out from the wall
        tang = Vector((-math.sin(math.radians(HATCH_A)), math.cos(math.radians(HATCH_A)), 0))
        for s_ in (-1, 1):
            beam(lb + tang * 26 * s_ + UP * ZTOP, lt + tang * 26 * s_ + UP * (ZLK + 70), 8, 8, (lt - lb).normalized())
        for k_ in range(1, 8):
            f_ = k_ / 8; p_ = lb.lerp(lt, f_) + UP * (ZTOP + f_ * (ZLK + 70 - ZTOP))
            beam(p_ - tang * 26, p_ + tang * 26, 6, 6, Vector((0, 0, 1)))
    else:
        ring(ZLK, 18, TL)                                     # the lookout's floor
        gr_ = [pol(SR + 4, a_, ZLK) for a_ in range(70, 381, 15)]  # its rail round the stairwell, open where the stair arrives
        for p_ in gr_: box("wood", (p_.x - 3, p_.y - 3, ZLK), (p_.x + 3, p_.y + 3, ZLK + 86))
        for p0, p1 in zip(gr_, gr_[1:]): beam(p0 + UP * 86, p1 + UP * 86, 7, 6, Vector((p0.x - SC.x, p0.y - SC.y, 0)).normalized())

    # the walls inside: stone below with the arch from the hall, timber above with the gallery's door, the lookout
    if TOWER3:   # V: the arch from the services, the opening onto the lobby and the attic's door, all in the front wall
        HG = {"front": [(TG[2] - SV_ARCH[1], TG[2] - SV_ARCH[0], -12 if NEWEL else 0, SV_ARCH[2])]}   # (W: from the threshold's foot)
        AD = (sum(ATTIC_DOOR) / 2 - DOOR_W / 2, sum(ATTIC_DOOR) / 2 + DOOR_W / 2)   # W: the attic's door, a real one
        HU = {"front": [(TU[2] - V_OPEN[1], TU[2] - V_OPEN[0], ZG - (1 if NEWEL else 0), ZG + 202)] +    # since the attic was built
                       ([(TU[2] - AD[1], TU[2] - AD[0], ZAT, ZAT + DOOR_H)] if NEWEL else         # (2026-10-26; shut, no
                        [(TU[2] - ATTIC_DOOR[1], TU[2] - ATTIC_DOOR[0], ZAT, ZAT + 180)])}            # hole, before)
    elif TOWER2:   # U: the arch from the services in the front wall; the lobby's door in the right wall, the attic's in the front
        HG = {"front": [(TG[2] - SV_ARCH[1], TG[2] - SV_ARCH[0], 0, SV_ARCH[2])]}
        HU = {"right": [(TU[3] - LOBBY_DOOR[1], TU[3] - LOBBY_DOOR[0], ZG, ZG + 202)], "front": [(TU[2] - ATTIC_DOOR[1], TU[2] - ATTIC_DOOR[0], ZAT, ZAT + 180)]}
    else:
        HG = {"left": [(TOWER_ARCH[0] - TG[1], TOWER_ARCH[1] - TG[1], 0, TOWER_ARCH[2])]}
        HU = {"left": [(880 - TU[1], 1000 - TU[1], ZG, ZG + 202)]}
    for side, (W, L) in room_walls(*TG).items():
        face("stone", W, 0, L, ZB if NEWEL else 0, 400, HG.get(side, ()))   # (W: down to the basement's floor)
    if NEWEL:   # W: the basement's door, shut (what lies beyond is for later: under the hall, the planned training hall), on
                # the left wall just past the flight's foot (it ends along that wall at y 957: the first place, y 860..980,
                # had the last steps running into it)
        WBD, LBD = room_walls(*TG)["left"]
        # (2026-10-28, the basement built: plans/BASEMENT.md) no longer shut: vanilla's Solitude interior load door (its run
        # along its local x: turned 90 onto this wall) down to the basement's hallway (basement_gen.py's "base_up"), in the
        # shut door's lintel and posts
        # (the first walk of hall2bi: the basement door was wrong, its prompt only showing when looking down: turned
        # 90 its body, 7 deep over its local -y, stood in the wall. Its record's bounds: x 0..95, y -7..0, z 0..175, the origin
        # a corner: turned 270 it runs to +y from the origin and stands 7 into the room (+x); centred on y 850, framed its size)
        # (the walk of 2026-10-30: the door swapped: basement_gen's note) SHouseIntDoor02Load: 8 deep over its local +x, turned into the room, 112 wide, its origin 128 over the floor
        wall_beam(WBD, (850 - 56 - 14 - TG[1], ZB + 191 + 12), (850 + 56 + 14 - TG[1], ZB + 191 + 12), w=24, deep=10)
        for ua in (850 - 56 - 7 - TG[1], 850 + 56 + 7 - TG[1]): wall_beam(WBD, (ua, ZB), (ua, ZB + 191), w=14, deep=10)
        piece("meshes/architecture/solitude/doors/shouseintdoor02load.nif", "SHouseIntDoor02Load", (TG[0], 850, ZB + 128), 0,
              name="AGHall2BasementDoorDownB", role="base_down", pair="base_up", arrive=(TG[0] + 70, 850, ZB), arrive_yaw=90)
        PLAN.append({"t": "door", "level": -1, "a": [TG[0], 790], "b": [TG[0], 910], "to": "basement"})
        # (the walk of 2026-11-01: the empty bay under the upper flight, the chosen one of three) a wood store, what vanilla keeps
        # under its stairs (of 391 flights in 75 lived-in cells: firewood, barrels, baskets, buckets). Along the long wall, where the
        # stair's underside leaves head room (136 over the pile, 190 at the barrel; 123 in the far corner, nothing there), clear
        # of the door's way to the last step. The lantern is the corner's light: it is dark
        piece("meshes/clutter/firewood/firewoodpilelarge01.nif", "FirewoodPileLarge01", (603, 1016, ZB), 101)   # (its long side down the wall)
        piece("meshes/clutter/barrel02.nif", "Barrel02Static", (641, 866, ZB), 7)   # (the placement gate's boxes turn with the piece: a few degrees, not 62, and each a body apart)
        sit("meshes/clutter/basket05.nif", "Basket05", 640, 806, ZB, 12)
        sit("meshes/clutter/bucket01.nif", "Bucket01", 584, 864, ZB, 121)
        sit("meshes/clutter/common/candlelanternwithcandle01.nif", "CandleLanternwithCandle01", 645, 861, ZB + 80, 0)
        NEW_LIGHTS.append((645, 861, ZB + 110, 1.0e6, (1.0, 0.78, 0.55), "candle", 122, 0.0))
    for side, (W, L) in room_walls(*TU).items():
        # (the walk of 2026-11-01: the tower stairwell's inside made consistent, one finish, not plaster and stone both; stone: the foot's own stone on
        # up to the lookout, its rails and corner posts gone with the plaster; the doors keep their timber frames)
        face("stone", W, 0, L, ZG - (1 if NEWEL else 0), ZLK, HU.get(side, ()))   # (W: from 1 under the floor, behind the
                                                                                    # ledges 0.5 under it: a crack at their foot)
        if TOWER2:
            for h in HU.get(side, ()):
                # (the trim walk of 2026-11-07, trim on the left but none at the top or on the right; then the inside in the
                # tower's stone, as the doorway downstairs: the opening onto the lobby framed on the lobby's face,
                # none in the tower, its sides and head the tower's stone. The attic's door keeps its frame)
                if side == "front" and h[2] < ZG + 5: opening_frame(W, h[0], h[1], h[2], h[3], TT, rev="stone", both=True, near=False)
                else: opening_frame(W, h[0], h[1], h[2], h[3], TT)
            if side == "front" and NEWEL:                     # W: the attic's door, opening into the attic; its threshold
                door_leaf((AD[0], (TY0 + TU[1]) / 2), (AD[1], (TY0 + TU[1]) / 2), ZAT, (0, -1), "AGHall2AtticDoor")
                box("planks", (AD[0], TY0, ZAT - 12), (AD[1], TU[1], ZAT + 2))   # (to the attic's floor, 2 over the landing)
            elif side == "front":                             # the attic door, shut (the attic is not built yet)
                h = HU["front"][-1]; quad_on(W, h[0], h[2], h[1], h[3], -TT + 1, *ATLAS["archdoor"], kind="archdoor")
    if NEWEL:   # W: the opening onto the lobby's threshold through the wall (a hole into the wall over the arch until 2026-10-25)
        box("planks", (V_OPEN[0], TY0, ZG - 17), (V_OPEN[1], TU[1], ZG))
    if NEWEL:   # W: the lookout is a cell of its own: what follows is exported as its own part (hall2_lookout)
        PART = "lookout"
        box("planks", (TL[0], TL[1], ZLK - 18), (TL[2], TL[3], ZLK))
    for side, (W, L) in room_walls(*TL).items():
        face("stone", W, 0, L, ZLK, TOWER_TOP)   # (stone with the stair under it, 2026-11-01)
    apex = Vector(((TX0 + TX1) / 2, SC.y, TOWER_TOP + 520 - 40))   # the lookout is open to its pyramid roof
    cs_ = [Vector((TL[0], TL[1], TOWER_TOP)), Vector((TL[2], TL[1], TOWER_TOP)), Vector((TL[2], TL[3], TOWER_TOP)), Vector((TL[0], TL[3], TOWER_TOP))]
    for p_, q_ in zip(cs_, cs_[1:] + cs_[:1]):
        poly("planks", [p_, apex, q_]); beam(p_, apex, 14, 12, Vector((0, 0, -1)))
    # (the hall2bf walk, 2026-10-28, the strongroom lit too brightly: the hall's 512 fill in a room 290 by 300; trimmed
    # as Dragonsreach's basement trims its own (lightsurvey: WRInteriorLightYellow at -357..-370), and the cell inherits its
    # template's ambient (Hall2.cs), as vanilla's back rooms do)
    (LOOK_LIGHTS if NEWEL else INT_LIGHTS).append((SC.x, SC.y, ZLK + 200, 0.8e6, (1.0, 0.8, 0.6), "lamp", -330, 0.0))
    if NEWEL: chandelier(SC.x, SC.y, ZLK + 260, 1868); INT_LIGHTS.pop()   # (the test walk of 2026-11-06, a bit low: 60 higher; its chain 248)   # (the 2026-10-30 run: a light has a fixture: the rings' note, below)
    if NEWEL:   # W, the fit-out (2026-10-26): not a lookout but the guild's Strongroom (an interior
                # cell, so not truly a lookout). Its cell belongs to the guild (Hall2.cs), so what it holds is stolen if
                # taken. A desk for the ledgers against the wall facing the hatch's, a chest and strongboxes along the sides,
                # a rug; the hatch's side stays clear. (Its ladder up from the tower locked on the Guild Hall Key since 2026-10-29.)
        SIDE_ = Vector((-WN.y, WN.x, 0))                             # along the hatch's wall
        CX_, CY_ = (TL[0] + TL[2]) / 2, (TL[1] + TL[3]) / 2
        half_n = (TL[2] - TL[0]) / 2 if abs(WN.x) > 0.5 else (TL[3] - TL[1]) / 2   # centre to the hatch's wall
        half_s = (TL[3] - TL[1]) / 2 if abs(WN.x) > 0.5 else (TL[2] - TL[0]) / 2   # centre to the side walls
        at_ = lambda dn, ds: (CX_ + WN.x * dn + SIDE_.x * ds, CY_ + WN.y * dn + SIDE_.y * ds, ZLK)
        face_ = lambda v_: math.degrees(math.atan2(v_.x, v_.y)) % 360   # a yaw whose local +y points along v_
        # (2026-11-03, the known faults: NobleDesk02 is sat at from its local +y (vanilla's chairs: Pairs.cs, 51 out, 14..43 to a side), and it stood
        # with its +y to the far wall, the chair at its back: turned round on the same footprint (37 toward the room), its things on it where they
        # were (D_, DY_ below keep the old frame); vanilla's NobleChair02R, entered from its side, 51 out and 15 aside, facing it)
        LOOK_PLACE.append(("meshes/furniture/noble/nobledesk02.nif", at_(-(half_n - 68), 0), face_(WN), 1.0,
                           dict(ed="NobleDesk02")))                   # (its -y 49 to the far wall)
        LOOK_PLACE.append(("meshes/furniture/noble/noblechair02.nif", at_(-(half_n - 68 - 51), -15), face_(-WN), 1.0,
                           dict(ed="NobleChair02R", name="AGHallStrongroomDeskChair")))   # (the sitter faces local +y: the desk; named 2026-11-13
                                                                      # for the NPC session: Merila's strongroom hours at the desk)
        # (2026-11-03, the hatch on the left wall: the gate found the records' shelf over it and the furniture check a corner cut off
        # beyond the chest, between it and the desk) the chest into that corner, 10 off the right wall's foot rail (68.4 its half
        # length), the shelf slid along the front wall the least that clears the hatch by 4 (the hatch to x 364.5, the shelf's half 67.8)
        CHEST_DN = -(half_n - 10 - 68.4); SHELF_DN = half_n - (364.5 + 4 - TL[0]) - 67.8
        LOOK_PLACE.append(("meshes/furniture/noble/noblechest01.nif", at_(CHEST_DN, half_s - 34), face_(SIDE_), 1.0,
                           dict(ed="NobleChest01", owner="gm")))      # (its lid opens to its local -y, the room, its back, +y 24.8,
                                                                      # to the wall: it stood backwards, 2026-10-27; its back clear of
        LOOK_PLACE.append(("meshes/clutter/upperclass/uppershelf01.nif", at_(SHELF_DN, half_s - 36), face_(SIDE_), 1.0,   # the
                           dict(ed="UpperShelf01")))                  # wall's foot rail, 8 deep): the records' shelf beside it
                                                                      # (its back, local +y, to the wall)
        # (the hall2bf walk: strongboxes on the floor looked wrong, they belong on a table or shelf: vanilla
        # sets its strongboxes on tables, shelves and cupboards' counters (onrefs); under the side window (its sill 90 over the
        # floor) a chest of drawers, 63 tall, its back (local +y 12) to the wall's foot rail, the two strongboxes on it)
        DR_, DRY_ = at_(-15, -(half_s - 20.5)), face_(-SIDE_)
        LOOK_PLACE.append(("meshes/furniture/noble/noblechestdrawers01.nif", DR_, DRY_, 1.0, dict(ed="NobleChestDrawers01")))
        LOOK_PLACE.append(("meshes/architecture/whiterun/wrclutter/wrjorrvaskrrugsquare01.nif", at_(-46, 0), 0, 0.7,
                           dict(ed="WRJorrvaskrRugSquare01")))        # (under the desk's chair, clear of the hatch)
        # the clutter pass (2026-10-27): the guild's money and records, as vanilla keeps a treasury (research: the Markarth
        # Treasury House's silver ingots and silver candlesticks; the guild's ledger, TGR's business ledger's open book, the
        # one vanilla mesh of a ledger in use). The desk (NobleDesk02, its top 63.3 within local x -80..83, y -49..12, the
        # sitter at -y): the ledger open before him, ink and quill, a candlestick, a few coins counted out and a purse. The
        # records' shelf (UpperShelf01, its boards 17, 62, 107 within x -58..58, y -18.6..20.1, its back +y): rolled records
        # on the top board, a strongbox and a purse on the middle, silver ingots stacked and a large purse on the bottom.
        # Nothing on the chest or the strongboxes (they open). All the guild master's (as the cell)
        def on_(base_, yaw0_, lx_, ly_, z_, m_, ed_, yaw_=0, rx_=0):
            global _CB
            if _CB is None:
                _CB = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "clutter_bounds.json")))
            b_ = _CB[m_]; r_ = math.radians(rx_)
            lo_ = min(-yy * math.sin(r_) + zz * math.cos(r_) for yy in (b_["lo"][1], b_["hi"][1]) for zz in (b_["lo"][2], b_["hi"][2]))
            t_ = math.radians(yaw0_)
            pos_ = (base_[0] + lx_ * math.cos(t_) + ly_ * math.sin(t_), base_[1] - lx_ * math.sin(t_) + ly_ * math.cos(t_), ZLK + z_ - lo_ + 0.15)
            LOOK_PLACE.append((m_, pos_, (yaw0_ + yaw_) % 360, 1.0, dict(ed=ed_, owner="gm", settled=True, **({"rx": rx_} if rx_ else {}))))
            return pos_
        D_, DY_ = at_(-(half_n - 31), 0), face_(-WN)
        DT_ = 63.3
        on_(D_, DY_, 3, -22, DT_, "meshes/clutter/quest/tgrbusinessledger.nif", "AGHall2Ledger", 7)   # (since the hall2bf walk,
        # too orderly: the ledger pushed askew, the rolls and the ingots on the shelf left as a hand put them down)
        # (their latches, local +y (the lid hinges at -y), to the room: the clutter audit, 2026-10-28, found them to the wall)
        on_(DR_, DRY_, -21, -9, 63.3, "meshes/clutter/common/strongbox01.nif", "StrongBox", 194)
        on_(DR_, DRY_, 23, -11, 63.3, "meshes/clutter/common/strongbox01.nif", "StrongBox", 148)
        c_ = on_(D_, DY_, -62, -2, DT_, "meshes/clutter/silver/silvercandlestick02.nif", "SilverCandleStick02", 90)
        on_(D_, DY_, 52, -6, DT_, "meshes/clutter/common/inkwell01.nif", "Inkwell01")
        on_(D_, DY_, 30, -4, DT_, "meshes/clutter/common/quill01.nif", "Quill01", 96, rx_=90)   # (lying along the desk, short of the
        # well at 52 and clear of the ledger's x -12..18, y -32..-12)
        for k_, (cx_, cy_, h_) in enumerate(((38, -38, 0), (38.4, -38.2, 0.31), (38.1, -37.8, 0.62), (44, -34, 0), (33, -33, 0), (41, -42, 0))):
            on_(D_, DY_, cx_, cy_, DT_ + h_, "meshes/clutter/coin01.nif", "Gold001", k_ * 37)
        on_(D_, DY_, 70, -32, DT_, "meshes/plants/coinbagmed.nif", "CoinPurseMedium", 30)
        LOOK_LIGHTS.append((c_[0], c_[1], ZLK + DT_ + 58, 0.4e6, (1.0, 0.72, 0.45), "candle_small"))
        S_, SY_ = at_(SHELF_DN, half_s - 36), face_(SIDE_)
        for k_, (lx_, ly_, h_, yw_) in enumerate(((-14, -5, 0, 0), (19, 0, 0, 8))):   # (two, apart: the clip check)
            on_(S_, SY_, lx_, ly_, 107 + h_, "meshes/clutter/quest/tgparchment01.nif", "PaperRoll", yw_)
        on_(S_, SY_, -22, 2, 62, "meshes/clutter/common/strongbox01.nif", "StrongBox", 180)
        on_(S_, SY_, 30, 0, 62, "meshes/plants/coinbagmed.nif", "CoinPurseMedium", 200)
        for k_, (lx_, ly_, h_, yw_) in enumerate(((-30, 0, 0, 90), (-16, 2, 0, 84), (-23.5, 1, 5.4, 97), (2, -3, 0, 61))):
            on_(S_, SY_, lx_, ly_, 17 + h_, "meshes/dungeons/mines/ore/ingotsilver.nif", "ingotSilver", yw_)
        # cobwebs (a room seldom visited): vanilla's corner web (FXcobwebCorner01: its
        # origin in the corner, 117 to either side and 154 out along its local -y, 126 up and 41 down) at 0.45 in three of
        # the room's upper corners under the wall plate, its -y along the corner's bisector; the hatch's corner left clear
        for sx_, sy_ in ((-1, -1), (1, -1), (-1, 1)):
            cx_ = TL[0] + 9 if sx_ < 0 else TL[2] - 9; cy_ = TL[1] + 9 if sy_ < 0 else TL[3] - 9
            LOOK_PLACE.append(("meshes/effects/fxcobwebcorner01.nif", (cx_, cy_, TOWER_TOP - 14 - 126 * 0.45), face_(Vector((sx_, sy_, 0))), 0.45,
                               dict(ed="FXcobwebCorner01")))
        # and an easter egg, a human skull in a basket: in the corner behind the desk, a basket (Basket03,
        # 34 across, 31 tall) with a skull (BoneHumanSkullFullStatic, 18 long, 9 under its origin) sitting high in it, its crown
        # over the rim, turned to look out at whoever opens the hatch
        B_ = at_(-(half_n - 34), -(half_s - 34))                 # (10 off the walls' foot rail: the gate found it 16 in)
        LOOK_PLACE.append(("meshes/clutter/basket03.nif", B_, 23, 1.0, dict(ed="Basket03", owner="gm", settled=True)))
        # (the walk of hall2bl: placements not validated: the skull sitting high had nothing
        # under it, 22 over the basket's floor; on the floor now (its mesh 8.9 under its origin, the floor 1 over the basket's))
        LOOK_PLACE.append(("meshes/clutter/bones/humanskullfullstatic.nif", (B_[0], B_[1], ZLK + 1 + 8.9 + 0.15), (face_(WN) + 195) % 360, 1.0,
                           dict(ed="BoneHumanSkullFullStatic")))
        on_(S_, SY_, 30, 0, 17, "meshes/plants/coinbaglarge.nif", "CoinPurseLarge", 15)
    if NEWEL:   # (2026-10-28) the routines' Strongroom spot, in the Strongroom's own cell (~150)
        LOOK_MARKERS.append(("AGHallSpotStrongroom", "XMarkerHeading", at_(-20, 0), 180))
    PART = "interior"
    # (455: centred on the plain wall, 380..530; at 500, 96 wide, it ran 18 past the arch's edge: the 2026-10-30 run)
    SCONCES = ((455, TG[1], 230, 1), (325, TU[1], 640 if NEWEL else 600, 1)) if TOWER3 else ((430, TG[3], 230, -1), (600, TU[1], 700, 1))
    if NEWEL:   # W: vanilla's two-candle Imperial wall sconces (the stand-in read as an odd block): by the arch,
                # halfway up (lifted 40: with the landing the flight under it rose), and in the basement by its door
        for x_, yw, z_, ny in SCONCES + ((330, TG[1], ZB + 200, 1),):     # (the basement's: on the front wall by its door)
            yaw_s = 90 if ny > 0 else (180 if ny == 0 else 270)               # (its plate is its local x = 0, it faces -x)
            pos_ = (x_ + (0.5 if ny == 0 else 0), yw + 0.5 * ny, z_)
            if NEWEL and (x_, yw) == (325, TU[1]):                            # (2026-11-03: the landing now runs over its front-wall spot; on the
                ys_ = (YW1 + 9 + TU[3]) / 2                                   # left wall over the open stairwell, in the middle of its panel, the end wall's
                zs_ = round(step_under_(TU[0] + 20, ys_) + 196)              # post (9 proud) to the back wall (centre_check; at the post's side, 4 clear, its
                # candle lit the end wall's plaster at 0.80, the cap 0.45: plaster_check, 2026-11-03), 196 over the step under it as before)
                pos_, yaw_s = (TU[0] + 0.5, ys_, zs_), 180                    # (yaw 180: its candles, local -x, into the stairwell, not the wall)
                TOWER_PLACE.append(("meshes/clutter/imperial/impwallsconce02candleon01.nif", pos_, yaw_s, 1.0))
                INT_LIGHTS.append((TU[0] + 82, ys_, zs_ + 30, 1.0e6, (1.0, 0.7, 0.42), "candle", -26, 0.0))
                print("TOWER W: the stair sconce on the left wall at", [round(v_, 1) for v_ in pos_], "; the step under it", round(zs_ - 196, 1)); continue
            TOWER_PLACE.append(("meshes/clutter/imperial/impwallsconce02candleon01.nif", pos_, yaw_s, 1.0))
            # (2026-11-02, the walk: the upper stairwell sconce's light bled through the wall into the main hall: 24 off a wall 23-39 thick, 128 reached 65-81 past it and lit the great hall's corner.
            # A light passes walls: the tower's two stand out in the stairwell, 82 off, within their fixture's 90, and reach to the wall's far face and no further)
            if (x_, yw, z_, ny) in SCONCES: INT_LIGHTS.append((x_, yw + 82 * ny, z_ + 30, 1.0e6, (1.0, 0.7, 0.42), "candle", -26, 0.0))
            else: INT_LIGHTS.append((x_ + (24 if ny == 0 else 0), yw + 24 * ny, z_ + 30, 1.0e6, (1.0, 0.7, 0.42), "candle"))
    else:
        for x_, yw, z_, ny in SCONCES:   # iron candle sconces on the walls: by the arch, halfway up (V: where the stair passes
                                         # under them a head's height below, and its next turn clears them)
            ym = yw + ny * 7
            box("iron", (x_ - 5, min(yw, yw + ny * 12), z_ - 16), (x_ + 5, max(yw, yw + ny * 12), z_ - 12))
            box("candle", (x_ - 2.5, ym - 2.5, z_ - 12), (x_ + 2.5, ym + 2.5, z_))
            INT_LIGHTS.append((x_, ym + ny * 10, z_ + 12, 1.0e6, (1.0, 0.7, 0.42)))
    PLAN.append({"t": "spiral", "c": [SC.x, SC.y], "r": SR, "r0": SR0 + 3, "z": [0, ZG, ZLK], "th": STH, "top": TOWER_TOP,
                 "steps": [[round(a0, 2), round(a1, 2), round(zt, 1)] for a0, a1, zt, h_ in STEPS],
                 "rooms": [list(TG), list(TU), list(TL)], "arch": list(TOWER_ARCH[:2]), "door": [880, 1000],
                 "style": "square" if SQUARE else "round", "sq": [list(TSQ), list(TU)], "last": LAST, "tower": [TX0, TY0, TX1, TY1],
                 **({"u": {"arch": list(SV_ARCH[:2]), "lobby_door": list(LOBBY_DOOR) if LOBBY_DOOR else None,
                           "open": list(V_OPEN) if TOWER3 else None, "attic_door": list(ATTIC_DOOR), "z_attic": ZAT,
                           "z_top": ZTOP, "hatch": list(HATCH), "cw": TOWER3}} if TOWER2 else {})})
    if TOWER2:
        # U: the lobby in the plan (2026-10-25): from the right gallery's door to the stair's door and the patio door,
        # walled off from the staff quarters (a door through to them in its front wall)
        LB = (XU + TT, 600, 1060 if HEARTH else 1080, WY1 - TT)   # 416, 600, 1080, 906 (W: its right wall on the staff
                                                               # quarters' partition's line, the plan of 2026-10-26)
        LOBBY = [(LB[0], LB[1], LB[2], TY0), (TX1, TY0, LB[2], LB[3])]
        for r_ in LOBBY:
            box("planks", (r_[0], r_[1], ZG - 4), (r_[2], r_[3], ZG)); box("planks", (r_[0], r_[1], T1), (r_[2], r_[3], T1 + 14))
            PLAN.append({"t": "corridor", "level": 1, "r": list(r_)})
        STAFF_DOOR = (900, 1000)
        walls_ = [((Vector((LB[2], LB[1], 0)), Vector((-1, 0, 0)), Vector((0, 1, 0))), LB[2] - LB[0], [(LB[2] - STAFF_DOOR[1], LB[2] - STAFF_DOOR[0], ZG, ZG + 202)]),
                  ((Vector((LB[2], LB[3], 0)), Vector((0, -1, 0)), Vector((-1, 0, 0))), LB[3] - LB[1], []),
                  ((Vector((TX1, LB[3], 0)), Vector((1, 0, 0)), Vector((0, -1, 0))), LB[2] - TX1, [(REAR_X - 100 - TX1, REAR_X + 100 - TX1, ZG, ZG + 196)]),
                  ((Vector((LB[0], LB[1], 0)), Vector((0, 1, 0)), Vector((1, 0, 0))), TY0 - LB[1], [(604 - LB[1], 724 - LB[1], ZG, ZG + 202)]),
                  ((Vector((LB[0], TY0, 0)), Vector((1, 0, 0)), Vector((0, -1, 0))), TX1 - LB[0],      # the tower's front (V: the
                   [(V_OPEN[0] - LB[0], V_OPEN[1] - LB[0], ZG, ZG + 202)] if TOWER3 else []),         # stair's opening)
                  ((Vector((TX1, TY0, 0)), Vector((0, 1, 0)), Vector((1, 0, 0))), LB[3] - TY0,
                   [] if TOWER3 else [(LOBBY_DOOR[0] - TY0, LOBBY_DOOR[1] - TY0, ZG, ZG + 202)])]
        R5D = (786, 882)                                       # W: room 5's door, off the lobby (2026-10-26); in its back   # (the trim walk of 2026-11-07: 10 toward the front, its frame clear of the back door's in the corner and its lintel short of the back wall)
                                                               # corner since 2026-11-06, its post flush with the back wall
        if HEARTH:   # W: the patio door shut, on a whole wall (the first walk: holes into the void); the staff door open into the
                     # staff quarters' common room since they were built (2026-10-26), and room 5's door in the lobby's right wall
            walls_[2] = walls_[2][:2] + ([],)
            walls_[1] = walls_[1][:2] + ([(LB[3] - R5D[1], LB[3] - R5D[0], ZG, ZG + DOOR_H)],)
        PD_U = REAR_X - TX1                                    # W: the back door's middle along the lobby's back wall
        shut_ = {2: [(PD_U - 91.5, PD_U + 91.5, ZG, ZG + 175.5)]} if HEARTH else {}
        for k_, (W, L, hs) in enumerate(walls_):
            face("stucco", W, 0, L, ZG, T1, hs)
            for zz in (ZG + 12, T1 - 12): wall_rail(W, 0, L, zz, list(hs) + shut_.get(k_, []), w=22)
            if HEARTH and k_ in (0, 1):                        # their reveals through to the quarters' side (12)
                for h in hs: opening_frame(W, h[0], h[1], h[2], h[3], 12)   # (their far sides framed by the quarters' own walls: both=False)
        if HEARTH:   # W: the gallery door's threshold through the hall's wall, on the wing's ceiling (a 4 deep pit until 2026-10-25)
            box("planks", (XU, 604, ZG - 4), (XU + TT, 724, ZG))
        if HEARTH:   # W: the back door, a real one since the hall2t walk (2026-10-26: a working back door): the
                     # outside's door (SDoubleDoorInt01, its leaves 182 x 175) inside too, 2 before the whole wall as the front
                     # door stands, under a timber frame as the front door's; it takes one out in front of the outside one
                     # (Hall2.cs: AGHall2PatioDoorOut), and one coming in by the outside one lands 90 before it, facing the lobby
            WPD = walls_[2][0]
            piece("meshes/architecture/solitude/doors/sdoubledoorint01.nif", "AGHall2PatioDoorOut", (REAR_X, LB[3] - 2, ZG), 0, 1.0)
            for sx_ in (-1, 1): wall_beam(WPD, (PD_U + sx_ * 101.5, ZG), (PD_U + sx_ * 101.5, ZG + 205), w=21, deep=12)
            wall_beam(WPD, (PD_U - 112, ZG + 190), (PD_U + 112, ZG + 190), w=30, deep=14)
            PATIO_LAND = ((REAR_X, LB[3] - 90, ZG), 180)            # (hall frame, the yaw facing -y)
            PLAN.append({"t": "frame", "level": 1, "a": [REAR_X - 112, LB[3]], "b": [REAR_X + 112, LB[3]]})
        else:
            quad_on(walls_[2][0], REAR_X - 100 - TX1, ZG, REAR_X + 100 - TX1, ZG + 196, 1.0, *ATLAS["archdoor"], kind="archdoor")   # the patio door
            quad_on(walls_[0][0], LB[2] - STAFF_DOOR[1], ZG, LB[2] - STAFF_DOOR[0], ZG + 202, 1.0, *ATLAS["archdoor"], kind="archdoor")
        # (2026-10-29: the upstairs hall far too bright, with no windows to explain it; measured: the
        # one upper lamp the floors' trim missed, the lobby not being a room, so at its full 512 through the walls and the
        # floor) trimmed as the rooms' are, to reach 60 below its floor, its fade at 1.0 as Proudspire's windowless hall's
        # fills (SolitudeInteriorLightLG, 320, 1.0)
        PLAN.append({"t": "wall", "level": 1, "a": [LB[0], LB[1]], "b": [LB[2], LB[1]], "gaps": [list(STAFF_DOOR)]})
        PLAN.append({"t": "wall", "level": 1, "a": [LB[2], LB[1]], "b": [LB[2], LB[3]], "gaps": []})
    else:
        PLAN.append({"t": "corridor", "level": 1, "r": [XU + TT, 620, 1028, 760]})     # from the right gallery's door to the
        PLAN.append({"t": "corridor", "level": 1, "r": [828, 760, 1028, 906]})         # patio door, past the tower

if TAVERN_OPEN:
    # The plan: the tavern's middle open to the wing's roof, a gallery along each long wall joined to the ring
    # through the pavilion's wall, the cross gable's bay (x < -1080) kept as two rooms, the bay's partition carrying the
    # kitchen chimney (the exterior's stack stands at x -1090, y 710) with a fireplace on the tavern's side.
    WX0, WX1 = -1068, -XU - TT                                # the open part: the bay's partition to the pavilion's wall (-416)
    WF, WB, GF, GBK = 158, 906, 300, 760                      # the timber storey's walls inside; the galleries' open edges
    TW = math.tan(math.radians(48))                           # the wing roof's pitch; its ridge along x at y 532, 1098 up
    WYR = (WY0 - J + WY1) / 2; WZR = T1 + (WY1 - (WY0 - J)) / 2 * TW
    ZW = lambda y_: WZR - abs(y_ - WYR) * TW - 18             # its underside (665 at the walls, 1080 under the ridge)
    DORMERS = (-881, -571); DH = 73                           # the front slope's dormers: axes, half their inside width
    ZWF = ZG - 4 if HEARTH else ZG                            # W: the walls' foot on the ceilings' tops (414), not 4 over them:
    for W, L in (room_walls(WX0, WF, WX1, WB)["front"], room_walls(WX0, WF, WX1, WB)["back"]):   # a slot into the void and
        face("stucco", W, 0, L, ZWF, ZW(WF))                                                      # the hall until 2026-10-25
        for zz in (ZG + 12, ZW(WF) - 12): wall_beam(W, (0, zz), (L, zz), w=22, deep=8)
    for side, wins in (("front", (-571, -881)), ("back", (-571, -881))):   # (the back's inside on the front's axes since 2026-11-10) posts: the ends, the bay line, either side of each window
        W, L = room_walls(WX0, WF, WX1, WB)[side]; o_, r_, n_ = W
        for xa_ in (WX1 - 9, -726, WX0 + 9) + tuple(a + s * 50 for a in wins for s in (-1, 1)):
            wall_beam(W, ((o_.x - xa_) if r_.x < 0 else (xa_ - o_.x), ZG), ((o_.x - xa_) if r_.x < 0 else (xa_ - o_.x), ZW(WF)), w=18, deep=8)
    def gable_face(W, L, holes, doors=()):
        """an end wall of the open part, up to the roof's underside: plaster below the wall plates, strips above (doors: shut
        ones on it, where its rails stop too)"""
        face("stucco", W, 0, L, ZWF, ZW(WF), holes)
        o_, r_, n_ = W
        for k_ in range(24):
            ua, ub = L * k_ / 24, L * (k_ + 1) / 24
            ya, yb = (o_ + r_ * ua).y, (o_ + r_ * ub).y
            p_ = [o_ + r_ * ua + UP * ZW(WF), o_ + r_ * ub + UP * ZW(WF), o_ + r_ * ub + UP * ZW(yb), o_ + r_ * ua + UP * ZW(ya)]
            poly("stucco", p_)
        for zz in (ZG + 12, ZW(WF) - 12): wall_rail(W, 0, L, zz, list(holes) + list(doors), w=22)
    WE, LE = room_walls(WX0, WF, WX1, WB)["left"]             # the bay's partition: doors into its two rooms
    GMD = ((184, 280), (788, 884))                            # W: the guild master's office and bedroom (2026-10-26): real doors
    if HEARTH:
        gable_face(WE, LE, [(a_ - WF, b_ - WF, ZWF, ZG + DOOR_H) for a_, b_ in GMD])   # (from the wall's foot, as
        for (a_, b_), nm_ in zip(GMD, ("AGHall2GMOfficeDoor", "AGHall2GMBedroomDoor")):     # the ring's doorways)
            opening_frame(WE, a_ - WF, b_ - WF, ZWF, ZG + DOOR_H, TT)   # (the rooms' side framed by their own walls: both=False)
            door_leaf((-1080, a_), (-1080, b_), ZG, (-1, 0), nm_, right=nm_ == "AGHall2GMOfficeDoor")   # (the walk of 2026-11-01: the office door should open in toward the window and the wall beside the door: hinged on that jamb)
            box("planks", (-1092, a_, ZG - 4), (WX0, b_, ZG))   # (their thresholds through the wall)
    else:
        gable_face(WE, LE, [(172 - WF, 292 - WF, ZG, ZG + 202), (776 - WF, 896 - WF, ZG, ZG + 202)])
        for a_, b_ in ((172, 292), (776, 896)):
            quad_on(WE, a_ - WF, ZG, b_ - WF, ZG + 202, 1.0, *ATLAS["archdoor"], kind="archdoor"); opening_frame(WE, a_ - WF, b_ - WF, ZG, ZG + 202, 2)
    WP, LP = room_walls(WX0, WF, WX1, WB)["right"]            # the pavilion's wall, its tavern side: the doorways to the ring
    gable_face(WP, LP, [(WB - 292, WB - 172, ZWF, ZG + 202), (WB - 896, WB - 776, ZWF, ZG + 202)])
    if HEARTH:   # W: their thresholds through the pavilion's wall, on its ceiling strip (a 4 deep pit in each until 2026-10-25)
        for a_, b_ in ((172, 292), (776, 896)): box("planks", (WX1, a_, ZG - 4), (-XU, b_, ZG))
    # the roof's underside: boards on rafters, the front slope cut for the two dormers, a ridge beam, a truss on the bay post
    def slope(xa, xb, y_lo, y_hi, front):
        p_ = [Vector((xa, y_lo, ZW(y_lo))), Vector((xb, y_lo, ZW(y_lo))), Vector((xb, y_hi, ZW(y_hi))), Vector((xa, y_hi, ZW(y_hi)))]
        poly("planks", [p_[1], p_[0], p_[3], p_[2]])
    cuts = sorted(x_ + s * DH for x_ in DORMERS for s in (-1, 1)); xs_ = [WX0] + cuts + [WX1]
    ymeet = WYR - (WZR - 18 - 826) / TW                       # where a dormer's ceiling (826) meets the slope
    for i, (xa, xb) in enumerate(zip(xs_, xs_[1:])):
        slope(xa, xb, ymeet if i % 2 else WF, WYR, True)
        slope(xa, xb, WYR, WB, False)
        if i % 2 and HEARTH: slope(xa, xb, WF, 164, True)     # (W: the boards under a dormer's front, a slot into the void before)
    nf = Vector((0, TW, -1)).normalized(); nb = Vector((0, -TW, -1)).normalized()
    xx = WX0 + 32
    while xx < WX1 - 16:
        if not any(abs(xx - d_) < DH + 8 for d_ in DORMERS): beam((xx, WF, ZW(WF) - 2), (xx, WYR, WZR - 20), 12, 16, nf)
        else: beam((xx, ymeet, ZW(ymeet) - 2), (xx, WYR, WZR - 20), 12, 16, nf)
        beam((xx, WB, ZW(WB) - 2), (xx, WYR, WZR - 20), 12, 16, nb)
        xx += 64
    box("wood", (WX0, WYR - 16, WZR - 60), (WX1, WYR + 16, WZR - 18))
    # the truss on the bay post, as the great hall's above its tie beam (2026-11-13)
    arch_truss(lambda u, z, t=0.0: (-726 + t, WYR + u, z), (WB - WF) / 2, lambda u: ZW(WYR + u), ZW(WF) - 37, ZW(WF) - 3,
               585, 590, 150, 935, 760, 105, 800, braces=False)   # (no wall posts or arch braces: cut short by the galleries, they do not work there, the walk of 2026-11-13)
    for x_ in DORMERS:                                        # each dormer, from inside: a bay in the slope with its window
        for xs in (x_ - DH, x_ + DH):
            p_ = [Vector((xs, 164, ZW(164))), Vector((xs, ymeet, 826)), Vector((xs, 164, 826))]
            poly("planks", p_[::-1] if xs > x_ else p_)   # (2026-10-30: the dormers' sides in matching wood, not plaster)
        poly("planks", [Vector((x_ - DH, 164, 826)), Vector((x_ + DH, 164, 826)), Vector((x_ + DH, ymeet, 826)), Vector((x_ - DH, ymeet, 826))][::-1])
        face("planks", (Vector((x_ + DH, 164, 0)), Vector((-1, 0, 0)), Vector((0, 1, 0))), 0, 2 * DH, ZW(164), 826)
    # the galleries, each with a post on the bay line, and the open middle (W since the fit-out, 2026-10-26: no posts, the
    # hall's carved brackets on the ground floor's front and back walls instead, the tavern gallery's
    # posts replaced by the hall's side braces; their arms reach under the fascias, 6 past the open edges, as the hall's do)
    if HEARTH:
        # (two brackets side by side since the palette study, centred between the windows, each under a joist: a board
        # under the gallery stood out of line with the brace, and a pair of braces hides it)
        gallery(WX0, WX1, WF, GF, [((WX0, GF), (WX1, GF))], joist_at=-694)
        gallery(WX0, WX1, GBK, WB, [((WX0, GBK), (WX1, GBK))], joist_at=-694)
        for O_, out_, d_, dr_ in [((x_, 210.5), (0, 1), GF - 210.5 + 6, 185) for x_ in (-758, -694)] + \
                                 [((x_, 889.5), (0, -1), 889.5 - GBK + 6, 227) for x_ in (-758, -694)]:
            bracket(O_, out_, (1, 0), ZG - 40.5, d_ * BR["reach"], dr_ * BR["drop"], thick=BR["thick"], t=BR["t"], pendant=True)
            PLAN.append({"t": "bracket", "p": list(O_)})
    else:
        gallery(WX0, WX1, WF, GF, [((WX0, GF), (WX1, GF))], posts=[(-726, GF)])
        gallery(WX0, WX1, GBK, WB, [((WX0, GBK), (WX1, GBK))], posts=[(-726, GBK)])
    PLAN.append({"t": "void", "level": 1, "r": [WX0, GF, WX1, GBK]})
    for x_ in DORMERS:
        CH_ = os.environ.get("AG_CHAND", "low")               # (2026-10-26: hung lower; up high they did little
        if CH_ == "horn":                                     # for the tavern)
            piece("meshes/clutter/candles/candlehornchandelier01.nif", "CandleHornChandelier01", (x_, 530, 300), 0)
            beam((x_, 530, 300 + 218), (x_, 530, WZR - 40), 3, 3, (1, 0, 0), key="iron")   # (its own chain ends 220 up)
            INT_LIGHTS.append((x_, 530, 300, 9.0e6, (1.0, 0.72, 0.42), "candle"))
        elif CH_ == "low": chandelier(x_, 530, 340, WZR - 58, gather=90)   # (the ridge beam's underside is WZR - 60)
        else: chandelier(x_, 530, 720, WZR - 40)
        PLAN.append({"t": "chandelier", "p": [x_, 530]})
    if HEARTH:   # the tavern dressed (2026-10-26: a mounted head on the bare end wall, with shields and
                 # banners): Dragonsreach's mounted dragon skull (its stone panel
                 # faces its local +y, its back at local y -20, the skull hung from its origin, 245 below to 119 above) on the
                 # end wall over the void, Jorrvaskr's wall shields either side of it (they face their local -x, backs at 0),
                 # and Jorrvaskr's hanging banners from the galleries' fronts (the cloth 19..28 along its local -y, 179 down)
        # (the walk of 2026-10-30: no second dragon skull in the tavern; 2026-11-01: an elk, and a guild banner a little lower on the opposite side)
        # vanilla's mounted elk between the wall's two shields, its middle at their height, its plate on the plaster, its head along its local +y; the guild's banner on the far end
        # wall, on the room's axis, its back on the ledge the wall steps out to under 520, its cloth facing its local -y
        piece("meshes/clutter/deadanimals/mountedmaleelk.nif", "WallMountedElkMale", (-417, 530, 581), 270, exact=True)
        # (the walk of 2026-11-01: far higher than the other banners, and stiff as paper: now the holds' own cloth with the guild's picture, make_cloth_banner.py, hung as theirs:
        # (the walk of 2026-11-01: too small, off to one side and at an odd height: it stood at y 612 over a hearth long gone, 40 over the holds' brackets) on the wall's middle, the
        # chandeliers' line, its bracket on the holds' (ZG - 6), and bigger, so it reads as the hall's own: 1.3, its bracket's 38 to the wall with it
        BN_ = 1.3
        piece("meshes/architecture/riften/clutter/rtbanneranchor01.nif", "RTBannerAnchor01", (-1060 + 38 * BN_, 530, ZG - 6), 180, BN_, exact=True)
        piece("meshes/clutter/banners/genericbannerred01.nif", "AGHall2BannerCloth", (-1060 + 38 * BN_, 530, ZG - 6), 180, BN_, exact=True)
        for y_, ed_ in ((370, "WRIntShield05"), (690, "WRIntShield06")):
            piece(f"meshes/architecture/whiterun/wrclutter/{ed_.lower()}.nif", ed_, (WX1 - 9, y_, 600), 0)   # (clear of the posts)
        # the holds' banners from the galleries' fronts (since the hall2ah walk, 2026-10-27: a single
        # banner from each hold, four a front; Eastmarch left out: vanilla has none but the Stormcloak bear; the
        # Reach's is vanilla's plain one): vanilla's hall banners (CityBanner*01: GenericBannerRed01 with each hold's
        # texture, a skinned cloth 90 wide hanging 184 from its origin, the wall at its local +x) on Riften's bracket
        # (RTBannerAnchor01, the wall 38 along its local +x from its origin), as Mistveil Keep hangs them. The north's on
        # the front gallery, the south's on the back
        for row_, yy_, yw_, holds_ in ((GF, GF + 36, 90, ("Solitude", "Hjaalmarch", "Dawnstar", "Winterhold")),
                                       (GBK, GBK - 36, 270, ("Markarth", "Falkreath", "Whiterun", "Riften"))):
            for x_, h_ in zip((-986, -823, -660, -497), holds_):
                piece("meshes/architecture/riften/clutter/rtbanneranchor01.nif", "RTBannerAnchor01", (x_, yy_, ZG - 6), yw_, exact=True)
                piece("meshes/clutter/banners/genericbannerred01.nif", f"CityBanner{h_}01", (x_, yy_, ZG - 6), yw_, exact=True)
    # downstairs: the bay's stone partition (the kitchen and its storage behind it), the fireplace, the bar
    WG, LG = room_walls(-1060, 210, -380, 890)["left"]
    if HEARTH:   # W since the hall2r walk (2026-10-26): one kitchen-and-storage room behind the partition, its
                 # single way in an open arch at the barkeep's lane (not a door); a fireplace
                 # through the partition, open to the tavern and the kitchen (a pass-through fireplace), on the kitchen's chimney
        FB = (650, 730, 120)                                  # the firebox through the partition: y, its height
        HB = (630, 750, 160)                                  # its stone block each side: y, its top (the mantel shelf)
        # (the walk of 2026-11-01: the kitchen doorway's frame clipped: at 764..884 it stood 6 from the back wall with a frame 14 wide, 8 of it inside the wall; between that wall
        # and the kitchen's chimney breast, y 743.5, there is room for 118 and its two frames, each edge on its neighbour; was 120. frame_check.py)
        KA = (758, 876, 300)                                  # the kitchen's arch: y, its crown
        # (the fit-out, 2026-10-26: the pass-through fire walled up on the tavern side, one cooking fire, the
        # kitchen's: the tavern's face is whole, the firebox stops FK, 4 short of it, and the tavern's cheeks, mantel,
        # hearthstone and breast are gone)
        FK = -1064                                            # the firebox's back
        face("stone", WG, 0, LG, 0, 400, [(KA[0] - 210, KA[1] - 210, 0, KA[2])])
        arch_head(WG, KA[0] - 210, KA[1] - 210, KA[2], TS)
        WK = (Vector((-1100, 890, 0)), Vector((0, -1, 0)), Vector((-1, 0, 0)))   # its kitchen face (u = 890 - y), into the bay
        if os.environ.get("AG_KITCHEN_FIRE", "wr") == "wr":
            # since the hall2z round (2026-10-26: real fireplace assets in place of the built ones):
            # Whiterun's wall fireplace, as Breezehome's kitchen has it (WRIntWallStrChimney02: its oak frame and plaster face
            # at local y 136, facing -y, its firebox back to 184, the slate hearth before it), at 0.7 on the kitchen's face,
            # clear of the kitchen arch's ring (744); the wall open behind its firebox (the piece closes it), its pot hung
            # in the firebox, its breast up to the ceiling
            # (since the hall2ac walk, 2026-10-26: the cooking pot could not be reached or used, with bad misalignment
            # and clipping: at 0.7 the cook's spot fell inside the frame, the pot jammed under the arch, the piece's open
            # sides showed, the breast sat on its frame) at its own size, as Breezehome has it, set into a chimney breast as
            # deep as its frame (its front at local y 81: 69 out), its sides 2 outside the frame's, up to the ceiling; the
            # firebox through the wall (its back 2 before the liner); the pot as vanilla hangs it in the firebox (its own
            # spot 24 before it, 6 before the frame)
            KS, KY = 1.0, 615
            ox_ = -1066 - 184 * KS                                        # its firebox's back at -1066
            xf_ = ox_ + 81 * KS                                           # its frame's front (-1169)
            piece("meshes/architecture/whiterun/wrinteriors/wrintwallstrchimney02.nif", "WRIntWallStrChimney02", (ox_, KY, 0), 90, KS)
            face("stone", WK, 0, 890 - 186, 0, 400, [(890 - KY - 100, 890 - KY + 100, 0, 245), (890 - KA[1], 890 - KA[0], 0, KA[2])])
            arch_head(WK, 890 - KA[1], 890 - KA[0], KA[2])
            # the breast (the walk of 2026-10-29: new clipping round the kitchen fireplace: its front stood
            # at the frame's line, 13.5 proud of the piece's top, whose front is set back to local y 95 over 240 (measured on
            # the mesh), so a ledge showed under it; its sides 2 out made a strip): over the piece (its top at 256) its front
            # continues the piece's own top front; its sides 0.5 outside the piece's (±128: they close its open sides, too
            # thin to read), from the frame's front below 256 and from the top's front above. Plaster over the slate base, as
            # the whole-height stone faces before it came out of face() (the pieces here are too short for its rule)
            bw_ = 128 * KS + 0.5; xt_ = ox_ + 95 * KS - 0.5; zt_ = 256 * KS
            face("stucco", (Vector((xt_, KY + bw_, 0)), Vector((0, -1, 0)), Vector((-1, 0, 0))), 0, 2 * bw_, zt_, 400)
            for s_ in (1, -1):
                for x_, z0_, z1_ in ((xf_ + 0.5, 0, zt_), (xt_, zt_, 400)):   # (plaster to the floor, 2026-11-04: no panelled band)
                    k_ = "stucco"
                    if s_ > 0: face(k_, (Vector((-1100, KY + bw_, 0)), Vector((-1, 0, 0)), Vector((0, 1, 0))), 0, -1100 - x_, z0_, z1_)
                    else: face(k_, (Vector((x_, KY - bw_, 0)), Vector((1, 0, 0)), Vector((0, -1, 0))), 0, -1100 - x_, z0_, z1_)
            k0_, k1_ = KY - 100, KY + 100                                 # the opening's liner, behind the firebox
            for W_ in ((Vector((FK, k0_, 0)), Vector((-1, 0, 0)), Vector((0, 1, 0))),
                       (Vector((-1100, k1_, 0)), Vector((1, 0, 0)), Vector((0, -1, 0)))):
                face("stone", W_, 0, FK + 1100, 0, 245)
            face("stone", (Vector((FK, k1_, 0)), Vector((0, -1, 0)), Vector((-1, 0, 0))), 0, k1_ - k0_, 0, 245)
            poly("stone", [Vector((-1100, k0_, 245)), Vector((-1100, k1_, 245)), Vector((FK, k1_, 245)), Vector((FK, k0_, 245))])
            # (the walk of 2026-10-29: the ember bed stuck out under the hearth's lip, and the kitchen far too bright;
            # DevBench: with its fire light off, right) the fire, its pot and its light as vanilla sets this piece in all four
            # houses that use it (HallSpike `pairs`, the piece's local frame): FXfireWithEmbersLogs01 on the firebox's raised
            # floor (2.8, 166.3, 33.5), two FXfireWithEmbersLight beside it, the pot at (-16.5, 34.6, 4.5) turned -3 with its
            # spit (-15.5, 81.3, 18.2), the fire light at (2.3, 118.2, 69.6) trimmed as Uthgerd's on this piece (radius
            # -460, fade -1: every vanilla house hearth light is cut, 322 to 460). Local (lx, ly) is the hall's (ly, -lx) at 90
            def wr_(lx, ly): return (ox_ + ly * KS, KY - lx * KS)
            # (the walk of 2026-10-30: the fire clipped through the wall into the tavern: its ember bed is 96 deep and vanilla's sets it 166 from
            # the piece's origin, 30 past the firebox's back, into a house's thick wall; here 4 of liner and wall stand behind it. Moving the piece
            # into the kitchen shut the cook's pot off behind the table, which the cellar's hatch pins (tried: placement gate); a thicker tavern wall
            # took the aisle from 62 to 38. So the fire at 0.73, its front where vanilla's is, 118 from the origin, its back to the wall)
            FS_ = 0.73
            piece("meshes/effects/fxfirewithemberslogs01.nif", "FXfireWithEmbersLogs01", (*wr_(2.8, 153), 33.5), 90, FS_)
            piece("meshes/effects/fxfirewithembers02.nif", "FXfireWithEmbersLight", (*wr_(25.5, 155), 30.8), 90 + 251.1, FS_)
            piece("meshes/effects/fxfirewithembers02.nif", "FXfireWithEmbersLight", (*wr_(-20, 157), 30.8), 90, FS_)
            # (the MGO walk of 2026-11-04: the shelf over the kitchen fireplace stood empty; a basket only) a basket
            # on its mantel shelf where Amren's and Baldor's kitchens set one on this piece (HallSpike `pairs`: local -60.6, 112.0, 144.3, its turn the piece's)
            piece("meshes/clutter/basket01.nif", "Basket01", (*wr_(-60.6, 112.0), 144.3 * KS), 90)
            piece("meshes/furniture/smallcookingpot.nif", "CraftingCookingPotSm", (*wr_(-16.5, 34.6), 4.5), 90 - 2.9)
            piece("meshes/clutter/cookingspitsm01.nif", "CookingSpitSm01", (*wr_(-15.5, 81.3), 18.2), 90 - 2.9)
            INT_LIGHTS.append((*wr_(2.3, 118.2), 69.6, 3.0e6, (1.0, 0.55, 0.25), "fire", -460, -1.0))
            PLAN.append({"t": "hearth", "r": [xf_, KY - bw_, -1100, KY + bw_]})
        else:
            face("stone", WK, 0, 890 - 186, 0, 400, [(890 - FB[1], 890 - FB[0], 0, FB[2]), (890 - KA[1], 890 - KA[0], 0, KA[2])])
            arch_head(WK, 890 - KA[1], 890 - KA[0], KA[2])
            for W_ in ((Vector((FK, FB[0], 0)), Vector((-1, 0, 0)), Vector((0, 1, 0))),        # the firebox in the wall: its sides,
                       (Vector((-1100, FB[1], 0)), Vector((1, 0, 0)), Vector((0, -1, 0)))):     # its back, its head, all stone
                face("stone", W_, 0, FK + 1100, 0, FB[2])
            face("stone", (Vector((FK, FB[1], 0)), Vector((0, -1, 0)), Vector((-1, 0, 0))), 0, FB[1] - FB[0], 0, FB[2])
            poly("stone", [Vector((-1100, FB[0], FB[2])), Vector((-1100, FB[1], FB[2])), Vector((FK, FB[1], FB[2])), Vector((FK, FB[0], FB[2]))])
            xa_, xb_, xm_ = -1150, -1100, -1156                   # the fireplace's block on the kitchen's side
            box("stone", (xa_, HB[0], 0), (xb_, FB[0], HB[2])); box("stone", (xa_, FB[1], 0), (xb_, HB[1], HB[2]))   # its cheeks
            box("stone", (xa_, FB[0], FB[2]), (xb_, FB[1], HB[2]))                                           # its lintel
            box("wood", (xm_, HB[0] - 6, HB[2]), (xb_, HB[1] + 6, HB[2] + 10))                               # the mantel
            box("trim", (-1150, FB[0], 0), (FK, FB[1], 4))                       # the firebox's floor
            box("trim", (-1196, HB[0] - 10, 0), (-1150, HB[1] + 10, 4))          # the hearthstone
            box("stone", (-1136, 645, HB[2] + 10), (-1096, 735, 400))           # the kitchen's breast, up to its ceiling (room 2's above it)
            piece("meshes/clutter/woodfires/fireplacewood01burning.nif", "FireplaceWood01Burning", ((-1150 + FK) / 2, 690, 4), 90, 0.45)
            # the cooking pot hangs in the firebox's kitchen mouth (its pot 46 along its local +y from where the cook stands)
            piece("meshes/furniture/smallcookingpot.nif", "CraftingCookingPotSm", (-1166, 695, 4), 90)
            INT_LIGHTS.append((-1130, 690, 60, 3.0e6, (1.0, 0.55, 0.25), "fire", -322, -0.51))   # (its light casts shadows: it stays in the
            # kitchen; since the hall2bd walk, far too bright, trimmed as Breezehome trims its own hearth's: 446, fade 2.49)
        box("stone", (WX0, GF, 400), (-1060, GBK, ZWF))   # a ledge on the partition's top between the galleries, under the wall
                                                          # above (set 8 back): a slot there showed the kitchen through the
                                                          # partition's open top (leak_check, 2026-10-26)
        # the bar, built in (the tavern plan): from the tavern to the great hall's wall, round the back gallery's post
        # (since the hall2t walk, 2026-10-26: vanilla's bar kit, fine wood like the Bannered Mare's bar counter: its
        # pieces run along their local y, 64 a module, 64 deep, 78 high, the customers' panelled face at local -x, the
        # barkeep's shelves at +x, BarLeft01/BarRight01 a 33 end at local -y/+y placed on the end module's own origin, as
        # vanilla's inns do. Here: six modules from 4 into the hall's wall, the end at the free end; its back kept on the
        # lane's line, so it stands 12 further out than the built one did)
        if os.environ.get("AG_BAR_CAP", "1") == "1":   # (2026-10-26, an end piece was missing at the wall end: its last 16
            # stood in the great hall's arch (y 610..720), its open end seen from there and from the lane): five modules and
            # an end at each end, the wall's BarLeft01 4 into the wall
            # (2026-11-12, the tavern plan: the bar one module shorter at its free end, to make room for the corner table,
            # and 20 back toward the wall behind it, the nudge agreed in the re-layout: the customers' side gains it, the barkeep's
            # lane keeps 76 of navmesh. An L-shaped end was optional: the outside corner piece's arm would shut that lane)
            # (the walk of 2026-11-13: in game it stood a little too far back, so it comes forward slightly; the sandbox,
            # seats/r3 bar_fwd.py: forward 10 keeps every walkway green, the west doorway's way to the bar 111 -> 91, every seat green;
            # 12 turns it yellow. So 10, which leaves it 10 back of where it stood before the re-layout)
            BY_ = 746
            BAR = (-698, BY_ - 32, -376, BY_ + 32)
            for k_ in range(4):
                piece("meshes/clutter/barset/barstraight01.nif", "BarStraight01", (-441 - 64 * k_, BY_, 0), 270)
            piece("meshes/clutter/barset/barleft01.nif", "BarLeft01", (-441, BY_, 0), 270)     # (local -y: the hall's +x)
            piece("meshes/clutter/barset/barright01.nif", "BarRight01", (-633, BY_, 0), 270)
            MARKERS.append(("AGHallBarLeanMarker", "CounterBarLeanMarker", (-569, BY_ + 52, 0), 180))
        else:
            BAR = (-793, 704, -376, 768)
            for k_ in range(6):
                piece("meshes/clutter/barset/barstraight01.nif", "BarStraight01", (-408 - 64 * k_, 736, 0), 270)
            piece("meshes/clutter/barset/barright01.nif", "BarRight01", (-728, 736, 0), 270)   # (local +y: the hall's -x)
            # the barkeep's lean marker, as the Bannered Mare places its own: 52 out on a module's barkeep side, facing the bar
            MARKERS.append(("AGHallBarLeanMarker", "CounterBarLeanMarker", (-536, 736 + 52, 0), 180))
        # the back bar: a niche through the great hall's wall into the mirror's mass at the lane's end (the tavern plan:
        # a niche built into the foundation), the hall's side of the mass left whole (its faces 36 and 56 away)
        # (since the hall2ad walk, 2026-10-26: the bar niche matched to the width of the display case's niche above
        # it: its back from -272 to -228, as far into the mass as the passage over it reaches)
        # (its far side brought in to the keg counter's end, 902 + 4, since the walk of 2026-10-27, so the keg table
        # fits it better; still behind the arch's jamb at 886)
        NX, NICHE_Y0 = (-340, -228, 906), 768                 # its chamber: x, its back, its far side y; its near side y (the
                                                              # opening through the wall: 768..890, the lane's end)
        face("stone", (Vector((NX[1], NICHE_Y0, 0)), Vector((-1, 0, 0)), Vector((0, 1, 0))), 0, NX[1] - NX[0], 0, 240)   # its sides
        WNC = (Vector((NX[0], NICHE_Y0, 0)), Vector((0, 1, 0)), Vector((1, 0, 0)))   # its front, round the arch (u = y - 768)
        face("stone", WNC, 0, NX[2] - NICHE_Y0, 0, 240, [(NICHE_W[0] - NICHE_Y0, NICHE_W[1] - NICHE_Y0, 0, NICHE_W[2])])
        arch_head(WNC, NICHE_W[0] - NICHE_Y0, NICHE_W[1] - NICHE_Y0, NICHE_W[2], key="stone", ring=0)
        face("stone", (Vector((NX[0], NX[2], 0)), Vector((1, 0, 0)), Vector((0, -1, 0))), 0, NX[1] - NX[0], 0, 240)
        face("stone", (Vector((NX[1], NX[2], 0)), Vector((0, -1, 0)), Vector((-1, 0, 0))), 0, NX[2] - NICHE_Y0, 0, 240)   # its back
        poly("stone", [Vector((NX[0], NICHE_Y0, 240)), Vector((NX[0], NX[2], 240)), Vector((NX[1], NX[2], 240)), Vector((NX[1], NICHE_Y0, 240))])   # its ceiling
        box("floor", (-380, NICHE_W[0], -12), (NX[0], NICHE_W[1], 0))        # the threshold through the wall (the hall's flags
                                                                             # run on under the mass: the chamber's floor)
        NEW_LIGHTS.append((-290, 840, 200, 0.6e6, (1.0, 0.72, 0.45), "candle_small"))
        piece("meshes/clutter/candles/candlehorntable01.nif", "CandleHornTable01", (-251, 822, 165), 90)   # (its fixture, on the shelf behind the bar)
        PLAN.append({"t": "counter", "r": list(BAR)})
        if os.environ.get("AG_KITCHEN_FIRE", "wr") != "wr": PLAN.append({"t": "hearth", "r": [-1150, HB[0], -1100, HB[1]]})
        PLAN.append({"t": "niche", "r": [-380, NICHE_Y0, NX[1], NX[2]]})
        PLAN.append({"t": "wall", "level": 0, "a": [-1080, 186], "b": [-1080, 890], "gaps": [list(KA[:2])], "th": 40})
    else:
        face("stone", WG, 0, LG, 0, 400, [(230 - 210, 350 - 210, 0, 240), (780 - 210, 880 - 210, 0, 240)])
        for a_, b_ in ((230, 350), (780, 880)):
            quad_on(WG, a_ - 210, 0, b_ - 210, 240, 1.0, *ATLAS["archdoor"], kind="archdoor"); opening_frame(WG, a_ - 210, b_ - 210, 0, 240, 2)
        box("stone", (-1060, 640, 0), (-1024, 760, ZW(760) - 2))                       # the chimney breast, up to the roof
        box("iron", (-1026, 664, 0), (-1022, 736, 104)); box("trim", (-1032, 646, 108), (-1016, 754, 122))   # the fire's mouth, the mantel
        INT_LIGHTS.append((-1000, 700, 50, 3.0e6, (1.0, 0.55, 0.25)))
        box("wood", (-760, 790, 0), (-470, 830, 72)); box("trim", (-766, 784, 72), (-464, 836, 80))           # the bar, under the back gallery
        for zz in (40, 110, 180): box("wood", (-760, 870, zz), (-470, 890, zz + 6))
        PLAN.append({"t": "counter", "r": [-766, 784, -464, 836]}); PLAN.append({"t": "hearth", "r": [-1060, 640, -1024, 760]})
        PLAN.append({"t": "wall", "level": 0, "a": [-1080, 210], "b": [-1080, 890], "gaps": [[230, 350], [780, 880]], "th": 40})
    if HEARTH:   # W: the tavern's seating, vanilla pieces (2026-10-26: real tables and chairs in place of the stand-ins,
                 # laid out so the seating makes sense to the eye and in use). Measured from
                 # vanilla's 18 inns (research/taverns/seating.py): its Nordic inns seat on FarmTable01 with its bench piece on
                 # the table's own origin and yaw (FarmTableBench02: two benches, two seats each, 86 from the table's axis),
                 # wooden chairs 26 off round tables, bar stools facing the bar about 70 out and 90-115 apart. Spaced to the
                 # restaurant rules (38-42" between rows, 18-24" behind a seat, 36" aisles: about 70, 35 and 65 in game units).
                 # 16 seats since the fit-out (the walk of 2026-10-26: the chair squeezed against the wall and the two by
                 # the fire, walled up, are gone): two farm tables across the middle (8) on Jorrvaskr's square rugs, a round
                 # table under each front window (4), four stools at the bar; the strip by the arches stays clear
                 # (since 2026-11-12, the tavern plan, after the re-layout study measured NPCs' routes squeezed to
                 # 48-52 and five of the sixteen seats unreachable (build/navtrial/tavern_round4_*.png): 13 seats. The two long tables
                 # 40 toward the front windows and 22 apart, end to end (closer together, not touching),
                 # so NPCs walk round the pair and every way to the bar, the kitchen and each seat is two actors wide; the window
                 # tables gone; a round table for two at the back window, where the bar was shortened to make room; three stools)
        SEAT = []
        TY_ = 437                                             # (the long tables' axis: 478 until 2026-11-12)
        # (since the hall2t walk, 2026-10-26: the hall is no slum: upper-class pieces in place of the
        # farm and common ones; UpperTableBench02 is table and both benches in one, 110 either side of its axis)
        for x_ in (-829, -611):                               # the middle row
            piece("meshes/clutter/upperclass/uppertablebench02.nif", "UpperTableBench02", (x_, TY_, 0), 0)
            SEAT += [("bench", x_ + dx_, TY_ + dy_) for dx_ in (-40, 40) for dy_ in (-83, 83)]
            # (at 0.75, 221 square, with the tables 218 apart: each 2 out from its table, 1.5 apart)
            piece("meshes/architecture/whiterun/wrclutter/wrjorrvaskrrugsquare01.nif", "WRJorrvaskrRugSquare01", (x_ - 2 if x_ < -700 else x_ + 2, TY_, 0), 0, 0.75)
        RT_ = (-848, 821)                                     # the round table at the back window, as planned: a chair
        piece("meshes/clutter/upperclass/uppertableround01.nif", "UpperTableRound01", (RT_[0], RT_[1], 0), 0)   # toward the room, one
        for cx_, cy_, yw_ in ((-850, 752.5, 0), (-925, 835, 90)):                                               # toward the kitchen
            piece("meshes/clutter/upperclass/upperchair01.nif", "UpperChair01LR", (cx_, cy_, 0), yw_); SEAT.append(("chair", cx_, cy_))   # (side-entry, as vanilla sets them at its round tables: 2026-11-07, NPCs stood up onto the tables)
        # (the walk of 2026-11-13: room for 4 stools instead of 3, as they stood well spaced: vanilla's bar stools stand
        # 70-90 apart (pairs WoodenBarStool, every inn); four 70 apart keep every seat and way green, the sandbox stools4.py)
        for x_ in (-657, -587, -517, -447):                   # the bar's stools
            piece("meshes/furniture/woodenbarstool.nif", "WoodenBarStool", (x_, BY_ - 58, 0), 0); SEAT.append(("stool", x_, BY_ - 58))
        # (2026-11-18: no drink stain before the bar for now: the AGH2XSpill decal read badly in VR; its texture and key are kept)
        # (2026-11-12, after the décor renders: the corner curio shelf, ivy on the wall that may still hang from under the
        # gallery, and an urn with a plant) the south-east corner's curio, a noble corner
        # shelf of jobs brought home (jars, troll fat, a giant's toes, a daedra heart, a sabre cat's tooth, a mammoth tusk on top), 5 out of
        # the corner so it clears the panelling; ivy against the east wall from under its gallery, over each window's arch (the gallery's two carved pendants stand 44 apart between the windows: no clump fits there), and one over the
        # bar; in the north-east corner a glazed urn with a sword fern (the corner is the way to the east benches' seats: 35 across is
        # the most it takes and keep that way green, the renders' sandbox; a barrel or a keg turned it orange or yellow)
        CX_, CY_ = -1049.0, 221.0                               # the curio's origin (its back 5 off both walls), turned to face the room
        piece("meshes/furniture/noble/noblecornershelf.nif", "NobleCornerShelf", (CX_, CY_, 0), 270)
        # (the walk of 2026-11-13: the jobs' trophies made no sense in a tavern, and they lay on the floor, thrown
        # as the cell loaded; a few mead bottles and a pitcher instead) vanilla's spots on this shelf, each in the shelf's own frame
        # and at vanilla's heights, which its houses share (onrefs NobleCornerShelf with ONREFS_XY=1: mead at (36,-12,53) and (11,-17,105)
        # in Windhelm's Cruel-Sea house, a jug at (20,-23,53) in the Hearthfire houses, a potion at (19,-11,105)). The jug's spout turned
        # away from the bottle beside it (its collision reaches 16 toward its +x)
        for m_, e_, lx_, ly_, z_, rel_ in (("clutter/silver/silverjug01.nif", "SilverJug01", 21, -25, 53, 128),
                                           ("clutter/ingredients/mead01.nif", "FoodMead", 36, -12, 53, -93),
                                           ("clutter/ingredients/mead01.nif", "FoodMead", 11, -17, 105, -81),
                                           ("clutter/ingredients/mead01.nif", "FoodMead", 19, -11, 105, -58)):
            piece("meshes/" + m_, e_, (CX_ - ly_, CY_ + lx_, z_), (270 + rel_) % 360)
        # (the walk of 2026-11-13: the urn with the fern far too small for this corner, and a bigger piece is not in the way: the
        # sandbox's "yellow" was only a shortcut past the corner, every seat keeps a green way with 80 across there. Of three
        # rendered options, the barrel first planned. Static, as the hall's yard's: nothing to knock about. The urn moves to the
        # guild services)
        piece("meshes/clutter/barrel02.nif", "Barrel02Static", (-411, 241, 0), 90)   # (square to the walls: at 120 its box reached 7 into the east wall)   # (54 across: 2 off the panelling's skirting)
        # (the walk of 2026-11-13: the ivy stood neither against the wall nor up under the gallery: it stood 34 off
        # the plaster with its top 32 under the gallery's boards, the mistake KNOWLEDGEBASE.local.md records from the site's ivy, 2026-10-24)
        # hung as vanilla hangs it: its wall on its local +y, the origin 4 off a flat wall (scaled), its leaves' top (76 over the origin)
        # at the gallery's boards (400, between the joists, which run through its top as through a creeper on a ceiling). The west one
        # 0.78, not 1.0: at full size it hung over its window's arch frame (276, 10 proud); ivy_fit_check.py now gates the interior's ivy
        for x_, wall_, yw_, sc_ in ((-571, 210, 180, 0.75), (-881, 210, 180, 0.72), (-440, 210, 180, 0.65), (-590, 890, 0, 0.78)):
            y_ = wall_ + (4 if yw_ == 180 else -4) * sc_
            # (the walk of 2026-11-13: still too low; the gallery's underside is its floor boards, not the joists' undersides: the
            # leaves' bound reached 400 but what shows stops lower: the mesh's top 20 are flat cards lying back into the wall, its dense leaves
            # reach 55 over the origin (54 at the 90th percentile of the leaves in front of the wall). Those at the boards' 400; the flat
            # cards end inside the wall and the deck's boards, 414 at most)
            piece("meshes/architecture/farmhouse/ivy02.nif", "Ivy02", (x_, y_, 400 - 55 * sc_), yw_, sc_)
        PLAN.append({"t": "seating", "room": "tavern", "seats": [list(s_) for s_ in SEAT]})
        print("TAVERN seats", len(SEAT))
        # the tavern's clutter, from vanilla's inns (research/taverns/refs_all.tsv: a long table carries about two candle
        # horns, two tankards, two plates with bread, a wine and a bottle; a round one a candle horn, a goblet, a tankard;
        # a bar top a few tankards, a bottle, cheese and a rag; behind it the bottles). Each table a little different: one
        # mid-meal, one being cleared
        T_ = "meshes/clutter/"
        TBT = 56.5                                              # (the long tables' board, measured: 59 is only its rim, which
                                                                # set everything 2.5 up in hall2ar)
        def place_setting(x, y, side, full=True, plate=True):   # a diner's place: plate before the bench, tankard by it; each
            r_ = random.Random(f"seat {x:.0f} {y:.0f}")         # diner's own (pushed, turned, the tankard either hand), not a
            px_, py_ = x + r_.uniform(-7, 7), y + side * r_.uniform(-3, 5)   # mirror of the next (2026-10-27)
            a_ = r_.uniform(-28, 28)                             # (plate=False: its tankard alone, where it stood: the draws kept)
            if plate: sit(T_ + "dining set/basicwoodenplate01.nif", "BasicWoodenPlate01", px_, py_, TBT, a_)
            if full:
                b_ = (px_ + r_.uniform(-8, 4), py_ + r_.uniform(-2, 2), r_.uniform(0, 360))
                if plate: sit(T_ + "food/bread01b.nif", "FoodBread01B", b_[0], b_[1], TBT + 4, b_[2])
            hand_ = r_.choice((-1, 1, 1))
            sit(T_ + "dining set/basictankard01.nif", "BasicTankard01", px_ + hand_ * r_.uniform(29, 36), py_ - side * r_.uniform(-2, 9), TBT, r_.uniform(0, 360))
        for k_, x_ in enumerate((-829, -611)):                  # the long tables (194 x 112), diners on y +-
            for dx_ in (-48, 48):
                for side_ in (-1, 1):
                    if k_ == 1 and dx_ > 0 and side_ > 0: continue   # (a diner gone from the table being cleared)
                    # (the test walk of 2026-11-06, more clutter on the tavern tables than needed: cut, the first table's two
                    # far-side plates with their bread and the second's empty plate; their tankards stay)
                    place_setting(x_ + dx_ + side_ * 4, TY_ + side_ * 30, side_, full=(k_ == 0 or dx_ < 0),
                                  plate=not ((k_ == 0 and side_ > 0) or (k_ == 1 and dx_ > 0)))
            sit(T_ + "candles/candlehorntable01.nif", "CandleHornTable01", x_ - 20, TY_, TBT, 90 if k_ else 84)
            NEW_LIGHTS.append((x_ - 20, TY_, TBT + 30, 0.35e6, (1.0, 0.72, 0.45), "candle_small"))
            if k_ == 0:
                sit(T_ + "food/bread01a.nif", "FoodBread01A", x_ + 22, TY_ - 8, TBT, 15)
                sit(T_ + "food/cheesewheel02a.nif", "FoodCheeseWheel02A", x_ + 50, TY_ + 8, TBT, 0)
                sit(T_ + "wine/winebottle02b.nif", "FoodWineBottle02", x_ - 62, TY_ + 4, TBT, 0)
                # (its second bottle, at the right end, cut with the plates, 2026-11-06)
            else:                                               # (being cleared: a bowl, the bottle, a rag)
                sit(T_ + "dining set/basicwoodenbowl01.nif", "BasicWoodenBowl01", x_ + 30, TY_ - 4, TBT, 0)
                sit(T_ + "ingredients/mead01.nif", "FoodMead", x_ - 58, TY_ + 2, TBT, 0)
                sit(T_ + "common/rag01.nif", "Rag01", x_ + 62, TY_ + 6, TBT, 70)
        # the round table at the back window (top 62, radius 39): two sharing a flagon, each tankard before its drinker, the candle
        # at the back by the wall (its light within 130 of the window's daylight: lit at night only, by the rule below)
        sit(T_ + "candles/candlehorntable01.nif", "CandleHornTable01", RT_[0] + 12, RT_[1] + 24, 62, 90)
        NEW_LIGHTS.append((RT_[0] + 12, RT_[1] + 24, 62 + 30, 0.35e6, (1.0, 0.72, 0.45), "candle_small"))
        sit(T_ + "common/flagon01.nif", "Flagon", RT_[0] - 6, RT_[1] - 4, 62, 0)
        sit(T_ + "dining set/basictankard01.nif", "BasicTankard01", RT_[0] + 2, RT_[1] - 24, 62, 200)
        sit(T_ + "dining set/basictankard01.nif", "BasicTankard01", RT_[0] - 24, RT_[1] + 8, 62, 20)
        # the bar top (78; the customers' edge at BY_ - 32): tankards set out, a flagon, cheese on the board, a rag on the end
        # piece, a candle; the y's below written for the bar at 756, moved with it (BDY_)
        BDY_ = (BY_ - 756) if os.environ.get("AG_BAR_CAP", "1") == "1" else 0
        for x_, y_, m_, e_, yw_ in ((-660, 738, "dining set/basictankard01", "BasicTankard01", 30), (-614, 742, "dining set/basictankard01", "BasicTankard01", 300),
                                   (-528, 736, "common/flagon01", "Flagon", 0), (-682, 764, "common/rag01", "Rag01", 10),
                                   (-470, 762, "food/cheesewheel02a", "FoodCheeseWheel02A", 0), (-490, 748, "food/cheesewedge02", "FoodCheeseWedge02", 40),
                                   (-575, 750, "candles/candlehorntable01", "CandleHornTable01", 90)):
            sit(T_ + m_ + ".nif", e_, x_, y_ + BDY_, 78, yw_)
        NEW_LIGHTS.append((-575, 750 + BDY_, 78 + 30, 0.35e6, (1.0, 0.72, 0.45), "candle_small"))
        # under the bar on the barkeep's side (the modules' shelves: at 55, y 748..783, 23 under the top; at 16, y 731..783):
        # sparse, as vanilla's are (an even row of bottles looked unnatural, 2026-10-27): a few tankards
        # and a goblet in a clump above, two meads and a wine below, long runs bare
        strew((-655, 768 + BDY_), (-462, 768 + BDY_), 55, ((T_ + "dining set/basictankard01.nif", "BasicTankard01", 3), (T_ + "glazedgoblet01.nif", "GlazedGoblet01", 1)),
              "bar shelf 55", depth=4)
        strew((-655, 762 + BDY_), (-462, 762 + BDY_), 16, ((T_ + "ingredients/mead01.nif", "FoodMead", 2), (T_ + "wine/winebottle02b.nif", "FoodWineBottle02", 1)),
              "bar shelf 16", depth=6, lie=0.25)
        niche_dress(T_)
    else:
        for (xa, xb), (ya, yb) in [((-990, -820), (420, 480)), ((-720, -560), (420, 480)), ((-990, -820), (580, 640)),
                                   ((-720, -560), (580, 640)), ((-990, -880), (225, 275)), ((-700, -590), (225, 275))]:
            box("wood", (xa, ya, 0), (xb, yb, 72)); PLAN.append({"t": "table", "r": [xa, ya, xb, yb]})
    PLAN.append({"t": "wall", "level": 1, "a": [-1080, WF], "b": [-1080, WB], "gaps": [[172, 292], [776, 896]]})

# ---------------------------------------------------------------- the working rooms (W, 2026-10-26: after the hall2r walk)
def small_hearth(xf, sgn, back, yc, zf, z_top):
    """a small fireplace in a chimney breast (the fit-out, 2026-10-26: fireplaces for the GM's bedroom and
    room 5): the breast from x `back` to its room face xf (facing sgn along x), y yc +-45, from 4 under
    the floor zf to z_top; a firebox 40 deep, 50 wide, 70 high in it, a hearthstone and a mantel shelf, a low fire"""
    xi = xf - sgn * 40                                        # the firebox's back
    lo, hi = sorted((back, xi)); box("stone", (lo, yc - 45, zf - 4), (hi, yc + 45, z_top))
    lo, hi = sorted((xi, xf))
    box("stone", (lo, yc - 45, zf - 4), (hi, yc - 25, z_top)); box("stone", (lo, yc + 25, zf - 4), (hi, yc + 45, z_top))   # its cheeks
    box("stone", (lo, yc - 25, zf + 70), (hi, yc + 25, z_top))                     # over the firebox
    box("trim", (lo, yc - 25, zf), (hi, yc + 25, zf + 2))                           # its floor
    a_, b_ = sorted((xf, xf + sgn * 40)); box("trim", (a_, yc - 35, zf), (b_, yc + 35, zf + 2))   # the hearthstone
    a_, b_ = sorted((xf, xf + sgn * 8)); box("wood", (a_, yc - 50, zf + 86), (b_, yc + 50, zf + 94))   # the mantel shelf
    piece("meshes/clutter/woodfires/fireplacewood01burning.nif", "FireplaceWood01Burning", ((xf + xi) / 2, yc, zf + 2), 0, 0.22)
    NEW_LIGHTS.append((xf + sgn * 20, yc, zf + 60, 1.0e6, (1.0, 0.55, 0.25), "fire_small"))
    PLAN.append({"t": "hearth", "r": [lo, yc - 45, hi, yc + 45]})          # (lo, hi: the firebox's x)

def manor_fireplace(xw, sgn, yc, zf, sc, rail=0.0, ztop=400, y_lo=None, y_hi=None):
    """vanilla's Solitude manor fireplace (SMdCFirePlace01: Proudspire's, Erikur's, Vittoria Vici's) against the wall at x xw,
    facing sgn along x, centred on y yc, at scale sc (2026-10-26: the built hearths read as placeholders, so real
    fireplace assets instead). As the game places it (vanilla's five uses agree): 224 wide, its back 88 and
    its front 204 along its local +y, its fire (FXfireWithEmbersHeavy at 1.13, its own turn 270) at local y 158. rail: what
    stands out of the wall behind it (its back stands 4 before that). It faces its local -y (in Solitude's kit it stands in
    a recess, its origin on the room's side): here it stands out of the wall, its back (local y 204) against it"""
    yaw_ = 270 if sgn > 0 else 90                                         # (its local -y to the room)
    xb_ = xw + sgn * (rail + 4)                                           # its back's plane, 4 off the wall (0.5 until
                                                                          # 2026-10-26: the great hearth flickered on its wall)
    piece("meshes/architecture/solitude/interiors/smdcfireplace01.nif", "SMdCFirePlace01", (xb_ + sgn * 204 * sc, yc, zf), yaw_, sc)
    piece("meshes/effects/fxfirewithembers01.nif", "FXfireWithEmbersHeavy", (xb_ + sgn * 46 * sc, yc, zf), (yaw_ + 270) % 360, 1.13 * sc)
    NEW_LIGHTS.append((xb_ + sgn * 150 * sc, yc, zf + 70 * sc, 1.0e6, (1.0, 0.55, 0.25), "fire_small"))
    # its chimney breast (since the hall2ac walk, 2026-10-26, another broken fireplace: the piece is a facade with
    # its hearth behind it, made for a recess in Solitude's thick walls; stood before a plain wall its hearth showed open at
    # both sides): stone from the facade's back (local depth 136) to the wall, as wide as the facade, up to the room's
    # ceiling, the fire's mouth open in it (local +-82, 108 high) and lined to the piece's back
    # (the walk of 2026-11-01, still a gap: the facade's outline is notched, 104 wide at places against the 112 of the side first closed; hearth_check.py found the lines through. The
    # stack's front now stands 2 behind the facade's faces, local depth 127, the mouth the only way in)
    W_, xm_ = 112 * sc, xb_ + sgn * (77 * sc)                            # its half width; its front
    xs0_, xs1_ = sorted((xm_, xw))
    n_ = Vector((sgn, 0, 0))
    # (the walk of 2026-11-03, FUS in VR: more gaps and seams: the breast was the facade's width, and each fireplace stands between a wall and a
    # door's frame wider than that, so a slot stood open floor to ceiling beside it, 2.4 to 12 wide) y_lo, y_hi: the faces either side; the breast's front
    # and sides run 0.5 into them, the mouth still on the fireplace. Bare stone ("stone!"), as the upstairs two read: the counter's, from the floor, was
    # plastered by face()'s rule for the stone storey's walls (stone, like upstairs)
    lo_, hi_ = (y_lo if y_lo is not None else yc - W_), (y_hi if y_hi is not None else yc + W_)
    o_ = lo_ if sgn > 0 else hi_
    mouth_ = sorted((sgn * (yc - 82 * sc - o_), sgn * (yc + 82 * sc - o_)))
    face("stone!", (Vector((xm_, o_, 0)), Vector((0, sgn, 0)), n_), 0, hi_ - lo_, zf, ztop,
         [(mouth_[0], mouth_[1], zf, zf + 108 * sc)])                   # its front, the mouth open
    face("stone!", (Vector((xs1_, hi_, 0)), Vector((-1, 0, 0)), Vector((0, 1, 0))), 0, xs1_ - xs0_, zf, ztop)   # its sides
    face("stone!", (Vector((xs0_, lo_, 0)), Vector((1, 0, 0)), Vector((0, -1, 0))), 0, xs1_ - xs0_, zf, ztop)
    k0_, k1_ = sorted((xm_, xw))                                        # the mouth's lining, to the wall (4 behind the
                                                                        # piece's back: not in its plane)
    face("stone", (Vector((k0_, yc + 82 * sc, 0)), Vector((1, 0, 0)), Vector((0, -1, 0))), 0, k1_ - k0_, zf, zf + 108 * sc)
    face("stone", (Vector((k1_, yc - 82 * sc, 0)), Vector((-1, 0, 0)), Vector((0, 1, 0))), 0, k1_ - k0_, zf, zf + 108 * sc)
    poly_n("stone", [(k0_, yc - 82 * sc, zf + 108 * sc), (k1_, yc - 82 * sc, zf + 108 * sc), (k1_, yc + 82 * sc, zf + 108 * sc),
                     (k0_, yc + 82 * sc, zf + 108 * sc)], (0, 0, -1))
    face("stone", (Vector((xw, yc - sgn * 82 * sc, 0)), Vector((0, sgn, 0)), n_), 0, 164 * sc, zf, zf + 108 * sc)   # its back
    # (the FUS and MGO walks of 2026-11-01, broken, with large gaps between the front and the stack: the facade's a sheet, its faces at local depth 120..125, drawn from the front
    # only, with 11 to 16 of nothing behind it to the stack, made for a recess whose walls hide that) its outline carried back to the stack, sides and top
    X_ = lambda ly_: xb_ + sgn * (204 - ly_) * sc
    OUT_ = [(112, 0), (112, 200), (104, 219), (96, 237), (88, 256)]
    for s_ in (1, -1):
        for (u0_, z0_), (u1_, z1_) in zip(OUT_, OUT_[1:]):
            poly_n("stone", [(X_(120), yc + s_ * u0_ * sc, zf + z0_ * sc), (X_(127), yc + s_ * u0_ * sc, zf + z0_ * sc),
                             (X_(127), yc + s_ * u1_ * sc, zf + z1_ * sc), (X_(120), yc + s_ * u1_ * sc, zf + z1_ * sc)], (0, s_ * (z1_ - z0_), u0_ - u1_))
    poly_n("stone", [(X_(120), yc - 88 * sc, zf + 256 * sc), (X_(127), yc - 88 * sc, zf + 256 * sc), (X_(127), yc + 88 * sc, zf + 256 * sc), (X_(120), yc + 88 * sc, zf + 256 * sc)], (0, 0, 1))
    xa_, xc_ = sorted((xw, xb_ + sgn * 204 * sc - sgn * 116 * sc))
    # a stone slab under its firebox, wall to front, 0.8 over the floor (2026-10-27, room 5's: the fire stood
    # on the room's boards: Solitude's floors are stone where this piece stands, ours upstairs are planks)
    box("stone", (xa_ + 0.5, yc - 84 * sc, zf), (xc_, yc + 84 * sc, zf + 0.8))
    PLAN.append({"t": "hearth", "r": [xa_, yc - 112 * sc, xc_, yc + 112 * sc]})

def wall_map(xc, yw, ny, zc, sc=1.0):
    """vanilla's paper map of Skyrim (CivilWarMap01, the war tables': 136 x 100, lying flat, 5 thick, north along its local
    +y) stood up on the wall at y yw facing ny (+-1) in an oak frame (2026-10-26: a map of Skyrim on a wall, perhaps a
    second in the guild master's office). Tilted about its own x: the game's x then z"""
    w_, h_ = 68 * sc, 50 * sc
    a_, b_ = sorted((yw, yw + ny * 1.5)); box("wood", (xc - w_ - 5, a_, zc - h_ - 5), (xc + w_ + 5, b_, zc + h_ + 5))   # its board
    for lo_, hi_ in (((xc - w_ - 9, zc - h_ - 9), (xc + w_ + 9, zc - h_ - 4)), ((xc - w_ - 9, zc + h_ + 4), (xc + w_ + 9, zc + h_ + 9)),
                     ((xc - w_ - 9, zc - h_ - 4), (xc - w_ - 4, zc + h_ + 4)), ((xc + w_ + 4, zc - h_ - 4), (xc + w_ + 9, zc + h_ + 4))):
        a_, b_ = sorted((yw, yw + ny * 7)); box("wood", (lo_[0], a_, lo_[1]), (hi_[0], b_, hi_[1]))   # its frame, 7 out
    piece("meshes/clutter/civilwar/civilwarmap01.nif", "CivilWarMap01", (xc, yw + ny * 1.6, zc), 180 if ny > 0 else 0, sc, rx=270)

def wall_painting(xc, yw, ny, zc, key, sc=1.0):
    """a painting in the map's oak frame (wall_map's): the canvas, our own texture (key: hall_nif's painting1/2), stood on
    the board 0.2 before it, the whole picture across it (2026-10-27: the maps away from the counter and the
    guild master's office replaced by a painting that belongs in the guild: the hall itself)"""
    w_, h_ = 68 * sc, 50 * sc
    a_, b_ = sorted((yw, yw + ny * 1.5)); box("wood", (xc - w_ - 5, a_, zc - h_ - 5), (xc + w_ + 5, b_, zc + h_ + 5))   # its board
    for lo_, hi_ in (((xc - w_ - 9, zc - h_ - 9), (xc + w_ + 9, zc - h_ - 4)), ((xc - w_ - 9, zc + h_ + 4), (xc + w_ + 9, zc + h_ + 9)),
                     ((xc - w_ - 9, zc - h_ - 4), (xc - w_ - 4, zc + h_ + 4)), ((xc + w_ + 4, zc - h_ - 4), (xc + w_ + 9, zc + h_ + 4))):
        a_, b_ = sorted((yw, yw + ny * 7)); box("wood", (lo_[0], a_, lo_[1]), (hi_[0], b_, hi_[1]))   # its frame, 7 out
    W_ = (Vector((xc, yw, 0)), Vector((-ny, 0, 0)), Vector((0, ny, 0)))      # (its right as one facing it sees it)
    quad_on(W_, -w_ - 4, zc - h_ - 4, w_ + 4, zc + h_ + 4, 1.7, key, rect=(0, 0, 1, 1))

def strips(W, u0, u1, z0, ztop, breaks=(), key="stucco"):
    """a wall face from z0 up to a top following ztop(u): the attic's ends under the roof"""
    o, r, n = W
    us = sorted(set([u0, u1] + [b for b in breaks if u0 < b < u1] + [u0 + (u1 - u0) * k / 24 for k in range(1, 24)]))
    for ua, ub in zip(us, us[1:]):
        za, zb = max(z0, ztop(ua)), max(z0, ztop(ub))
        if za - z0 < 0.5 and zb - z0 < 0.5: continue
        poly_n(key, [o + r * ua + UP * z0, o + r * ub + UP * z0, o + r * ub + UP * zb, o + r * ua + UP * za], n)

if HEARTH:
    # the kitchen and its storage, one room behind the tavern's partition (the tavern kitchen combined with
    # the storage room): the fireplace's kitchen side and the cooking pot are with the fireplace above. Since the fit-out
    # (the walk of 2026-10-26: the kitchen too tight, its walls to stay; the first relayout pinched to 56 at the
    # table's ends): one work line along the end wall's windows, the prep table under the middle one
    # between counters under the other two; the pantry shelf and the stores at the front; the hearth and its pot opposite,
    # an aisle of 100 at the hearth and 140..190 elsewhere
    # (2026-10-28: the table 10 north and the counter by the stores 8 south of where the fit-out set them, clear of the
    # cellar's hatch between them (76 square in their 64 gap: the placement gate found the table 7 and the counter 5 over its
    # frame); KTY and KSY carry everything laid on them)
    KTY, KSY = 10, -8
    piece("meshes/clutter/upperclass/uppertable01.nif", "UpperTable01", (-1343, 520 + KTY, 0), 90)   # (its long side 0.5 off the wall)
    for y_ in (290 + KSY, 790):                               # counters under the end wall's windows (63 high, the sills at 90)
        piece("meshes/clutter/upperclass/uppershelf02.nif", "UpperShelf02", (-1366, y_, 0), 270)   # (a low cabinet: the counter's footprint)
    piece("meshes/clutter/upperclass/uppershelf01.nif", "UpperShelf01", (-1127, 270, 0), 90)   # the pantry, its back to the partition
    piece("meshes/furniture/noble/noblecrate01.nif", "NobleCrate01", (-1270, 211, 0), 0)
    for x_, y_ in ((-1373, 673),):                            # (the one between the crate and the pantry clipped both)
        piece("meshes/clutter/barrel01.nif", "BarrelFood01_NoRespawn", (x_, y_, 0), (x_ * 3 + y_) % 360)
    PLAN.append({"t": "room", "level": 0, "name": "kitchen and storage", "r": [-1400, 186, -1100, 890]})
    # the kitchen's clutter (the clutter pass, 2026-10-27), as vanilla's kitchens keep theirs (research/rooms: Castle Dour's,
    # the Blue Palace's; the farm inns' game rings): the prep table mid-work (a joint, fish on a plate, a knife, garlic in a
    # bowl, leeks and carrots laid down, a cabbage, a pot, salt, bread); the counter by the stores washed up (plates and
    # bowls stacked, tankards, a rag; a bucket and boards below); the other for bread and cheese (baskets of potatoes and
    # apples below); the pantry stocked by board (cheese, bottles, sacks and potatoes; its top is a crown, not a board);
    # a barrel and a sack on the floor at the walls, firewood and a bucket by the hearth, a wall shelf over them; game on
    # a ring over the table, herbs over the counters. Everything inside the boards' own extents, measured from the meshes
    # (blender/../research: the table's board 56.5 within local x +-90, y +-50, its rim 59; the counters' tops 62 over
    # their whole outline, their inner boards 10.5 only local x +-55, y -24..16; the pantry's boards 17, 62, 107 local
    # x +-58, y -18.6..20); nothing in the aisles or the arch
    K_ = "meshes/clutter/"
    TK = 56.5                                                 # the prep table (yaw 90: its board x -1391..-1295, y 442..618)
    sit("meshes/plants/cabbage01.nif", "FoodCabbage", -1376, 446 + KTY, TK, 30)
    sit(K_ + "ingredients/venison.nif", "FoodVenison", -1342, 456 + KTY, TK, 25)
    sit(K_ + "food/bread01a.nif", "FoodBread01A", -1384, 478 + KTY, TK, 90)
    sit(K_ + "ingredients/saltpile.nif", "SaltPile", -1310, 470 + KTY, TK, 0)
    sit(K_ + "dining set/basicwoodenplate01.nif", "BasicWoodenPlate01", -1322, 505 + KTY, TK, 90)
    for y_, a_ in ((497, 20), (512, 70)):
        sit(K_ + "deadanimals/salmonmeat01.nif", "FoodSalmon", -1322, y_ + KTY, TK + 1, a_)   # (on the plate's dish, 1 up: at 4 it floated 3)
    sit(K_ + "dining set/basicknife01.nif", "BasicKnife01", -1306, 538 + KTY, TK, 10)
    sit(K_ + "dining set/basicwoodenbowl01.nif", "BasicWoodenBowl01", -1362, 507 + KTY, TK, 0)
    for dx_, dy_ in ((-3, -3), (4, 1), (-1, 5)):
        sit("meshes/plants/garlic01.nif", "Garlic", -1362 + dx_, 507 + KTY + dy_, TK + 2, dx_ * 40)
    for k_, (x_, y_) in enumerate(((-1338, 556), (-1328, 566))):
        sit("meshes/plants/leek01.nif", "FoodLeek", x_, y_ + KTY, TK, 8 - 16 * k_, rx=90)
    for x_, y_, a_ in ((-1366, 579, 74), (-1361, 587, 121), (-1370, 594, 96)):     # (a loose handful)
        sit(K_ + "ingredients/carrot01.nif", "FoodCarrot", x_, y_ + KTY, TK, a_, rx=90)
    sit(K_ + "kitchen/castironpotmedium01.nif", "CastIronPotMedium01", -1318, 590 + KTY, TK, 90)
    # the counter by the stores (UpperShelf02 at yaw 270: its top x -1393..-1339, y 214..350; its inner board x -1382..-1342,
    # y 226..338): washed up
    KCX, KIX = -1368, -1362
    pile(K_ + "dining set/basicplate02.nif", "BasicPlate02", KCX, 246 + KSY, 62, 4, "kitchen plates", step=3.8)
    pile(K_ + "dining set/basicwoodenbowl01.nif", "BasicWoodenBowl01", KCX + 2, 286 + KSY, 62, 3, "kitchen bowls", step=3.0)
    for y_, a_ in ((314, 40), (332, 200)):
        sit(K_ + "dining set/basictankard01.nif", "BasicTankard01", KCX + 10, y_ + KSY, 62, a_)
    sit(K_ + "common/rag01.nif", "Rag01", KCX - 10, 340 + KSY, 62, 25)
    sit(K_ + "bucket01.nif", "Bucket01", KIX, 318 + KSY, 10.5, 15)
    pile(K_ + "dining set/basicwoodenplate01.nif", "BasicWoodenPlate01", KIX + 3, 256 + KSY, 10.5, 3, "kitchen wooden plates", spin=8, drift=0.4)
    # the other (y 722..858; its inner board y 734..846): bread and cheese on it, potatoes and apples below
    sit(K_ + "food/bread01a.nif", "FoodBread01A", KCX + 4, 745, 62, 71)            # (two loaves, as left: not a row of three)
    sit(K_ + "food/bread01a.nif", "FoodBread01A", KCX - 2, 763, 62, 118)
    sit(K_ + "food/cheesewheel01a.nif", "FoodCheeseWheel01A", KCX, 822, 62, 0)
    sit(K_ + "food/cheesewedge01.nif", "FoodCheeseWedge01", KCX + 12, 798, 62, 40)
    for yb_, (m_, e_, n_) in ((756, ("plants/potato01", "FoodPotato", 4)), (826, ("clutter/food/apple01", "FoodApple", 3))):
        sit(K_ + "basket01.nif", "Basket01", KIX, yb_, 10.5, 0)
        for k_, (dx_, dy_) in enumerate(((-6, -5), (6, -4), (0, 6), (-5, 8))[:n_]):
            sit("meshes/" + m_ + ".nif", e_, KIX + dx_, yb_ + dy_, 14.5 if "potato" in m_ else 11.6, dx_ * 30 + dy_, **({"rx": 90} if "potato" in m_ else {}))   # (the apples on
            # the basket's floor, 11: at 14.5 they floated 3)
    # the pantry (UpperShelf01 at x -1127, y 270, yaw 90: its boards x -1146..-1107, y 212..328)
    KPX = -1126
    # (sparse and as left, uneven as real shelves are, 2026-10-27: two wheels
    # stacked at one end, a wedge cut from another; a few bottles clumped on the middle board; one sack below)
    pile(K_ + "food/cheesewheel01a.nif", "FoodCheeseWheel01A", KPX - 1, 238, 107, 2, "pantry cheese", spin=40, drift=1.5)
    sit(K_ + "food/cheesewedge01.nif", "FoodCheeseWedge01", KPX + 3, 271, 107, 63)
    strew((KPX, 216), (KPX, 324), 62, ((K_ + "wine/winebottle01b.nif", "FoodWineAlto", 1), (K_ + "ingredients/mead01.nif", "FoodMead", 2)),
          "pantry 62", depth=5, lie=0.2)
    sit(K_ + "containers/miscsack02small.nif", "MiscSack02Small", KPX + 2, 231, 17, 104)
    sit(K_ + "basket01.nif", "Basket01", KPX, 300, 17, 0)
    for dx_, dy_ in ((-6, -5), (6, -4), (0, 6), (-5, 8)):
        sit("meshes/plants/potato01.nif", "FoodPotato", KPX + dx_, 300 + dy_, 21, dx_ * 30 + dy_, rx=90)
    # (preview only, 2026-10-28: where a hatch down to the basement's cellar could lie in the kitchen's floor, flush, as the
    # library loft's; AG_KHATCH="x,y;x,y", never in a build)
    for hp_ in [q for q in os.environ.get("AG_KHATCH", "").split(";") if q]:
        hx_, hy_ = (float(v) for v in hp_.split(","))
        piece("meshes/architecture/farmhouse/interior/basement/farmbtrapdoor02.nif", "FarmBTrapdoor02", (hx_, hy_, -4.5), 0, 1.0)
    # the floor, at the walls
    # (2026-10-28: the hatch at the barrel's spot, so the hatch is not in the middle of the floor upstairs and the
    # ladder not in the middle of the cellar's walkway) the barrel gone; the farmhouse floor hatch, flush as the
    # library loft's, down the ladder to the basement's cellar (basement_gen.py's "cellar_ladder")
    piece("meshes/architecture/farmhouse/interior/basement/farmbtrapdoor02.nif", "FarmBTrapdoor02", (-1372, 391, -4.5), 0, 1.0,
          name="AGHall2KitchenHatch", role="kitchen_hatch", pair="cellar_ladder", arrive=(-1300, 391, 0), arrive_yaw=90)
    sit(K_ + "containers/miscsack02large.nif", "MiscSack02Large", -1179, 214, 0, 0)
    sit(K_ + "firewood/firewoodpilesmall01.nif", "FirewoodPileSmall01", -1133, 420, 0, 0)
    sit(K_ + "bucket01.nif", "Bucket01", -1124, 362, 0, 60)
    # a wall shelf over the firewood (NobleWallShelf01: its board at 131 over its origin, 34.5 deep from its back)
    piece("meshes/furniture/noble/noblewallshelf01.nif", "NobleWallShelf01", (-1100.5, 420, 20), 90)   # (its back on the wall at -1100:
    # it stood 4 off, the placement gate, 2026-10-29)
    sit(K_ + "glazedpot02.nif", "GlazedPot02", -1117.5, 395, 20 + 131.4, 0)
    sit(K_ + "kitchen/castironpotmedium01.nif", "CastIronPotMedium01", -1117.5, 446, 20 + 131.4, 0)
    # herbs and game hung from pegs under the wall shelf's front edge, within reach (2026-10-29: herbs hung from this
    # ceiling were far out of anyone's reach, so they go on a wall-mounted shelf within reach; the game ring over the
    # table, from the same ceiling, onto wall pegs). The shelf's front at x -1135, y 371..469, its
    # board's underside about 147.5. Each piece hung by its mesh's top middle (the game is modelled off its origin, for the
    # ring: rabbit01's top middle at (-14.9, -13.8, 11.1), pheasant02's (-18.6, -9.5, 4.5)); seeded spacing and turns
    rhg_ = random.Random("kitchen pegs")
    # (four, not five, clear of the end brackets, 2..4 in front of the board's edge: the placement gate's first pass found the
    # bundles in the shelf's own box)
    # (the 2026-10-30 walk: the herbs looked hung from the ceiling and the shelf at once: HangingRabbit01 and HangingPheasant02 are
    # dynamic, two 5-mass bodies on hinges under a fixed anchor, their skin stretched from the shelf to the ceiling when the bodies were
    # pushed out of what they were hung beside. Herbs only here, all fixed bodies (motion system 5: read from the meshes); the game stays
    # on the ring, fixed too. physics_check.py gates it)
    HANG_ = (("plants/hanginggarlicbraid01", "HangingGarlicBraid", (0.05, 0.7, 0.18)),
             ("plants/hangingfrostmirriam01", "HangingFrostMirriam", (0.1, -2.9, 8.45)),
             ("plants/hangingelvesear01", "HangingElvesEar01", (0.3, 5.6, 15.1)))
    for k_, (m_, e_, (cx_, cy_, top_)) in enumerate(HANG_):
        py_ = 388 + k_ * 32 + rhg_.uniform(-2, 2); a_ = rhg_.uniform(0, 360); c_, s_ = math.cos(math.radians(a_)), math.sin(math.radians(a_))
        ox_, oy_ = cx_ * c_ + cy_ * s_, -cx_ * s_ + cy_ * c_            # (its top middle, turned with it: the game turns clockwise)
        piece("meshes/" + m_ + ".nif", e_, (-1138 + rhg_.uniform(-1, 1) - ox_, py_ - oy_, 147.5 - top_), a_, exact=True)

    # the guild services (the plan): the counter set back from the hall's arches, the clerks' pen closed behind it,
    # a partition on the cross gable's side wall's line with an open arch at its front, the clerks' way in from the backroom
    # (hinting at an administrative area behind), and a door at its back; a back counter in the pen. Since the
    # fit-out (2026-10-26, the plan, properly designed): the counter pushed back under the front window
    # (x 821..941), the pen's wall on the pigeonholes' line from the partition to the counter, stopping flush with the
    # counter's public face in a dressed-stone end (nothing stands out into the room), the clerks 124 between the counter and
    # the back counter; the hearth on the partition's public face under the same chimney, the floor before it left open;
    # the backroom without a hearth, its desk at the back wall
    # (since the hall2t walk, 2026-10-26: vanilla's bar kit, as the tavern's bar: six modules wall to wall at 0.95, 60.8
    # each, 2.4 into each wall (their ends are open), the panelled face to the hall, 74 high, 61 deep)
    CS_ = 0.95; CT = (832.5, 832.5 + 64 * CS_)                # the counter: x (its public face 0.5 behind the dressed end's)
    # (the walks of 2026-11-01, the clerks wiping thin air: a lean marker's idle is made for the bar kit's 78, as the tavern's bar and the back counter stand; at 0.95 this one's top was 74.1.
    # Its width kept, it stands on a plinth to 78.1, and what sits on it goes up with it)
    CZ_ = 4; CTOP = 78 * CS_ + CZ_
    # the clerks' spots (the NPC session's request, 2026-10-26): in the gap behind the counter, facing the public side
    # (the NPC session's request, 2026-10-29, both centred: each clerk in the middle of her half of the front
    # counter, its five modules spanning y 207.5..511.5 (the middle 359.5): the day clerk 283.5, the evening 435.5; depth,
    # height and turn kept)
    CLERK_Y = {"Day": 283.5, "Eve": 435.5}
    MARKERS += [(n_, "XMarkerHeading", ((CT[1] + 992) / 2, y_, 0), 270) for n_, y_ in (("AGHallClerkDayMarker", CLERK_Y["Day"]), ("AGHallClerkEveMarker", CLERK_Y["Eve"]))]
    # (the NPC session's request, 2026-10-28: the clerks lean on the counter as Belethor leans on his) a lean
    # marker for each: the counter is vanilla's bar kit, so the bar's own marker (CounterBarLeanMarker), placed as the
    # tavern's is, as the Bannered Mare places its own: 52 out from a module's origin (its centreline) on the clerk's side,
    # at the counter's 0.95, facing the counter
    # (the 2026-10-30 walk, the clerk stood inside the counter: 52 at the module's own size, the Mare's measure, not scaled with the counter: an actor does not shrink with it)
    # (read live, 2026-10-30: her root 42 toward the counter of the marker: the lean's own pull, 20 inside the staff face at 52, inside the counter as seen; at 80, 8 behind it)
    # (the walk of 2026-11-01, Margot scrubbing air, again too far back: the 80 above was built on a pull the marker does not have: CounterLeanMarker.nif's one furniture position is (0, 0, 32).
    # Measured from Skyrim.esm: its 24 placements stand 50.8..63.5 from their bar's centreline, the median 54, 22 behind the top's edge of 32. The same 22 here, the top's edge being 30.4. Inside the counter at 52
    # was on a counter 74 tall, 4 under vanilla's; it is 78 since)
    MARKERS += [(n_, "CounterBarLeanMarker", (CT[0] + 32 * CS_ * 2 + 22, y_, 0), 270)
                for n_, y_ in (("AGHallClerkDayLeanMarker", CLERK_Y["Day"]), ("AGHallClerkEveLeanMarker", CLERK_Y["Eve"]))]
    # the other staff's spots (the NPC session's request, 2026-10-26; the marker faces its local +y, as the clerks'): the
    # guild master behind the office desk facing the door, the assistant at the library's case run, the cook at the
    # kitchen's work line, the server in the tavern by the kitchen arch
    MARKERS += [("AGHallGuildMasterMarker", "XMarkerHeading", (-1372, 440, ZG), 90),
                ("AGHallAssistantMarker", "XMarkerHeading", (1352, 285, 0), 0),   # (the backroom, beside the desk's chair,
                ("AGHallAssistantLibraryMarker", "XMarkerHeading", (300, 110, ZG), 90),   # facing the room, 2026-10-27;
                                                                                         # the library her second stop)
                ("AGHallCookMarker", "XMarkerHeading", (-1250, 520, 0), 270),
                ("AGHallServerMarker", "XMarkerHeading", (-1012, 740, 0), 90)]
    # the residents' spots (the NPC session's request, 2026-10-27: the four adventurers in the attic, Caralion in a
    # nicer room as he pays well for it, room 5): each at the foot of his or her own bunk in
    # the attic's aisle (between the chests, 486..578), facing it; Caralion beside his bed on its window side, facing it
    # (2026-10-28: each at the foot of the resident's own bunk since Ghrulek's moved to the back row's at 1210: the bunks are
    # Ylva's (2) at 1000, Zhasim's (3) at 1142 and Marius's (4) at 1330 in front, Ghrulek's (1) at 1210 behind; the markers
    # had stood at one another's)
    _att = int(os.environ.get("AG_ATTIC", "1"))                # (2026-11-03: with the attic's new timbers Ylva's bunk moved 6 and Marius's 20; their spots with them)
    MARKERS += [("AGHallResidentOrcMarker", "XMarkerHeading", (1210, 554, T1 + 14), 0),
                ("AGHallResidentRangerMarker", "XMarkerHeading", (1000 - (6 if _att else 0), 510, T1 + 14), 180),
                ("AGHallResidentScoutMarker", "XMarkerHeading", (1142, 510, T1 + 14), 180),
                ("AGHallResidentVeteranMarker", "XMarkerHeading", (1330 - (20 if _att == 1 else 0), 510, T1 + 14), 180),
                ("AGHallResidentNobleMarker", "XMarkerHeading", (1330, 845, ZG), 180)]   # (2026-11-03: on the double's open side; plan D, 2026-11-06: its back side, facing it)
    for k_ in range(6):
        piece("meshes/clutter/barset/barstraight01.nif", "BarStraight01", (CT[0] + 32 * CS_, 207.6 + 32 * CS_ + 64 * CS_ * k_, CZ_), 0, CS_)
    box("wood", (CT[0], 207.6, 0), (CT[1], 570, CZ_))
    # (its free end plaster over the slate base as its faces, since the MGO walk of 2026-11-04: the guild counter's side wall had the wrong
    # texture on its edge, not matching the plaster; it was a bare-stone dressed end)
    partition(CT[0], 570, 1054, 594, 0, 400, key="stone", timbers=False, ends=(True, False))      # the pen's wall
    partition(1054, 210, BRF, 890, 0, 400, holes=[(775, 871, 0, DOOR_H)], key="stone", arches=[(230, 350, 300)])
    face("stone", (Vector((BRF, 186, 0)), Vector((0, 1, 0)), Vector((1, 0, 0))), 0, 24, 0, 400)   # its backroom face, on to the front
    # (2026-11-01: the counter's back office door locked at Adept, openable by both clerks, the GM and the assistant: their own key, the Guild Hall
    # Key opening the case and the strongroom besides; the guild master's so the rest of the hall does not path through it. behind: what it closes off, the pen and the backroom, for lock_check.py)
    # (2026-11-11: Uthgerd walked straight through it and back out, so the door is left unlocked and its keys
    # removed: no lock and no Back Office Key since; AGHallBackOfficeDoor still closes it behind the staff, without locking)
    door_leaf(((1054 + BRF) / 2, 775), ((1054 + BRF) / 2, 871), 0, (1, 0), "AGHall2BackroomDoor", owner="gm")
    # the back counter, the bar kit's too: two modules from 2 into the pen's wall and an end, its shelves to the clerks (the
    # barkeep's side), its panelled back to the partition (into it 2)
    # (since the hall2ae walk, 2026-10-27: built in, as close to the door as needed, no floating shelves, the
    # pigeonholes ending on an upright): the back counter and its pigeonholes one
    # built-in run from the pen's wall to the clerks' doorway (its opening 230..350, its stone surround to 364): three
    # modules from 7 into the pen's wall, the end piece's face 2 short of the opening's edge
    for y_ in (545, 481, 417): piece("meshes/clutter/barset/barstraight01.nif", "BarStraight01", (1024, y_, 0), 180)
    piece("meshes/clutter/barset/barright01.nif", "BarRight01", (1024, 417, 0), 180)   # (local +y: the hall's -y, y 352..385)
    box("wood", (992, 564, 0), (1054, 568, 76))   # its side at the pen's wall, over the modules' open shelf ends (2 off the
                                                  # wall; 2026-10-27: its foot was open at the side, so it has a side)
    # its pigeonholes, the original kind (as they stood before the wall moved), across the
    # counter's top from the doorway's surround (2 past it, 366) to the pen's wall (570): an upright at each end, the end
    # one against the wall; five cells; the shelves between the end uprights, 1 behind the uprights' fronts; one top board
    # over all of them, 2 proud
    PY0, PY1 = 366, 570
    dv_ = [PY0 + (PY1 - 6 - PY0) * k_ / 5 for k_ in range(6)]
    for y_ in dv_: box("wood", (1030, y_, 78), (1053.5, y_ + 6, 250))
    for zz in (130, 190): box("wood", (1031, PY0 + 6, zz), (1053.5, PY1 - 6, zz + 6))
    box("wood", (1028, PY0, 250), (1053.5, PY1, 256))
    # the hearth on the partition's public face, under the services wing's chimney (the outside's stack at x 1090, y 710):
    # since the hall2w walk (2026-10-26) vanilla's manor fireplace, at 0.72 the most that fits between the pen's wall
    # (594) and the backroom door's frame (760)
    manor_fireplace(1054, -1, 677, 0, 0.72, y_lo=593.5, y_hi=761)   # (into the pen's wall, 594, and the back office door's post, 760.5)
    # (2026-11-03, wall G, the panel removed) the party leader board where the adventurers' map hung, map and
    # its built-in board gone: on the plaster at its bottom middle, its front (its local -y) toward the room, centred
    # in the bay between the windows (644..812); its bottom at 100, the map frame's, clear of the bench under it (63.1 tall)
    piece("meshes/adventurersguild/leaderboard/agleaderboard.nif", "AGHall2LeaderBoard", (728, 210.2, 100), 180)
    # (2026-11-13: the tavern's urn with its fern was far too small for that corner, so it moved to a spot in the hall that
    # wanted some life; of three rendered spots by the counter, on the floor before the counter's right end, by the wall
    # and the leader board) in the corner of the counter's public face and the front wall, 4 off the counter, 2 off the skirting
    piece("meshes/clutter/glazed02potteryurn01.nif", "AGHall2UrnStatic", (812, 230, 0), 25)   # (a static since 2026-11-13: the loose urn was knocked away from its fern)
    piece("meshes/landscape/plants/swordfern01.nif", "TreeSwordFern01", (812, 230, 28), 70, 0.28)
    # (2026-11-04, the detail session's story pieces) the fresh slip and the Golden Hand's strike, each its own mesh on the board's origin, on the
    # board's spot; AG's DLL shows or hides them as the story stands (LeaderBoard.cpp, by their models)
    for ed_ in ("Slip", "Strike"):
        piece(f"meshes/adventurersguild/leaderboard/agleader{ed_.lower()}.nif", "AGHall2Leader" + ed_, (728, 210.2, 100), 180)
    # (2026-11-04: Merila updating the board, others reading it; RENOWN_PLAN F) vanilla's idle markers square before it, the bench moved
    # out from under it: Merila's ledger in the middle, a reader to each side turned in toward it (each faces its local +y)
    MARKERS += [("AGHallLeaderBoardWriteMarker", "WritingLedgerIdleMarker", (728, 262, 0), 180),
                ("AGHallLeaderBoardReadMarker1", "DBExamineIdleMarker", (676, 272, 0), 160),
                ("AGHallLeaderBoardReadMarker2", "StudyMarker", (780, 272, 0), 200)]
    # the backroom: the desk under the front window (since the hall2ak review, 2026-10-27: moved for more room coming in
    # through the doorway: it stood on the back wall, across the way in; the back
    # wall stays clear). Since the hall2bd walk (2026-10-28: a shelf blocked the window and stood empty, and nothing in the
    # room read as an office) the clerks' office, as vanilla's business rooms keep theirs
    # (research/services: the East Empire Company's office, the Treasury House): the guild's records on the partition
    # (a shelf of ledgers and rolled papers, a chest of drawers with the day's letters), a low bookcase between the end
    # wall's windows (231..349, 481..599, sills at 90), the records chest under the second, a cupboard past it (from 632,
    # clear of the window the old shelf stood across), the stock barrels and sacks gone
    # (2026-11-03: turned round on the same footprint, its things on it where they were: NobleDesk02 is sat at from its local +y (vanilla's
    # chairs: Pairs.cs, DrelasCottage01 and ThalmorEmbassy02, 51 out, 14..43 to a side), and this one had its +y to the wall, the chair at its back)
    piece("meshes/furniture/noble/nobledesk02.nif", "NobleDesk02", (1256, 198.5 + 37, 0), 0)
    # (2026-11-03, the known faults: NobleChair01 enters only from its front, which the desk blocks) vanilla's NobleChair02R, entered from its side, 51 out and 15 aside
    piece("meshes/furniture/noble/noblechair02.nif", "NobleChair02R", (1256 - 15, 198.5 + 37 + 51, 0), 180)
    piece("meshes/furniture/noble/nobleshelf04.nif", "NobleShelf04", (1380.5, 415, 0), 90)       # (its back at local +18: the wall)
    piece("meshes/furniture/noble/noblechest01.nif", "NobleChest01", (1373, 540, 0), 90)   # (its lid opens to its local -y: the room)
    piece("meshes/clutter/upperclass/uppercupboard01.nif", "UpperCupboard01", (1371, 700, 0), 90)
    if os.environ.get("AG_SVC_DRESS", "1") == "1":   # (reviewed 2026-10-27: the rug upgraded, the desk moved, the counter filled)
        # The services wing dressed (2026-10-26: researched furniture, lighting, decor and objects for the whole
        # services wing: the waiting area, before the board, the backroom, and the side by the fireplace). From vanilla's own business rooms (research/services: Windhelm's East Empire Company and Shatter-Shield
        # offices, the Markarth Treasury House, the Arcanaeum's counter, Mistveil Keep's steward, the courts' benches):
        # the business ledger on a table with its strongbox and a purse beside it; inkwell, quill and parchment where a clerk
        # writes; stock in barrels, crates, sacks and on a common shelf; horn chandeliers and candle lanterns for light; benches
        # against walls where people wait. No seat near the fire.
        # (the hall2bd walk, hanging so low it struck the player's head: CandleHornChandelier01's chain is 220, its horns
        # 29 below its origin, so from a 400 ceiling at full size they hang at 151; hall2bd's CandleHornChandelier02 on its 50
        # rope then sat against the ceiling, too high: vanilla hangs that one only under ceilings of 217..274 (hangrefs).
        # The rule since (2026-10-28): a hanging light clears the characters over walkable floor and hangs well down
        # from a medium or high ceiling (hang_check.py: its foot 200 over the floor, a third of the room under the ceiling).
        # Vanilla meets a low ceiling by scaling the long chain (hangrefs: the Ratway 0.75, Laraks's longhouse 0.72,
        # Pinewatch 0.65, Gray-Mane's 0.91): at 0.75 the chain 165, the horns at 213, 187 under the ceiling)
        CH_ = "meshes/clutter/candles/candlehornchandelier01.nif"
        def hang(x, y, ztop=400, s=0.75):
            piece(CH_, "CandleHornChandelier01", (x, y, ztop - 220 * s), 0, s, exact=True)
            NEW_LIGHTS.append((x, y, ztop - 220 * s + 10, 1.4e6, (1.0, 0.75, 0.5), "candle", 128, 0.0))   # (256, as Breezehome's
                                                                           # chandelier light: a candle's 128 left the floor dark)
        def ware(m, ed, pos, yaw=0, **kw):                                  # small things set on a surface: the guild's, kept put
            piece(m, ed, pos, yaw, owner="guild", settled=True, **kw)
        def writing(x, y, z, yaw=0):                                        # an inkwell with its quill standing in it, parchment by it
            ware("meshes/clutter/common/inkwell01.nif", "Inkwell01", (x, y, z), yaw)
            # (the quill lying beside the well, on its side away from the parchment: of the two spots 20 to either side in the
            # desk's own frame, the one farther from the roll)
            c_, s_ = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
            cand_ = [(x + 8 * c_ + sy_ * 20 * s_, y - 8 * s_ + sy_ * 20 * c_) for sy_ in (-1, 1)]
            qx_, qy_ = max(cand_, key=lambda q: math.dist(q, (x - 4, y + 22)))
            ware("meshes/clutter/common/quill01.nif", "Quill01", (qx_, qy_, z + QUILL_LIE_Z), yaw + 8, rx=90)
            ware("meshes/clutter/quest/tgparchment01.nif", "PaperRoll", (x - 4, y + 22, z + 3), 0)
        # the waiting area: a low bench under the map between the front windows (its back to the wall; under the map's frame at
        # 101), a sideboard with drink in the corner by the first window (as Mistveil Keep's steward has by its bench), a rug,
        # a horn chandelier over the floor
        # (turned 0: its seat, sit marker heading 0, faces its local +y, the room; at 180 it faced the wall 18 behind it: the
        # placement gate's seat check, 2026-10-28)
        # (2026-11-04, RENOWN_PLAN G) the bench out from under the leader board, centred under the first front window
        # (508..644), so the board's readers stand square before it; the sideboard turned into the front-west corner, its back 2 off the west
        # wall (x 382, in front of the arch surround's foot: option A), its end in the corner (y 211..300), its things turned with it
        piece("meshes/furniture/noble/noblebench04.nif", "NobleBench04Front", (576, 210 + 18.5, 0), 0, exact=True)
        piece("meshes/furniture/noble/noblesideboard01.nif", "NobleSideBoard01", (382 + 12.5, 211 + 44.65, 0), 270)
        # (its things 8 toward its open end: with its end now in the corner the candle horn's arms cut 6 into the front wall, the placement gate)
        ware("meshes/clutter/silver/silverjug01.nif", "SilverJug01", (402, 289.65, 63.3), 290)
        for y_, yw_ in ((261.65, 120), (243.65, 340)): ware("meshes/clutter/silver/silvergoblet01.nif", "SilverGoblet01", (408, y_, 63.3), yw_)
        ware("meshes/clutter/candles/candlehorntable01.nif", "CandleHornTable01", (398, 231.65, 63.3), 180)
        piece("meshes/architecture/whiterun/wrclutter/wrcastlerugefree01.nif", "WRCastleRugEFree01", (606, 470, 0.3), 0)   # (Dragonsreach's
                                                  # red rug, the great hall's runner's: the rug upgraded, 2026-10-27)
        hang(648, 470)                                                     # (between the joists at 572..596 and 700..724:
                                                                           # raised, at 606 its horns met the first, the clip check)
        NEW_LIGHTS.append((432, 640, 330, 0.9e6, (1.0, 0.75, 0.5), "candle"))   # the board's light, from above (a chandelier there
                                                                           # hung between the board and its readers)
        # the counter: a clerk's writing things at each clerk's spot, a candlestick between them (as the Arcanaeum's counter)
        for y_ in (250, 460): writing(872, y_ - 18, CTOP + 0.2)
        ware("meshes/clutter/silver/silvercandlestick02.nif", "SilverCandleStick02", (880, 355, CTOP + 0.2), 90)
        # (the lived-in pass, 2026-11-17) the cards of members found dead, which the counter takes in, kept in a locked box on the
        # clerks' side between the day clerk and the candlestick (empty: a card in it could be taken and handed in again)
        piece("meshes/clutter/common/strongbox01.nif", "AGHall2CardBox", (878, 320, CTOP + 0.2), 266, owner="guild", lock="Expert")   # (as the back counter's)
        # the back counter (its top x 992..1054): the business ledger, its strongbox and a purse,
        # as Windhelm's offices keep them
        piece("meshes/clutter/quest/tgrbusinessledger.nif", "TGRFOBusinessLedger", (1007, 522, 78 + 3.2), 90)
        piece("meshes/clutter/common/strongbox01.nif", "StrongBox", (1012, 456, 78.2), 270, owner="guild")
        piece("meshes/plants/coinbagsmall.nif", "CoinPurseSmall", (1004, 482, 78.2), 0, owner="guild")
        ware("meshes/clutter/common/candlelanternwithcandle01.nif", "CandleLanternwithCandle01", (1041, 426, 136.3), 0)   # (in a
        NEW_LIGHTS.append((1041, 426, 165, 0.5e6, (1.0, 0.75, 0.5), "candle_small"))                                     # pigeonhole)
        # the counter's shelves and pigeonholes, where the player looks (2026-10-27: more clutter on the
        # counter shelves, where objects matter most): the guild's paperwork in every cell, as a
        # records office keeps it: stacks of notices, books lying flat, rolled papers poking out, journals, the purse.
        # Cells 33.6 wide (centres below), 23.5 deep (x 1030..1053.5), tiers at 78, 136 and 196, the top board 256
        BOOKMESH = {"Book01": "basicbook01", "Book03": "basicbook03", "Book06": "basicbook06", "BookLarge": "book02lowpoly02"}
        def notes(x, y, z, n, yw=0):
            for k_ in range(n):
                piece(f"meshes/clutter/books/note0{k_ % 4 + 1}.nif", f"AGHall2Note0{k_ % 4 + 1}",
                      (x + (k_ % 2) * 0.8, y + (k_ % 3) * 0.6, z + 0.3 * k_ + 0.1), yw + (k_ * 37) % 11 - 5, exact=True, bake="services")
        def books(x, y, z, kinds, yw=0):
            zz = z
            for k_, b_ in enumerate(kinds):
                big_ = b_ == "BookLarge"
                piece(f"meshes/clutter/books/{BOOKMESH[b_]}.nif", "AGHall2" + b_, (x, y, zz + (3 if big_ else 2)), yw + (k_ * 29) % 9 - 4, exact=True, bake="services")
                zz += 6 if big_ else 4
        def rolls(y, z, n):                                            # rolled papers piled in a pyramid, poking out
            rows_, k_ = [], 0
            for row_ in range(4):
                for c_ in range(3 - row_ if row_ < 3 else 1):
                    if k_ < n: rows_.append((row_, c_, 3 - row_)); k_ += 1
            for row_, c_, w_ in rows_:
                ware("meshes/clutter/quest/tgparchment01.nif", "PaperRoll",   # (their back ends 2 short of the cells' backs: they
                     (1021 + (c_ * 5 + row_ * 3) % 5 - 2, y + (c_ - (w_ - 1) / 2) * 7.0, z + 2.7 + row_ * 4.4), ((c_ * 7 + row_ * 3) % 5 - 2) * 0.4, square=True)   # met the wall's rail;
                                                                       # 6 across: packed 7.0 apart, each row up in the gap under it; at 6.2 apart, each turned
                                                                       # a little, neighbours sank ~2 into each other: the known faults, 2026-11-03. By the mesh a roll is 6.2 across but 5.2 tall,
                                                                       # so its bottom row stands 0.1 over the shelf at 2.7 and a roll 3.5 aside rests at 4.4 up (4.29 touches); it is 48 long,
                                                                       # so with 0.8 between them their turns stay under 1 degree, and a square one keeps its own (the loose turn's 3..12
                                                                       # swung its ends 4 into the next)
        def standing(y, z, n, big=False):                              # books stood spines out (rx 90), as they are put back:
            t_ = 6 if big else 4                                       # uneven gaps, a little turned, standing in or out
            r_ = random.Random(f"standing {y:.1f} {z:.1f}")
            gaps_ = [r_.uniform(0.2, 1.6) for _ in range(n - 1)]; w_ = n * t_ + sum(gaps_); u_ = -w_ / 2 + t_ / 2
            for k_ in range(n):
                b_ = "BookLarge" if big else r_.choice(("Book01", "Book03", "Book06"))
                piece(f"meshes/clutter/books/{BOOKMESH[b_]}.nif", "AGHall2" + b_,
                      (1042 + r_.uniform(-1.5, 1.0), y + u_, z + (15 if big else 12)), r_.uniform(-4, 4), rx=90, exact=True, bake="services")
                if k_ < n - 1: u_ += t_ + gaps_[k_]
        C_ = (388.8, 428.4, 468, 507.6, 547.2); T_ = (78.2, 136.3, 196.3)
        standing(C_[0], T_[0], 5)
        notes(1042, C_[1] - 9.5, T_[0], 8, 0); books(1042, C_[1] + 7.5, T_[0], ("Book03", "Book01"), 90)   # (side by side)
        piece("meshes/clutter/books/journallowpoly01.nif", "AGHall2Journal", (1042, C_[2] - 4, T_[0] + 1), 84, exact=True, bake="services")
        ware("meshes/clutter/common/inkwell01.nif", "Inkwell01", (1036, C_[2] + 10, T_[0]), 0)
        standing(C_[3], T_[0], 4)                                      # (no rolls at the counter's level: they ran into the ledger)
        piece("meshes/plants/coinbagsmall.nif", "CoinPurseSmall", (1040, C_[4] - 7, T_[0]), 20, owner="guild")
        notes(1044, C_[4] + 6, T_[0], 6, 90)
        rolls(C_[0], T_[1], 5)   # (5, rows of 3 and 2: the settle test, 2026-11-13, threw all six of the 3-2-1 pile; the 3-2 beside it held)
        standing(C_[2], T_[1], 4, big=True)
        notes(1042, C_[3], T_[1], 8, 90); books(1042, C_[3], T_[1] + 2.6, ("Book06",), 92)
        standing(C_[4], T_[1], 6)
        notes(1042, C_[0], T_[2], 6, 90)
        standing(C_[1], T_[2], 7)
        rolls(C_[2], T_[2], 5)
        books(1042, C_[3], T_[2], ("Book03", "Book06", "Book01", "Book03"))
        standing(C_[4], T_[2], 5)
        books(1041, 400, 256.3, ("BookLarge", "Book03"))               # on the top board
        ware("meshes/clutter/quest/tgparchment01.nif", "PaperRoll", (1040, 522, 256.3 + 3), 92)
        # the public counter (its top CTOP, the clerks' writing things at 232 and 442, the candelabra at 355): a pile of
        # notices for the board, a ledger, a journal; on the back counter's free top a stack of letters
        notes(866, 298, CTOP + 0.1, 4, 95)
        piece("meshes/clutter/books/book02lowpoly02.nif", "AGHall2BookLarge", (874, 532, CTOP + 0.1 + 3), 82, exact=True, bake="services")
        piece("meshes/clutter/books/journallowpoly01.nif", "AGHall2Journal", (866, 500, CTOP + 0.1 + 1), 70, exact=True, bake="services")
        notes(1008, 400, 78.2, 3, 0)
        # the back counter's own shelves under its top, open to the room (BarStraight01's: at 16, x 997..1049, and at 55,
        # x 997..1032; 2026-10-27: the bottom shelf looked empty and wanted a small box or container, the shelf above
        # some blank scrolls): a small open crate and a closed basket below, rolled blank
        # parchment along the shelf above
        # (the shelves are 35 deep: the module's inner panel stands at x 1032..1035; 2026-10-27: the box
        # clipped at the back)
        piece("meshes/clutter/common/crateopen01.nif", "CrateOpen", (1014.5, 500, 16.3), 2, 0.68, exact=True)   # (48 x 70 x 37 at
                                                  # 1: 33 x 48 x 25 here, lengthwise along the shelf)
        ware("meshes/clutter/basketclosed01.nif", "BasketClosed01", (1015, 432, 16.3), 15, scale=0.92)
        # (the settle test in game, 2026-11-13: these piles came apart, three rolls thrown 7-13 and the rest spread 3-6; vanilla never
        # stacks rolls (pairs PaperRoll PaperRoll: side by side on one surface, 6-10 apart, never on each other) so one layer, 8 apart)
        for k_, (y_, z_) in enumerate(((409, 0), (417, 0), (470, 0), (478, 0), (486, 0))):
            ware("meshes/clutter/quest/tgparchment01.nif", "PaperRoll", (1014 + (k_ * 3) % 5, y_, 55.3 + 2.9 + z_ / 4 * 4.8), 90 + (k_ * 5) % 7 - 3)   # (a roll
            # on two 6 apart lies 4.7 over them, in their groove: at 3.8 it sat 1.4 in, the placement gate, 2026-10-29)
        # the fireplace's side: a standing planning table on the back wall (no seats), the map of Skyrim laid on it as on
        # vanilla's war tables, a candle horn and writing things; firewood by the pen's wall
        # (in the nook's far corner, against the tower's wall: a long table on the back wall closed the way to the backroom's
        # door past the hearth, and with it the backroom and the pen, furniture_check)
        # (2026-11-04, RENOWN_PLAN G: the table stays, a waiting spot, its map of Skyrim taken off; the wall map that hung where the
        # leader board is now hangs on the back wall beside it, free from the table to the office door's post (802..1043), its middle 160 as before)
        piece("meshes/furniture/noble/nobletablesquare01.nif", "NobleTableSquare01", (768, 841, 0), 0, exact=True)
        wall_map(922 - 25, 890, -1, 160)   # (the trim walk of 2026-11-07, centred between the furniture and the door it looked unbalanced: 25 toward the table)
        # (2026-11-14, for the NPC session: until her welcome, Merila waits by the backroom's door studying the map of Skyrim)
        # one of vanilla's idle markers before it, as the Guild Board's middle one stands before the board: 59 off the canvas (888.4), facing it
        # (+y); 82 clear of the planning table's east edge (815), the way to the backroom's door (x 1054+) left open
        MARKERS.append(("AGHallAssistantMapMarker", "StudyMarker", (897, 829, 0), 0))
        ware("meshes/clutter/candles/candlehorntable01.nif", "CandleHornTable01", (735, 870, 63.3), 0)   # (2026-11-03: 8 off the wall; it stood 6 into it)
        writing(803, 808, 63.3, 200)
        # (no chandelier over it since 2026-11-03: it hung too close to the walls and lit them poorly, and the candle,
        # the fireplace and the room's chandelier already light it)
        piece("meshes/clutter/firewood/firewoodpilesmall01.nif", "FirewoodPileSmall01", (938, 632, 0), 12)
        # the office (2026-10-28): along the partition, between the clerks' arch (230..350) and the door (774..872), the
        # records shelf (UpperShelf01, its boards 17, 62, 107 within x 1102..1141, y 412..528) and a chest of drawers
        # (NobleChestDrawers02, its back at local +12 on the partition, its top 63 within x 1094..1155, y 595..685)
        piece("meshes/clutter/upperclass/uppershelf01.nif", "UpperShelf01", (BRF + 27.5, 470, 0), 270)   # (BRF: on the partition, 16 nearer since 2026-11-07)
        shelf_books((BRF + 24.5, 414), (BRF + 24.5, 526), 107, 180, "OF2", room=40, fill=0.8, bake="office")
        for k_ in range(3):
            ware("meshes/clutter/quest/tgparchment01.nif", "PaperRoll", (BRF + 27 - (k_ % 2) * 3, 455 + (k_ - 1) * 6.2, 62 + 2.8 + (k_ == 1) * 5.3), 90)
        piece("meshes/clutter/common/strongbox01.nif", "StrongBox", (BRF + 27, 500, 62.2), 90, owner="guild")
        shelf_books((BRF + 24.5, 414), (BRF + 24.5, 470), 17, 180, "OF0", room=40, fill=0.9, bake="office")
        ware("meshes/clutter/basketclosed01.nif", "BasketClosed01", (BRF + 26, 500, 17.3), 10)
        piece("meshes/furniture/noble/noblechestdrawers02.nif", "NobleChestDrawers02", (BRF + 12.5, 640, 0), 270)
        ware("meshes/clutter/candles/candlehorntable01.nif", "CandleHornTable01", (BRF + 24, 668, 63.3), 0)
        NEW_LIGHTS.append((BRF + 24, 668, 63.3 + 40, 0.4e6, (1.0, 0.72, 0.45), "candle_small"))
        for k_ in range(3):                                       # the day's letters, waiting to be filed
            piece(f"meshes/clutter/books/note0{k_ + 1}.nif", f"AGHall2Note0{k_ + 1}", (1126 + k_ * 0.7, 618 - k_ * 0.9, 63.3 + 0.35 + 0.3 * k_), 4 + k_ * 7, exact=True, bake="office")
        # the cupboard past the second window (UpperCupboard01 at x 1371, y 700, its back on the wall; measured: its counter
        # 62 within local x -68..68, y -27..27, its shelf 107 within x -58..58, y -19..20, its top 153), since the hall2bf walk
        # (it still stood empty): dressed as vanilla dresses its own (onrefs, 36 of them: all carry something; in
        # working rooms books, a strongbox, a purse; a basket on top): on the counter a strongbox, a purse and two ledgers
        # laid flat; on the shelf the guild's books and two rolled records; a basket on top
        ware("meshes/clutter/common/strongbox01.nif", "StrongBox", (1363, 737, 62.3), 281)   # (its latch, +y, to the room: the audit)
        ware("meshes/plants/coinbagsmall.nif", "CoinPurseSmall", (1360, 712, 62.3), 34)
        for k_, bk_ in enumerate(("BookLarge", "Book06")):
            piece(f"meshes/clutter/books/{LIB_BOOKS[bk_]}.nif", "AGHall2" + bk_, (1366, 668, 62.3 + (3.4 if k_ == 0 else 6.9 + 2.1)), 84 + k_ * 9, exact=True, bake="office")
        shelf_books((1375, 648), (1375, 706), 107, 0, "OC1", room=42, fill=0.85, bake="office")
        for k_, (x_, yw_) in enumerate(((1368, 4), (1379, 357))):         # (side by side, 710..744 along the board's 642..758)
            ware("meshes/clutter/quest/tgparchment01.nif", "PaperRoll", (x_, 727 + 2 * k_, 107 + 2.8), 90 + yw_)
        ware("meshes/clutter/basket01.nif", "Basket01", (1373, 676, 153.4), 18)
        # the low bookcase between the windows (NobleShelf04, its boards at 15.5 and 61, its top 117): ledgers
        shelf_books((1384.5, 384), (1384.5, 446), 15.5, 0, "OB0", room=42, fill=0.85, bake="office")
        shelf_books((1384.5, 384), (1384.5, 446), 61, 0, "OB1", room=50, fill=0.8, bake="office")
        # the clerk's desk under the front window (its top 63.3 within x 1173..1337, y 187..248; the sitter at +y): the
        # day book open before the sitter, ink, quill and paper, letters, two books, the lantern at the back
        writing(1214, 214.5, 63.3, 0)
        ware("meshes/clutter/common/candlelanternwithcandle01.nif", "CandleLanternwithCandle01", (1186, 202.5, 63.3), 0)
        piece("meshes/clutter/books/journallowpoly01.nif", "AGHall2Journal", (1262, 224, 63.3 + 1.0), 180, exact=True, bake="office")
        for k_ in range(2):
            piece(f"meshes/clutter/books/note0{k_ + 1}.nif", f"AGHall2Note0{k_ + 1}", (1298 + k_ * 0.8, 214 + k_ * 0.6, 63.3 + 0.35 + 0.3 * k_), 172 + k_ * 9, exact=True, bake="office")
        for k_, bk_ in enumerate(("BookLarge", "Book06")):
            piece(f"meshes/clutter/books/{LIB_BOOKS[bk_]}.nif", "AGHall2" + bk_, (1322, 205, 63.3 + (3.4 if k_ == 0 else 6.9 + 2.1)), 180 + k_ * 7, exact=True, bake="office")
        piece("meshes/clutter/common/rug06.nif", "Rug06", (1252, 560, 0.3), 0)
        hang(1252, 560)
    else:   # (until then the rooms keep their lamps)
        NEW_LIGHTS += [(600, 450, 300, 1.5e6, (1.0, 0.78, 0.55), "lamp"), (1250, 520, 300, 1.5e6, (1.0, 0.78, 0.55), "lamp")]
    PLAN.append({"t": "counter", "r": [CT[0], 210, CT[1], 570]}); PLAN.append({"t": "counter", "r": [992, 352, 1054, 570]})
    PLAN.append({"t": "room", "level": 0, "name": "backroom", "r": [BRF, 186, 1400, 890]})

    # the guild master's office (room 1) and bedroom (room 2) over the kitchen, off the tavern's galleries, a door between
    # them (room 1 the guild master's new office); their floor on the kitchen's ceiling, a ceiling at the plates
    box("planks", (-1452, 134, ZG - 4), (-1092, 906, ZG)); box("planks", (-1452, 134, T1), (-1092, 906, T1 + 14))
    RR = (ZG + 12, T1 - 12)                                   # the upper rooms' rails (the windows lie between them, 448..559)
    for W, L, hs in (((Vector((-1092, 134, 0)), Vector((-1, 0, 0)), Vector((0, 1, 0))), 360, []),          # the cross gable's front
                     ((Vector((-1452, 134, 0)), Vector((0, 1, 0)), Vector((1, 0, 0))), 772, []),            # the outer end
                     ((Vector((-1452, 906, 0)), Vector((1, 0, 0)), Vector((0, -1, 0))), 360, []),          # room 2's back
                     ((Vector((-1092, 906, 0)), Vector((0, -1, 0)), Vector((-1, 0, 0))), 772,              # the partition, their side
                      [(906 - b_, 906 - a_, ZG, ZG + DOOR_H) for a_, b_ in GMD])):
        face("stucco", W, 0, L, ZG, T1, hs)
        for zz in RR: wall_rail(W, 0, L, zz, hs, w=22)
        for h in hs: frame_timbers(W, h[0], h[1], h[2], h[3])
    partition(-1452, 616, -1092, 640, ZG, T1, holes=[(-1318, -1222, ZG, ZG + DOOR_H)], rails=RR)
    door_leaf((-1318, 628), (-1222, 628), ZG, (0, -1), "AGHall2GMSuiteDoor")   # (into the office: the bed is where it would swing)
    # room 2's fire, the kitchen's chimney on up: since the hall2w walk (2026-10-26) vanilla's manor fireplace, at 0.558 the
    # most that fits beside the gallery door (787..885) on this wall
    manor_fireplace(-1092, -1, 710.5, ZG, 0.558, rail=8, ztop=T1, y_lo=639.5, y_hi=774)   # (the suite's partition, 640, and its door's post, 773.5)
    # (the guild master's office and bedroom are his own faction's, as the Harbinger's rooms are: the NPC session, 2026-10-27)
    # (2026-11-03: turned round on the same footprint, its things on it where they were: NobleDesk02 is sat at from its local +y (vanilla's
    # chairs: Pairs.cs, DrelasCottage01 and ThalmorEmbassy02, 51 out, 14..43 to a side), and this one had its +y to the wall, the chair at its back)
    piece("meshes/furniture/noble/nobledesk02.nif", "NobleDesk02", (-1300 - 37, 380, ZG), 270, owner="gm")      # the office: the desk faces the door, its master too
    # (2026-11-03, the known faults: NobleChair01 enters only from its front, which the desk blocks) vanilla's NobleChair02R, entered from its side, 51 out and 15 aside
    piece("meshes/furniture/noble/noblechair02.nif", "NobleChair02R", (-1300 - 37 - 51, 380 - 15, ZG), 90, owner="gm", name="AGHallGuildMasterDeskChair")   # (named 2026-11-07: his desk hours seated, the NPC session's SitTarget)
    piece("meshes/clutter/upperclass/uppershelf01.nif", "UpperShelf01", (-1129, 487, ZG), 90, owner="gm")
    wall_map(-1388.5, 616, -1, ZG + 165, 0.72)                 # the guild master's map, west of the bedroom door (its wall's
                                                              # rails 8 in from the end wall, the door's frame at -1333)
    # the bedroom since the fit-out (the walk of 2026-10-26: the guild master's door was blocked: the chest stood just
    # inside it): the bed in the back half, its head to the end wall, the chest at its foot; the door opens onto clear floor
    # Since the hall2t walk (2026-10-26: a single bed with a noble chest wider than it, well off
    # the mark, so researched): vanilla's noble bedrooms (research/bedrooms: 296 beds, six rooms rendered to scale) put the head on a
    # wall, a night table at its side with a candlestick, storage on another wall, a rug on the open floor; a noble chest
    # goes with double beds, a chest of drawers with singles. The double (163 x 202) leaves 52 at the office door here, so
    # NobleBedSingle01 (109 x 203, headboard at its local -y), head to the end wall under its window (the room's doors
    # leave no other wall), the night table in the corner by its head, the drawers on the back wall clear of the gallery
    # door's swing, a rug where the office door opens. No wardrobe: the only wall left gives 67 before it
    piece("meshes/furniture/noble/noblebedsingle01.nif", "NobleBedSingle01", (-1334.5, 790, ZG), 90, name="AGHallBedGM", owner="gm")
    # (option 1 of the two renders, 2026-10-26, with the wardrobe and the remaining nightstand moved under the
    # other window: the wardrobe in the corner by the head, the drawers centred under the back window, the candle on them)
    piece("meshes/furniture/noble/noblewardrobe01.nif", "NobleWardrobe01", (-1427.5, 692, ZG), 270, owner="gm")
    CANDLE_ = (-1274, 880, ZG + 63)
    piece("meshes/clutter/silver/silvercandlestick01.nif", "SilverCandleStick01", CANDLE_, 0)
    piece("meshes/furniture/noble/noblechestdrawers01.nif", "NobleChestDrawers01", (-1299, 884.5, ZG), 0, owner="gm")   # (its back at local +y 12.5)
    piece("meshes/clutter/common/rug01.nif", "Rug01", (-1250, 714, ZG + 0.3), 90)   # (of vanilla's rugs: ornate, it fits)
    # the clutter pass (2026-10-27): his rooms as vanilla dresses a leader's, lightly (research/gmrooms: Falk Firebeard's desk
    # in the Blue Palace carries three books and a candlestick; Kodlak's room a few goblets, a book, his purse). The office:
    # on the desk (NobleDesk02, its top 63.3 within local x -80..83, y -49..12; the sitter at -x) a candlestick at the back,
    # the guild's journal open before the sitter with letters beside it, ink and quill, a pile of books, his purse, a goblet;
    # on the shelf (UpperShelf01, its boards 17, 62, 107 within x -1146..-1107, y 429..545) the guild's records, rolled
    # charters and a strongbox; a rug under the desk. The bedroom's drawers: a book and a goblet by the candle. Everything
    # here his faction's (guildhall_gen's export owns his rooms); the decorative books baked ("gm")
    DZG = ZG + 63.3
    piece("meshes/clutter/common/rug02.nif", "Rug02", (-1336, 380, ZG + 0.3), 90)
    piece("meshes/clutter/silver/silvercandlestick01.nif", "SilverCandleStick01", (-1298, 448, DZG), 0)
    NEW_LIGHTS.append((-1298, 448, DZG + 52, 0.4e6, (1.0, 0.72, 0.45), "candle_small"))
    piece("meshes/clutter/books/journallowpoly01.nif", "AGHall2Journal", (-1326, 382, DZG + 1.0), 90, exact=True, bake="gm")
    for k_ in range(3):
        piece(f"meshes/clutter/books/note0{k_ + 1}.nif", f"AGHall2Note0{k_ + 1}", (-1324 + k_ * 0.8, 338 + k_ * 0.6, DZG + 0.35 + 0.3 * k_), 95 + k_ * 6, exact=True, bake="gm")
    piece("meshes/clutter/common/inkwell01.nif", "Inkwell01", (-1304, 412, DZG), 0, owner="gm", settled=True)
    piece("meshes/clutter/common/quill01.nif", "Quill01", (-1313, 428, DZG + QUILL_LIE_Z), 7, owner="gm", settled=True, rx=90)   # (along
    # the desk beside the well, clear of the journal at -1326, 382, the purse and the candlestick)
    for k_, bk_ in enumerate(("BookLarge", "Book06", "Book03a")):
        piece(f"meshes/clutter/books/{LIB_BOOKS[bk_]}.nif", "AGHall2" + bk_, (-1302, 312, DZG + (3.4 if k_ == 0 else 6.9 + 4.15 * (k_ - 1) + 2.1)), 90 + (k_ * 7) % 9, exact=True, bake="gm")
    piece("meshes/plants/coinbagsmall.nif", "CoinPurseSmall", (-1336, 440, DZG), 30, owner="gm", settled=True)
    # (the lived-in pass, 2026-11-17) three sealed letters between the books and the well: the letters he still writes to families
    for k_ in range(3):
        piece("meshes/clutter/books/note03.nif", "AGHall2Note03", (-1300 + k_ * 0.7, 362 + k_ * 0.5, DZG + 0.35 + 0.3 * k_), 100 + k_ * 7, exact=True, bake="gm")
    sit("meshes/clutter/silver/silvergoblet01.nif", "SilverGoblet01", -1336, 304, DZG, 0)
    shelf_books((-1126, 432), (-1126, 542), ZG + 107, 0, "GM2", room=40, fill=0.85, bake="gm")
    for k_ in range(3):
        piece("meshes/clutter/quest/tgparchment01.nif", "PaperRoll", (-1127 + (k_ % 2) * 3, 487 + (k_ - 1) * 6.2, ZG + 62 + 2.8 + (k_ == 1) * 5.3), 90, owner="gm", settled=True)
    piece("meshes/clutter/common/strongbox01.nif", "StrongBox", (-1126, 500, ZG + 17.2), 270, owner="gm")
    shelf_books((-1126, 432), (-1126, 476), ZG + 17, 0, "GM0", room=40, fill=0.9, bake="gm")
    # the bedroom's drawers (NobleChestDrawers01, its top 63.3 within x -1343..-1255, y 860..897; the candle at -1274)
    piece(f"meshes/clutter/books/{LIB_BOOKS['Book05a']}.nif", "AGHall2Book05a", (-1326, 878, DZG + 2.1), 80, exact=True, bake="gm")
    sit("meshes/clutter/silver/silvergoblet01.nif", "SilverGoblet01", -1302, 874, DZG, 0)
    NEW_LIGHTS += [(-1310, 380, ZG + 190, 1.5e6, (1.0, 0.78, 0.55), "lamp"), (-1290, 800, ZG + 190, 1.2e6, (1.0, 0.78, 0.55), "lamp"),
                   (CANDLE_[0], CANDLE_[1], CANDLE_[2] + 50, 0.4e6, (1.0, 0.72, 0.45), "candle_small")]   # (the candlestick's own light)
    PLAN.append({"t": "room", "level": 1, "name": "guild master's office", "r": [-1452, 134, -1092, 616]})
    PLAN.append({"t": "room", "level": 1, "name": "guild master's bedroom", "r": [-1452, 640, -1092, 906]})

    # the staff quarters off the lobby (all private, every room its own door, round a single common room rather than a
    # corridor, room 5 off the lobby): rooms 6 and 7 where the dorm was (7 has no window), the common room behind the
    # staff door, rooms 3, 4 and 5 down the cross gable's end. One partition runs front to back on the cross gable's line
    # (the lobby's right wall moved onto it), and the walls between 3, 4 and 5 were nudged so their windows sit framed
    # (room 4's window sat tight in the corner): room 3 to 374, room 4 386..630, room 5 from 642
    # (2026-11-06, plan D, after the walk found the staff rooms too cramped, Caralion's most of all: Henriette to the
    # basement, Margot to her room 6, rooms 3 and 4 down to room 7's size, room 5 the rest) rooms 3 and 4 380 x 210, room 5 380 x 328;
    # their windows inside moved onto the beds (STAFF_WIN, the window loop below; outside they stay)
    Y34, Y45 = 344, 566                                       # the near faces of the walls between rooms 3 and 4, 4 and 5
    box("planks", (416, 158, ZG - 4), (1060, 600, ZG)); box("planks", (1060, 134, ZG - 4), (1452, 906, ZG))
    box("planks", (416, 158, T1), (1060, 600, T1 + 14)); box("planks", (1060, 134, T1), (1452, 906, T1 + 14))   # their ceilings:
    # the doors of rooms 3, 4 and 5 (plan D): 3 and 5 in their back corners hinged at the back, 4 in its front corner hinged at the front;
    # each post flush with its corner's wall, the open leaf against that wall (the attic's floor: the boxes above)
    RD = ((234, 330), (Y34 + 26, Y34 + 122), R5D)
    for W, L, hs in (((Vector((1060, 158, 0)), Vector((-1, 0, 0)), Vector((0, 1, 0))), 644, []),      # the front: room 6, common room
                     ((Vector((1452, 134, 0)), Vector((-1, 0, 0)), Vector((0, 1, 0))), 380, []),      # the cross gable's front: room 3
                     ((Vector((1452, 906, 0)), Vector((0, -1, 0)), Vector((-1, 0, 0))), 772, []),     # the outer end
                     ((Vector((1072, 906, 0)), Vector((1, 0, 0)), Vector((0, -1, 0))), 380, []),      # room 5's back
                     ((Vector((416, 158, 0)), Vector((0, 1, 0)), Vector((1, 0, 0))), 430, []),        # the hall's wall: rooms 6 and 7
                     ((Vector((416, 588, 0)), Vector((1, 0, 0)), Vector((0, -1, 0))), 644,            # the lobby's wall, their side
                      [(STAFF_DOOR[0] - 416, STAFF_DOOR[1] - 416, ZG, ZG + 202)]),
                     ((Vector((1060, 588, 0)), Vector((0, -1, 0)), Vector((-1, 0, 0))), 430,          # the partition, the common room's side
                      [(588 - b_, 588 - a_, ZG, ZG + DOOR_H) for a_, b_ in RD[:2]]),
                     ((Vector((1072, 134, 0)), Vector((0, 1, 0)), Vector((1, 0, 0))), 772,            # the partition, rooms 3, 4 and 5's side
                      [(a_ - 134, b_ - 134, ZG, ZG + DOOR_H) for a_, b_ in RD])):
        face("stucco", W, 0, L, ZG, T1, hs)
        for zz in RR: wall_rail(W, 0, L, zz, hs, w=22)
        if L == 430 and W[0].x == 1060:                       # (the common room's side draws the reveals of rooms 3 and 4's doors;
            for h in hs: opening_frame(W, h[0], h[1], h[2], h[3], 12)   # room 5's come from the lobby's wall) (their room side framed by the rooms' own walls: both=False)
        else:
            for h in hs: frame_timbers(W, h[0], h[1], h[2], h[3])
    partition(760, 158, 772, 588, ZG, T1, holes=[(256, 352, ZG, ZG + DOOR_H), (476, 572, ZG, ZG + DOOR_H)], rails=RR)   # (rooms 6 and 7's doors in their back corners)
    partition(416, 366, 760, 378, ZG, T1, rails=RR)
    partition(1072, Y34, 1452, Y34 + 12, ZG, T1, rails=RR)
    partition(1072, Y45, 1452, Y45 + 12, ZG, T1, rails=RR)
    for (a_, b_), nm_ in (((256, 352), "AGHall2Room6Door"), ((476, 572), "AGHall2Room7Door")): door_leaf((766, a_), (766, b_), ZG, (-1, 0), nm_)
    for (a_, b_), nm_ in zip(RD, ("AGHall2Room3Door", "AGHall2Room4Door", "AGHall2Room5Door")):   # (R: hinged at the back end)
        door_leaf((1066, a_), (1066, b_), ZG, (1, 0), nm_, right=nm_ in ("AGHall2Room3Door", "AGHall2Room5Door"))
    # room 5's, where it has always stood (centre 710); its breast run 0.5 into what stands either side, as the walk of 2026-11-03 fixed
    # it: since plan D (2026-11-06) the wall to room 4 at 578 and the post of the door in the back corner (782; both sides fixed)
    manor_fireplace(1072, 1, 710, ZG, 0.5, rail=8, ztop=T1, y_lo=710 - (R5D[0] - 14 + 0.5 - 710), y_hi=R5D[0] - 14 + 0.5)   # (the test walk of 2026-11-06: not to the wall, it looked wrong; even both sides, to the door's post: 637.5..782.5)
    # since the fit-out (the walk of 2026-10-26: rooms 3 and 4 and the common room impassable): four doors on the
    # common room's long walls leave no room for a long table, so a round one with two chairs, 104 clear past every door, and
    # a bench under the front window; in every room the bed's head to a wall, along the room, its chest beside the head (its
    # latch, local +y, to the room), 84 or more clear from each door (no chair by room 5's fire: a hearth
    # needs no seat before it and small rooms keep their floor)
    piece("meshes/clutter/upperclass/uppertableround01.nif", "UpperTableRound01", (916, 373, ZG), 0)
    piece("meshes/clutter/upperclass/upperchair01.nif", "UpperChair01LR", (916, 303, ZG), 0)     # (side-entry, 70 out: 2026-11-07, NPCs stood up onto the tables)
    piece("meshes/clutter/upperclass/upperchair01.nif", "UpperChair01LR", (916, 443, ZG), 180)
    # (turned 0: its backrest is its local -y, its seats face +y; at 180 its back was to the room and its sitters faced the
    # window wall: the placement gate's seat check and its render, 2026-10-28)
    piece("meshes/clutter/upperclass/upperbench01.nif", "UpperBench01", (881, 186, ZG), 0)
    # room 3 (y 143..431 inside its rails), the clerks', an inn's twin room: both heads to the outer wall either side of its
    # window (y 248..332), one bed along each long wall, an aisle of 82 between them under the window, a chest at each foot
    # opening to the room; room 4 (461..621), Merila's, its bed across under its window, its chest at the foot (heads 15 off
    # the outer wall: its window frames). Each bed and chest named, so the NPC build can give it an owner (the NPC session,
    # 2026-10-27): AGHallBed<room>, AGHallChest<room>
    # (plan D, 2026-11-06) rooms 6 and 7: the bed along the front wall, its head to the hall's wall, the nightstand behind its head, the
    # chest past its foot; rooms 3 and 4 the same turned round (a true copy of rooms 6 and 7, rotated): the bed along the
    # back wall, head to the end wall under the window, nightstand before it, chest at the foot. Margot (the day clerk, AGHallBedRoom3)
    # in room 4 and Merila (AGHallBedRoom4) in room 6 since 2026-11-06 (the clerks next door); Nessa (AGHallBedRoom3b) room 3; Brynja room 7
    B3_, B4_ = Y34 - 61, Y45 - 61                             # rooms 3 and 4's beds' middles (9 off their back walls)
    BEDS34 = (((1344, B3_, 270), (1219, B3_, 270), "Room3b"), ((1344, B4_, 270), (1219, B4_, 270), "Room3"))   # (2026-11-06: the clerks next door, Nessa 3, Margot 4)
    for (bx_, by_, ba_), (cx_, cy_, ca_), rn_ in (((518.5, 440, 90), (662, 413, 0), "Room7"), ((518.5, 220, 90), (662, 193, 0), "Room4")) + BEDS34:
        # (all 9 off their walls since the clip check, 2026-10-27: heads and chests ran into the rails and posts)
        piece("meshes/clutter/upperclass/upperbedsingle01.nif", "UpperBedSingle01", (bx_, by_, ZG), ba_, name="AGHallBed" + rn_)   # (its pillow
        piece("meshes/clutter/upperclass/upperchest01.nif", "AGHall2Chest", (cx_, cy_, ZG), ca_, name="AGHallChest" + rn_)        # at local -y)
    # the staff rooms' clutter (the clutter pass, 2026-10-27), as vanilla's rented rooms are kept: a small table by the bed
    # with a candle and a little of its owner (the NPC session's bios), nothing in the way of a bed's side or a chest's
    # front. Room 3, the clerks': vanilla's end table (its top 62, under the window's sill at 70) between their beds' heads
    # under the window, Margot's lists and a book by the candle; rooms 4, 6 and 7 the smaller nightstand (its top 30)
    # by the bed's head: Merila's books, Henriette's sweetroll, Brynja's mead. Their pieces are their owners' (the
    # export's room groups); the papers baked ("staff")
    CT_ = "meshes/clutter/candles/candlehorntable01.nif"
    # (the nightstand's top is 34 x 30: a small candlestick and one thing beside it)
    # (the walk of 2026-11-01: the rings hung over rooms 4 and 6 went; a single candle lantern is enough there: on the nightstand, where the candlestick stood, not on the chest, whose lid opens)
    STAFF_NT = (((450, 295), None, True),                                                     # Merila (room 6 since 2026-11-06: the clerks next door; her book since the lived-in pass)
                ((450, 515), ("ingredients/mead01", "FoodMead"), False),                  # Brynja
                ((1418, B4_ - 75), ("books/note01", "AGHall2Note01"), "candle"),         # Margot, her lists and a candle (room 4)
                ((1418, B3_ - 75), None, "candle"))                                       # Nessa, a candle (room 3; its wall sconce stood on the window)
    # (lit_: True a candle lantern, "candle" vanilla's single candle (ImpCandle01, 10 across: the horn candle's 37 is longer than
    # this top's 34) at the top's back left, False a candlestick)
    def nt_light(nx_, ny_, lit_): return (nx_ - 12, ny_ + 3) if lit_ == "candle" else (nx_ - 8, ny_ + 6)
    for (nx_, ny_), it_, lit_ in STAFF_NT:
        piece("meshes/clutter/upperclass/uppernightstand01.nif", "UpperNightstand01", (nx_, ny_, ZG), 0)
        if lit_ is True: sit("meshes/clutter/common/candlelanternwithcandle01.nif", "CandleLanternwithCandle01", nx_ - 8, ny_ + 6, ZG + 31.6, 0)
        elif lit_ == "candle": sit("meshes/clutter/imperial/impcandle01.nif", "ImpCandle01", *nt_light(nx_, ny_, lit_), ZG + 30, 0)
        elif lit_ is False: sit("meshes/clutter/silver/silvercandlestick03.nif", "SilverCandleStick03", nx_ - 8, ny_ + 6, ZG + 30, 0)
        if it_ is None: continue
        m_, e_ = it_
        if e_.startswith("AGHall2"):
            piece(f"meshes/clutter/{m_}.nif", e_, (nx_ + 10, ny_ - 6, ZG + 30 + 1.0), 0, exact=True, bake="staff")
        else:
            sit(f"meshes/clutter/{m_}.nif", e_, nx_ + 9, ny_ - 6, ZG + 30, 0)
    # the lived-in pass (2026-11-17: the staff rooms all alike, the trunks empty, the cellar bare): a little more of each owner, from
    # their bios, as vanilla's kept rooms carry it (Jorrvaskr's and the College's bedrooms: 15 to 25 pieces of their own each: books
    # picked for the owner, a purse, food and drink, a keepsake). Small rooms: on the nightstands and on one wall shelf each, nothing
    # on a chest's lid or in a bed's side. Each piece its room's (the export's room groups); real books, so they can be read
    NT_ = ZG + 30                                             # (the nightstands' tops: 34 x 30, x +-17.3, y +-15.4)
    WS_ = "meshes/furniture/noble/noblewallshelf01.nif"       # (its board's top 131.4 over its origin, its back at local y 0 on the wall,
    WSZ = ZG + 131.4                                          # 96 long, 34.5 deep; turned 0 its front faces -y, 180 +y, 270 +x)
    # Nessa (room 3, her nightstand at (1418, B3_ - 75)): the pick-your-path adventure she grew up on, and a Dwarven gear from the
    # barrow outside Markarth she means to go back into, set down on the book
    # (2026-11-17: both at the top's right, clear of her candle at its back left)
    sit("meshes/clutter/books/basicbook06.nif", "Book1CheapKolbAndTheDragon", 1424, B3_ - 75, NT_, 7)
    sit("meshes/clutter/dwemer/dwarvengear.nif", "DwarvenGear", 1425, B3_ - 73, NT_ + 3.91 + 0.15, 31)   # (on the book's top: it is 3.91 thick)
    # Margot (room 4): a wall shelf on her wall with room 5 (y Y45, the room on its -y side), over the bed's middle: two of the
    # adventure stories she loves, a small jug and a few mountain flowers laid by it (no vase among vanilla's pieces)
    piece(WS_, "NobleWallShelf01", (1300, Y45 - 0.5, ZG), 0)
    sit("meshes/clutter/books/basicbook03.nif", "Book2CommonLegendofRedEagle", 1271, Y45 - 17, WSZ, 84)
    sit("meshes/clutter/books/basicbook03.nif", "Book3ValuableLostLegends", 1272, Y45 - 18, WSZ + 4.0, 97)
    sit("meshes/clutter/glazedjugsmall01.nif", "GlazedJugSmall01", 1318, Y45 - 15, WSZ, 40)
    sit("meshes/plants/mountainflower01blue.nif", "MountainFlower01Blue", 1334, Y45 - 21, WSZ, 72, rx=90)
    sit("meshes/plants/mountainflower01purple.nif", "MountainFlower01Purple", 1337, Y45 - 16, WSZ, 101, rx=90)
    # Merila (room 6): A Dance in Fire on her nightstand, three volumes stacked and the fifth on them askew (she is rereading it);
    # her dungeon map taken upstairs: a wall shelf on the hall's wall (x 416) over the nightstand, clear of the bed's head (y 172..268)
    for k_, (m_, e_) in enumerate((("basicbook05", "Book0DanceInFireV1"), ("basicbook05", "Book0DanceInFireV3"), ("basicbook05", "Book0DanceInFireV4"))):
        sit(f"meshes/clutter/books/{m_}.nif", e_, 458 + 0.4 * k_, 290 - 0.3 * k_, NT_ + 4.1 * k_, 4 + 5 * k_)
    sit("meshes/clutter/books/basicbook04a.nif", "Book4RareADanceInFireV5", 459, 291, NT_ + 4.1 * 3 + 0.1, 27)
    piece(WS_, "NobleWallShelf01", (416.5, 316, ZG), 270)
    sit("meshes/clutter/quest/tgparchment01.nif", "PaperRoll", 431, 300, WSZ, 92)        # (54 long: along the shelf)
    sit("meshes/clutter/quest/tgparchment01.nif", "PaperRoll", 437, 304, WSZ + 2.2, 265)
    sit("meshes/clutter/common/inkwell01.nif", "Inkwell01", 432, 334, WSZ, 0)
    sit("meshes/clutter/common/quill01.nif", "Quill01", 437, 343, WSZ, 0, rx=90)
    # Brynja (room 7): the night's tips by her mead; wildflowers from an admirer on a wall shelf over the bed, on the wall she shares
    # with room 6 (y 378, the room on its +y side)
    sit("meshes/plants/coinbagmed.nif", "CoinPurseMedium", 458, 524, NT_, 0)
    piece(WS_, "NobleWallShelf01", (566, 378.5, ZG), 180)
    sit("meshes/plants/lavender01.nif", "Lavender", 552, 396, WSZ, 8)
    sit("meshes/plants/mountainflower01blue.nif", "MountainFlower01Blue", 560, 392, WSZ + 1.0, 340, rx=90)
    sit("meshes/plants/mountainflower01purple.nif", "MountainFlower01Purple", 556, 400, WSZ + 1.0, 21, rx=90)
    sit("meshes/clutter/glazedjugsmall01.nif", "GlazedJugSmall01", 588, 394, WSZ, 60)
    # the common room's round table (UpperTableRound01, its top 62, radius 39): a candle, two tankards, bread on a plate
    sit("meshes/clutter/wine/winebottle02b.nif", "FoodWineBottle02", 916, 388, ZG + 62, 90)   # (the walk of 2026-11-06: the candle under the chandelier out, a wine bottle instead)
    sit("meshes/clutter/dining set/basictankard01.nif", "BasicTankard01", 896, 360, ZG + 62, 30)
    sit("meshes/clutter/dining set/basictankard01.nif", "BasicTankard01", 936, 356, ZG + 62, 200)
    sit("meshes/clutter/dining set/basicwoodenplate01.nif", "BasicWoodenPlate01", 916, 340, ZG + 62, 0)
    sit("meshes/clutter/food/bread01a.nif", "FoodBread01A", 916, 340, ZG + 66, 10)
    # room 5, Caralion of Cloudrest's (2026-10-27: the Altmer noble's son has a nicer room, as he pays well for it,
    # room 5 with its fire; then, the room too full to walk in, modelled on the Thalmor Embassy with a small single
    # bed and a smaller chest): as the Embassy's single noble room is set
    # (research/services/embassy.tsv, ThalmorEmbassy02: a noble single bed, its night table by the head, an upper chest
    # beside the foot, the rest of the floor open). The bed in the far corner: its head on the windowless wall it shares
    # with room 4, its side along the outer wall under the window's sill (60 up), 9 off both walls to clear their posts
    # and rails (8 deep); the night table by the head with a candle and a cup; the chest on the back wall beside the
    # bed's foot, under the back window's sill; a rug on the open floor between the fire, the door and the bed
    # (2026-11-03: room 5 becomes the player's home, for any spouse) a double in the far corner, its right side to the outer wall and its
    # left one open toward the fire (about 93 clear: a spouse walks to that side; the player gets in from either), as vanilla's homes stand theirs
    # (five of six player homes have one side to a wall; the spouse's side open only). (2026-11-04: the larger bed
    # from the start, no swap) Caralion sleeps in it from the start, and the room's handover changes its owner, not the furniture:
    # one bed, named as his was so its owner (the room's faction) and his schedule hold; no single, no swap marker
    # (plan D, 2026-11-06: Caralion's bed rotated, the chest out of the way) the double turned, its head (local -y)
    # to the end wall under the window (moved onto it, 720), 9 off it; both its sides open to walk to, the night table on the front one
    # (one is enough); the chest on the back wall past the door's swing, as it stood
    B5_ = 720
    piece("meshes/furniture/noble/noblebeddouble01.nif", "NobleBedDouble01", (1452 - 9 - 101, B5_, ZG), 270, name="AGHallBedRoom5")
    # the spouse's spot in the room, by the fire
    MARKERS += [("AGHallRoom5SpouseMarker", "XMarkerHeading", (1190, 760, ZG), 270)]
    # the night table against the end wall beside the head (52 x 38, its back local +y: turned 90), the candle and the cup on it
    NTX_, NTY_ = 1452 - 5.5 - 19, B5_ - 82 - 9 - 26
    piece("meshes/furniture/noble/noblenighttable01.nif", "NobleNightTable01", (NTX_, NTY_, ZG), 90)
    piece("meshes/clutter/silver/silvercandlestick01.nif", "SilverCandleStick01", (NTX_ - 3.5, NTY_ - 8.4, ZG + 63.3), 0, owner="guild", settled=True)
    piece("meshes/clutter/silver/silvergoblet01.nif", "SilverGoblet01", (NTX_ + 4.5, NTY_ + 8.6, ZG + 63.3), 40, owner="guild", settled=True)
    # (the lived-in pass, 2026-11-17) two good wines by them: he drinks alone more than he admits
    sit("meshes/clutter/wine/winebottle01b.nif", "FoodWineAlto", NTX_ - 6, NTY_ + 17, ZG + 63.3, 0)
    sit("meshes/clutter/wine/winebottle02b.nif", "FoodWineBottle02", NTX_ + 7, NTY_ - 17, ZG + 63.3, 0)
    # the chest (Caralion's things stay and become the player's), 60 along the back wall from under the window so
    # the double's foot leaves its lid free
    # (2026-11-06, the room plan) the chest in the back corner beside the bed's head, against the end wall, its lid (local +y) to
    # the room (turned 270), the walk behind the bed open; the rug on that open side where one's feet land, under the bed's foot corner,
    # clear of the door's swing, the chest and the hearth
    piece("meshes/clutter/upperclass/upperchest01.nif", "AGHall2Chest", (1452 - 9 - 49, 906 - 9 - 23, ZG), 180, name="AGHallChestRoom5")   # along the back wall, lid to the bed; 9 off both walls (the rail)
    piece("meshes/clutter/common/rug02.nif", "Rug02", (1258, 812, ZG + 0.3), 90)
    NEW_LIGHTS += [(916, 373, ZG + 200, 1.5e6, (1.0, 0.78, 0.55), "lamp")] + [(x_, y_, ZG + z_, 1.0e6, (1.0, 0.78, 0.55), "candle", 122, f_)
                                                                            for x_, y_, z_, f_ in [(*nt_light(nx_, ny_, lit_), 72 if lit_ is True else 52, 0.0 if lit_ is True else -1.1) for (nx_, ny_), it_, lit_ in STAFF_NT if lit_]]   # (a lantern's flame 42 up, a candle's 18)   # (each lit lantern's own, plan D)   # (the two lanterns: 250, the room's length from its corner)
    for nm_, r_ in (("room 6", [416, 158, 760, 366]), ("room 7", [416, 378, 760, 588]), ("common room", [772, 158, 1060, 588]),
                    ("room 3", [1072, 134, 1452, Y34]), ("room 4", [1072, Y34 + 12, 1452, Y45]), ("room 5", [1072, Y45 + 12, 1452, 906])):
        PLAN.append({"t": "room", "level": 1, "name": nm_, "r": r_})

    # the services wing's attic: recruits' bunks along the ridge, each with its own storage
    # chest as in vanilla, heads under the eaves; in through the tower stair's attic door. Its ceiling is the
    # wing roof's underside (as the tavern's), the two dormers cut into its front slope and the cross gable's own roof over
    # its far end (its ridge along y, pitch 54: abut_gable_roof's numbers), meeting the front slope in two valleys
    ZA = T1 + 14                                              # the attic's floor (670)
    CGc, TC = (1036 + 1476) / 2, math.tan(math.radians(54))
    ZCR = T1 + (1476 - 1036) / 2 * TC - 18                    # the cross gable's underside at its ridge (941)
    ZC = lambda x_: ZCR - abs(x_ - CGc) * TC
    yv = lambda x_: WYR - (WZR - 18 - ZC(x_)) / TW            # where it meets the front slope (the valleys)
    XE = 1452                                                 # the attic's outer end
    DORM_R = (571, 881)
    # (the walk of 2026-11-03: the attic's timbers simply stopped at the gable and the dormers; option 1: valley rafters and trimmed
    # dormers, every rafter ending on a timber. AG_ATTIC=0 is the attic before it, 2 the closed cross gable, not chosen)
    ATT = int(os.environ.get("AG_ATTIC", "1")); ATT_LOG = []
    def nbeam(p0, p1, w, deep, nrm, what):                    # a new timber, logged for the clearance check
        beam(p0, p1, w, deep, nrm); ATT_LOG.append({"what": what, "p0": list(p0), "p1": list(p1), "w": w, "deep": deep, "n": list(nrm)})
    YJ = yv(CGc)                                              # where the cross gable's ridge meets the front slope (the valleys' top)
    cuts = sorted(x_ + s * DH for x_ in DORM_R for s in (-1, 1)); xs_ = [XU + TT] + cuts + [1060]
    for i, (xa, xb) in enumerate(zip(xs_, xs_[1:])):          # the front slope: whole between the dormers, from where a dormer's
        slope(xa, xb, ymeet if i % 2 else WF, WYR, True)     # ceiling meets it over them, from the valleys over the cross gable
        if i % 2: slope(xa, xb, WF, 164, True)
    if ATT == 2:
        P2_ = XU + TT + 32 + 64 * math.ceil((1060 - (XU + TT + 32)) / 64)   # (the first rafter past 1060: the panel's edge on its middle)
        slope(1060, P2_, WF, WYR, True); slope(P2_, XE, YJ, WYR, True)
        pp_ = [Vector((P2_, WF, ZW(WF))), Vector((XE, WF, ZW(WF))), Vector((XE, YJ, ZW(YJ))), Vector((P2_, YJ, ZW(YJ)))]
        bo_ = Vector((0, -TW, 1)).normalized()                # (its back faced too, 1 behind it: the gable's windows look at it)
        poly_n("stucco", pp_, (0, TW, -1))
        pb_ = [Vector((1060, WF, ZW(WF))), Vector((XE, WF, ZW(WF))), Vector((XE, WYR, WZR - 18)), Vector((1060, WYR, WZR - 18))]
        poly_n("planks", [q_ + bo_ for q_ in pb_], (0, -TW, 1))
    else:
      for xa, xb in ((1060, CGc), (CGc, XE)):
        poly_n("planks", [Vector((xa, yv(xa), ZW(yv(xa)))), Vector((xb, yv(xb), ZW(yv(xb)))), Vector((xb, WYR, WZR - 18)), Vector((xa, WYR, WZR - 18))], (0, TW, -1))
    slope(XU + TT, TX1, WYR, TY0, False); slope(TX1, XE, WYR, WB, False)   # the back slope (the tower's corner is the tower's)
    for xa, xb, nx_ in (((1060, CGc, TC), (CGc, XE, -TC)) if ATT != 2 else ()):     # the cross gable's two slopes, its front to the valleys
        poly_n("planks", [Vector((xa, 134, ZC(xa))), Vector((xb, 134, ZC(xb))), Vector((xb, yv(xb), ZC(xb))), Vector((xa, yv(xa), ZC(xa)))], (nx_, 0, -1))
    if ATT != 2: poly_n("stucco", [Vector((1060, 134, ZA)), Vector((XE, 134, ZA)), Vector((XE, 134, ZC(XE))), Vector((CGc, 134, ZCR)), Vector((1060, 134, ZC(1060)))], (0, 1, 0))   # its gable
    if ATT != 2: face("stucco", (Vector((1060, 134, 0)), Vector((0, 1, 0)), Vector((1, 0, 0))), 0, WF - 134, ZA - 1, ZC(1060) + 1)   # its left side's
                                              # foot: a slit 1 high under the slope there led out (leak_check, 2026-10-26)
    if ATT == 2: strips((Vector((XE, WB, 0)), Vector((0, -1, 0)), Vector((-1, 0, 0))), 0, WB - WF, ZA, lambda u_: ZW(WB - u_), breaks=(WB - WYR,))
    else: strips((Vector((XE, WB, 0)), Vector((0, -1, 0)), Vector((-1, 0, 0))), 0, WB - 134, ZA,           # the outer end's gable
           lambda u_: ZW(WB - u_) if WB - u_ >= yv(XE) else ZC(XE), breaks=(WB - WYR, WB - yv(XE)))
    strips((Vector((XU + TT, WF, 0)), Vector((0, 1, 0)), Vector((1, 0, 0))), 0, TY0 - WF, ZA,        # the hall's wall, its attic side
           lambda u_: ZW(WF + u_), breaks=(WYR - WF,))
    WTA = (Vector((XU + TT, TY0, 0)), Vector((1, 0, 0)), Vector((0, -1, 0)))                         # the tower's front, its door
    face("stucco", WTA, 0, TX1 - XU - TT, ZA, ZW(TY0), [(AD[0] - XU - TT, AD[1] - XU - TT, ZA, ZAT + DOOR_H)])
    for ua_ in (AD[0] - XU - TT - 7, AD[1] - XU - TT + 7): wall_beam(WTA, (ua_, ZA), (ua_, ZAT + DOOR_H), w=14, deep=10)
    wall_beam(WTA, (AD[0] - XU - TT - 14, ZAT + DOOR_H + 5), (AD[1] - XU - TT + 14, ZAT + DOOR_H + 5), w=10, deep=10)   # (a thin
                                                              # lintel: the roof comes down to 858 over the door's 846)
    strips((Vector((TX1, TY0, 0)), Vector((0, 1, 0)), Vector((1, 0, 0))), 0, WB - TY0, ZA, lambda u_: ZW(TY0 + u_))   # its side
    for x_ in DORM_R:                                         # each dormer from inside, as the tavern's
        for xs in (x_ - DH, x_ + DH):
            p_ = [Vector((xs, 164, ZW(164))), Vector((xs, ymeet, 826)), Vector((xs, 164, 826))]
            poly("planks", p_[::-1] if xs > x_ else p_)   # (2026-10-30: the dormers' sides in matching wood, not plaster)
        poly("planks", [Vector((x_ - DH, 164, 826)), Vector((x_ + DH, 164, 826)), Vector((x_ + DH, ymeet, 826)), Vector((x_ - DH, ymeet, 826))][::-1])
        face("planks", (Vector((x_ + DH, 164, 0)), Vector((-1, 0, 0)), Vector((0, 1, 0))), 0, 2 * DH, ZW(164), 826)
    box("wood", (XU + TT, WYR - 16, WZR - 60), (XE, WYR + 16, WZR - 18))   # the ridge beam; the cross gable's
    if ATT != 2: box("wood", (CGc - 16, 134.5, ZCR - 42), (CGc + 16, yv(CGc), ZCR))
    xx = XU + TT + 32; COMMONS = []
    while xx < XE - 16:                                       # rafters every 64 (from a dormer's ceiling over it, from the valley
        dd_ = [d_ for d_ in DORM_R if abs(xx - d_) < DH + 8]
        if ATT and dd_ and abs(xx - dd_[0]) > DH - 7: y0_ = None      # (trimmed: where a trimmer stands, no rafter)
        elif ATT and dd_: y0_ = ymeet + 23                    # (trimmed: a cripple, from the top header to the ridge)
        elif dd_: y0_ = ymeet   # over the cross gable)
        elif xx > 1060 and ATT != 2: y0_ = yv(xx)
        else: y0_ = WF
        if y0_ is not None: beam((xx, y0_, ZW(y0_) - 2), (xx, WYR, WZR - 20), 12, 16, nf)
        COMMONS.append(xx)
        y1_ = TY0 if xx < TX1 + 8 else WB
        beam((xx, y1_, ZW(y1_) - 2), (xx, WYR, WZR - 20), 12, 16, nb)
        xx += 64
    if ATT:   # each dormer trimmed: a doubled rafter each side, plate to ridge, its inner face 0.5 off the cheek; a doubled header
              # across the top between them, its lower edge on the line where the dormer's ceiling meets the slope
        for d_ in DORM_R:
            for e_, sg_ in ((d_ - DH, -1), (d_ + DH, 1)):
                for k_ in (0, 1):
                    xc_ = e_ + sg_ * (0.5 + 6 + k_ * 12.6)
                    nbeam((xc_, WF, ZW(WF) - 2), (xc_, WYR, WZR - 20), 12, 16, nf, f"trimmer {d_}")
            yh_ = ymeet + 12
            nbeam((d_ - DH - 6.5, yh_, ZW(yh_) - 3), (d_ + DH + 6.5, yh_, ZW(yh_) - 3), 24, 14, nf, f"header {d_}")   # (its ends in the trimmers' inner halves, its top 1 under theirs and its foot 1 over: no face in another's plane, as wall_beam's posts stand 1 proud)
    if ATT == 1:   # the cross gable's valleys: from the eaves' corners up the two slopes' meeting to the junction, 1.5 x 1.33 the
                   # rafters; a doubled header across the junction between the two commons there takes their heads and the ridge's
        J_ = Vector((CGc, YJ, ZW(YJ)))
        for x0_, nx_ in ((1060, TC), (XE, -TC)):
            P0_ = Vector((x0_, yv(x0_), ZW(yv(x0_)))); a_ = (J_ - P0_).normalized()
            n_ = (Vector((0, TW, -1)).normalized() + Vector((nx_, 0, -1)).normalized()); n_ -= a_ * n_.dot(a_); n_.normalize()
            nbeam(tuple(P0_ + n_ * 2), tuple(J_ + n_ * 2), 18, 21, tuple(n_), f"valley {x0_}")
        xa_ = max(c_ for c_ in COMMONS if c_ < CGc); xb_ = min(c_ for c_ in COMMONS if c_ > CGc); yh_ = YJ + 12
        nbeam((xa_, yh_, ZW(yh_) - 3), (xb_, yh_, ZW(yh_) - 3), 24, 14, nf, "junction header")   # (from rafter's middle to rafter's middle)
    if ATT == 2:   # the closed panel's head: a rail between the commons on the junction's line, the panel's plaster below it
        xs2_ = [c_ for c_ in COMMONS if c_ > 1060] + [XE + 2]   # (from the first rafter's middle, the panel's edge, into the end wall)
        for a2_, b2_ in zip(xs2_, xs2_[1:]):
            nbeam((a2_, YJ, ZW(YJ) - 3), (b2_, YJ, ZW(YJ) - 3), 20, 14, nf, "panel rail")
    if os.environ.get("AG_ATTIC_LOG"): json.dump({"opt": ATT, "beams": ATT_LOG, "ymeet": ymeet, "YJ": YJ}, open(os.environ["AG_ATTIC_LOG"], "w"))
    for yy in ((166, 230, 294, 358) if ATT != 2 else ()):     # the cross gable's rafters, from each valley to its ridge
        xv_ = CGc - (ZCR - (WZR - 18 - (WYR - yy) * TW)) / TC
        for sx_ in (-1, 1):
            x0_ = CGc + sx_ * (CGc - xv_)
            beam((x0_, yy, ZC(x0_) - 2), (CGc, yy, ZCR - 20), 12, 16, Vector((-sx_ * TC, 0, -1)).normalized())
    box("stone", (1068, 665, ZA - 2), (1136, 755, ZW(665) + 40))   # the chimney, through the attic and out
    # the bunks since the fit-out (the walk of 2026-10-26: the 2 bunks before the dormers removed, homely furniture
    # added as in Jorrvaskr's bunk room): eight, heads under the eaves (their pillows at local -y), paired round
    # nightstands, a chest at each foot; a table with three chairs by the stair's door and a seat in each dormer. Then
    # Jorrvaskr's bunk room as measured (WhiterunJorrvaskrBasement): its runner down the aisle, horn chandeliers over it,
    # its candle sconces (at 1.7) with its shields and a banner on the end wall, a dresser and a cupboard where the roof
    # is high enough (78 and 167), baskets, firewood by the chimney
    # (each bunk and chest named for the NPC build, AGHallBunk1-8 / AGHallChestBunk1-8; 6-8 the guild's, for the player and
    # the members: the NPC session, 2026-10-27)
    # (2026-10-27: the free bunks were all at the far end, so the near one is free too: the bunk inside the
    # door, by the dormer, is the guild's (6) and Ghrulek's (1) is the back row's at 1210, by the nightstand there, his
    # things moved to it; a nightstand of his own by 912 cut off a pocket under the eave, the furniture check)
    BUNK_ = iter((6, 2, 3, 4, 5, 7, 1, 8))
    BDY_ = {}
    # (AG_ATTIC: the headboard's corner posts, 95.5 tall at local x +-40..48, stand 2 under the boards at the eave: bunk 1000's left one was
    # under where dormer 881's right trimmer runs, 1330's right one under the valley: 1000 6 toward the dormer, its post in the bay; 1330 20 in)
    # (2026-11-03, the known faults, by the meshes against the rafters, which are 12 thick every 64 (rafter3..5.py): a bunk
    # clears only where both posts fall between rafters; 737 is the front row's one such place clear of the dormer at 808)
    for x_ in (737, 1000 - (6 if ATT else 0), 1142, 1330 - (20 if ATT == 1 else 0)):   # under the front eave (2 in from it since the clip check: the
                                                              # headboards grazed it) (none before the dormers: x 498..644, 808..954)
        n_ = next(BUNK_); own_ = {"owner": "guild"} if n_ >= 6 else {}
        piece("meshes/clutter/upperclass/upperbedsingle01.nif", "UpperBedSingle01", (x_, 250 + 95 + BDY_.get(x_, 0), ZA), 0, name=f"AGHallBunk{n_}", **own_)   # (its
        piece("meshes/clutter/upperclass/upperchest01.nif", "AGHall2Chest", (x_, 464, ZA), 0, name=f"AGHallChestBunk{n_}", **own_)       # headboard clears the eave)
    # (1382 since the walk of 2026-11-01: Ghrulek could not get round his trunk and the chimney stack to his bed: at 1360 the 45 between bunks 1 and 8 held no mesh, and neither bunk could be reached from a long side; at 1370 the mesh between them was 24 wide: nav_routes.py's bed sides, 36 needed)
    # (2026-11-03, the known faults: the headboard posts of four bunks rose ~15 into a rafter, 784, 913 and 1383 here (the
    # box gate saw only the last), measured by mesh; each moved to the nearest place clear of every rafter)
    for x_ in (780, 903, 1210, 1397):                         # and under the back eave (the tower and the chimney between; the
                                                              # first 14 off the tower's wall since the clip check)
        n_ = next(BUNK_); own_ = {"owner": "guild"} if n_ >= 6 else {}
        piece("meshes/clutter/upperclass/upperbedsingle01.nif", "UpperBedSingle01", (x_, 814 - 95, ZA), 180, name=f"AGHallBunk{n_}", **own_)
        piece("meshes/clutter/upperclass/upperchest01.nif", "AGHall2Chest", (x_, 600, ZA), 180, name=f"AGHallChestBunk{n_}", **own_)
    for x_, y_, a_ in ((1071, 270, 0), (1100, 790, 180)):
        piece("meshes/clutter/upperclass/uppernightstand01.nif", "UpperNightstand01", (x_, y_, ZA), a_)
    piece("meshes/clutter/upperclass/uppertableround01.nif", "UpperTableRound01", (520, 480, ZA), 0)
    for x_, y_, a_ in ((520, 410, 0), (520, 550, 180), (450, 480, 90)):     # (side-entry, 70 out: 2026-11-07, NPCs stood up onto the tables)
        piece("meshes/clutter/upperclass/upperchair01.nif", "UpperChair01LR", (x_, y_, ZA), a_)
    # one seat in a dormer, pulled back from it and turned a little (2026-10-26: one in each looked fake, perfectly
    # aligned, so one went and the other is angled slightly)
    piece("meshes/clutter/upperclass/upperchair01.nif", "UpperChair01F", (565, 260, ZA), 194, exact=True)
    RS = 0.62                                                 # the runner, 95 wide in the 110 between the chests: two lengths
    xr_ = 615 + 81.6 * RS + 256 * RS                          # and its ends (Jorrvaskr's own pieces), x 615..1446
    for k_ in (0, 1):
        piece("meshes/architecture/whiterun/wrclutter/wrjorrvaskrrugstr01.nif", "WRJorrvaskrRugStr01", (xr_ + 512 * RS * k_, WYR, ZA + 0.3), 0, RS)
    piece("meshes/architecture/whiterun/wrclutter/wrjorrvaskrrugendl01.nif", "WRJorrvaskrRugEndL01", (xr_ - 256 * RS, WYR, ZA), 0, RS)
    piece("meshes/architecture/whiterun/wrclutter/wrjorrvaskrrugendr01.nif", "WRJorrvaskrRugEndR01", (xr_ + 768 * RS, WYR, ZA), 0, RS)
    # the chandeliers over the aisle, their chains' tops on the ridge beam's underside (WZR - 60, 368 over the floor): since
    # the hall2bd walk's rule (hang_check.py), the long chain at 0.65 (Pinewatch's, vanilla's smallest), its horns 206 over
    # the aisle and 162 under the beam (on CandleHornChandelier02's 50 rope until then they sat against it)
    for x_ in (851, 1210):
        piece("meshes/clutter/candles/candlehornchandelier01.nif", "CandleHornChandelier01", (x_, WYR, WZR - 60 - 220 * 0.65), 0, 0.65)
        NEW_LIGHTS.append((x_, WYR, ZA + 230, 1.2e6, (1.0, 0.78, 0.55), "lamp"))   # (under them: a candle's 256 from up there
                                                                                  # would not reach the floor)
    # the walls: the outer end (x 1452) shield, sconce, banner, sconce, shield; a sconce over the table on the hall's wall and
    # one over the dresser on the cross gable's gable. A sconce faces its local -x, its plate at +1.5 (scaled); a shield faces
    # its local -x, its back at 0; the banner hangs 19..28 along its local -y from its origin, on the wall
    # (2026-11-03, the known faults: the end wall's two sat ~3 into the shields' rims, seen in a screenshot: each 6 further from its shield)
    for x_, y_, n_ in ((1452, 482, (-1, 0)), (1452, 582, (-1, 0)), (416, 400, (1, 0))) + (((CGc, 134, (0, 1)),) if ATT != 2 else ()):
        z_ = ZA + (170 if n_[1] else 150)
        piece("meshes/clutter/imperial/impwallsconcecandle01.nif", "ImpWallSconceCandle01", (x_ + 2 * n_[0], y_ + 2 * n_[1], z_),
              math.degrees(math.atan2(n_[1], -n_[0])) % 360, 1.7)
        # (the walk: only one of these seemed to give light: the pair on the end wall, 112 apart, share one light between them, on the banner)
        if x_ != 1452: NEW_LIGHTS.append((x_ + 26 * n_[0], y_ + 26 * n_[1], z_ + 30, 1.0e6, (1.0, 0.7, 0.42), "candle"))
    NEW_LIGHTS.append((1426, 532, ZA + 180, 1.0e6, (1.0, 0.7, 0.42), "candle", 64, 0.0))
    for y_, ed_ in ((420, "WRIntShield05"), (644, "WRIntShield06")):
        piece(f"meshes/architecture/whiterun/wrclutter/{ed_.lower()}.nif", ed_, (XE - 0.5, y_, ZA + 160), 0)
    # (Jorrvaskr's banner stood between them until 2026-11-02: it breaks the lore in the Guild's own hall)
    # (the dresser in the cross gable clipped its windows: dropped after the hall2u walk, 2026-10-26)
    piece("meshes/clutter/upperclass/uppercupboard01.nif", "UpperCupboard01", (XU + TT + 28, 664, ZA), 270)   # (its doors, local -y, to the room)
    piece("meshes/clutter/basket02.nif", "Basket02", (XU + TT + 22, 572, ZA), 20)
    piece("meshes/clutter/basketclosed01.nif", "BasketClosed01", (1160, 166, ZA) if ATT != 2 else (895, 228, ZA), 35)
    piece("meshes/clutter/firewood/firewoodpilesmall01.nif", "FirewoodPileSmall01", (1102, 630, ZA), 0)   # (before the chimney)
    # the clutter pass (2026-10-27): dressed as Jorrvaskr's bunk room is (research/gmrooms/WhiterunJorrvaskrBasement: cups
    # and goblets on the tables between its bunks, a book or two, a drum; its round table a candle, food and goblets; its
    # cupboard stocked with wine, mead, goblets and a stack of plates; nothing on its chests, which open). Nightstands
    # (top 30, x +-17.3, y +-15.4) for the two residents whose bunks stand alone: Ghrulek's (bunk 1) on its dormer side,
    # Marius's (bunk 4) toward the end wall; the residents' things are theirs (the export's bunk groups: a nightstand by
    # nearness, its things named here), the rest the guild's (the NPC session's bios: Ghrulek buys the rounds and sends
    # half home, Ylva says little, Zhasim sells the Guild its caves, Marius was the Great War company's sergeant)
    NZ = ZA + 30
    piece("meshes/clutter/upperclass/uppernightstand01.nif", "UpperNightstand01", (810, 270, ZA), 0)        # the guild's bunk's
    # (the horn candles here and below: 37 long, so along the nightstands' long side (34) give or take a little; neighbours
    # point opposite ways (base), and each one's turn and place come from the seed, so none sits square or like the next)
    ha_ = random.Random("attic horns")
    def horn(x, y, z, base=90, spread=10, **kw):
        sit("meshes/clutter/candles/candlehorntable01.nif", "CandleHornTable01", x + ha_.uniform(-1.5, 1.5), y + ha_.uniform(-1.5, 1.5), z,
            base + ha_.uniform(-spread, spread), **kw)
    horn(810, 268, NZ, base=270)                                                                          # (a candle, for whoever)
    # (2026-11-03: 7 along with its bunk, now at 737 off the rafters, whose mesh reaches 788: it stood 4..7 into the headboard)
    sit("meshes/clutter/ingredients/mead01.nif", "Ale", 1093, 781, NZ, 0, group="bunk1")                  # Ghrulek's, on the
    sit("meshes/clutter/common/flagon01.nif", "Flagon", 1107, 779, NZ, 220, group="bunk1")              # back row's (his flagon, the lived-in pass)
                                                                                                         # nightstand by his bunk at 1210
    horn(1071, 262, NZ, spread=5)                                                                         # Ylva's and Zhasim's
    sit("meshes/clutter/glazedcup01.nif", "GlazedCup01", 1074, 279, NZ, 0, group="bunk2")
    piece("meshes/clutter/upperclass/uppernightstand01.nif", "UpperNightstand01", (1407, 270, ZA), 0)       # Marius's
    sit("meshes/clutter/books/basicbook01.nif", "Book1CheapBriefHistoryoftheEmpirev1", 1399, 270, NZ, 5, group="bunk4")
    # (the lived-in pass, 2026-11-17) the residents' own: Marius's Legion helmet, kept polished and set dead straight (his goblet gave
    # way to it); Ylva's sabre cat tooth (the beast she is still hunting) and Zhasim's lockpicks (he pretends he doesn't) on their
    # shared nightstand, each on their own side; Ghrulek's keg under the back eave by his nightstand, its spout to the room;
    # Cassius's brandy from Bruma on the floor by his bunk's head (his bunk has no nightstand); a fur over the foot of Ylva's bunk
    piece("meshes/armor/imperial/helmetfullfacegnd.nif", "ArmorImperialHelmet", (1416, 270, NZ + 0.15), 0, group="bunk4", owner="guild", settled=True, square=True)
    sit("meshes/clutter/ingredients/sabrecattooth.nif", "SabrecatTooth", 1060, 276, NZ, 38, group="bunk2")
    sit("meshes/clutter/common/lockpick.nif", "Lockpick", 1083, 268, NZ, 61, group="bunk3")
    sit("meshes/clutter/common/lockpick.nif", "Lockpick", 1084, 271, NZ + 1.0, 74, group="bunk3")
    piece("meshes/clutter/meadery/meadbarrel01.nif", "MeadBarrel01", (1060, 795, ZA), 0, group="bunk1")
    sit("meshes/clutter/wine/winebottle02a.nif", "WEDL03CyrodilicBrandy", 842, 798, ZA, 0, group="bunk5")
    horn(1100, 799, NZ, base=270, spread=6)                                                               # (Ghrulek's nightstand's
                                                                                                         # candle, at its back)
    # the round table (top 62.2, radius 39; its chairs at -y, +y and -x): a candle, the flagon and two cups, bread on a
    # plate; Zhasim's Explorer's Guide and a rolled map on the aisle side
    TZ = ZA + 62.2
    horn(512, 480, TZ, base=300, spread=15)                                                               # (the round table's: room all round)
    sit("meshes/clutter/common/flagon01.nif", "Flagon", 503, 461, TZ, 20)
    sit("meshes/clutter/glazedcup01.nif", "GlazedCup01", 488, 474, TZ, 0)
    sit("meshes/clutter/glazedcup01.nif", "GlazedCup01", 546, 494, TZ, 0)
    sit("meshes/clutter/dining set/basicwoodenplate01.nif", "BasicWoodenPlate01", 515, 506, TZ, 0)
    sit("meshes/clutter/food/bread01a.nif", "FoodBread01A", 515, 506, TZ + 4.0, 10)
    sit("meshes/clutter/books/basicbook04a.nif", "Book2CommonExplorersGuideToSkyrim", 547, 472, TZ, 100, group="bunk3")
    sit("meshes/clutter/quest/tgparchment01.nif", "PaperRoll", 522, 448, TZ, 4, group="bunk3")
    # the cupboard (UpperCupboard01 at (444, 664) turned 270: the hall's x = 444 - its y, y = 664 + its x; its counter 62
    # within x +-67, y +-27 under the open shelf at 107 (y -18.7..20.1), its top 151.7): wine and mead and a glazed pot
    # on the counter, goblets and a stack of plates on the shelf, a jug on top
    CZ = ZA + 62
    strew((458, 600), (458, 684), CZ, (("meshes/clutter/wine/winebottle02b.nif", "FoodWineBottle02", 1), ("meshes/clutter/ingredients/mead01.nif", "Ale", 2)),
          "attic cupboard 62", depth=4)
    sit("meshes/clutter/glazedpot02.nif", "GlazedPot02", 452, 704, CZ, 0)
    strew((444, 604), (444, 670), ZA + 107, (("meshes/clutter/glazedgoblet01.nif", "GlazedGoblet01", 2),), "attic cupboard 107", depth=7, lie=0.3)
    pile("meshes/clutter/silver/silverplate01.nif", "SilverPlate01", 444, 694, ZA + 107, 3, "attic plates", step=0.7)
    sit("meshes/clutter/glazedjugsmall01.nif", "GlazedJugSmall01", 444, 699, ZA + 151.7 + 1.6, 0)
    PLAN.append({"t": "room", "level": 2, "name": "attic", "r": [XU + TT, WF, XE, WB], "z": ZA})

if HEARTH:
    # the clutter pass's last rooms (2026-10-27: the great hall gets a waiting bench or two, the galleries
    # and the lobby their walls only). The great hall: vanilla's upper-class bench (174 long, its back at local -y, its seat 30)
    # in the left front bay, its back to the wall, where members wait (the front windows' bays, 81 between banner and wall,
    # are too short for it; the right front bay is the bear's), a pack by its end and a tankard on it (no shields or
    # trophies on the hall's walls: they did not fit, the hall2ab walk).
    # The galleries' walls (Jorrvaskr's banners on the side galleries' outer walls until 2026-11-02, then removed): the map of Skyrim on the front
    # gallery's (the library's wall, left of its door); the lobby's long wall a map
    piece("meshes/clutter/upperclass/upperbench01.nif", "UpperBench01", (-XG + 26, 170, 0), 90, exact=True)
    # the lost and found: vanilla's open crate (CommonCrate02: 73 x 46, its floor at 12, x -30..30, y -13..20, its walls to
    # 26..31) pushed into the front right corner, its back to the side wall and its end by the front wall, filling the nook
    # between the bear and the front wall (the crate under the window left that nook a dead end through a 64 gap: the pinch
    # gate); in it a helmet and a pair of gauntlets, side by side on its floor; the shield (44 across, the crate's inside
    # 33) stood on the floor against the crate's long side, leaning on its rim, its face to the hall
    lf_ = random.Random("lost and found"); LFX, LFY, LFA = 340 - 19.4 - 3, 40 + 36.6 + 4, 270 + 3 + lf_.uniform(0, 2)
    def lf_at(lx, ly):                                       # (the crate's frame to the hall's: yaw clockwise)
        c_, s_ = math.cos(math.radians(LFA)), math.sin(math.radians(LFA))
        return LFX + lx * c_ + ly * s_, LFY - lx * s_ + ly * c_
    piece("meshes/clutter/common/commoncrate02.nif", "CommonCrate02", (LFX, LFY, 0), LFA, exact=True)
    sit("meshes/armor/iron/male/helmetgnd.nif", "ArmorIronHelmet", *lf_at(-12.5, 3.5), 12, LFA + lf_.uniform(-3, 3))
    sit("meshes/armor/iron/male/gauntletsgnd.nif", "ArmorIronGauntlets", *lf_at(17.5, 3.5), 12, LFA + lf_.uniform(-3, 3))
    # (tilted 75: its back touches the long side's rim (y 24.1, 26 up) 7.2 behind its origin)
    sit("meshes/armor/hide/hideshield.nif", "ArmorHideShield", *lf_at(-4, 24.1 + 0.3 + 7.2), 0, LFA + lf_.uniform(-4, 4), rx=75)
    sit("meshes/clutter/containers/miscsack02small.nif", "MiscSack02Small", -XG + 22, 272, 0, 15)
    sit("meshes/clutter/dining set/basictankard01.nif", "BasicTankard01", -XG + 30, 104, 30, 70)
    # (no sconces on the piers: each carries a gallery bracket's leg and turned pendant down its face to 160, and the pier is
    # too narrow beside them; the clip check, hall2ax)
    # (2026-11-02: one on each side of the gallery) the guild's banner where Jorrvaskr's hung, 160 x 44, its own loop each, moving as the holds' do: banner_nif.py; its bracket under the wall's rail (over it, the gate: 35 into the timber)
    for x_, yb_, yaw_, v_ in ((-391.5, 466, 270, "E"), (391.5, 394, 90, "F")):   # (rays over the walls, every 4: panels at 392, posts 9 proud, not opposite each other: each the middle of its own bay)
        piece(f"meshes/adventurersguild/hall2/aghall2banner160{v_.lower()}.nif", "AGHall2Banner160" + v_, (x_, yb_, ZG + 212), yaw_, exact=True)
    wall_painting(-100, OFF1, 1, ZG + 165, "painting2", 0.72)   # (the hall from the stair's foot; paintings, not maps,
    wall_painting(560, 600, 1, ZG + 143, "painting1", 0.72)    # here: the maps stay by the counter and in the GM's office) (the walk of 2026-11-06: 22 lower, its frame 27.5 under the timber above as the library one is under its beam)
    # (the lobby's two round shields beside its map dropped, as the pair read badly; the map alone)

# windows: every exterior window of the pavilion and of the wings' ground floors, from inside
STAFF_WIN = {290: Y34 - 61, 540: Y45 - 61, 790: 720} if HEARTH else {}   # (the staff rooms' end-wall windows inside, onto the beds, 2026-11-06)
for op in OPENINGS:
    if op["kind"] not in ("arched", "leaded", "grid", "small", "gothic") + (("door leaf",) if HEARTH else ()) + (("fan",) if FAN_IN else ()): continue   # (W: and
                                                              # the office's balcony door, its two glazed leaves, shut, as outside)
    if op["kind"] == "door leaf": op = dict(op, kind="panes")
    w_ = op["what"]
    n_ = op["n"]
    if w_.startswith("pavilion"):
        grd = "ground" in w_
        if abs(n_[1]) > 0.5: window_inside(op, (YF if grd else YFU) if n_[1] < 0 else (YB if grd else YBU))
        else: window_inside(op, (XG if grd else XU) * (1 if n_[0] > 0 else -1))
    elif w_.startswith("wing") and " ground " in w_ and "cross gable" not in w_:
        if abs(n_[1]) > 0.5: window_inside(op, 210 if n_[1] < 0 else 890)
        else: window_inside(op, (PX1 + 1060 - TS) * (1 if n_[0] > 0 else -1))
    elif TOWER_STAIR and w_.startswith("tower"):              # the tower's: two lighting the stair, four in the lookout
        look_ = HEARTH and min(p[2] for p in op["c"]) >= ZLK  # (W: the lookout's go to its own cell, with their fill lights)
        if look_: PART = "lookout"
        pl_ = {(1, 0): TU[2], (0, 1): TU[3], (0, -1): TU[1], (-1, 0): TL[0]}[(round(n_[0]), round(n_[1]))]
        window_inside(op, pl_)
        # (a door's timbers and a sill stood round these while they were pictures on the wall; the walk of 2026-11-01: that frame removed: a real window has its own)
        if look_: LOOK_LIGHTS.append(INT_LIGHTS.pop()); PART = "interior"
    elif TAVERN_OPEN and (w_.startswith("wing L upper") or w_.startswith("dormer x-")) and min(p[0] for p in op["c"]) > WX0:
        window_inside(op, 164 if w_.startswith("dormer") else (WF if n_[1] < 0 else WB))   # the tavern's: its galleries' and the dormers'
    elif HEARTH and "cross gable ground" in w_:               # W, the working rooms (2026-10-26): the bays' (the kitchen's, the
        window_inside(op, 186)                                # backroom's)
    elif HEARTH and (w_.startswith("wing L upper") or (w_.startswith("wing L cross gable upper") and op["kind"] == "grid")):
        if abs(n_[1]) > 0.5: window_inside(op, 134 if "cross gable" in w_ else (WF if n_[1] < 0 else WB))   # the guild master's rooms
        else: window_inside(op, -1452)                        # (the gable's two small ones light the closed roof over them)
    elif HEARTH and (w_.startswith("wing R upper") or w_.startswith("wing R cross gable upper") or
                     (w_.startswith("dormer x") and not w_.startswith("dormer x-"))):   # the staff quarters' and the attic's
        if w_.startswith("dormer"): window_inside(op, 164)
        elif abs(n_[1]) > 0.5:
            if not (int(os.environ.get("AG_ATTIC", "1")) == 2 and "cross gable" in w_ and min(p[2] for p in op["c"]) >= T1): window_inside(op, 134 if "cross gable" in w_ else (WF if n_[1] < 0 else WB))
        else:   # (plan D, 2026-11-06: rooms 3 and 4's windows centred on the beds) moved inside only
            yc_ = sum(c_[1] for c_ in op["c"]) / 4; dy_ = STAFF_WIN.get(round(yc_), yc_) - yc_
            window_inside(dict(op, c=[[c_[0], c_[1] + dy_, c_[2]] for c_ in op["c"]]) if abs(dy_) > 0.01 else op, 1452)

PLACE = [("meshes/architecture/solitude/doors/sdoubledoorint01.nif", (0, YF + 2, 0), 180, DSC)]
if HEARTH:   # W: the front doors' frame inside (after the hall2t walk, 2026-10-26): two
             # posts and a lintel, clear of the doors' leaves (vanilla's 182 x 175, here 1.3: 237 x 228)
    WFr = RW["front"][0]
    # (2026-11-14: the outside already has a fanlight over the door, and the slatted transom of 2026-11-13 filled that
    # space, which the interior never had. From the rendered options, front_door_fanlight_options.png:
    # the transom removed; the fanlight 11 lower than outside (FAN_DZ), clear of the joists' ledge along this wall (ZG - 46), the
    # lintel under it 19 tall instead of 30; the posts on up beside it to the ledge, with a thin piece at the top about as
    # far over the window as the lintel is under it: a rail between the posts as far over the fanlight's frame as the lintel is
    # under it (4.8), up into the ledge's underside, 3.8 of it showing). 2026-11-14, seen in game, the side and top trim did
    # not look right and came off: the posts stop at the lintel's top again and the rail is gone; the fanlight sits in the plaster
    LH_ = 30 + FAN_DZ                                          # the lintel's height, under the fanlight
    FZ_ = [min(p_[2] for p_ in op_["c"]) for op_ in OPENINGS if op_["kind"] == "fan"] if FAN_IN else []
    for sx in (-1, 1): wall_beam(WFr, (XG - sx * (DOOR_HW + 10.5), 0), (XG - sx * (DOOR_HW + 10.5), DOOR_TOP + LH_), w=21, deep=12)
    wall_beam(WFr, (XG - DOOR_HW - 21, DOOR_TOP + LH_ / 2), (XG + DOOR_HW + 21, DOOR_TOP + LH_ / 2), w=LH_, deep=14)
    if FZ_:
        fop_ = next(op_ for op_ in OPENINGS if op_["kind"] == "fan")
        fz0_, fz1_ = min(p_[2] for p_ in fop_["c"]) + FAN_DZ, max(p_[2] for p_ in fop_["c"]) + FAN_DZ   # its frame's foot and crown, inside
        print("FANLIGHT inside", round(fz0_, 1), round(fz1_, 1), "lintel top", round(DOOR_TOP + LH_, 1), "gap", round(fz0_ - (DOOR_TOP + LH_), 1))
    PLAN.append({"t": "frame", "level": 0, "a": [-DOOR_HW - 21, YF], "b": [DOOR_HW + 21, YF]})
if HEARTH:   # W: the hearth's fire (vanilla FireplaceWood01Burning); the tower's: its sconces and its ladder (a load door, with
             # where one arriving through it stands: role, arrive). (The dragon's skull on the hood went in the fit-out,
             # 2026-10-26: the shield rack on the breast took its place, with the hearth above)
    PLACE += TOWER_PLACE
    if os.environ.get("AG_GREAT_HEARTH", "castle") != "castle": PLACE += [("meshes/clutter/woodfires/fireplacewood01burning.nif", (0, YB - 50, DAIS), 0,
               1.2 if os.environ.get("AG_GREAT_HEARTH", "castle") == "castle" else 0.75)]   # (the castle hearth's grate: 296)
if HEARTH:   # W: palette 2's woods where they make sense (after the palette study, 2026-10-26: mostly palette 1, with
             # palette 2's woods mixed in for variety only where they make sense): the nailed boards and beam
             # in the working rooms (kitchen, backroom), the attic and the lookout; the boards on the staff rooms' floors.
             # By where a face's middle lies (a room's outline 3 out, so its own wall faces come along, never the next room's)
    def rekey(part_, key_from, key_to, inside):
        src_ = GEO.get((part_, key_from), [])
        keep_, moved_, remap_ = [], [], {}
        for i_, f_ in enumerate(src_):
            c_ = sum(f_[0], Vector()) / len(f_[0])
            if inside(c_): remap_[i_] = (key_to, len(GEO.get((part_, key_to), [])) + len(moved_)); moved_.append(f_)
            else: remap_[i_] = (key_from, len(keep_)); keep_.append(f_)
        if not moved_: return 0
        GEO[(part_, key_from)] = keep_; GEO.setdefault((part_, key_to), []).extend(moved_)
        old_ = {t_ for t_ in NOCOLL_IDS if t_[0] == part_ and t_[1] == key_from}   # (re-indexed all at once: one by one, a
        NOCOLL_IDS.difference_update(old_)                                        # new index could meet an old one)
        NOCOLL_IDS.update((part_,) + remap_[t_[2]] for t_ in old_)
        return len(moved_)
    def in_rects(rects, z0_, z1_):
        return lambda c_: z0_ <= c_.z < z1_ and any(r_[0] - 3 <= c_.x <= r_[2] + 3 and r_[1] - 3 <= c_.y <= r_[3] + 3 for r_ in rects)
    WORK = [(-1400, 186, -1100, 890), (BRF, 186, 1400, 890)]                       # the kitchen and storage, the backroom
    STAFF = [(416, 158, 760, 366), (416, 378, 760, 588), (1072, 134, 1452, 374), (1072, 386, 1452, 630), (1072, 642, 1452, 906),
             (416, 600, 1060, 732), (720, 732, 1060, 906)]                          # rooms 6, 7, 3, 4, 5 and their corridors
    ATTIC = [(416, 158, 1452, 906)]
    n_ = 0
    for kf_, kt_ in (("planks", "planks2"), ("wood", "wood2")):
        n_ += rekey("interior", kf_, kt_, in_rects(WORK, -100, ZG - 10))
        n_ += rekey("interior", kf_, kt_, in_rects(ATTIC, ZA - 10, 5000))
        n_ += rekey("lookout", kf_, kt_, lambda c_: True)
    n_ += rekey("interior", "planks", "planks2", in_rects(STAFF, ZG - 10, ZA - 10))
    print("PALETTE 2 woods:", n_, "faces")
INT_LIGHTS += NEW_LIGHTS    # (2026-10-26) the working rooms' lamps and pieces after everything the last build had: Hall2.cs
# (2026-10-30: lights with no visible source can misbehave under lighting mods, and the upstairs hall's white-out had
# no source to see) a light has a fixture: a lit chandelier hard up to the ceiling at each of the rooms' lamps that had none.
# Its own candle light goes: the lamp is the room's
if HEARTH:
    # (2026-10-30, the walk of hall2bz: this fixture broke the chandelier height rule and stood in the way: a ceiling of 238 leaves a
    # hanging fixture 159 over the floor, and the rule is 200 unless it hangs over furniture) these only, over a table, a desk, a bed; the rest of the low rooms on the walls
    # (2026-11-03, the known faults: the office desk turned round sits 37 nearer its wall, x -1350..-1288, and the office's
    # fixture with its lamp went with it, from -1270 over the floor to -1310 over the desk, toward the room's side of it)
    for x_, y_, top_ in ((916, 373, 656), (-1310, 380, 656), (-1290, 800, 656)):
        chandelier(x_, y_, ZG + 190, top_, low=True); INT_LIGHTS.pop()
    # (2026-11-02) the Landing's: off its front wall by the door, where it flipped with SSGI; not spot A, along that wall (the painting hangs there, so A
    # was rejected), but C of four on a plan, the wall behind the strip, across from the painting (unproven against the flip).
    # (2026-11-03, C flipped too; through the textures session, moved off the failing spot to location A, the wall
    # facing room 5: the wing's left wall, mid-face and mid-height, out of the strip)
    for x_, y_, z_, n_, l_ in ((720, 819, ZG + 150, (1, 0), 300), (416, 483, ZG + 150, (1, 0), 200), (1394, 906, ZG + 150, (0, -1), 200)):   # (room 3's, at (1230, 143), went 2026-11-17: it stood on the window)   # (room 5's: the test walk of 2026-11-06, it blocked the way along the far side of the bed: option A, the back wall over the chest)   # (plan D: rooms 3 and 5's along their front walls, 130 from their windows' daylight)
        wall_sconce(x_, y_, z_, n_, l_)
    # the kitchen's, off the wall and out of the corner (the walk: wrong both in height and in nearness to a wall): over the middle of its floor, 150 tall, clear of a head
    piece("meshes/clutter/candles/candlehornchandelier01.nif", "CandleHornChandelier01", (-1250, 470, 400 - 220 * 0.6), 0, 0.6, exact=True)
    INT_LIGHTS.append((-1250, 470, 400 - 220 * 0.6 + 10, 1.2e6, (1.0, 0.78, 0.55), "candle", 128, 0.0))
# (the walk of 2026-10-28: the kitchen far too bright, lit through its ceiling by the fire and the two fills of the
# guild master's rooms over it) a light passes through floors, so one in an upper room is trimmed in place, as vanilla
# trims its own (the reference's radius offset: Breezehome's hearth at -322), to reach no more than 60 below its floor.
# The kinds' records' radii (Hall2.cs); candles (128) and the windows' daylight left as they are
BASE_R = {"lamp": 512, "fire_small": 512, "fire": 768}
UPPER_ROOMS = [(i_["r"], i_.get("z", ZG)) for i_ in PLAN if i_["t"] == "room" and i_.get("level", 0) >= 1]
for k_, l_ in enumerate(INT_LIGHTS):
    x_, y_, z_, w_, c_, *rest_ = l_
    if not rest_ or rest_[0] not in BASE_R or len(rest_) > 1: continue
    floors_ = [f_ for r_, f_ in UPPER_ROOMS if r_[0] <= x_ <= r_[2] and r_[1] <= y_ <= r_[3] and f_ <= z_]
    if not floors_: continue
    reach_ = max(160, z_ - max(floors_) + 60)
    if reach_ < BASE_R[rest_[0]]: INT_LIGHTS[k_] = (x_, y_, z_, w_, c_, rest_[0], reach_ - BASE_R[rest_[0]], 0.0)
print("LIGHTS trimmed to their floors:", sum(1 for l_ in INT_LIGHTS if len(l_) > 6))
# (2026-11-02) the big rooms' soft daylight, deeper in than the fills reach, as Lux's DefaultSunBounce (r500, a median 464 from a window): it has no fixture, against the light
# placement rule, and counts as the windows' daylight. Only where the room stands open to its full height: in the low rooms 500 would come through the floors (light rule 5). Hall frame
INT_LIGHTS += [(0, 500, 300, 2.0e5, (0.77, 0.77, 0.77), "bounce"), (-640, 531, 360, 2.0e5, (0.77, 0.77, 0.77), "bounce")]   # the great hall, the tavern
# (2026-10-30, a white-out in the tavern, from a candle under a window adding to its daylight) a candle within 130 of a window's daylight comes up at dusk and is black by
# day (candle_night: Hall2.cs, vanilla's inverted region); dropping them outright left flames that lit nothing after dark
fills_ = [l_ for l_ in INT_LIGHTS if len(l_) > 5 and l_[5] == "window"]
n_night_ = 0
for k_, l_ in enumerate(INT_LIGHTS):
    if len(l_) > 5 and l_[5] in ("candle", "candle_small") and any(math.dist(l_[:3], f_[:3]) < 130 for f_ in fills_):
        INT_LIGHTS[k_] = l_[:5] + ("candle_night",) + tuple(l_[6:]); n_night_ += 1
print("LIGHTS by a window: at night only:", n_night_)
def tavern_panelling():
    """(AG_TAVERN_PANEL=0 turns it off; 2026-11-12: wood panelling in the tavern only, finer and properly built in,
    then from two reference photos: a frame of stiles and rails with recessed panels, thin and in the same wood
    as the bar's top, low contrast: dark, thick frames read too heavy, and the table and bar tops have the right wood
    tone): the tavern's plaster walls panelled up to the cap rail, framed and panelled as a joiner builds it.
    Every plaster face on the tavern's four wall planes is cut at the cap's top: above stays plaster, below becomes the panels'
    field (vertical boards, flush in the wall's plane, so nothing sits in front of the plaster's old line). On the field, through
    the baseboard solver (mitred at the corners, stopped at the arches, the niche and the fireplace): a skirting, a top rail and
    a cap; between skirting and top rail, stiles about a panel apart, spaced evenly in each run. The trim stands 1.5 to 3 proud
    and is drawn without collision: the navmesh, and so the walkways, are the same as the plaster's."""
    ZC_, BAND_S, BAND_R, BAND_C = 86.0, (-0.5, 12.0), (72.0, 78.0), (78.0, 86.0)
    field_ = os.environ.get("AG_TAVERN_PANEL_FIELD", "planks")
    X0_, X1_, Y0_, Y1_ = -1060.0, -380.0, 210.0, 890.0           # the tavern's walls (hall frame): the partition's tavern face, the pavilion's
    planes_ = [("x", X0_, Vector((1, 0, 0))), ("x", X1_, Vector((-1, 0, 0))), ("y", Y0_, Vector((0, 1, 0))), ("y", Y1_, Vector((0, -1, 0)))]
    runs_ = {i_: [] for i_ in range(4)}
    n_cut = 0
    def cut(P_, U_, k_, v_, keep_ge):
        """the part of polygon P_ (uvs U_) with coordinate k_ >= v_ (keep_ge) or <= v_"""
        out_, ouv_ = [], []
        for j_ in range(len(P_)):
            a_, b_ = P_[j_ - 1], P_[j_]; ua_, ub_ = Vector(U_[j_ - 1]), Vector(U_[j_])
            ina_ = (a_[k_] >= v_) if keep_ge else (a_[k_] <= v_); inb_ = (b_[k_] >= v_) if keep_ge else (b_[k_] <= v_)
            if ina_ != inb_:
                t_ = (v_ - a_[k_]) / (b_[k_] - a_[k_]); out_.append(a_ + (b_ - a_) * t_); ouv_.append(tuple(ua_ + (ub_ - ua_) * t_))
            if inb_: out_.append(b_); ouv_.append(tuple(ub_))
        return out_, ouv_
    for gk_ in [k_ for k_ in GEO if k_[0] == PART and k_[1] in ("stucco",)]:
        keep_ = []
        for pts_, uvs_ in GEO[gk_]:
            P_ = [Vector(q_) for q_ in pts_]
            hit_ = None
            for i_, (ax_, c_, n_) in enumerate(planes_):
                k_ = 0 if ax_ == "x" else 1
                if all(abs(q_[k_] - c_) < 0.6 for q_ in P_):
                    o_ = 1 - k_; lo_, hi_ = ((Y0_, Y1_) if ax_ == "x" else (X0_, X1_))
                    if max(q_[o_] for q_ in P_) > lo_ + 0.6 and min(q_[o_] for q_ in P_) < hi_ - 0.6:
                        nn_ = Vector((0, 0, 0))
                        for j_ in range(len(P_)): nn_ += P_[j_ - 1].cross(P_[j_])
                        if nn_.dot(n_) > 0: hit_ = (i_, o_, lo_, hi_)
            if hit_ is None or min(q_.z for q_ in P_) >= ZC_ - 0.01:
                keep_.append((pts_, uvs_)); continue
            i_, o_, lo_, hi_ = hit_
            # the parts beyond the tavern's ends stay as they are
            for v_, ge_ in ((lo_, False), (hi_, True)):
                q_, qu_ = cut(P_, uvs_, o_, v_, ge_)
                if len(q_) >= 3 and max(abs(x_[o_] - v_) for x_ in q_) > 0.3: keep_.append(([tuple(x_) for x_ in q_], qu_))
            q_, qu_ = cut(P_, uvs_, o_, lo_, True); q_, qu_ = cut(q_, qu_, o_, hi_, False) if len(q_) >= 3 else ([], [])
            if len(q_) < 3: continue
            up_, upuv_ = cut(q_, qu_, 2, ZC_, True); dn_, dnuv_ = cut(q_, qu_, 2, ZC_, False)
            if len(up_) >= 3: keep_.append(([tuple(x_) for x_ in up_], upuv_))
            if len(dn_) >= 3:
                n_cut += 1
                runs_[i_].append((dn_, dnuv_, gk_))
        GEO[gk_] = keep_
    tiers_ = {"1": [(18.0, 73.0)], "2": [(18.0, 44.0), (48.0, 73.0)]}[os.environ.get("AG_TAVERN_PANEL_TIERS", "1")]
    PW_ = float(os.environ.get("AG_TAVERN_PANEL_W", "26"))     # a panel's width (the frame's stiles between are SW_): tall and narrow
    SW_, FD_, PD_, BV_ = 5.0, 1.6, 0.6, 1.4                     # stile width; the frame's face, the panel's face (proud of the
                                                                # plaster's plane); the bevel's width round each panel
    for i_, (ax_, c_, n_) in enumerate(planes_):
        if not runs_[i_]: continue
        r_ = UP.cross(n_)
        o_ = Vector((c_, 0, 0)) if ax_ == "x" else Vector((0, c_, 0))
        W_ = (o_, r_, n_)
        iv_ = sorted((min((q_ - o_).dot(r_) for q_ in dn_ if q_.z < 1), max((q_ - o_).dot(r_) for q_ in dn_ if q_.z < 1))
                     for dn_, _, _ in runs_[i_] if sum(1 for q_ in dn_ if q_.z < 1) >= 2)
        merged_ = []
        for a_, b_ in iv_:
            if merged_ and a_ <= merged_[-1][1] + 1.0: merged_[-1][1] = max(merged_[-1][1], b_)
            else: merged_.append([a_, b_])
        # (the walk of 2026-11-13: the panelling ran over the archways' stone edging; built in, it stops at
        # that stone) the arches' stone surrounds, strips 1.5 proud of this wall that
        # come down to the floor, taken out of the runs: the panelling stops at each, capped, and the stone shows to the floor
        strips_ = []
        for gk_ in [k_ for k_ in GEO if k_[0] == PART and k_[1] == "stone"]:
            for pts_, _ in GEO[gk_]:
                P_ = [Vector(q_) for q_ in pts_]
                if min(q_.z for q_ in P_) >= ZC_: continue
                dd_ = [(q_ - o_).dot(n_) for q_ in P_]
                if not all(0.2 < d_ < 4.0 for d_ in dd_): continue
                nn_ = Vector((0, 0, 0))
                for j_ in range(len(P_)): nn_ += P_[j_ - 1].cross(P_[j_])
                if nn_.length < 1e-6 or nn_.normalized().dot(n_) < 0.9: continue
                us_ = [(q_ - o_).dot(r_) for q_ in P_]; strips_.append((min(us_), max(us_)))
        for sa_, sb_ in strips_:
            cut_ = []
            for a_, b_ in merged_:
                if sb_ <= a_ + 0.3 or sa_ >= b_ - 0.3: cut_.append([a_, b_]); continue
                if sa_ - a_ > 0.5: cut_.append([a_, sa_])
                if b_ - sb_ > 0.5: cut_.append([sb_, b_])
            merged_ = cut_
        if strips_: print("TAVERN PANELLING: wall", i_, "stops at", len(strips_), "stone surrounds", sorted((round(a_), round(b_)) for a_, b_ in strips_))
        # (the walk of 2026-11-13: the tiny piece of panel on the pier between the archways is not needed) a run under 30 with stone at both ends (the 22 of the pier between two arches) keeps its plaster, unpanelled
        def _at_stone(u_): return any(abs(u_ - sa_) < 1.0 or abs(u_ - sb_) < 1.0 for sa_, sb_ in strips_)
        plain_ = [(a_, b_) for a_, b_ in merged_ if b_ - a_ < 30 and _at_stone(a_) and _at_stone(b_)]
        merged_ = [[a_, b_] for a_, b_ in merged_ if (a_, b_) not in plain_]
        k_ax_ = 1 if ax_ == "x" else 0; sg_ = 1 if r_[k_ax_] > 0 else -1; c0_ = o_[k_ax_]
        def _clip(P_, U_, lo_, hi_):                          # the part of a face between u lo_..hi_ along this wall
            w0_, w1_ = sorted((c0_ + sg_ * lo_, c0_ + sg_ * hi_))
            q_, qu_ = cut(P_, U_, k_ax_, w0_, True)
            return cut(q_, qu_, k_ax_, w1_, False) if len(q_) >= 3 else ([], [])
        for dn_, dnuv_, gk_ in runs_[i_]:
            for a_, b_ in plain_:                             # the plaster put back
                q_, qu_ = _clip(dn_, dnuv_, a_, b_)
                if len(q_) >= 3: GEO[gk_].append(([tuple(x_) for x_ in q_], qu_))
            rest_ = [(dn_, dnuv_)]                            # the rest of the wall's plane below the cap: collision only, as the plaster's was
            for a_, b_ in plain_:
                nxt_ = []
                for P_, U_ in rest_:
                    for lo_, hi_ in ((-1e6, a_), (b_, 1e6)):
                        q_, qu_ = _clip(P_, U_, lo_, hi_)
                        if len(q_) >= 3: nxt_.append((q_, qu_))
                rest_ = nxt_
            for P_, _ in rest_:
                COLL_ONLY.setdefault(PART, []).extend([[tuple(P_[0]), tuple(P_[j_]), tuple(P_[j_ + 1])] for j_ in range(1, len(P_) - 1)])
                COLL_ONLY_KEY.setdefault(PART, []).extend([gk_[1]] * (len(P_) - 2))   # the wall's own plaster
        if plain_: print("TAVERN PANELLING: wall", i_, "left plain between stones", [(round(a_), round(b_)) for a_, b_ in plain_])
        if not merged_: continue
        u0_, u1_ = merged_[0][0], merged_[-1][1]
        holes_ = [(merged_[k_][1], merged_[k_ + 1][0]) for k_ in range(len(merged_) - 1)]
        for band_, d_, key_ in ((BAND_S, 2.6, "wainframe"), (BAND_C, 3.4, "wainframe")):
            BASE_RUNS.append({"W": W_, "u0": u0_, "u1": u1_, "deep": d_, "part": PART, "frame": FRAME, "band": band_, "holes": holes_})
            NOCOLL_BANDS.add(band_); BAND_KEY[band_] = key_
        A_ = lambda u_, d_, z_: o_ + r_ * u_ + n_ * d_ + UP * z_
        def corner(u_, sg_):
            """an end of this run at an inside corner, as a joiner makes it: the run that reaches the other wall's plane runs
            into the corner ("into": no cap); a run that stops short of it, by up to the frame's depth and a little, butts
            against the other's frame ("butt": it ends in that frame's face, no cap); else None (an arch, a doorway: capped)"""
            p_ = o_ + r_ * u_
            for j_, (ax2_, c2_, n2_) in enumerate(planes_):
                if j_ == i_: continue
                d_ = abs((p_.x if ax2_ == "x" else p_.y) - c2_)
                if d_ < 1.0: return ("into", u_)
                if d_ < FD_ + 2.0: return ("butt", u_ - sg_ * (FD_ - d_))   # (to the other frame's face, FD_ off its wall)
            return None
        def run(a_, b_):
            ka_, kb_ = corner(a_, -1), corner(b_, 1)                       # (the leak check's sliver, 2026-11-12: both runs cut short
            if ka_: a_ = ka_[1]                                            # left a corner column with a one-sided cap on its far side)
            if kb_: b_ = kb_[1]
            ca_, cb_ = ka_ is not None, kb_ is not None
            L_ = b_ - a_
            if L_ < 0.5: return
            short_ = L_ < SW_ * 2 + 12                            # (a run too short for a panel, by an arch: the frame alone)
            if short_: holes2_ = []
            m_ = max(1, round((L_ - SW_) / (PW_ + SW_)))         # panels in the run, all one width
            pw_ = (L_ - SW_ * (m_ + 1)) / m_
            if not short_: holes2_ = [(SW_ + k_ * (pw_ + SW_) + a_, SW_ + k_ * (pw_ + SW_) + pw_ + a_, z0_, z1_) for k_ in range(m_) for z0_, z1_ in tiers_]
            face("wainframe", (o_ + n_ * FD_, r_, n_), a_, b_, BAND_S[1], BAND_C[0], holes2_)   # the frame: stiles and rails, one face
            # (its back, 0.05 behind it, facing the wall: a ray grazing past an arch's jamb from the kitchen saw the frame from behind,
            # the leak check, 2026-11-12)
            face("wainframe", (o_ + n_ * (FD_ - 0.05), -r_, -n_), -b_, -a_, BAND_S[1], BAND_C[0], [(-ub_, -ua_, z0_, z1_) for ua_, ub_, z0_, z1_ in holes2_])
            for ua_, ub_, z0_, z1_ in holes2_:                  # each panel: a bevel down from the frame, its field
                P0 = [A_(ua_, FD_, z0_), A_(ub_, FD_, z0_), A_(ub_, FD_, z1_), A_(ua_, FD_, z1_)]
                P1 = [A_(ua_ + BV_, PD_, z0_ + BV_), A_(ub_ - BV_, PD_, z0_ + BV_), A_(ub_ - BV_, PD_, z1_ - BV_), A_(ua_ + BV_, PD_, z1_ - BV_)]
                for k_ in range(4): poly("wainframe", [P0[k_], P1[k_], P1[(k_ + 1) % 4], P0[(k_ + 1) % 4]][::-1])
                poly("wainpanel", P1)
            for ue_, sg_, cn_ in ((a_, -1, ca_), (b_, 1, cb_)):  # the frame's ends where the run stops at an arch (none in a corner: hidden)
                if cn_: continue
                q_ = [A_(ue_, -0.5, BAND_S[1]), A_(ue_, FD_, BAND_S[1]), A_(ue_, FD_, BAND_C[0]), A_(ue_, -0.5, BAND_C[0])]   # (0.5 into the wall: no crack where it meets a jamb's reveal)
                poly("wainframe", q_ if sg_ < 0 else q_[::-1])
        for a_, b_ in merged_: drawn_only(run, a_, b_)
    print("TAVERN PANELLING:", n_cut, "plaster faces cut, per wall", {k_: len(v_) for k_, v_ in runs_.items()})
if os.environ.get("AG_TAVERN_PANEL", "1") == "1": tavern_panelling()
baseboards()   # (every wall built: the floor rails, mitred where they meet)
json.dump(BASE_LOG, open(os.path.join(out, f"baseboards_{VARIANT}.json"), "w"))
PLACE += NEW_PLACE          # places the first fifteen lamps and the unnamed pieces as before, then these, in this order
# (2026-10-28) the basement, a cell of its own (plans/BASEMENT.md): its rooms, pieces and lights (part "basement")
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd(), "basement_gen.py"), encoding="utf-8").read())
json.dump({"variant": VARIANT, "zg": ZG, "inner": {"ground": [XG, YF, YB], "upper": [XU, YFU, YBU]}, "items": PLAN,
           "openings_tower": [op_ for op_ in OPENINGS if op_["what"].startswith("tower")]},   # (they move with AG_TOWER_BOX)
          open(os.path.join(out, f"interior_plan_{VARIANT}.json"), "w"), indent=1)
if os.environ.get("AG_PLAN_ONLY"): print("PLAN written"); sys.exit(0)
print("INTERIOR", VARIANT, sum(len(v) for v in GEO.values()), "faces,", len(INT_LIGHTS), "lights")
