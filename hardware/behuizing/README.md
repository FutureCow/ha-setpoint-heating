# Behuizing OpenTherm-bridge

Doosje voor een **ESP32-C6-DevKitC-1** (origineel van Espressif) of een **ESP32-C6 SuperMini**, samen met de
**[OpenTherm-adapter van Ihor Melnyk](https://ihormelnyk.com/opentherm_adapter)**, verbonden met losse dupont-draadjes.

Buitenmaat 66 × 59,5 × 39,5 mm (met deksel).

| Bestand | Wat |
|---|---|
| `bak.stl` | onderbak, zo printen (bodem op het bed) |
| `deksel.stl` | klikdeksel, al omgedraaid: bovenkant op het bed |
| `behuizing.step` | bak + deksel in montagestand, voor CAD |
| `behuizing.py` | het parametrische model (FreeCAD) |

## Drie versies

| | DevKitC-1 naast elkaar | DevKitC-1 onder elkaar (gestapeld) | SuperMini naast elkaar |
|---|---|---|---|
| Buitenmaat | 66 × 59,5 × 39,5 mm | 66 × 33,5 × 43 mm | 38 × 46,4 × 37,5 mm |
| Bestanden | `bak.stl`, `deksel.stl`, `behuizing.step`, `behuizing.py` | `bak-gestapeld.stl`, `deksel-gestapeld.stl`, `behuizing-gestapeld.step`, `behuizing_gestapeld.py` | `bak-supermini.stl`, `deksel-supermini.stl`, `behuizing-supermini.step`, `behuizing_supermini.py` |
| ESP-stekkers | op alle pinnen | alleen op de 3V3-pinrij (3V3, G, GPIO10, GPIO11) | alleen op de rij met 5V/GND/3V3 |
| OT-kabel | kopse wand aan de antennekant | lange voorwand, naast de adapter | kopse wand tegenover de USB |

De gestapelde versie zet de adapter onderin (pinnen omhoog, aan de USB-kant) en de DevKit erboven op 26 mm.
Daartussen zitten de rechte dupont-stekkers van de adapter (16,5 mm) plus 5,4 mm om de draadjes te buigen.
Eerst de adapter plaatsen en aansluiten, dan de DevKit erop. Met haakse pinheaders of gesoldeerde draadjes
kan `WIRE_BEND`/`DUPONT_UP` omlaag en wordt het doosje 12–15 mm lager.

## SuperMini-versie
- **Pinheaders aan de onderkant** solderen (pinnen omlaag). Alleen de rij met 5V/GND/3V3 krijgt dupont-stekkers;
  die rij zit aan de kant van de adapter. Op de andere rij (TX/RX/0–7) mogen headers zitten, maar geen stekkers.
- De SuperMini heeft geen GPIO10/11. Gebruik twee pinnen op dezelfde rij, bijvoorbeeld GPIO19 en GPIO20, en zet
  `in_pin`/`out_pin` in de ESPHome-YAML daarop. Vermijd de strapping-pinnen 8, 9 en 15. De RGB-LED zit ook hier op GPIO8.
- De print rust op twee pijlers tussen de pinrijen; de headers aan weerszijden houden hem op zijn plek.
  Een aanslag aan het eind en de USB-opening houden hem in de lengte, een vinger in het deksel drukt op de chip.
- De maten van de SuperMini komen uit een productfoto met maatpijlen (±0,3 mm). Klonen verschillen onderling:
  meet de plek van de USB-C-bus en de RGB-LED na voor je print (`USB_T`, `LED_S`/`LED_T` in `behuizing_supermini.py`).

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
