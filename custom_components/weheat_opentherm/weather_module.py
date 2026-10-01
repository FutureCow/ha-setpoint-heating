"""Weersvoorspelling module: windchill- en zoncorrectie."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.sun import get_astral_location
from homeassistant.util import dt as dt_util

from .solar_forecast import async_get_pv_forecast

_LOGGER = logging.getLogger(__name__)

# Windchill JAG/TI formule is alleen geldig bij T ≤ 10°C en v ≥ 4.8 km/h
_WINDCHILL_TEMP_MAX = 10.0
_WINDCHILL_SPEED_MIN = 4.8  # km/h

_SUN_WIND_LIMIT = 15.0  # km/h – bij hogere windsnelheid geen zoncorrectie
_MAX_SUN_CORRECTION = 4.0  # °C
# Onder deze zonshoogte geen zoncorrectie. Nodig omdat "partlycloudy" ook
# 's nachts gebruikt wordt (alleen "sunny" heeft een nachtvariant).
_SUN_MIN_ELEVATION = 5.0  # graden

SUN_SOURCE_PV = "forecast.solar"
SUN_SOURCE_WEATHER = "weer"
SUN_SOURCE_MIXED = "gemengd"


def _windchill_temperature(temp_c: float, wind_kmh: float) -> float:
    """Bereken gevoelstemperatuur (JAG/TI formule).

    Args:
        temp_c: Luchttemperatuur in °C.
        wind_kmh: Windsnelheid in km/h.

    Returns:
        Gevoelstemperatuur in °C; gelijk aan temp_c buiten geldig bereik.
    """
    if temp_c > _WINDCHILL_TEMP_MAX or wind_kmh < _WINDCHILL_SPEED_MIN:
        return temp_c
    v016 = wind_kmh**0.16
    return 13.12 + 0.6215 * temp_c - 11.37 * v016 + 0.3965 * temp_c * v016


def _windchill_delta(temp_c: float, wind_kmh: float) -> float:
    """Verschil lucht- minus gevoelstemperatuur in buiten-°C (≥ 0).

    Dit is géén aanvoer-correctie: heating_curve.calculate_windchill_correction
    rekent het via de stooklijn om naar aanvoer-°C.
    """
    feels_like = _windchill_temperature(temp_c, wind_kmh)
    return max(0.0, temp_c - feels_like)


def _sun_correction(
    condition: str,
    wind_kmh: float,
    sun_by_condition: dict[str, float],
) -> float:
    """Opwarmreductie door zonne-instaling. Nul bij te hoge windsnelheid."""
    if wind_kmh >= _SUN_WIND_LIMIT:
        return 0.0
    return sun_by_condition.get(condition, 0.0)


def _sun_is_up(hass: HomeAssistant, forecast_time: str | None) -> bool:
    """True als de zon midden in het voorspelde uur boven _SUN_MIN_ELEVATION staat.

    Zonder (leesbaar) tijdstip wordt de zon als op beschouwd, zodat de
    correctie dan alleen op de condition blijft leunen.
    """
    when: datetime | None = dt_util.parse_datetime(forecast_time) if forecast_time else None
    if when is None:
        return True
    location, elevation = get_astral_location(hass)
    sun_elevation = location.solar_elevation(when + timedelta(minutes=30), elevation)
    return sun_elevation >= _SUN_MIN_ELEVATION


def _to_kmh(wind_speed: float, unit: str) -> float:
    """Converteer windsnelheid naar km/h."""
    if unit == "m/s":
        return wind_speed * 3.6
    if unit == "mph":
        return wind_speed * 1.60934
    return wind_speed  # Ga uit van km/h


async def async_get_forecast_corrections(
    hass: HomeAssistant,
    weather_entity: str,
    hours: int,
    sun_sunny: float,
    sun_partlycloudy: float,
) -> tuple[float, float, str | None]:
    """Haal weersvoorspelling op en bereken correcties voor het opgegeven venster.

    De zoncorrectie per uur komt bij voorkeur uit de Forecast.Solar-prognose
    (fractie van volle zon × sun_sunny); valt die weg, dan uit het weertype.

    Args:
        hass: Home Assistant instantie.
        weather_entity: Entity-ID van de weer-entiteit.
        hours: Aantal uren vooruit te kijken (1-6).
        sun_sunny: Zoncorrectie (°C) bij volledig zonnig weer.
        sun_partlycloudy: Zoncorrectie (°C) bij deels bewolkt weer.

    Returns:
        Tuple (windchill_delta, zon_correctie, zon_bron):
        - windchill_delta: buiten-°C, maximum over venster (ergste kou)
        - zon_correctie: aanvoer-°C, gemiddelde over venster (verwachte zonneopbrengst)
        - zon_bron: SUN_SOURCE_PV, SUN_SOURCE_WEATHER of SUN_SOURCE_MIXED; None zonder data
    """
    sun_by_condition = {
        "sunny": sun_sunny,
        "partlycloudy": sun_partlycloudy,
    }
    try:
        response = await hass.services.async_call(
            "weather",
            "get_forecasts",
            {"entity_id": weather_entity, "type": "hourly"},
            blocking=True,
            return_response=True,
        )
        forecasts: list[dict] = response.get(weather_entity, {}).get("forecast", [])
    except Exception as exc:  # noqa: BLE001
        _LOGGER.warning("Kan weersvoorspelling niet ophalen voor %s: %s", weather_entity, exc)
        return 0.0, 0.0, None

    # Bepaal windsnelheidseenheid van de weer-entiteit
    state = hass.states.get(weather_entity)
    wind_unit = (state.attributes.get("wind_speed_unit", "km/h") if state else "km/h") or "km/h"

    pv = await async_get_pv_forecast(hass)

    windchill_values: list[float] = []
    sun_values: list[float] = []
    sources: set[str] = set()

    for entry in forecasts[:hours]:
        temp = float(entry.get("temperature") or 0.0)
        wind_raw = float(entry.get("wind_speed") or 0.0)
        wind = _to_kmh(wind_raw, wind_unit)
        condition = str(entry.get("condition") or "")

        windchill_values.append(_windchill_delta(temp, wind))

        forecast_time = entry.get("datetime")
        hour_start = dt_util.parse_datetime(forecast_time) if forecast_time else None
        fraction = pv.sun_fraction(hour_start) if pv and hour_start else None
        if fraction is not None:
            sources.add(SUN_SOURCE_PV)
            sun = 0.0 if wind >= _SUN_WIND_LIMIT else fraction * sun_sunny
        else:
            sources.add(SUN_SOURCE_WEATHER)
            sun = (
                _sun_correction(condition, wind, sun_by_condition)
                if _sun_is_up(hass, forecast_time)
                else 0.0
            )
        sun_values.append(sun)

    if not windchill_values:
        return 0.0, 0.0, None

    wc = round(max(windchill_values), 2)
    sc = round(
        min(_MAX_SUN_CORRECTION, sum(sun_values) / len(sun_values)),
        2,
    )
    source = sources.pop() if len(sources) == 1 else (SUN_SOURCE_MIXED if sources else None)
    return wc, sc, source
