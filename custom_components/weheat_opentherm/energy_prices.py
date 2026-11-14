"""Dynamische energieprijzen module: setpoint-correctie op basis van stroomprijs."""
from __future__ import annotations

import logging
import statistics
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

_CHEAP_SIGMA = 0.5   # drempel voor "goedkoop": < gemiddelde - 0.5 * sigma
_EXP_SIGMA = 0.5     # drempel voor "duur":    > gemiddelde + 0.5 * sigma
_PREHEAT_MARGIN = 1.5  # niet voorverwarmen als kamer al warm genoeg is
# Vergelijk de huidige prijs met de komende uren; prijzen uit het verleden
# zeggen niets over of het nu beter is om te stoken dan straks.
_LOOKAHEAD = timedelta(hours=24)

PRICE_CHEAP = "goedkoop"
PRICE_NORMAL = "normaal"
PRICE_EXPENSIVE = "duur"


# Bekende attribuutsleutels voor uursrijzen in diverse HA-integraties
_PRICE_ATTR_KEYS = (
    "forecast",
    "prices",
    "prices_today",
    "prices_tomorrow",
    "hourly_prices",
    "raw_today",
    "raw_tomorrow",
)
_ITEM_VALUE_KEYS = ("value", "price", "total", "electricity_price")
_ITEM_TIME_KEYS = ("datetime", "start", "start_time", "start_date", "from", "time")

# Tibber (core) zet geen prijslijst in de sensor; die komt uit de actie
# tibber.get_prices. Resultaat per sensor bewaard: (opgehaald, prijzen).
_TIBBER_DOMAIN = "tibber"
_TIBBER_CACHE_TTL = timedelta(minutes=15)
_tibber_cache: dict[str, tuple[datetime, list[tuple[datetime | None, float]]]] = {}


def _item_time(item: dict[str, Any]) -> datetime | None:
    """Begintijd (UTC) van een prijsitem, als de integratie die meegeeft."""
    for tk in _ITEM_TIME_KEYS:
        raw = item.get(tk)
        if isinstance(raw, str):
            raw = dt_util.parse_datetime(raw)
        if isinstance(raw, datetime) and raw.tzinfo is not None:
            return dt_util.as_utc(raw)
    return None


def _extract_prices(attributes: dict[str, Any]) -> list[tuple[datetime | None, float]]:
    """Lees een lijst (begintijd, prijs) uit de sensor-attributen.

    Ondersteunt zowel lijsten van floats (zonder tijd) als lijsten van dicts
    met een prijssleutel (bijv. Nordpool, ENTSO-e, Frank Energie, Zonneplan).
    """
    for key in _PRICE_ATTR_KEYS:
        val = attributes.get(key)
        if not isinstance(val, list):
            continue
        items = list(val)
        # Vandaag en morgen in losse attributen (bv. Nordpool raw_today/raw_tomorrow):
        # samenvoegen, anders ziet de 24-uursvergelijking 's avonds alleen de
        # laatste uren van vandaag.
        if key.endswith("_today"):
            tomorrow = attributes.get(key.removesuffix("_today") + "_tomorrow")
            if isinstance(tomorrow, list):
                items += tomorrow
        prices: list[tuple[datetime | None, float]] = []
        for item in items:
            if isinstance(item, (int, float)):
                prices.append((None, float(item)))
            elif isinstance(item, dict):
                for vk in _ITEM_VALUE_KEYS:
                    if (raw := item.get(vk)) is not None:
                        try:
                            prices.append((_item_time(item), float(raw)))
                        except (TypeError, ValueError):
                            pass
                        break
        if prices:
            return prices
    return []


