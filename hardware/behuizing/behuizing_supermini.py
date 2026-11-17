"""Behuizing voor een ESP32-C6 SuperMini (18 x 26 mm) + Ihor Melnyk OpenTherm-adapter, naast elkaar.

Kleinere variant van behuizing.py (die is voor de DevKitC-1). Draaien:
    "C:/Program Files/FreeCAD 1.1/bin/freecadcmd.exe" behuizing_supermini.py

Uitgangspunt: SuperMini met de pinheaders aan de onderkant (pinnen omlaag), rechte dupont-stekkers
alleen op de rij met 5V/GND/3V3 (naar de adapter toe). De rij TX/RX/0..7 krijgt geen stekkers.
Op de adapter zitten rechte dupont-stekkers, pinnen omhoog.

Maten in mm. Oorsprong = binnenhoek op de bovenkant van de bodem (in de slicer dus +2,5 mm):
x = lengte (USB-kant x=0, kabelkant x=L), y = breedte (SuperMini-kant y=0), z omhoog.

SuperMini-maten afgeleid uit een productfoto met maatpijlen (26 x 18, 20 px/mm), dus +-0,3 mm:
USB-C steekt 1,75 uit, midden t=8,75; RGB-LED op s=14,45 t=14,6; ESP-chip midden s=15,2 t=8,4;
pinrijen 2,54 mm raster vanaf s=1,35, op ca. 1 mm van de lange randen (castellated).
s = vanaf de USB-rand, t = vanaf de 5V/GND/3V3-rand (bovenaanzicht, USB links).
Bronnen voor de adapter: zie behuizing.py.
"""
import os
import Part
from FreeCAD import Vector as V

OUT = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- algemeen
WALL = 2.0
FLOOR = 2.5
LID_T = 2.0
L, W, H = 34.0, 42.4, 33.0   # binnenmaten
R_OUT = 3.0
R_IN = R_OUT - WALL

LIP_H = 5.0
LIP_T = 1.2
LIP_CLR = 0.25
RIDGE_R = 0.6
GROOVE_D = 0.7
GROOVE_Z = H - LIP_H / 2
GROOVE_PRESS = 0.1  # ribbel drukt zoveel in de schuine bovenkant van de groef (0 = net geen speling)

# ---------------------------------------------------------------- SuperMini
SM_LEN, SM_WID, SM_T = 26.0, 18.0, 1.6
SM_X = 2.0          # USB-rand van de print; de bus steekt 1,75 uit
SM_Y = 0.6          # TX/RX-rand van de print
SM_ZB = 22.0        # onderkant print: header 2,5 + dupont 14 + 5,5 om de draadjes te buigen
USB_T = 8.75        # midden USB-C
USB_W, USB_H = 13.0, 7.5     # opening voor stekker met omhulsel
LED_S, LED_T = 14.45, 14.6   # RGB-LED (GPIO8)
CHIP_S, CHIP_T = 15.2, 8.4   # ESP32-C6-chip, de drukvinger van het deksel staat erboven
PIN_S0, PITCH, NPIN = 1.35, 2.54, 10
ROW_T = (1.0, 17.0)          # pinrijen (onzeker tussen 0,75 en 1,4 vanaf de rand)
LED_SKIN = 0.0      # 0 = open gat; 0.4 = twee laagjes dicht (licht schijnt door bij wit/naturel filament)


def sm(s, t):
    """SuperMini-coördinaten -> box x, y (bovenaanzicht: 5V-rij aan de adapterkant)."""
    return SM_X + s, SM_Y + SM_WID - t


# ---------------------------------------------------------------- OT-adapter
AD_W, AD_LEN, AD_T = 20.2, 25.5, 1.6   # a-richting (over y), b-richting (over x)
AD_X = 1.0          # b=0 (kant IN/OUT-header), aan de USB-kant
AD_Y = 20.8         # a=AD_W (IN/OUT-kant) naar de SuperMini; a=0 (OT-header) tegen de achterwand
AD_ZB = 4.0
AD_HOLE = (2.84, 9.0)
PEG_D = 2.7


def ad(a, b):
    return AD_X + b, AD_Y + AD_W - a


# ---------------------------------------------------------------- kabel en montage
OT_D = 5.5          # OpenTherm-kabel door de kopse wand x=L, achter de adapter langs
OT_Y, OT_Z = 36.0, 8.0
SCREW_D, SCREW_HEAD = 4.2, 8.0
SCREWS = [(15.0, 9.6), (30.0, 26.0)]


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


def groove():
    """Groef voor de klikribbels. De bovenkant loopt 45 graden schuin: de verende rand van het deksel duwt de
    ribbel tegen die schuinte en trekt het deksel zo omlaag op de rand. Daardoor geen speling op en neer,
    ook niet als de print een tiende afwijkt. GROOVE_PRESS = hoeveel de ribbel de schuinte in drukt."""
    zc, d = GROOVE_Z, GROOVE_D
    z_t = zc - LIP_CLR - d + (RIDGE_R - GROOVE_PRESS) * 2 ** 0.5
    low = rbox(-d, -d, zc - 0.8, L + 2 * d, W + 2 * d, z_t - (zc - 0.8), R_IN + d)

    def wire(off, z):
        f = rbox(-off, -off, z, L + 2 * off, W + 2 * off, 1, R_IN + off)
        return [fc for fc in f.Faces if fc.BoundBox.ZMax < z + 1e-6][0].OuterWire

    top = Part.makeLoft([wire(d, z_t), wire(-0.05, z_t + d + 0.05)], True, True)
    return low.fuse(top).removeSplitter()


