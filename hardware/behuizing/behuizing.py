"""Behuizing voor de OpenTherm-bridge: ESP32-C6-DevKitC-1 + Ihor Melnyk OpenTherm-adapter.

Draaien (maakt STL's en een STEP naast dit script):
    "C:/Program Files/FreeCAD 1.1/bin/freecadcmd.exe" behuizing.py

Alle maten in mm. Oorsprong = binnenhoek op de bovenkant van de bodem:
x = lengte (USB-kant x=0, antennekant x=L), y = breedte (DevKit-kant y=0), z omhoog.

Bronnen:
- DevKitC-1 v1.2: https://dl.espressif.com/dl/schematics/esp32-c6-devkitc-1-dimensions_v1.2.dxf
  Print 51,8 x 25,4; WROOM-module 18 x 25,5 x 3,2 steekt 6,35 voorbij de print uit;
  USB-C-bussen 8,64 breed, 0,4 voorbij de rand; RGB-LED (GPIO8) op u=6,5 v=18.
- OT-adapter: https://ihormelnyk.com/opentherm_adapter (PCB-afbeelding, 2,54-raster als maatstaf)
  Print ca. 20,2 x 25,5, één gat Ø3 op a=2,84 b=9,0, headers met pinnen omhoog.
"""
import os
import FreeCAD as App
import Part
from FreeCAD import Vector as V

OUT = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- algemeen
WALL = 2.0          # wanddikte
FLOOR = 2.5         # bodemdikte (ruimte voor verzonken schroefgaten)
LID_T = 2.0         # dekseldikte
L, W, H = 62.0, 55.5, 35.0   # binnenmaten
R_OUT = 3.0         # afronding buitenhoeken
R_IN = R_OUT - WALL

# klikdeksel
LIP_H = 5.0         # hoogte van de rand onder het deksel
LIP_T = 1.2         # dikte van die rand (moet kunnen veren)
LIP_CLR = 0.25      # speling rand <-> binnenwand
RIDGE_R = 0.6       # klikribbel op de rand
GROOVE_D = 0.7      # diepte van de groef in de wand
GROOVE_Z = H - LIP_H / 2

# ---------------------------------------------------------------- DevKitC-1
DK_X = 1.0          # USB-rand van de print, vanaf de binnenwand
DK_Y = 2.0          # u=25,4-rand (pinrij G/TX/RX...) van de print
DK_ZB = 22.0        # onderkant print: ruimte voor dupont-stekkers op de pinnen eronder
DK_LEN, DK_WID, DK_T = 51.8, 25.4, 1.6
DK_ANT = 6.35       # module steekt voorbij de print uit
MOD_H = 3.2         # WROOM-module
USB_W, USB_H = 13.0, 7.5     # opening voor stekker met omhulsel
USB_PORTS = [5.5, 19.9]      # u-midden van UART- en USB-poort; haal er een weg als je hem niet gebruikt
LED_U, LED_V = 6.5, 18.0
LED_SKIN = 0.0      # 0 = open gat; 0.4 = twee laagjes dicht (licht schijnt door bij wit/naturel filament)


def dk(u, v):
    """DevKit-coördinaten (u over de breedte vanaf de 3V3-rij, v vanaf de USB-rand) -> box x, y."""
    return DK_X + v, DK_Y + DK_WID - u


# ---------------------------------------------------------------- OT-adapter
AD_W, AD_LEN, AD_T = 20.2, 25.5, 1.6   # a-richting, b-richting
AD_X = 18.0         # b=0 (kant IN/OUT-header)
AD_Y = 52.7         # a=0 (kant OT-header)
AD_ZB = 4.0         # onderkant print
AD_HOLE = (2.84, 9.0)
PEG_D = 2.7


def ad(a, b):
    return AD_X + b, AD_Y - a


# ---------------------------------------------------------------- kabel en montage
OT_D = 5.5          # gat voor de OpenTherm-kabel in de kopse wand (antennekant)
OT_Y, OT_Z = 48.0, 8.0
SCREW_D, SCREW_HEAD = 4.2, 8.0
SCREWS = [(8.0, 43.0), (52.0, 37.0)]


# ================================================================= hulpfuncties
def box(x, y, z, lx, ly, lz):
    return Part.makeBox(lx, ly, lz, V(x, y, z))


def rbox(x, y, z, lx, ly, lz, r):
    """Kubus met afgeronde verticale ribben."""
    if r <= 0.01:
        return box(x, y, z, lx, ly, lz)
    s = box(x + r, y, z, lx - 2 * r, ly, lz).fuse(box(x, y + r, z, lx, ly - 2 * r, lz))
    for cx in (x + r, x + lx - r):
        for cy in (y + r, y + ly - r):
            s = s.fuse(Part.makeCylinder(r, lz, V(cx, cy, z)))
    return s.removeSplitter()


