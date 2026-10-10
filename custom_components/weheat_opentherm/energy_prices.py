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

    Sommige integraties (bv. Zonneplan) bewaren forecast-waarden als integer
    × 1e7 terwijl de state in EUR/kWh staat. De schaal is dus een macht van
    tien; gekozen wordt de macht waarbij de huidige prijs het best in de
    lijst terug te vinden is (het lopende uur staat er zelf in).

    Schalen op de mediaan mag niet: dan valt de huidige prijs per definitie
    op de mediaan en is geen uur ooit goedkoop of duur.
    """
    if len(prices) < 2:
        return prices

    def mismatch(exponent: int) -> tuple[float, float]:
        scale = 10.0**exponent
        # Hoe ver ligt de dichtstbijzijnde geschaalde prijs van de huidige prijs?
        distance = min(abs(p * scale - current_price) for p in prices)
        # Bij gelijke afstand (bv. huidige prijs 0): kies de schaal waarbij
        # de mediaan een gangbare EUR/kWh-waarde is.
        median = abs(statistics.median(prices)) * scale
        implausible = 0.0 if 0.01 <= median < 1.0 else 1.0
        return (round(distance, 6), implausible + abs(exponent) * 1e-3)

    best = min(range(-9, 4), key=mismatch)
    if best == 0:
        return prices  # Zelfde schaal, geen normalisatie nodig
    scale = 10.0**best
    _LOGGER.debug("Prijs-forecast geschaald met factor %.0e", scale)
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
