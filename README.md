# WeHeat OpenTherm Setpoint

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/FutureCow/ha-setpoint-heating)](https://github.com/FutureCow/ha-setpoint-heating/releases)

Home Assistant custom integratie die elke minuut het optimale **OpenTherm aanvoertemperatuur-setpoint** berekent voor een **WeHeat Flint warmtepomp**. Het setpoint wordt via ESPHome op een ESP32-C6 OpenTherm gateway naar de warmtepomp gestuurd.

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
              │  WeHeat Flint      │
              │  warmtepomp        │
              └────────────────────┘
```

**Eindformule:**
```
T = stooklijn + kamercomp + windchill − zon + prijs
T = clamp(T, T_min, T_max)
```

## Vereisten

- Home Assistant **2024.1** of nieuwer
- WeHeat Flint warmtepomp met OpenTherm interface
- ESP32-C6 (of een ander OpenTherm-compatibel ESP) met DIYLESS / Ihormelnyk OpenTherm shield
- Een weer-entiteit in HA (Buienradar, OpenWeatherMap, KNMI, etc.) — optioneel maar aanbevolen
- Een dynamische energieprijssensor (EPEX Spot, Tibber, Nordpool) — optioneel
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
   | Weer-entiteit | optioneel | `weather.buienradar` |
   | Energieprijssensor | optioneel | `sensor.epex_spot_data_net` |
   | Setpoint-bridge | optioneel | leeg laten — ESPHome leest direct van integratiesensor |

4. **Doorloop de 3 options-stappen** voor temperatuurinstellingen, stooklijn en geavanceerde correcties (kun je later altijd aanpassen via CONFIGUREREN op de integratie).

### Stap 3 — ESPHome flashen

Gebruik de [meegeleverde YAML](esphome/weheat-flint-ot.yaml) als basis. Belangrijkste regels:

```yaml
opentherm:
  in_pin: GPIO10
  out_pin: GPIO11
  sync_mode: false
  t_set: stooklijn_setpoint
  ch_enable: ch_enable_switch

sensor:
  - platform: homeassistant
    id: stooklijn_setpoint
    entity_id: sensor.weheat_opentherm_aanvoersetpoint  # ← van deze integratie
    filters:
      - filter_out: nan  # behoud laatste waarde bij verbroken HA-koppeling
```

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
| **Weer** | `weather_module.py` | Windchill (JAG/TI formule, +0…4°C) + zoncorrectie (−0…4°C) over instelbaar vooruitkijkvenster |
| **Prijs** | `energy_prices.py` | μ/σ-analyse op uursrijzen; goedkoop → voorverwarmen, duur → bezuinigen (±max correctie) |

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

### Via climate-entiteit
- Gewenste kamertemperatuur

### Via options flow (3 stappen)
- **Stap 1 — Temperatuurinstellingen:** doel, min/max, factoren
- **Stap 2 — Stooklijn:** 5 (buitentemp → aanvoertemp) koppels
- **Stap 3 — Geavanceerde correcties:** voorverwarm-bonus, besparing, zonnig/deels bewolkt

### Via reset-knop
- Wis alle geleerde stooklijn-offsets

## Adaptieve stooklijn

De integratie leert over weken automatisch je 5 stooklijn-punten bij te slijpen op basis van werkelijke kamer-afwijking.

**Werking in het kort:**
- Elke 60s: bij stabiele omstandigheden bewaar `(target − kamer)` per buitentemp-bucket
- Elk uur: per curve-punt bij persistente afwijking >0.3°C → offset met `learning_rate` aanpassen
- Offsets begrensd op ±5°C, oude data vervalt na 7 dagen
- Auto-reset bij handmatige curve-wijziging

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

## Tips & FAQ

### Beter buitentemperatuur gebruiken

De WeHeat's eigen `t_outside` (via OpenTherm) fluctueert wanneer de compressor draait of ontdooit. Een **KNMI/Buienradar template-sensor** is veel stabieler:

```yaml
# configuration.yaml → template:
- sensor:
    - name: "Buitentemperatuur stabiel"
      unit_of_measurement: "°C"
      device_class: temperature
      state: "{{ state_attr('weather.buienradar', 'temperature') | float(0) }}"
```

Gebruik deze als `outdoor_temp_sensor` in de integratie-setup.

### Welke prijssensoren werken?

De integratie leest automatisch een lijst uursrijzen uit de sensor-attributen. Ondersteund:
- **EPEX Spot** (via `sensor.epex_spot_data_net.prices_today`)
- **Tibber** (via `forecast`)
- **Nordpool** (via `raw_today` / `raw_tomorrow`)
- Elke sensor met een attribuut `forecast`, `prices_today`, `prices_tomorrow`, `hourly_prices`, of `raw_today` met lijst van floats of `{value/price/total}`-dicts

### Wat als ESPHome geen verbinding heeft met HA?

In de [meegeleverde YAML](esphome/weheat-flint-ot.yaml) zit `filter_out: nan` waardoor het laatste geldige setpoint behouden blijft. Het OpenTherm-protocol heeft zelf ook een fallback (boiler valt terug op interne logica bij signaal-verlies).

### Hoe weet ik of de adaptieve laag werkt?

Kijk naar de 5 `_stooklijn_offset_*` sensoren in HA history. Na enkele dagen zie je daar kleine waarden (positief = werkt te koud, integratie verhoogt; negatief = werkt te warm). Een log-regel in de HA logs (zoek op `Adaptieve stooklijn:`) toont elke succesvolle leerstap.

### Setpoint te laag/hoog — wat nu?

1. Check `sensor.…_stooklijn_basistemperatuur` — klopt deze met je curve?
2. Check `sensor.…_kamercompensatie` — als die continu groot is, klopt je curve nog niet voor jouw woning
3. Wacht 1–2 weken; de adaptieve stooklijn corrigeert dit automatisch
4. Of: pas de curve handmatig aan via **CONFIGUREREN → Stooklijn** (offsets worden dan automatisch gereset)

## Licentie

MIT
