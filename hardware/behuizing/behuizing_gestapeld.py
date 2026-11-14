"""Gestapelde behuizing: OT-adapter onderin, ESP32-C6-DevKitC-1 erboven.

Smallere variant van behuizing.py (die zet ze naast elkaar). Draaien:
    "C:/Program Files/FreeCAD 1.1/bin/freecadcmd.exe" behuizing_gestapeld.py

Uitgangspunt: op de DevKit zitten alleen dupont-stekkers op de 3V3-pinrij (3V3, G, GPIO10, GPIO11).
De pinrij aan de andere kant (G/TX/RX/...) staat boven de adapter en kan geen stekkers hebben.
Op de adapter zitten rechte dupont-stekkers, pinnen omhoog.

Maten in mm. Oorsprong = binnenhoek op de bovenkant van de bodem (in de slicer dus +2,5 mm):
x = lengte (USB-kant x=0, antennekant x=L), y = breedte (kabelkant y=0), z omhoog.
Bronnen voor de printmaten: zie behuizing.py.
"""
import os
import Part
from FreeCAD import Vector as V

OUT = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- algemeen
WALL = 2.0
FLOOR = 2.5
LID_T = 2.0
L, W, H = 62.0, 29.5, 38.5   # binnenmaten
R_OUT = 3.0
R_IN = R_OUT - WALL

LIP_H = 5.0
LIP_T = 1.2
LIP_CLR = 0.25
RIDGE_R = 0.6
GROOVE_D = 0.7
GROOVE_Z = H - LIP_H / 2

# ---------------------------------------------------------------- OT-adapter (onderin)
AD_W, AD_LEN, AD_T = 20.2, 25.5, 1.6   # a-richting (over y), b-richting (over x)
AD_X = 11.0         # b=0 (kant IN/OUT-header), weg van de antenne
AD_Y = 3.7          # a=0 (kant OT-header), naar de kabelkant
AD_ZB = 2.5         # onderkant print (soldeerpunten ca. 1,5 mm)
AD_HOLE = (2.84, 9.0)
PEG_D = 2.7
DUPONT_UP = 2.5 + 14.0   # headerplastic + dupont-huisje boven de adapterprint
WIRE_BEND = 5.4          # ruimte om de draadjes boven de stekkers om te buigen


def ad(a, b):
    return AD_X + b, AD_Y + a


# ---------------------------------------------------------------- DevKitC-1 (erboven)
DK_X = 1.0
DK_Y = 2.0          # u=25,4-rand (G/TX/RX-rij) van de print
DK_ZB = AD_ZB + AD_T + DUPONT_UP + WIRE_BEND   # = 26,0
DK_LEN, DK_WID, DK_T = 51.8, 25.4, 1.6
MOD_H = 3.2
USB_W, USB_H = 13.0, 7.5
USB_PORTS = [5.5, 19.9]
LED_U, LED_V = 6.5, 18.0
LED_SKIN = 0.0


def dk(u, v):
    return DK_X + v, DK_Y + DK_WID - u


# ---------------------------------------------------------------- kabel en montage
OT_D = 5.5          # OpenTherm-kabel door de lange voorwand (y=0)
OT_X, OT_Z = 41.0, 10.0
SCREW_D, SCREW_HEAD = 4.2, 8.0
SCREWS = [(5.8, 14.7), (41.0, 15.0)]


# ================================================================= hulpfuncties
def box(x, y, z, lx, ly, lz):
    return Part.makeBox(lx, ly, lz, V(x, y, z))


def rbox(x, y, z, lx, ly, lz, r):
    if r <= 0.01:
        return box(x, y, z, lx, ly, lz)
    s = box(x + r, y, z, lx - 2 * r, ly, lz).fuse(box(x, y + r, z, lx, ly - 2 * r, lz))
    for cx in (x + r, x + lx - r):
        for cy in (y + r, y + ly - r):
            s = s.fuse(Part.makeCylinder(r, lz, V(cx, cy, z)))
    return s.removeSplitter()


