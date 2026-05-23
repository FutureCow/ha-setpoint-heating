"""Reset-knop voor de adaptieve stooklijn."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import WeheatCoordinator

RESET_DESCRIPTION = ButtonEntityDescription(
    key="reset_learning",
    translation_key="reset_learning",
    entity_category=EntityCategory.CONFIG,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Registreer de reset-knop voor de adaptieve stooklijn."""
    coordinator: WeheatCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([WeheatResetButton(coordinator, entry)])


class WeheatResetButton(CoordinatorEntity[WeheatCoordinator], ButtonEntity):
    """Knop die de geleerde stooklijn-offsets en bucket-data wist."""

    _attr_has_entity_name = True
    entity_description = RESET_DESCRIPTION

    def __init__(self, coordinator: WeheatCoordinator, entry: ConfigEntry) -> None:
        """Initialiseer reset-knop."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_reset_learning"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="WeHeat OpenTherm",
            manufacturer="WeHeat",
            model="Flint",
        )

    async def async_press(self) -> None:
        """Reset de adaptieve stooklijn-leerstaat en ververs de coordinator."""
        await self.coordinator.learning.async_reset()
        await self.coordinator.async_request_refresh()
