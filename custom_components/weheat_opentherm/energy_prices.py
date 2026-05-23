"""Dynamische energieprijzen module: setpoint-correctie op basis van stroomprijs."""
from __future__ import annotations

import logging
import statistics
from typing import Any

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

_CHEAP_SIGMA = 0.5   # drempel voor "goedkoop": < gemiddelde - 0.5 * sigma
_EXP_SIGMA = 0.5     # drempel voor "duur":    > gemiddelde + 0.5 * sigma
_PREHEAT_MARGIN = 1.5  # niet voorverwarmen als kamer al warm genoeg is


# Bekende attribuutsleutels voor uursrijzen in diverse HA-integraties
_PRICE_ATTR_KEYS = (
    "forecast",
    "prices_today",
    "prices_tomorrow",
    "hourly_prices",
    "raw_today",
    "raw_tomorrow",
)
_ITEM_VALUE_KEYS = ("value", "price", "total", "electricity_price")


def _extract_prices(attributes: dict[str, Any]) -> list[float]:
    """Lees een lijst prijzen uit de sensor-attributen.

    Ondersteunt zowel lijsten van floats als lijsten van dicts met een
    prijssleutel (bijv. Tibber, EPEX Spot, Nordpool-integraties).
    """
    for key in _PRICE_ATTR_KEYS:
        val = attributes.get(key)
        if not isinstance(val, list):
            continue
        prices: list[float] = []
        for item in val:
            if isinstance(item, (int, float)):
                prices.append(float(item))
            elif isinstance(item, dict):
                for vk in _ITEM_VALUE_KEYS:
                    if (raw := item.get(vk)) is not None:
                        try:
                            prices.append(float(raw))
                        except (TypeError, ValueError):
                            pass
                        break
        if prices:
            return prices
    return []


def calculate_price_correction(
    current_price: float,
    all_prices: list[float],
    room_temp: float,
    target_temp: float,
    max_correction: float,
    cheap_delta: float,
    expensive_delta: float,
) -> float:
    """Bereken setpoint-correctie op basis van energieprijs.

    Args:
        current_price: Huidig stroomtarief in EUR/kWh.
        all_prices: Alle beschikbare tarieven voor statistische berekening.
        room_temp: Actuele kamertemperatuur in °C.
        target_temp: Gewenste kamertemperatuur in °C.
        max_correction: Maximale correctie in °C (instelbaar).
        cheap_delta: Voorverwarm-bonus bij goedkope stroom (positieve °C).
        expensive_delta: Besparing bij dure stroom (positieve °C, intern negatief).

    Returns:
        Correctie in °C, begrensd op ±max_correction.
    """
    if len(all_prices) < 2:
        return 0.0

    mean = statistics.mean(all_prices)
    stdev = statistics.stdev(all_prices)

    if stdev == 0.0:
        return 0.0

    if current_price < mean - _CHEAP_SIGMA * stdev:
        # Goedkope stroom: voorverwarmen als kamer nog niet te warm is
        correction = cheap_delta if room_temp < target_temp + _PREHEAT_MARGIN else 0.0
    elif current_price > mean + _EXP_SIGMA * stdev:
        # Dure stroom: bezuinigen
        correction = -abs(expensive_delta)
    else:
        correction = 0.0

    return round(max(-max_correction, min(max_correction, correction)), 2)


def _normalize_to_state_scale(
    current_price: float, prices: list[float]
) -> list[float]:
    """Schaal forecast-prijzen naar de eenheid van de huidige state.

    Sommige integraties (bv. Zonneplan) bewaren forecast-waarden in een
    andere eenheid (bv. integer × 1e7) dan de state. We detecteren dit door
    de mediaan met de state te vergelijken; bij >10× verschil schalen we
    uniform zodat de σ-vergelijking weer klopt.
    """
    if current_price <= 0 or len(prices) < 2:
        return prices
    median_p = statistics.median(prices)
    if median_p <= 0:
        return prices
    ratio = median_p / current_price
    if 0.1 <= ratio <= 10:
        return prices  # Zelfde schaal, geen normalisatie nodig
    scale = current_price / median_p
    _LOGGER.debug(
        "Prijs-forecast geschaald met factor %.2e (median %.4g → %.4g)",
        scale,
        median_p,
        median_p * scale,
    )
    return [p * scale for p in prices]


async def async_get_price_data(
    hass: HomeAssistant,
    price_sensor: str,
) -> tuple[float, list[float]]:
    """Lees actuele prijs en prijslijst uit de prijssensor.

    Returns:
        Tuple (huidig_tarief, alle_tarieven). Bij een fout: (0.0, []).
    """
    state = hass.states.get(price_sensor)
    if state is None:
        _LOGGER.warning("Prijssensor %s niet gevonden", price_sensor)
        return 0.0, []

    try:
        current_price = float(state.state)
    except (TypeError, ValueError):
        _LOGGER.warning("Kan waarde van prijssensor %s niet lezen: %s", price_sensor, state.state)
        return 0.0, []

    all_prices = _extract_prices(state.attributes)
    if not all_prices:
        all_prices = [current_price]
    else:
        all_prices = _normalize_to_state_scale(current_price, all_prices)

    return current_price, all_prices