def slot_x(x0, length, yc, zc, wy, hz, r):
    """Afgerond rechthoekig gat in de x-richting."""
    r = min(r, wy / 2, hz / 2)
    s = box(x0, yc - wy / 2 + r, zc - hz / 2, length, wy - 2 * r, hz)
    s = s.fuse(box(x0, yc - wy / 2, zc - hz / 2 + r, length, wy, hz - 2 * r))
    for dy in (-1, 1):
        for dz in (-1, 1):
            s = s.fuse(Part.makeCylinder(r, length, V(x0, yc + dy * (wy / 2 - r), zc + dz * (hz / 2 - r)), V(1, 0, 0)))
    return s


def wedge_y(x, y_face, z_low, length, depth, height, inward, straight=0.6):
    """Klikneus in het yz-vlak, `inward` = +1/-1 richting de print, over lengte in x.
    Eerst `straight` mm recht (vasthouden), daarna schuin aflopend (inklikken).
    Minstens 0,8 diep, anders print een 0,4-nozzle het neusje niet."""
    p = [V(x, y_face, z_low), V(x, y_face + inward * depth, z_low),
         V(x, y_face + inward * depth, z_low + straight),
         V(x, y_face, z_low + height), V(x, y_face, z_low)]
    return Part.Face(Part.makePolygon(p)).extrude(V(length, 0, 0))


# ================================================================= bak
def make_box():
    s = rbox(-WALL, -WALL, -FLOOR, L + 2 * WALL, W + 2 * WALL, FLOOR + H, R_OUT)
    s = s.cut(rbox(0, 0, 0, L, W, H + 1, R_IN))

    # groef voor het klikdeksel, rondom
    s = s.cut(rbox(-GROOVE_D, -GROOVE_D, GROOVE_Z - 0.8, L + 2 * GROOVE_D, W + 2 * GROOVE_D, 1.6, R_IN + GROOVE_D))
    # wrikinkeping aan de lange voorkant, voor een schroevendraaier
    s = s.cut(box(L / 2 - 5, -WALL - 0.1, H - 1.5, 10, 1.1, 1.6))

    # USB-C-openingen in de kopse wand x=0
    usb_z = DK_ZB + DK_T + 1.6
    for u in USB_PORTS:
        _, yc = dk(u, 0)
        s = s.cut(slot_x(-WALL - 1, WALL + 1.5, yc, usb_z, USB_W, USB_H, 2.5))

    # OpenTherm-kabel in de kopse wand x=L, met trekontlasting (tunnel voor tie-wrap)
    s = s.cut(Part.makeCylinder(OT_D / 2, WALL + 2, V(L - 0.5, OT_Y, OT_Z), V(1, 0, 0)))
    bridge_top = OT_Z - OT_D / 2
    br = box(L - 11.5, OT_Y - 4, 0, 6, 8, bridge_top)
    br = br.cut(box(L - 10.5, OT_Y - 5, 0, 4, 10, 2.0))
    s = s.fuse(br)

    # schroefgaten in de bodem, verzonken aan de binnenkant
    for (x, y) in SCREWS:
        s = s.cut(Part.makeCylinder(SCREW_D / 2, FLOOR + 2, V(x, y, -FLOOR - 1)))
        depth = (SCREW_HEAD - SCREW_D) / 2
        s = s.cut(Part.makeCone(SCREW_D / 2, SCREW_HEAD / 2, depth, V(x, y, -depth)))
        s = s.cut(Part.makeCylinder(SCREW_HEAD / 2, 1, V(x, y, -0.001)))

    # ---- DevKit: twee pijlers aan de USB-kant met zijlipjes (onder de print zitten daar geen pinnen)
    x0, x1 = DK_X + 0.5, DK_X + 9.0
    y_lo, y_hi = DK_Y, DK_Y + DK_WID
    s = s.fuse(box(x0, y_lo - 1.5, 0, x1 - x0, 7.5, DK_ZB))
    s = s.fuse(box(x0, y_lo - 1.5, DK_ZB, x1 - x0, 1.2, 1.5))
    s = s.fuse(box(x0, y_hi - 6.0, 0, x1 - x0, 7.5, DK_ZB))
    s = s.fuse(box(x0, y_hi + 0.3, DK_ZB, x1 - x0, 1.2, 1.5))
    # steun aan de antennekant, tussen de pinrijen
    ax0, ay1 = dk(18.4, 44.0)
    _, ay0 = dk(7.0, 0)
    s = s.fuse(box(ax0, ay1, 0, 6.0, ay0 - ay1, DK_ZB))
    # aanslag achter de print (niet onder de module), verbonden met een lage dwarsbalk
    sx = DK_X + DK_LEN + 0.3
    s = s.fuse(box(sx, y_lo + 0.3, 0, 3.0, DK_WID - 0.6, 3.0))
    for yy in (y_lo + 0.3, y_hi - 3.3):
        s = s.fuse(box(sx, yy, 0, 3.0, 3.0, DK_ZB + 2.5))

    # ---- OT-adapter: pen in het montagegat, steunpootjes op de hoeken, twee klikhaken
    hx, hy = ad(*AD_HOLE)
    s = s.fuse(Part.makeCylinder(2.6, AD_ZB, V(hx, hy, 0)))
    s = s.fuse(Part.makeCylinder(PEG_D / 2, AD_ZB + AD_T + 1.0, V(hx, hy, 0)))
    # 1,5 mm: de soldeerpunten van de headers zitten 2 mm van de rand
    for a, b in ((0, 0), (AD_W - 1.5, 0), (0, AD_LEN - 1.5), (AD_W - 1.5, AD_LEN - 1.5)):
        cx, cy = ad(a, b)
        s = s.fuse(box(cx, cy - 1.5, 0, 1.5, 1.5, AD_ZB))
    hook_l = 6.0
    hx0 = AD_X + AD_LEN / 2 - hook_l / 2
    top = AD_ZB + AD_T
    # haak aan de OT-kant (y groot) en aan de andere kant (y klein)
    y_face_hi = AD_Y + 0.2
    s = s.fuse(box(hx0, y_face_hi, 0, hook_l, 1.2, top + 1.7))
    s = s.fuse(wedge_y(hx0, y_face_hi, top + 0.05, hook_l, 0.8, 1.6, -1))
    y_face_lo = AD_Y - AD_W - 0.2
    s = s.fuse(box(hx0, y_face_lo - 1.2, 0, hook_l, 1.2, top + 1.7))
    s = s.fuse(wedge_y(hx0, y_face_lo, top + 0.05, hook_l, 0.8, 1.6, +1))

    return s.removeSplitter()


