"""Weersvoorspelling module: windchill- en zoncorrectie."""
from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Windchill JAG/TI formule is alleen geldig bij T ≤ 10°C en v ≥ 4.8 km/h
_WINDCHILL_TEMP_MAX = 10.0
_WINDCHILL_SPEED_MIN = 4.8  # km/h

_SUN_WIND_LIMIT = 15.0  # km/h – bij hogere windsnelheid geen zoncorrectie
_MAX_WINDCHILL_CORRECTION = 4.0  # °C
_MAX_SUN_CORRECTION = 4.0  # °C


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


def _windchill_correction(temp_c: float, wind_kmh: float) -> float:
    """Extra opwarming nodig door windchill, begrensd op +4°C."""
    feels_like = _windchill_temperature(temp_c, wind_kmh)
    correction = max(0.0, temp_c - feels_like)
    return min(_MAX_WINDCHILL_CORRECTION, correction)


def _sun_correction(
    condition: str,
    wind_kmh: float,
    sun_by_condition: dict[str, float],
) -> float:
    """Opwarmreductie door zonne-instaling. Nul bij te hoge windsnelheid."""
    if wind_kmh >= _SUN_WIND_LIMIT:
        return 0.0
    return sun_by_condition.get(condition, 0.0)


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
) -> tuple[float, float]:
    """Haal weersvoorspelling op en bereken correcties voor het opgegeven venster.

    Args:
        hass: Home Assistant instantie.
        weather_entity: Entity-ID van de weer-entiteit.
        hours: Aantal uren vooruit te kijken (1-6).
        sun_sunny: Zoncorrectie (°C) bij volledig zonnig weer.
        sun_partlycloudy: Zoncorrectie (°C) bij deels bewolkt weer.

    Returns:
        Tuple (windchill_correctie, zon_correctie) in °C:
        - windchill_correctie: maximum over venster (ergste kou)
        - zon_correctie: gemiddelde over venster (verwachte zonneopbrengst)
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
        return 0.0, 0.0

    # Bepaal windsnelheidseenheid van de weer-entiteit
    state = hass.states.get(weather_entity)
    wind_unit = (state.attributes.get("wind_speed_unit", "km/h") if state else "km/h") or "km/h"

    windchill_values: list[float] = []
    sun_values: list[float] = []

    for entry in forecasts[:hours]:
        temp = float(entry.get("temperature") or 0.0)
        wind_raw = float(entry.get("wind_speed") or 0.0)
        wind = _to_kmh(wind_raw, wind_unit)
        condition = str(entry.get("condition") or "")

        windchill_values.append(_windchill_correction(temp, wind))
        sun_values.append(_sun_correction(condition, wind, sun_by_condition))

    if not windchill_values:
        return 0.0, 0.0

    wc = round(max(windchill_values), 2)
    sc = round(
        min(_MAX_SUN_CORRECTION, sum(sun_values) / len(sun_values)),
        2,
    )
    return wc, sc