# ================================================================= bak
def make_box():
    s = rbox(-WALL, -WALL, -FLOOR, L + 2 * WALL, W + 2 * WALL, FLOOR + H, R_OUT)
    s = s.cut(rbox(0, 0, 0, L, W, H + 1, R_IN))
    s = s.cut(groove())
    s = s.cut(box(L / 2 - 5, -WALL - 0.1, H - 1.5, 10, 1.1, 1.6))   # wrikinkeping

    # USB-C-opening in de kopse wand x=0
    _, yc = sm(0, USB_T)
    s = s.cut(slot_x(-WALL - 1, WALL + 1.5, yc, SM_ZB + SM_T + 1.6, USB_W, USB_H, 2.5))

    # OpenTherm-kabel in de kopse wand x=L, met trekontlasting (tunnel in y-richting voor de tie-wrap)
    s = s.cut(Part.makeCylinder(OT_D / 2, WALL + 2, V(L - 0.5, OT_Y, OT_Z), V(1, 0, 0)))
    bridge_top = OT_Z - OT_D / 2
    br = box(L - 6.8, OT_Y - 4, 0, 5.5, 8, bridge_top)
    br = br.cut(box(L - 5.8, OT_Y - 5, 0, 3.5, 10, 2.0))
    s = s.fuse(br)

    for (x, y) in SCREWS:
        s = s.cut(Part.makeCylinder(SCREW_D / 2, FLOOR + 2, V(x, y, -FLOOR - 1)))
        depth = (SCREW_HEAD - SCREW_D) / 2
        s = s.cut(Part.makeCone(SCREW_D / 2, SCREW_HEAD / 2, depth, V(x, y, -depth)))
        s = s.cut(Part.makeCylinder(SCREW_HEAD / 2, 1, V(x, y, -0.001)))

    # ---- SuperMini: twee pijlers tussen de pinrijen (de headers aan weerszijden houden hem op zijn plek in y),
    #      een aanslag aan het eind; de USB-bus zit tegen de wand
    _, y_hi = sm(0, 3.0)
    _, y_lo = sm(0, 15.0)
    for s0 in (3.0, 19.0):
        x0, _ = sm(s0, 0)
        s = s.fuse(box(x0, y_lo, 0, 4.0, y_hi - y_lo, SM_ZB))
    sx, _ = sm(SM_LEN + 0.15, 0)
    s = s.fuse(box(sx, y_lo, 0, 3.0, y_hi - y_lo, SM_ZB + 2.5))

    # ---- OT-adapter: pen in het montagegat, hoekpootjes, twee klikhaken
    hx, hy = ad(*AD_HOLE)
    s = s.fuse(Part.makeCylinder(2.6, AD_ZB, V(hx, hy, 0)))
    s = s.fuse(Part.makeCylinder(PEG_D / 2, AD_ZB + AD_T + 1.0, V(hx, hy, 0)))
    # 1,5 mm: de soldeerpunten van de headers zitten 2 mm van de rand
    for cx in (AD_X, AD_X + AD_LEN - 1.5):
        for cy in (AD_Y, AD_Y + AD_W - 1.5):
            s = s.fuse(box(cx, cy, 0, 1.5, 1.5, AD_ZB))
    hook_l = 6.0
    hx0 = AD_X + AD_LEN / 2 - hook_l / 2
    top = AD_ZB + AD_T
    y_face_lo = AD_Y - 0.2
    s = s.fuse(box(hx0, y_face_lo - 1.2, 0, hook_l, 1.2, top + 1.7))
    s = s.fuse(wedge_y(hx0, y_face_lo, top + 0.05, hook_l, 0.8, 1.6, +1))
    y_face_hi = AD_Y + AD_W + 0.2
    s = s.fuse(box(hx0, y_face_hi, 0, hook_l, W - y_face_hi + 0.5, top + 1.7))   # tegen de achterwand
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
        s = s.fuse(Part.makeCylinder(RIDGE_R, 20, V(L / 2 - 10, y, zr), V(1, 0, 0)))
    for x in (c, L - c):
        s = s.fuse(Part.makeCylinder(RIDGE_R, 16, V(x, W / 2 - 8, zr), V(0, 1, 0)))

    # lichtgeleider boven de RGB-LED
    lx, ly = sm(LED_S, LED_T)
    tube_bottom = SM_ZB + SM_T + 1.0 + 0.6
    s = s.fuse(Part.makeCylinder(3.2, H - tube_bottom + 0.01, V(lx, ly, tube_bottom)))
    s = s.cut(Part.makeCylinder(2.3, H + LID_T - LED_SKIN - tube_bottom + 1, V(lx, ly, tube_bottom - 1)))

    # drukvinger op de ESP-chip, houdt de SuperMini omlaag
    fx, fy = sm(CHIP_S, CHIP_T)
    f_bottom = SM_ZB + SM_T + 0.9 + 0.2
    s = s.fuse(box(fx - 1.5, fy - 1.5, f_bottom, 3, 3, H - f_bottom + 0.01))
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
print("overlap bak/deksel (alleen klikribbels verwacht):", round(bak.common(deksel).Volume, 2), "mm3")

export(bak, "bak-supermini.stl")
d = deksel.copy()
d.rotate(V(0, 0, H + LID_T), V(1, 0, 0), 180)
d.translate(V(0, 0, -d.BoundBox.ZMin))
export(d, "deksel-supermini.stl")
export(Part.makeCompound([bak, deksel]), "behuizing-supermini.step")