# ================================================================= deksel (in montagestand)
def make_lid():
    s = rbox(-WALL, -WALL, H, L + 2 * WALL, W + 2 * WALL, LID_T, R_OUT)
    c = LIP_CLR
    ring = rbox(c, c, H - LIP_H, L - 2 * c, W - 2 * c, LIP_H + 0.01, max(R_IN - c, 0.2))
    ring = ring.cut(rbox(c + LIP_T, c + LIP_T, H - LIP_H - 1, L - 2 * (c + LIP_T), W - 2 * (c + LIP_T), LIP_H + 2, 0.2))
    s = s.fuse(ring)

    # klikribbels op de buitenkant van de rand
    zr = GROOVE_Z
    for y in (c, W - c):
        s = s.fuse(Part.makeCylinder(RIDGE_R, 24, V(L / 2 - 12, y, zr), V(1, 0, 0)))
    for x in (c, L - c):
        s = s.fuse(Part.makeCylinder(RIDGE_R, 16, V(x, W / 2 - 8, zr), V(0, 1, 0)))
    # het halve cilinderdeel aan de binnenkant van de rand weer weg (blijft vol materiaal = rand)

    # lichtgeleider boven de RGB-LED
    lx, ly = dk(LED_U, LED_V)
    tube_bottom = DK_ZB + DK_T + 1.0 + 0.6
    s = s.fuse(Part.makeCylinder(3.5, H - tube_bottom + 0.01, V(lx, ly, tube_bottom)))
    s = s.cut(Part.makeCylinder(2.5, H + LID_T - LED_SKIN - tube_bottom + 1, V(lx, ly, tube_bottom - 1)))

    # drukvinger op de WROOM-module, houdt de DevKit omlaag
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
        Mesh.Mesh(m).write(path, "STL")   # binair
    else:
        shape.exportStep(path)
    print("geschreven:", path)


bak = make_box()
deksel = make_lid()
for nm, sh in (("bak", bak), ("deksel", deksel)):
    print(nm, "geldig:", sh.isValid(), "volume:", round(sh.Volume / 1000, 1), "cm3", "bbox:", sh.BoundBox)

# controle: deksel mag de bak niet raken (behalve de bedoelde klikribbels in de groef)
overlap = bak.common(deksel).Volume
print("overlap bak/deksel (alleen klikribbels verwacht):", round(overlap, 2), "mm3")

export(bak, "bak.stl")
# deksel omgedraaid zodat de bovenkant op het printbed ligt
d = deksel.copy()
d.rotate(V(0, 0, H + LID_T), V(1, 0, 0), 180)
d.translate(V(0, 0, -d.BoundBox.ZMin))
export(d, "deksel.stl")
export(Part.makeCompound([bak, deksel]), "behuizing.step")
