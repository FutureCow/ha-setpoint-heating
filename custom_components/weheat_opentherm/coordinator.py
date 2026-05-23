"""DataUpdateCoordinator voor WeHeat OpenTherm aanvoertemperatuur-setpoint."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_COMPENSATION_FACTOR,
    CONF_CURVE_POINTS,
    CONF_FORECAST_HOURS,
    CONF_MAX_PRICE_CORRECTION,
    CONF_OUTDOOR_TEMP_SENSOR,
    CONF_PRICE_SENSOR,
    CONF_ROOM_TEMP_SENSOR,
    CONF_SETPOINT_ENTITY,
    CONF_T_MAX,
    CONF_T_MIN,
    CONF_TARGET_TEMP,
    CONF_WEATHER_ENTITY,
    DEFAULT_COMPENSATION_FACTOR,
    DEFAULT_CURVE_POINTS,
    DEFAULT_FORECAST_HOURS,
    DEFAULT_MAX_PRICE_CORRECTION,
    DEFAULT_T_MAX,
    DEFAULT_T_MIN,
    DEFAULT_TARGET_TEMP,
    DOMAIN,
    KEY_CURRENT_PRICE,
    KEY_OUTDOOR_TEMP,
    KEY_ROOM_TEMP,
    KEY_T_DEFINITIEF,
    KEY_T_KAMER_COMP,
    KEY_T_PRIJS,
    KEY_T_STOOKLIJN,
    KEY_T_WINDCHILL,
    KEY_T_ZON,
)
from .energy_prices import async_get_price_data, calculate_price_correction
from .heating_curve import calculate_heating_curve, calculate_room_compensation
from .weather_module import async_get_forecast_corrections

_LOGGER = logging.getLogger(__name__)
_SCAN_INTERVAL = timedelta(seconds=60)


class WeheatCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Berekent elke minuut het optimale OpenTherm aanvoertemperatuur-setpoint."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialiseer de coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=_SCAN_INTERVAL,
        )
        self._entry = entry

    @property
    def entry(self) -> ConfigEntry:
        """Geef de config entry terug."""
        return self._entry

    def _opt(self, key: str, default: Any) -> Any:
        """Lees een optie uit de config entry met terugvalwaarde."""
        return self._entry.options.get(key, default)

    async def _async_update_data(self) -> dict[str, Any]:
        """Voer alle berekeningen uit en schrijf setpoint naar input_number."""
        data = self._entry.data

        outdoor_sensor: str = data[CONF_OUTDOOR_TEMP_SENSOR]
        room_sensor: str = data[CONF_ROOM_TEMP_SENSOR]
        weather_entity: str | None = data.get(CONF_WEATHER_ENTITY)
        price_sensor: str | None = data.get(CONF_PRICE_SENSOR)
        setpoint_entity: str = data.get(CONF_SETPOINT_ENTITY, "input_number.ot_setpoint")

        outdoor_temp = self._read_sensor(outdoor_sensor)
        room_temp = self._read_sensor(room_sensor)

        if outdoor_temp is None:
            raise UpdateFailed(f"Buitentemperatuursensor {outdoor_sensor} niet beschikbaar")
        if room_temp is None:
            raise UpdateFailed(f"Kamertemperatuursensor {room_sensor} niet beschikbaar")

        # Instellingen ophalen (met standaardwaarden als terugval)
        target_temp: float = self._opt(CONF_TARGET_TEMP, DEFAULT_TARGET_TEMP)
        t_min: float = self._opt(CONF_T_MIN, DEFAULT_T_MIN)
        t_max: float = self._opt(CONF_T_MAX, DEFAULT_T_MAX)
        factor: float = self._opt(CONF_COMPENSATION_FACTOR, DEFAULT_COMPENSATION_FACTOR)
        forecast_hours: int = int(self._opt(CONF_FORECAST_HOURS, DEFAULT_FORECAST_HOURS))
        max_price_corr: float = self._opt(CONF_MAX_PRICE_CORRECTION, DEFAULT_MAX_PRICE_CORRECTION)
        curve_points: list[list[float]] = self._opt(CONF_CURVE_POINTS, DEFAULT_CURVE_POINTS)

        # Module 1: Stooklijn + kamercompensatie
        t_stooklijn = calculate_heating_curve(outdoor_temp, curve_points)
        t_kamer_comp = calculate_room_compensation(target_temp, room_temp, factor)

        # Module 2: Weersvoorspelling
        t_windchill, t_zon = 0.0, 0.0
        if weather_entity:
            t_windchill, t_zon = await async_get_forecast_corrections(
                self.hass, weather_entity, forecast_hours
            )

        # Module 3: Dynamische energieprijzen
        t_prijs = 0.0
        current_price = 0.0
        if price_sensor:
            current_price, all_prices = await async_get_price_data(self.hass, price_sensor)
            t_prijs = calculate_price_correction(
                current_price, all_prices, room_temp, target_temp, max_price_corr
            )

        # Eindberekening
        t_definitief = t_stooklijn + t_kamer_comp + t_windchill - t_zon + t_prijs
        t_definitief = round(max(t_min, min(t_max, t_definitief)), 1)

        await self._async_write_setpoint(setpoint_entity, t_definitief)

        return {
            KEY_OUTDOOR_TEMP: outdoor_temp,
            KEY_ROOM_TEMP: room_temp,
            KEY_T_STOOKLIJN: t_stooklijn,
            KEY_T_KAMER_COMP: t_kamer_comp,
            KEY_T_WINDCHILL: t_windchill,
            KEY_T_ZON: t_zon,
            KEY_T_PRIJS: t_prijs,
            KEY_T_DEFINITIEF: t_definitief,
            KEY_CURRENT_PRICE: current_price,
        }

    def _read_sensor(self, entity_id: str) -> float | None:
        """Lees de numerieke waarde van een sensor; geeft None bij onbeschikbaar."""
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unknown", "unavailable", ""):
            return None
        try:
            return float(state.state)
        except (TypeError, ValueError):
            _LOGGER.warning("Kan sensorwaarde niet lezen: %s = %s", entity_id, state.state)
            return None

    async def _async_write_setpoint(self, entity_id: str, value: float) -> None:
        """Schrijf het berekende setpoint naar de input_number entiteit."""
        try:
            await self.hass.services.async_call(
                "input_number",
                "set_value",
                {"entity_id": entity_id, "value": value},
                blocking=True,
            )
            _LOGGER.debug("Setpoint %s ingesteld op %.1f°C", entity_id, value)
        except Exception as exc:  # noqa: BLE001
            _LOGGER.warning("Kan setpoint niet schrijven naar %s: %s", entity_id, exc)