def slot_x(x0, length, yc, zc, wy, hz, r):
    r = min(r, wy / 2, hz / 2)
    s = box(x0, yc - wy / 2 + r, zc - hz / 2, length, wy - 2 * r, hz)
    s = s.fuse(box(x0, yc - wy / 2, zc - hz / 2 + r, length, wy, hz - 2 * r))
    for dy in (-1, 1):
        for dz in (-1, 1):
            s = s.fuse(Part.makeCylinder(r, length, V(x0, yc + dy * (wy / 2 - r), zc + dz * (hz / 2 - r)), V(1, 0, 0)))
    return s


def wedge_y(x, y_face, z_low, length, depth, height, inward, straight=0.6):
    """Klikneus: eerst `straight` mm recht, daarna schuin; minstens 0,8 diep voor een 0,4-nozzle."""
    p = [V(x, y_face, z_low), V(x, y_face + inward * depth, z_low),
         V(x, y_face + inward * depth, z_low + straight),
         V(x, y_face, z_low + height), V(x, y_face, z_low)]
    return Part.Face(Part.makePolygon(p)).extrude(V(length, 0, 0))


# ================================================================= bak
def make_box():
    s = rbox(-WALL, -WALL, -FLOOR, L + 2 * WALL, W + 2 * WALL, FLOOR + H, R_OUT)
    s = s.cut(rbox(0, 0, 0, L, W, H + 1, R_IN))
    s = s.cut(rbox(-GROOVE_D, -GROOVE_D, GROOVE_Z - 0.8, L + 2 * GROOVE_D, W + 2 * GROOVE_D, 1.6, R_IN + GROOVE_D))
    s = s.cut(box(L / 2 - 5, -WALL - 0.1, H - 1.5, 10, 1.1, 1.6))   # wrikinkeping

    usb_z = DK_ZB + DK_T + 1.6
    for u in USB_PORTS:
        _, yc = dk(u, 0)
        s = s.cut(slot_x(-WALL - 1, WALL + 1.5, yc, usb_z, USB_W, USB_H, 2.5))

    # OpenTherm-kabel door de voorwand, trekontlasting erachter (tunnel in x-richting voor de tie-wrap)
    s = s.cut(Part.makeCylinder(OT_D / 2, WALL + 2, V(OT_X, 0.5, OT_Z), V(0, -1, 0)))
    bridge_top = OT_Z - OT_D / 2
    br = box(OT_X - 3.5, 2.0, 0, 7.0, 6.0, bridge_top)
    br = br.cut(box(OT_X - 4.5, 3.0, 0, 9.0, 4.0, 2.0))
    s = s.fuse(br)

    for (x, y) in SCREWS:
        s = s.cut(Part.makeCylinder(SCREW_D / 2, FLOOR + 2, V(x, y, -FLOOR - 1)))
        depth = (SCREW_HEAD - SCREW_D) / 2
        s = s.cut(Part.makeCone(SCREW_D / 2, SCREW_HEAD / 2, depth, V(x, y, -depth)))
        s = s.cut(Part.makeCylinder(SCREW_HEAD / 2, 1, V(x, y, -0.001)))

    # ---- DevKit: pijlers aan de USB-kant met zijlipjes, steun en aanslagen aan de antennekant
    x0, x1 = DK_X + 0.5, DK_X + 9.0
    y_lo, y_hi = DK_Y, DK_Y + DK_WID
    s = s.fuse(box(x0, y_lo - 1.5, 0, x1 - x0, 7.5, DK_ZB))
    s = s.fuse(box(x0, y_lo - 1.5, DK_ZB, x1 - x0, 1.2, 1.5))
    s = s.fuse(box(x0, y_hi - 6.0, 0, x1 - x0, 7.5, DK_ZB))
    s = s.fuse(box(x0, y_hi + 0.3, DK_ZB, x1 - x0, 1.2, 1.5))
    ax0, ay1 = dk(18.4, 44.0)
    _, ay0 = dk(7.0, 0)
    s = s.fuse(box(ax0, ay1, 0, 6.0, ay0 - ay1, DK_ZB))
    sx = DK_X + DK_LEN + 0.3
    s = s.fuse(box(sx, y_lo + 0.3, 0, 3.0, DK_WID - 0.6, 3.0))
    for yy in (y_lo + 0.3, y_hi - 3.3):
        s = s.fuse(box(sx, yy, 0, 3.0, 3.0, DK_ZB + 2.5))

    # ---- OT-adapter: pen, hoekpootjes, twee klikhaken
    hx, hy = ad(*AD_HOLE)
    s = s.fuse(Part.makeCylinder(2.6, AD_ZB, V(hx, hy, 0)))
    s = s.fuse(Part.makeCylinder(PEG_D / 2, AD_ZB + AD_T + 1.0, V(hx, hy, 0)))
    for a, b in ((0, 0), (AD_W - 1.5, 0), (0, AD_LEN - 1.5), (AD_W - 1.5, AD_LEN - 1.5)):
        cx, cy = ad(a, b)
        s = s.fuse(box(cx, cy, 0, 1.5, 1.5, AD_ZB))
    hook_l = 6.0
    hx0 = AD_X + AD_LEN / 2 - hook_l / 2
    top = AD_ZB + AD_T
    y_face_lo = AD_Y - 0.2
    s = s.fuse(box(hx0, y_face_lo - 1.2, 0, hook_l, 1.2, top + 1.7))
    s = s.fuse(wedge_y(hx0, y_face_lo, top + 0.05, hook_l, 0.8, 1.6, +1))
    y_face_hi = AD_Y + AD_W + 0.2
    s = s.fuse(box(hx0, y_face_hi, 0, hook_l, 1.2, top + 1.7))
    s = s.fuse(wedge_y(hx0, y_face_hi, top + 0.05, hook_l, 0.8, 1.6, -1))

    return s.removeSplitter()