async def _async_tibber_prices(
    hass: HomeAssistant, price_sensor: str, nickname: str | None
) -> list[tuple[datetime | None, float]]:
    """Prijzen van de komende 24 uur via tibber.get_prices (leeg bij geen Tibber)."""
    entity = er.async_get(hass).async_get(price_sensor)
    if entity is None or entity.platform != _TIBBER_DOMAIN:
        return []
    if not hass.services.has_service(_TIBBER_DOMAIN, "get_prices"):
        return []

    now = dt_util.utcnow()
    cached = _tibber_cache.get(price_sensor)
    if cached and now - cached[0] < _TIBBER_CACHE_TTL:
        return cached[1]

    start = dt_util.as_local(now).replace(minute=0, second=0, microsecond=0)
    try:
        response = await hass.services.async_call(
            _TIBBER_DOMAIN,
            "get_prices",
            {
                "start": start.isoformat(),
                "end": (start + _LOOKAHEAD).isoformat(),
            },
            blocking=True,
            return_response=True,
        )
    except Exception as exc:  # noqa: BLE001
        _LOGGER.warning("Kan Tibber-prijzen niet ophalen: %s", exc)
        # Ook een mislukte poging onthouden: anders volgt elke minuut een
        # nieuwe aanroep en een nieuwe waarschuwing.
        entries = cached[1] if cached else []
        _tibber_cache[price_sensor] = (now, entries)
        return entries

    homes = (response or {}).get("prices") or {}
    # Meerdere huizen: neem het huis van deze sensor, anders het eerste.
    items = homes.get(nickname) if nickname in homes else next(iter(homes.values()), [])
    entries = _extract_prices({"forecast": items or []})
    _tibber_cache[price_sensor] = (now, entries)
    return entries


def _upcoming(
    entries: list[tuple[datetime | None, float]], now: datetime
) -> list[float]:
    """Prijzen van het lopende uur tot _LOOKAHEAD vooruit.

    Zonder tijden, of met minder dan twee toekomstige prijzen, wordt de hele
    lijst gebruikt.
    """
    hour_start = now.replace(minute=0, second=0, microsecond=0)
    window = [
        price
        for ts, price in entries
        if ts is not None and hour_start <= ts < hour_start + _LOOKAHEAD
    ]
    return window if len(window) >= 2 else [price for _, price in entries]


def classify_price(current_price: float, prices: list[float]) -> str:
    """Deel de huidige prijs in als goedkoop, normaal of duur t.o.v. de lijst."""
    if len(prices) < 2:
        return PRICE_NORMAL
    mean = statistics.mean(prices)
    stdev = statistics.stdev(prices)
    if stdev == 0.0:
        return PRICE_NORMAL
    if current_price < mean - _CHEAP_SIGMA * stdev:
        return PRICE_CHEAP
    if current_price > mean + _EXP_SIGMA * stdev:
        return PRICE_EXPENSIVE
    return PRICE_NORMAL


def calculate_price_correction(
    category: str,
    room_temp: float,
    target_temp: float,
    max_correction: float,
    cheap_delta: float,
    expensive_delta: float,
) -> float:
    """Bereken setpoint-correctie op basis van de prijsindeling.

    Args:
        category: PRICE_CHEAP, PRICE_NORMAL of PRICE_EXPENSIVE.
        room_temp: Actuele kamertemperatuur in °C.
        target_temp: Gewenste kamertemperatuur in °C.
        max_correction: Maximale correctie in °C (instelbaar).
        cheap_delta: Voorverwarm-bonus bij goedkope stroom (positieve °C).
        expensive_delta: Besparing bij dure stroom (positieve °C, intern negatief).

    Returns:
        Correctie in °C, begrensd op ±max_correction.
    """
    if category == PRICE_CHEAP:
        # Goedkope stroom: voorverwarmen als kamer nog niet te warm is
        correction = cheap_delta if room_temp < target_temp + _PREHEAT_MARGIN else 0.0
    elif category == PRICE_EXPENSIVE:
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
    """Lees actuele prijs en de prijzen van de komende 24 uur uit de prijssensor.

    Returns:
        Tuple (huidig_tarief, tarieven_vooruit). Bij een fout: (0.0, []).
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

    entries = _extract_prices(state.attributes)
    if not entries:
        entries = await _async_tibber_prices(
            hass, price_sensor, state.attributes.get("app_nickname")
        )
    if not entries:
        return current_price, [current_price]

    # Schaal bepalen op de hele lijst, daarna pas het venster kiezen.
    scaled = _normalize_to_state_scale(current_price, [price for _, price in entries])
    entries = [(ts, price) for (ts, _), price in zip(entries, scaled)]
    return current_price, _upcoming(entries, dt_util.utcnow())
