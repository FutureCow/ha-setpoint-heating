# Behuizing OpenTherm-bridge

Doosje voor een **ESP32-C6-DevKitC-1** (origineel van Espressif) en de
**[OpenTherm-adapter van Ihor Melnyk](https://ihormelnyk.com/opentherm_adapter)**, verbonden met losse dupont-draadjes.

Buitenmaat 66 × 59,5 × 39,5 mm (met deksel).

| Bestand | Wat |
|---|---|
| `bak.stl` | onderbak, zo printen (bodem op het bed) |
| `deksel.stl` | klikdeksel, al omgedraaid: bovenkant op het bed |
| `behuizing.step` | bak + deksel in montagestand, voor CAD |
| `behuizing.py` | het parametrische model (FreeCAD) |

## Twee versies

| | Naast elkaar | Onder elkaar (gestapeld) |
|---|---|---|
| Buitenmaat | 66 × 59,5 × 39,5 mm | 66 × 33,5 × 43 mm |
| Bestanden | `bak.stl`, `deksel.stl`, `behuizing.step`, `behuizing.py` | `bak-gestapeld.stl`, `deksel-gestapeld.stl`, `behuizing-gestapeld.step`, `behuizing_gestapeld.py` |
| DevKit-stekkers | op alle pinnen | alleen op de 3V3-pinrij (3V3, G, GPIO10, GPIO11) |
| OT-kabel | kopse wand aan de antennekant | lange voorwand, naast de adapter |

De gestapelde versie zet de adapter onderin (pinnen omhoog, aan de USB-kant) en de DevKit erboven op 26 mm.
Daartussen zitten de rechte dupont-stekkers van de adapter (16,5 mm) plus 5,4 mm om de draadjes te buigen.
Eerst de adapter plaatsen en aansluiten, dan de DevKit erop. Met haakse pinheaders of gesoldeerde draadjes
kan `WIRE_BEND`/`DUPONT_UP` omlaag en wordt het doosje 12–15 mm lager.

## Printen
- PLA of PETG, 0,2 mm laag, 3 wanden, geen support nodig (de USB-openingen hebben ronde hoeken
  en de tunnel van de trekontlasting is 2 mm hoog).
- De lichtgeleider boven de RGB-LED is een open gat. Wil je een dicht deksel waar het licht doorheen schijnt,
  zet dan `LED_SKIN = 0.4` en print het deksel in wit of naturel filament.

## Inbouw
- **DevKit**: met de pinnen omlaag, de USB-C-kant tegen de wand met de twee openingen. De print rust op twee pijlers
  aan de USB-kant (met lipjes langs de zijkant) en één steun aan de antennekant. Onder de print is 22 mm vrij
  voor de dupont-stekkers. Het deksel heeft een vinger die de module omlaag houdt.
- **OT-adapter**: met de pinnen omhoog over de pen in het montagegat, de OT-header naar de achterwand. Druk de print
  tussen de twee klikhaken.
- **OT-kabel**: door het gat (Ø5,5) in de kopse wand aan de antennekant. Zet hem vast met een tie-wrap door de
  tunnel achter het gat.
- **Ophangen**: twee verzonken gaten in de bodem voor schroeven van 4 mm.
- **Deksel openen**: steek een schroevendraaier in de inkeping aan de lange voorkant.

## Aanpassen
Alle maten staan bovenaan `behuizing.py`. Opnieuw genereren:

```
"C:/Program Files/FreeCAD 1.1/bin/freecadcmd.exe" behuizing.py
```

Belangrijkste knoppen: `DK_ZB` (ruimte onder de DevKit), `USB_PORTS` (haal de poort weg die je niet gebruikt),
`OT_D` (kabeldikte), `LIP_CLR` en `RIDGE_R` (hoe strak het deksel klikt), `SCREWS` (posities ophanggaten).

De maten van de DevKit komen uit de DXF-tekening van Espressif (v1.2). Die van de adapter zijn afgeleid uit de
PCB-afbeelding op de site van Ihor Melnyk, met het 2,54-mm-raster van de headers als maatstaf.
Meet die adapter na als je hem hebt (verwacht ca. 20,2 × 25,5 mm, gat Ø3).