# ================================================================= deksel (in montagestand)
def make_lid():
    s = rbox(-WALL, -WALL, H, L + 2 * WALL, W + 2 * WALL, LID_T, R_OUT)
    c = LIP_CLR
    ring = rbox(c, c, H - LIP_H, L - 2 * c, W - 2 * c, LIP_H + 0.01, max(R_IN - c, 0.2))
    ring = ring.cut(rbox(c + LIP_T, c + LIP_T, H - LIP_H - 1, L - 2 * (c + LIP_T), W - 2 * (c + LIP_T), LIP_H + 2, 0.2))
    s = s.fuse(ring)
    zr = GROOVE_Z
    for y in (c, W - c):
        s = s.fuse(Part.makeCylinder(RIDGE_R, 24, V(L / 2 - 12, y, zr), V(1, 0, 0)))
    for x in (c, L - c):
        s = s.fuse(Part.makeCylinder(RIDGE_R, 12, V(x, W / 2 - 6, zr), V(0, 1, 0)))

    lx, ly = dk(LED_U, LED_V)
    tube_bottom = DK_ZB + DK_T + 1.0 + 0.6
    s = s.fuse(Part.makeCylinder(3.5, H - tube_bottom + 0.01, V(lx, ly, tube_bottom)))
    s = s.cut(Part.makeCylinder(2.5, H + LID_T - LED_SKIN - tube_bottom + 1, V(lx, ly, tube_bottom - 1)))

    fx, fy = dk(12.7, 40.0)
    f_bottom = DK_ZB + DK_T + MOD_H + 0.2
    s = s.fuse(box(fx - 2, fy - 2, f_bottom, 4, 4, H - f_bottom + 0.01))
    return s.removeSplitter()


def export(shape, name):
    path = os.path.join(OUT, name)
    if name.endswith(".stl"):
        import Mesh
        import MeshPart
        m = MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.05, AngularDeflection=0.2, Relative=False)
        Mesh.Mesh(m).write(path, "STL")
    else:
        shape.exportStep(path)
    print("geschreven:", path)


bak = make_box()
deksel = make_lid()
for nm, sh in (("bak", bak), ("deksel", deksel)):
    print(nm, "geldig:", sh.isValid(), "volume:", round(sh.Volume / 1000, 1), "cm3", "bbox:", sh.BoundBox)
print("overlap bak/deksel:", round(bak.common(deksel).Volume, 2), "mm3")

export(bak, "bak-gestapeld.stl")
d = deksel.copy()
d.rotate(V(0, 0, H + LID_T), V(1, 0, 0), 180)
d.translate(V(0, 0, -d.BoundBox.ZMin))
export(d, "deksel-gestapeld.stl")
export(Part.makeCompound([bak, deksel]), "behuizing-gestapeld.step")
