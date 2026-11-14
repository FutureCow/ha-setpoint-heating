# WeHeat OpenTherm Setpoint

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/FutureCow/ha-setpoint-heating)](https://github.com/FutureCow/ha-setpoint-heating/releases)

Home Assistant custom integratie die elke minuut het optimale **OpenTherm aanvoertemperatuur-setpoint** berekent voor een **WeHeat-warmtepomp** met OpenTherm-aansluiting. Het setpoint wordt via ESPHome op een ESP32-C6 OpenTherm gateway naar de warmtepomp gestuurd.

De berekening combineert klassieke stooklijn-regeling met kamercompensatie, weersvoorspelling (windchill + zon) en dynamische energieprijzen. Een ingebouwd lerend systeem fine-tunet de stooklijn over weken op basis van werkelijke kamer-afwijking.

## Inhoudsopgave

- [Hoe het werkt](#hoe-het-werkt)
- [Vereisten](#vereisten)
- [Installatie](#installatie)
  - [Stap 1 — Integratie installeren](#stap-1--integratie-installeren-via-hacs)
  - [Stap 2 — Integratie configureren](#stap-2--integratie-configureren)
  - [Stap 3 — ESPHome flashen](#stap-3--esphome-flashen)
  - [Stap 4 — Lovelace card](#stap-4--lovelace-card-optioneel)
- [Architectuur](#architectuur)
- [Aanpasbare parameters](#aanpasbare-parameters)
- [Adaptieve stooklijn](#adaptieve-stooklijn)
- [Entiteiten](#entiteiten)
- [Tips & FAQ](#tips--faq)
- [Licentie](#licentie)

## Hoe het werkt

```
┌──────────────────────────────────────────────────────────────┐
│                  Home Assistant (deze integratie)            │
│                                                              │
│   buitentemp ──┐                                             │
│   kamertemp ───┤                                             │
│   weer-entiteit┼──→ DataUpdateCoordinator (elke 60s)         │
│   prijssensor ─┘    ├ stooklijn + kamercompensatie           │
│                     ├ windchill + zon                        │
│                     ├ prijscorrectie                         │
│                     └ adaptieve offsets (zelflerend)         │
│                                                              │
│   t_setpoint ─→ sensor.weheat_opentherm_aanvoersetpoint      │
└──────────────────────┬───────────────────────────────────────┘
                       ▼
              ┌────────────────────┐
              │ ESPHome ESP32-C6   │ leest sensor uit HA
              │ + OpenTherm shield │ stuurt t_set via OT-bus
              └─────────┬──────────┘
                        ▼
              ┌────────────────────┐
              │  WeHeat            │
              │  warmtepomp        │
              └────────────────────┘
```

**Eindformule:**
```
T = stooklijn + kamercomp + windchill − zon + prijs
T = clamp(T, T_min, T_max)
```

## Vereisten

- Home Assistant **2024.11** of nieuwer
- WeHeat-warmtepomp met OpenTherm-aansluiting. Gebouwd en getest met een Flint P40; andere WeHeat-modellen met OpenTherm zouden op dezelfde manier moeten werken, maar zijn niet getest
- ESP32-C6 (of een ander OpenTherm-compatibel ESP) met DIYLESS / Ihormelnyk OpenTherm shield
- Een weer-entiteit met uurvoorspelling (Met.no, OpenWeatherMap, KNMI; niet Buienradar) — optioneel maar aanbevolen
- Een dynamische energieprijssensor: Zonneplan, Frank Energie, Tibber, Nordpool, ENTSO-e of een andere met de komende prijzen in een attribuut (zie [prijssensoren](#welke-prijssensoren-werken)) — optioneel
- HACS geïnstalleerd

## Installatie

### Stap 1 — Integratie installeren via HACS

1. Open **HACS → Integraties**
2. Klik rechtsboven op het **3-puntsmenu → Custom repositories**
3. Voeg toe:
   - **URL:** `https://github.com/FutureCow/ha-setpoint-heating`
   - **Categorie:** `Integration`
4. Zoek op "WeHeat OpenTherm" en klik **Download**
5. **Herstart Home Assistant**

### Stap 2 — Integratie configureren

1. Ga naar **Instellingen → Apparaten & diensten → Integratie toevoegen**
2. Zoek "**WeHeat OpenTherm**" en selecteer
3. Doorloop de installatiewizard:

   **Stap 1 — Sensoren**

   | Veld | Verplicht | Voorbeeld |
   |---|---|---|
   | Kamertemperatuursensor | ✅ | `sensor.woonkamer_temperatuur` |
   | Buitentemperatuursensor | ✅ | `sensor.knmi_temperatuur` of template-sensor (zie [tips](#beter-buitentemperatuur-gebruiken)) |
   | Weer-entiteit | optioneel | `weather.forecast_home` (Met.no). Moet een uurvoorspelling hebben; Buienradar heeft die niet |
   | Energieprijssensor | optioneel | `sensor.zonneplan_current_electricity_tariff` |
   | Setpoint input_number | optioneel | leeg laten — ESPHome leest direct van integratiesensor |
   | Warmtepomp status-sensor | aanbevolen | `sensor.<warmtepomp>_heat_pump` uit de WeHeat-integratie; nodig om niet te leren van zon en tapwater |

4. **Doorloop de 4 options-stappen** voor temperatuurinstellingen, stooklijn en geavanceerde correcties (kun je later altijd aanpassen via CONFIGUREREN op de integratie).

### Stap 3 — ESPHome flashen

Gebruik de [meegeleverde YAML](esphome/weheat-opentherm-bridge.yaml) als basis. Vul bovenin bij `substitutions` je eigen entiteiten in.

> **Let op de entity-ID's.** HA maakt ze aan in de taal die HA had toen je de integratie toevoegde. In het Nederlands is dat `sensor.weheat_opentherm_aanvoersetpoint`, `sensor.weheat_opentherm_actieve_modus` en `climate.weheat_opentherm_verwarmingsdoelwit`; in het Engels `sensor.weheat_opentherm_supply_setpoint`, `sensor.weheat_opentherm_active_mode` en `climate.weheat_opentherm_heating_target`. Controleer ze onder **Instellingen → Entiteiten**.

Belangrijkste regels:

```yaml
opentherm:
  in_pin: GPIO10
  out_pin: GPIO11
  sync_mode: true
  t_set: stooklijn_setpoint       # aanvoersetpoint van deze integratie
  t_room: kamertemperatuur        # gemeten kamertemperatuur
  t_room_set: kamer_setpoint      # gewenste kamertemperatuur (anders toont de WeHeat -1)

sensor:
  - platform: homeassistant
    id: stooklijn_setpoint
    entity_id: sensor.weheat_opentherm_aanvoersetpoint  # ← van deze integratie
    filters:
      - filter_out: nan  # behoud laatste waarde bij verbroken HA-koppeling
  - platform: homeassistant
    id: kamer_setpoint
    entity_id: climate.weheat_opentherm_verwarmingsdoelwit
    attribute: temperature
    filters:
      - filter_out: nan
```

`ch_enable` wordt in de YAML door een switch geschakeld die de actieve modus van de integratie volgt.

Vul je eigen `wifi`, `api`, `ota` secrets in en flash de ESP. Voeg het apparaat toe in HA via **Instellingen → Apparaten → ESPHome**.

### Stap 4 — Lovelace card (optioneel)

Voor een compacte dashboard-weergave: [ha-weheat-opentherm-card](https://github.com/FutureCow/ha-weheat-opentherm-card)

```yaml
type: custom:weheat-opentherm-card
entity_prefix: sensor.weheat_opentherm
target_temp_entity: climate.weheat_opentherm_verwarmingsdoelwit
```

## Architectuur

### Drie reken-modules

| Module | Bestand | Doel |
|---|---|---|
| **Stooklijn** | `heating_curve.py` | 5 instelbare (buitentemp → aanvoertemp) punten met lineaire interpolatie + kamercompensatie (±5°C) |
| **Weer** | `weather_module.py` | Windchill (JAG/TI-gevoelstemperatuur; alleen het verschil boven dat bij 10 km/h telt, want de stooklijn bevat gewone wind al; tussen 10 en 13°C lineair afgebouwd; de helft daarvan telt als kouder buiten, via de helling van de ingestelde stooklijn zonder geleerde offsets omgerekend naar aanvoer, +0…4°C) + zoncorrectie (−0…4°C) over instelbaar vooruitkijkvenster. Zon bij voorkeur uit **Forecast.Solar** (automatisch, zie hieronder), anders uit het weertype (alleen uren met de zon > 5° boven de horizon) |
| **Prijs** | `energy_prices.py` | μ/σ-analyse op de prijzen van de komende 24 uur; goedkoop → voorverwarmen, duur → bezuinigen (±max correctie). Eén indeling per prijsperiode: een ververste prijslijst halverwege het uur verandert de indeling niet |

### Zoncorrectie via Forecast.Solar (optioneel, automatisch)

Is de HA-integratie **Forecast.Solar** ingesteld, dan gebruikt de zoncorrectie per uur de opbrengstprognose in plaats van het weertype — dezelfde uurprognose als in het energiedashboard, opgeteld over alle Forecast.Solar-entries en -vlakken.

- Fractie volle zon = verwachte kWh in dat uur ÷ kWp ÷ 0,6 (max 1); correctie = fractie × *zonnig*-instelling.
- Werkt ook als de Forecast.Solar-sensoren tijdelijk `unavailable` zijn: de laatst opgehaalde prognose blijft gebruikt.
- Dekt de prognose een uur niet (bv. verouderd), dan valt dat uur terug op het weertype.
- Welke bron gebruikt is staat in het attribuut `zon_bron` van de aanvoersetpoint-sensor (`forecast.solar`, `weer` of `gemengd`).

### Adaptieve laag

| Module | Bestand | Doel |
|---|---|---|
| **Lerend systeem** | `learning.py` | Verzamelt kamer-afwijking per buitentemp-bucket en past de 5 stooklijn-punten bij, met persistente opslag |

## Aanpasbare parameters

Alles wat je kunt bijregelen, op één rij:

### Via number-entiteiten (dagelijkse tuning)
- Kamercompensatiefactor (0–10, default 2.0)
- Min/max aanvoertemperatuur (defaults 15/45°C)
- Vooruitkijkvenster (1–6 uur, default 3)
- Max prijscorrectie (0–5°C, default 3.0)
- Leersnelheid adaptieve stooklijn (0–0.5°C/uur, default 0.1, 0 = uit)
- Stookgrens (10–25°C buiten, default 17°C) — boven deze drempel stopt verwarmen automatisch
- Stookgrens-hysterese (0–3°C, default 1.0) — pas weer verwarmen onder stookgrens − hysterese

### Via climate-entiteit
- Gewenste kamertemperatuur
- HVAC-modus: **Verwarmen** (stooklijn-berekening) / **Uit** (warmtepomp stopt). Koelen wordt door de WeHeat intern geregeld (eigen koelstooklijn, geen OpenTherm-aansturing).

### Via options flow (4 stappen)
- **Stap 1 — Temperatuurinstellingen:** doel, min/max, factoren
- **Stap 2 — Stooklijn:** 5 (buitentemp → aanvoertemp) koppels
- **Stap 3 — Geavanceerde correcties:** voorverwarm-bonus, besparing, zonnig/deels bewolkt
- **Stap 4 — Extra sensoren:** status-sensor van de warmtepomp

### Via reset-knop
- Wis alle geleerde stooklijn-offsets

## Adaptieve stooklijn

De integratie leert over weken automatisch je 5 stooklijn-punten bij te slijpen op basis van werkelijke kamer-afwijking.

**Werking in het kort:**
- Elke 60s: bij stabiele omstandigheden bewaar `(target − kamer)` per buitentemp-bucket
- Elk uur: per curve-punt bij persistente afwijking >0.3°C → offset met `learning_rate` aanpassen
- Offsets begrensd op ±5°C, oude data vervalt na 7 dagen
- Auto-reset bij handmatige curve-wijziging (buiten- of aanvoerwaarde)
- Niet leren als het setpoint al op de minimale of maximale aanvoertemperatuur staat
- Niet leren terwijl de warmtepomp tapwater maakt (`dhw` of `legionella_prevention`, alleen met gekoppelde status-sensor)

**Stabiliteitseisen** (voorkomt leren van verkeerde signalen):
- Geen doeltemperatuur-wijziging in laatste 60 min
- Buitentemperatuur verandert <1°C/uur
- Minimaal 30 samples per bucket

**Wat je ziet:**
- 5 diagnostische sensoren `…_stooklijn_offset_1..5` met history voor convergentiegrafieken
- `number.…_leersnelheid` (slider, 0 = uit)
- `button.…_reset_adaptieve_stooklijn`

**Te verwachten gedrag:**
- Eerste 2–3 dagen: offsets blijven 0 (onvoldoende data)
- Dag 4–14: zichtbare convergentie op meest voorkomende buitentemperaturen
- Na ~3 weken: stabiel, kamer dichter bij doel

Tip: zet `leersnelheid` op 0.2 in de eerste weken voor snellere convergentie, daarna terug naar 0.05.

## Entiteiten

Onder device "WeHeat OpenTherm" verschijnen automatisch:

### Sensoren
| Entity ID | Wat | Categorie |
|---|---|---|
| `sensor.…_aanvoersetpoint` | Berekend setpoint (eindwaarde) | normaal |
| `sensor.…_buitentemperatuur` | Bron buitentemp | normaal |
| `sensor.…_kamertemperatuur` | Bron kamertemp | normaal |
| `sensor.…_stooklijn_basistemperatuur` | Basis uit interpolatie | normaal |
| `sensor.…_kamercompensatie` | Correctie (±5°C) | diagnostic |
| `sensor.…_windchill_correctie` | Correctie (0…+4°C) | diagnostic |
| `sensor.…_zoncorrectie` | Correctie (0…+4°C, wordt afgetrokken) | diagnostic |
| `sensor.…_prijscorrectie` | Correctie (±max) | diagnostic |
| `sensor.…_huidige_energieprijs` | Actuele prijs | diagnostic |
| `sensor.…_stooklijn_offset_1..5` | Adaptieve offsets per curve-punt | diagnostic |

### Bediening
- `climate.…_verwarmingsdoelwit` — doeltemperatuur
- `number.…_kamercompensatiefactor`, `_minimale_aanvoertemperatuur`, `_maximale_aanvoertemperatuur`, `_vooruitkijkvenster`, `_max_prijscorrectie`, `_leersnelheid` — instelbare parameters
- `button.…_reset_adaptieve_stooklijn` — wis leerstaat

## Stookgrens (zomerstop)

De climate-mode is wat jij wilt; de **actieve modus** is wat er echt gebeurt na een buitentemp-check.

- **Stookgrens** (default 17°C): bij HEAT-modus + buitentemp ≥ stookgrens → actieve modus wordt `off`, warmtepomp stopt.
- **Hysterese** (default 1°C): daarna pas weer `heat` als buitentemp < stookgrens − hysterese (dus < 16°C). Daartussen blijft de vorige stand staan, zodat schommelen rond de grens niet steeds aan/uit schakelt.

De ESP leest `sensor.weheat_opentherm_actieve_modus` rechtstreeks en zet `ch_enable` op die basis. Geen `t_set` meer geschreven in `off`.

Voorbeeld: kamer 21°C, buiten 20°C, climate=HEAT, stookgrens=17 → 20 ≥ 17 → **actieve modus = off** → warmtepomp doet niks. Zet je stookgrens op 25 dan zou hij wél verwarmen.

## Koelen

**Niet aangestuurd** door deze integratie — de WeHeat regelt koeling intern via een eigen koelstooklijn (geen OpenTherm-pad). Zet de koelmodus aan/uit via de WeHeat-app of de fysieke knop. De climate-entiteit heeft daarom alleen **Verwarmen** en **Uit**.

### Maar wel zichtbaar maken
Sinds v2.1 kun je de status-sensor van de warmtepomp (**`sensor.<warmtepomp>_heat_pump`** uit de officiële WeHeat-integratie) koppelen via *Configureren → Extra sensoren → Warmtepomp status-sensor*. De climate-tegel toont dan via `hvac_action`:

| Pomp-status | Climate-tegel laat zien |
|---|---|
| Verwarming | 🔥 Verwarmen |
| Koelen | ❄️ Koelen |
| Stand-by | 💤 Inactief |
| Mode = Uit + pomp Stand-by | ⏻ Uit |

Actief verwarmen/koelen wint altijd van de mode-keuze — je ziet dus ook wanneer de warmtepomp zelf besluit te koelen ondanks `climate=HEAT/OFF`.

## Tips & FAQ

### Beter buitentemperatuur gebruiken

De WeHeat's eigen `t_outside` (via OpenTherm) fluctueert wanneer de compressor draait of ontdooit. Een **KNMI/Buienradar template-sensor** is veel stabieler:

```yaml
# configuration.yaml → template:
- sensor:
    - name: "Buitentemperatuur stabiel"
      unit_of_measurement: "°C"
      device_class: temperature
      state: "{{ state_attr('weather.buienradar', 'temperature') }}"
      availability: "{{ state_attr('weather.buienradar', 'temperature') is number }}"
```

Gebruik deze als `outdoor_temp_sensor` in de integratie-setup. Gebruik geen `float(0)`: valt het weer weg, dan rekent de integratie anders met 0 °C buiten en stookt ze veel te warm. Met `availability` wordt de sensor `unavailable` en houdt de ESP het laatste setpoint vast.

### Welke prijssensoren werken?

De integratie leest de komende prijzen uit een attribuut van de prijssensor. Dat attribuut moet een lijst zijn, met getallen of met items als `{start/time/from: tijd, value/price/total/electricity_price: prijs}`. Gezocht wordt in `forecast`, `prices`, `prices_today` (+ `prices_tomorrow`), `hourly_prices` en `raw_today` (+ `raw_tomorrow`).

- **Zonneplan**: getest (`forecast` → `electricity_price`). Zonneplan slaat de lijst op als integer × 1e7; de integratie herkent dat schaalverschil zelf.
- **Frank Energie** (HACS): kies de sensor met de huidige all-in prijs; die heeft attribuut `prices` (`from`/`price`).
- **Tibber** (standaard in HA): de sensor heeft geen prijslijst; de integratie haalt de komende 24 uur op via de actie `tibber.get_prices` (hooguit eens per 15 minuten).
- **Nordpool** (HACS, `raw_today`/`raw_tomorrow`) en **ENTSO-e** (`prices`) volgen dit formaat.
- Frank, Tibber, Nordpool en ENTSO-e zijn nagebootst op basis van hun broncode, niet getest met een echt account.
- Heeft je sensor geen prijslijst in een attribuut, dan blijft de prijscorrectie 0. De rest werkt gewoon.

Controleer het in het attribuut `prijs_correctie` van de aanvoersetpoint-sensor: bij een werkende koppeling wisselt het over de dag tussen −2, 0 en +2.

### Wat als een temperatuursensor wegvalt?

- **Eerste 15 minuten:** de integratie rekent niet en de ESP houdt het laatste setpoint vast. Een korte hapering (bv. Bluetooth) laat het setpoint zo niet verspringen.
- **Daarna, kamersensor weg:** de integratie rekent door zonder kamercompensatie. Het setpoint blijft het weer volgen.
- **Daarna, buitensensor weg:** de integratie gebruikt de huidige temperatuur van de weer-entiteit. Is er geen weer-entiteit, dan blijft het laatste setpoint staan.
- Zolang de terugval actief is, leert de stooklijn niet. Het attribuut `terugval` van de aanvoersetpoint-sensor en een waarschuwing in het log laten zien dat het speelt.

### Wat als ESPHome geen verbinding heeft met HA?

In de [meegeleverde YAML](esphome/weheat-opentherm-bridge.yaml) zit `filter_out: nan` waardoor het laatste geldige setpoint behouden blijft. De CV-schakelaar reageert alleen op de modus `heat` of `off`; bij `unavailable` (bv. terwijl HA herstart) blijft de laatste stand staan, zodat de warmtepomp niet even uitgaat. Het OpenTherm-protocol heeft zelf ook een fallback (boiler valt terug op interne logica bij signaal-verlies).

### Hoe weet ik of de adaptieve laag werkt?

Kijk naar de 5 `_stooklijn_offset_*` sensoren in HA history. Na enkele dagen zie je daar kleine waarden (positief = werkt te koud, integratie verhoogt; negatief = werkt te warm). Een log-regel in de HA logs (zoek op `Adaptieve stooklijn:`) toont elke succesvolle leerstap.

### Setpoint te laag/hoog — wat nu?

1. Check `sensor.…_stooklijn_basistemperatuur` — klopt deze met je curve?
2. Check `sensor.…_kamercompensatie` — als die continu groot is, klopt je curve nog niet voor jouw woning
3. Wacht 1–2 weken; de adaptieve stooklijn corrigeert dit automatisch
4. Of: pas de curve handmatig aan via **CONFIGUREREN → Stooklijn** (offsets worden dan automatisch gereset)

## Licentie

MIT
