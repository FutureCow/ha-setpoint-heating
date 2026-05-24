"""Climate-entiteit voor het instellen van de gewenste kamertemperatuur."""
from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_HVAC_MODE,
    CONF_TARGET_TEMP,
    DEFAULT_HVAC_MODE,
    DEFAULT_TARGET_TEMP,
    DOMAIN,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    KEY_ROOM_TEMP,
)
from .coordinator import WeheatCoordinator

_MODE_FROM_STR = {
    HVAC_MODE_HEAT: HVACMode.HEAT,
    HVAC_MODE_OFF: HVACMode.OFF,
}
_STR_FROM_MODE = {v: k for k, v in _MODE_FROM_STR.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Registreer de climate-entiteit."""
    coordinator: WeheatCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([WeheatClimate(coordinator, entry)])


class WeheatClimate(CoordinatorEntity[WeheatCoordinator], ClimateEntity):
    """Climate-entiteit voor het gewenste kamertemperatuur-setpoint.

    De ingestelde doeltemperatuur wordt opgeslagen in de config entry options
    en direct door de coordinator meegenomen bij de volgende berekening.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "thermostat"
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 0.5
    _attr_min_temp = 10.0
    _attr_max_temp = 30.0

    def __init__(self, coordinator: WeheatCoordinator, entry: ConfigEntry) -> None:
        """Initialiseer climate-entiteit."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_climate"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="WeHeat OpenTherm",
            manufacturer="WeHeat",
            model="Flint",
        )

    @property
    def hvac_mode(self) -> HVACMode:
        """Huidige HVAC-modus uit entry.options."""
        stored = self._entry.options.get(CONF_HVAC_MODE, DEFAULT_HVAC_MODE)
        return _MODE_FROM_STR.get(stored, HVACMode.HEAT)

    @property
    def current_temperature(self) -> float | None:
        """Huidige kamertemperatuur uit de coordinator."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(KEY_ROOM_TEMP)

    @property
    def target_temperature(self) -> float:
        """Ingestelde doeltemperatuur uit de config entry options."""
        return float(self._entry.options.get(CONF_TARGET_TEMP, DEFAULT_TARGET_TEMP))

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Sla nieuwe doeltemperatuur op en ververs de coordinator."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
        new_options = {**self._entry.options, CONF_TARGET_TEMP: float(temp)}
        self.hass.config_entries.async_update_entry(self._entry, options=new_options)
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Sla nieuwe HVAC-modus op en ververs de coordinator."""
        mode_str = _STR_FROM_MODE.get(hvac_mode)
        if mode_str is None:
            return
        new_options = {**self._entry.options, CONF_HVAC_MODE: mode_str}
        self.hass.config_entries.async_update_entry(self._entry, options=new_options)
        self.async_write_ha_state()
