"""Zonne-opbrengstprognose uit dezelfde bronnen als het HA-energiedashboard.

Welke prognoses meetellen, volgt uit de zonbronnen in het energiedashboard
(`config_entry_solar_forecast`). Elke bron wordt gelezen via het energy-platform
van zijn integratie, net zoals het dashboard dat doet. Ondersteund voor het
piekvermogen: Forecast.Solar en Solar Forecast ML. Staat er in het
energiedashboard niets, dan tellen alle geladen Forecast.Solar-entries (het
gedrag van vóór v2.6.0).

Die prognose blijft beschikbaar als een update mislukt (de sensoren worden dan
wel 'unavailable').
"""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

_FORECAST_SOLAR_DOMAIN = "forecast_solar"
_PLANE_SUBENTRY = "plane"
_MODULES_POWER = "modules_power"  # W per vlak

_SFML_DOMAIN = "solar_forecast_ml"
_SFML_PANEL_GROUPS = "panel_groups"
_SFML_GROUP_POWER = "power_wp"  # W per vlakgroep

# Opbrengst per uur (kWh per kWp) die als "volle zon" telt. Zuidoost-panelen
# halen dit rond het middaguur bij heldere lucht van herfst tot voorjaar; in
# de zomer ligt het hoger, maar dan wordt er niet gestookt.
_FULL_SUN_KWH_PER_KWP = 0.6


@dataclass
class PvForecast:
    """Opgetelde uurprognose van alle gebruikte prognosebronnen."""

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


def _forecast_solar_kwp(entry: ConfigEntry) -> float:
    """Piekvermogen (kWp) van alle vlakken van één Forecast.Solar-entry."""
    total_w = sum(
        float(sub.data.get(_MODULES_POWER, 0))
        for sub in getattr(entry, "subentries", {}).values()
        if sub.subentry_type == _PLANE_SUBENTRY
    )
    if not total_w:  # oudere config-versie: vlak stond in de options
        total_w = float(entry.options.get(_MODULES_POWER, 0))
    return total_w / 1000.0


def _sfml_kwp(entry: ConfigEntry) -> float:
    """Piekvermogen (kWp) van alle vlakgroepen van Solar Forecast ML."""
    groups = entry.options.get(_SFML_PANEL_GROUPS) or entry.data.get(_SFML_PANEL_GROUPS) or []
    total_w = 0.0
    for group in groups:
        try:
            total_w += float(group.get(_SFML_GROUP_POWER) or 0)
        except (AttributeError, TypeError, ValueError):
            continue
    return total_w / 1000.0


_KWP_BY_DOMAIN = {
    _FORECAST_SOLAR_DOMAIN: _forecast_solar_kwp,
    _SFML_DOMAIN: _sfml_kwp,
}


def entry_kwp(entry: ConfigEntry) -> float:
    """Piekvermogen (kWp) van een prognose-entry; 0 als het onbekend is."""
    reader = _KWP_BY_DOMAIN.get(entry.domain)
    return reader(entry) if reader else 0.0


async def _energy_dashboard_entry_ids(hass: HomeAssistant) -> list[str]:
    """Config-entry-id's van de zonprognoses in het energiedashboard, zonder dubbele."""
    try:
        from homeassistant.components.energy.data import (  # noqa: PLC0415
            async_get_manager,
        )

        manager = await async_get_manager(hass)
    except Exception as exc:  # noqa: BLE001
        _LOGGER.debug("Energiedashboard niet leesbaar: %s", exc)
        return []
    prefs = manager.data or {}
    ids: list[str] = []
    for source in prefs.get("energy_sources", []):
        if source.get("type") != "solar":
            continue
        for entry_id in source.get("config_entry_solar_forecast") or []:
            if entry_id not in ids:
                ids.append(entry_id)
    return ids


def _forecast_entries(hass: HomeAssistant, entry_ids: list[str]) -> list[ConfigEntry]:
    """Geladen prognose-entries: die uit het energiedashboard, anders alle Forecast.Solar."""
    if entry_ids:
        candidates = [hass.config_entries.async_get_entry(i) for i in entry_ids]
    else:
        candidates = hass.config_entries.async_entries(_FORECAST_SOLAR_DOMAIN)
    return [e for e in candidates if e is not None and e.state is ConfigEntryState.LOADED]


async def _energy_platform(hass: HomeAssistant, domain: str):
    """Het energy-platform van een integratie, of None."""
    try:
        integration = await async_get_integration(hass, domain)
        return await integration.async_get_platform("energy")
    except Exception as exc:  # noqa: BLE001
        _LOGGER.debug("Geen energy-platform voor %s: %s", domain, exc)
        return None


async def async_get_pv_forecast(hass: HomeAssistant) -> PvForecast | None:
    """Tel de uurprognoses van alle gebruikte bronnen op.

    Returns None als er geen bron is, geen bron data heeft of het piekvermogen
    van geen enkele bron bekend is.
    """
    entries = _forecast_entries(hass, await _energy_dashboard_entry_ids(hass))
    if not entries:
        return None

    wh_by_time: dict[datetime, float] = defaultdict(float)
    kwp = 0.0
    for entry in entries:
        kwp_entry = entry_kwp(entry)
        if kwp_entry <= 0:
            _LOGGER.debug("Piekvermogen van %s (%s) onbekend, overgeslagen", entry.title, entry.domain)
            continue
        platform = await _energy_platform(hass, entry.domain)
        get_forecast = getattr(platform, "async_get_solar_forecast", None)
        if get_forecast is None:
            continue
        try:
            data = await get_forecast(hass, entry.entry_id)
        except Exception as exc:  # noqa: BLE001
            _LOGGER.debug("Geen prognose van %s: %s", entry.title, exc)
            continue
        if not data:
            continue
        for iso, wh in data.get("wh_hours", {}).items():
            if (ts := dt_util.parse_datetime(iso)) is not None:
                wh_by_time[ts] += float(wh)
        kwp += kwp_entry

    if kwp <= 0 or not wh_by_time:
        return None
    covered = {dt_util.as_local(t).date() for t in wh_by_time}
    return PvForecast(dict(wh_by_time), kwp, covered)
