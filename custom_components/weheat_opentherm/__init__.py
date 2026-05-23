"""WeHeat OpenTherm Setpoint — Home Assistant custom integratie."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .coordinator import WeheatCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Stel de integratie in op basis van een config entry."""
    coordinator = WeheatCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Bij optie-wijzigingen coordinator verversen (geen volledige herlaad nodig)
    entry.async_on_unload(entry.add_update_listener(_async_update_options))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Verwijder een config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def _async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Ververs de coordinator bij een optie-wijziging."""
    coordinator: WeheatCoordinator | None = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if coordinator is not None:
        await coordinator.async_request_refresh()
