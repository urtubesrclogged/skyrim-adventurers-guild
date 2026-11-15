"""The main cell's rooms, for the engine's room bounds and portals (the performance pass). Vanilla's way, measured (`dotnet run -- roomsurvey`, Dragonsreach and the Blue Palace): each room is one or more
boxes (a RoomMarker's primitive, full sizes, never overlapping), the boxes of one room linked to each other (XLRM), a
portal (a PortalMarker's thin box) in every opening between two rooms; everything drawn has its origin in exactly one
room (Dragonsreach: 1404 of 1414 references), and a room is drawn only when the player is in it or sees it through a
portal. So a box's side must run inside a wall (never in front of one: the wall's face would then belong to the room on
the other side and vanish), and every gap in a shared side needs its portal: blender/rooms_check.py checks both and
makes the portals.

Boxes are in the cell's frame (the export's: x to the front, y along the hall, z up), (x0, x1, y0, y1, z0, z1). Where
the walls between the ground floor and the floors above stand in different places, a room has a box per storey."""

ROOMS = {
    # the great hall: its floor, the galleries round it, the hearth's bay, the mirror of the tower's foot beside it (open to
    # the gallery), the open space under the roof and the loft over the library at the front, which is open to it. On the
    # ground floor its sides to the tavern and the services run in the arcades' piers (y -382..-338), upstairs in the walls
    # (-416..-392)
    "GreatHall": [(-744, -260, -372, 372, -30, 416), (-744, -260, -404, 404, 416, 1480),
                  (-260, 24, -372, 372, -30, 416), (-260, 24, -404, 404, 683, 1480), (-1100, -744, -228, 228, -30, 1480),
                  (-1100, -744, -372, -228, -30, 416), (-1100, -744, -404, -228, 416, 683)],
    "Library": [(-260, 24, -404, 404, 416, 683)],
    "Tower": [(-1150, -760, 228, 708, -280, 416), (-1150, -744, 228, 708, 416, 1480)],
    # (the kitchen's hearth is cut into the wall to -1064, so the ground floor's side runs behind it)
    "Tavern": [(-912, -150, -1062, -372, -30, 416), (-912, -150, -1080, -404, 416, 1090)],
    "Kitchen": [(-912, -150, -1460, -1062, -30, 416)],
    "GmOffice": [(-628, -120, -1460, -1080, 416, 663)],
    "GmBedroom": [(-912, -628, -1460, -1080, 416, 663)],
    "Services": [(-760, -150, 372, 1074, -30, 416), (-912, -760, 708, 1074, -30, 416)],
    "Backroom": [(-912, -150, 1074, 1460, -30, 416)],
    "Landing": [(-744, -594, 404, 1066, 416, 663), (-912, -744, 708, 1066, 416, 663)],
    "Room6": [(-372, -150, 404, 766, 416, 663)],
    "Room7": [(-594, -372, 404, 766, 416, 663)],
    "CommonRoom": [(-594, -150, 766, 1066, 416, 663)],
    "Room3": [(-350, -120, 1066, 1460, 416, 663)],   # (plan D, 2026-11-06: rooms 3 and 4 380 x 210, room 5 the rest)
    "Room4": [(-572, -350, 1066, 1460, 416, 663)],
    "Room5": [(-912, -572, 1066, 1460, 416, 663)],
    "Attic": [(-744, -120, 404, 1460, 663, 1090), (-912, -744, 708, 1460, 663, 1090)],
}


def boxes():
    """every box: (room, index, box)"""
    return [(r, i, b) for r, bs in ROOMS.items() for i, b in enumerate(bs)]


def inside(p, b, pad=0.0):
    return b[0] - pad <= p[0] <= b[1] + pad and b[2] - pad <= p[1] <= b[3] + pad and b[4] - pad <= p[2] <= b[5] + pad


def room_of(p):
    """the rooms whose boxes hold p (more than one only on a shared side)"""
    return sorted({r for r, _, b in boxes() if inside(p, b)})


def origin(room):
    """where a room's own meshes are pivoted: the middle of its first box, at that box's floor (so the pivot is inside it)"""
    b = ROOMS[room][0]
    return ((b[0] + b[1]) / 2, (b[2] + b[3]) / 2, b[4] + 40)


def overlaps():
    """pairs of boxes that overlap (they must only touch)"""
    out, B = [], boxes()
    for i in range(len(B)):
        for j in range(i + 1, len(B)):
            a, b = B[i][2], B[j][2]
            if all(min(a[2 * k + 1], b[2 * k + 1]) - max(a[2 * k], b[2 * k]) > 0.5 for k in range(3)):
                out.append((B[i][:2], B[j][:2]))
    return out


def shared_faces():
    """pairs of boxes that touch: (box A, box B, axis, plane, the shared rectangle on the other two axes)"""
    out, B = [], boxes()
    for i in range(len(B)):
        for j in range(i + 1, len(B)):
            a, b = B[i][2], B[j][2]
            for k in range(3):
                for s, t in ((a, b), (b, a)):
                    if abs(s[2 * k + 1] - t[2 * k]) < 0.5:
                        o = [m for m in range(3) if m != k]
                        lo = [max(a[2 * m], b[2 * m]) for m in o]; hi = [min(a[2 * m + 1], b[2 * m + 1]) for m in o]
                        if hi[0] - lo[0] > 1 and hi[1] - lo[1] > 1:
                            out.append((B[i][:2], B[j][:2], k, s[2 * k + 1], o, lo, hi))
    return out


# the lights' reach, for the per-piece light count: each kind's record's radius (Hall2.cs's lightOf: WRCandleFlickerNS
# 128, WRWindowFill 200, WRFireLightShadow01 768, WRLightFire01 512, WRInteriorLightYellow 512) plus the reference's own
# trim, the export's fifth entry (XRDS)
LIGHT_RADIUS = {"candle": 128, "candle_small": 128, "window": 200, "fire": 768, "fire_small": 512, "lamp": 512}
LIMIT = 4          # lights a piece may be touched by: the vanilla renderer lights a shape with only a few (the CK's own
                   # "# of lights" view, Beyond Skyrim's 4 per shape; Light Limit Fix lifts it, not every VR setup has it)


def lights_of(D):
    """(position, radius) of each light the export places in the cell (the renders' glows have none)"""
    out = []
    for l in D["lights"]:
        kind = l[3] if len(l) > 3 else None
        if kind is None or kind == "glow" or kind not in LIGHT_RADIUS: continue
        out.append((l[0], max(16.0, LIGHT_RADIUS[kind] + (l[4] if len(l) > 4 else 0))))
    return out


def lights_on(lo, hi, lights):
    """the lights touching a piece, as the engine picks them: by the piece's bounding sphere"""
    c = [(lo[k] + hi[k]) / 2 for k in range(3)]
    r = sum((hi[k] - lo[k]) ** 2 for k in range(3)) ** 0.5 / 2
    return [L for L in lights if sum((L[0][k] - c[k]) ** 2 for k in range(3)) ** 0.5 < r + L[1]]
