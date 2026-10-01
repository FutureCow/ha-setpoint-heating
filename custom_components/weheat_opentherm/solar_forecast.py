"""Zonne-opbrengstprognose uit de Forecast.Solar-integratie (indien aanwezig).

Leest dezelfde uurprognose die het HA-energiedashboard toont, via het
energy-platform van forecast_solar. Die prognose blijft beschikbaar als een
update mislukt (de sensoren worden dan wel 'unavailable').
"""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

_FORECAST_SOLAR_DOMAIN = "forecast_solar"
_PLANE_SUBENTRY = "plane"
_MODULES_POWER = "modules_power"  # W per vlak

# Opbrengst per uur (kWh per kWp) die als "volle zon" telt. Zuidoost-panelen
# halen dit rond het middaguur bij heldere lucht van herfst tot voorjaar; in
# de zomer ligt het hoger, maar dan wordt er niet gestookt.
_FULL_SUN_KWH_PER_KWP = 0.6


@dataclass
class PvForecast:
    """Opgetelde uurprognose van alle Forecast.Solar-entries."""

    wh_by_time: dict[datetime, float]
    kwp: float
    covered_dates: set

    def sun_fraction(self, hour_start: datetime) -> float | None:
        """Fractie 0–1 van 'volle zon' in het uur vanaf hour_start.

        None als de prognose die dag niet dekt (dan moet de aanroeper
        terugvallen op het weertype).
        """
        local_start = dt_util.as_local(hour_start)
        if local_start.date() not in self.covered_dates:
            return None
        hour_end = hour_start + timedelta(hours=1)
        wh = sum(v for t, v in self.wh_by_time.items() if hour_start <= t < hour_end)
        return min(1.0, wh / 1000.0 / self.kwp / _FULL_SUN_KWH_PER_KWP)


def _entry_kwp(entry: ConfigEntry) -> float:
    """Piekvermogen (kWp) van alle vlakken van één Forecast.Solar-entry."""
    total_w = sum(
        float(sub.data.get(_MODULES_POWER, 0))
        for sub in getattr(entry, "subentries", {}).values()
        if sub.subentry_type == _PLANE_SUBENTRY
    )
    if not total_w:  # oudere config-versie: vlak stond in de options
        total_w = float(entry.options.get(_MODULES_POWER, 0))
    return total_w / 1000.0


async def async_get_pv_forecast(hass: HomeAssistant) -> PvForecast | None:
    """Tel de uurprognoses van alle geladen Forecast.Solar-entries op.

    Returns None als Forecast.Solar niet is ingesteld of nog geen data heeft.
    """
    entries = [
        e
        for e in hass.config_entries.async_entries(_FORECAST_SOLAR_DOMAIN)
        if e.state is ConfigEntryState.LOADED
    ]
    if not entries:
        return None

    try:
        from homeassistant.components.forecast_solar.energy import (  # noqa: PLC0415
            async_get_solar_forecast,
        )
    except ImportError:
        _LOGGER.debug("forecast_solar energy-platform niet beschikbaar")
        return None

    wh_by_time: dict[datetime, float] = defaultdict(float)
    kwp = 0.0
    for entry in entries:
        entry_kwp = _entry_kwp(entry)
        try:
            data = await async_get_solar_forecast(hass, entry.entry_id)
        except Exception as exc:  # noqa: BLE001
            _LOGGER.debug("Geen prognose van %s: %s", entry.title, exc)
            continue
        if not data or entry_kwp <= 0:
            continue
        for iso, wh in data.get("wh_hours", {}).items():
            if (ts := dt_util.parse_datetime(iso)) is not None:
                wh_by_time[ts] += float(wh)
        kwp += entry_kwp

    if kwp <= 0 or not wh_by_time:
        return None
    covered = {dt_util.as_local(t).date() for t in wh_by_time}
    return PvForecast(dict(wh_by_time), kwp, covered)
