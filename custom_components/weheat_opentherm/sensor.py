"""Diagnostische sensoren voor elke correctieterm en het eindresultaat."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    KEY_CURRENT_PRICE,
    KEY_OFFSETS,
    KEY_OUTDOOR_TEMP,
    KEY_ROOM_TEMP,
    KEY_T_DEFINITIEF,
    KEY_T_KAMER_COMP,
    KEY_T_PRIJS,
    KEY_T_STOOKLIJN,
    KEY_T_WINDCHILL,
    KEY_T_ZON,
)
from .coordinator import WeheatCoordinator


@dataclass(frozen=True, kw_only=True)
class WeheatSensorDescription(SensorEntityDescription):
    """Uitgebreide beschrijving met de sleutel in coordinator.data."""

    data_key: str = ""


_TEMP_SENSOR = dict(
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    device_class=SensorDeviceClass.TEMPERATURE,
    state_class=SensorStateClass.MEASUREMENT,
)

SENSORS: tuple[WeheatSensorDescription, ...] = (
    WeheatSensorDescription(
        key="outdoor_temp",
        data_key=KEY_OUTDOOR_TEMP,
        translation_key="outdoor_temp",
        **_TEMP_SENSOR,
    ),
    WeheatSensorDescription(
        key="room_temp",
        data_key=KEY_ROOM_TEMP,
        translation_key="room_temp",
        **_TEMP_SENSOR,
    ),
    WeheatSensorDescription(
        key="t_stooklijn",
        data_key=KEY_T_STOOKLIJN,
        translation_key="t_stooklijn",
        **_TEMP_SENSOR,
    ),
    WeheatSensorDescription(
        key="t_definitief",
        data_key=KEY_T_DEFINITIEF,
        translation_key="t_definitief",
        **_TEMP_SENSOR,
    ),
    WeheatSensorDescription(
        key="t_kamer_comp",
        data_key=KEY_T_KAMER_COMP,
        translation_key="t_kamer_comp",
        entity_category=EntityCategory.DIAGNOSTIC,
        **_TEMP_SENSOR,
    ),
    WeheatSensorDescription(
        key="t_windchill",
        data_key=KEY_T_WINDCHILL,
        translation_key="t_windchill",
        entity_category=EntityCategory.DIAGNOSTIC,
        **_TEMP_SENSOR,
    ),
    WeheatSensorDescription(
        key="t_zon",
        data_key=KEY_T_ZON,
        translation_key="t_zon",
        entity_category=EntityCategory.DIAGNOSTIC,
        **_TEMP_SENSOR,
    ),
    WeheatSensorDescription(
        key="t_prijs",
        data_key=KEY_T_PRIJS,
        translation_key="t_prijs",
        entity_category=EntityCategory.DIAGNOSTIC,
        **_TEMP_SENSOR,
    ),
    WeheatSensorDescription(
        key="current_price",
        data_key=KEY_CURRENT_PRICE,
        translation_key="current_price",
        native_unit_of_measurement="EUR/kWh",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=4,
    ),
)


_OFFSET_INDEX_FROM_KEY = {f"curve_offset_{i + 1}": i for i in range(5)}

OFFSET_SENSORS: tuple[WeheatSensorDescription, ...] = tuple(
    WeheatSensorDescription(
        key=f"curve_offset_{i + 1}",
        data_key=KEY_OFFSETS,
        translation_key=f"curve_offset_{i + 1}",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=2,
    )
    for i in range(5)
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Registreer diagnostische sensoren voor deze config entry."""
    coordinator: WeheatCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [
        WeheatSensor(coordinator, description, entry) for description in SENSORS
    ]
    entities.extend(
        WeheatOffsetSensor(coordinator, description, entry)
        for description in OFFSET_SENSORS
    )
    async_add_entities(entities)


class WeheatSensor(CoordinatorEntity[WeheatCoordinator], SensorEntity):
    """Diagnostische sensor die één correctieterm of het eindresultaat toont."""

    entity_description: WeheatSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: WeheatCoordinator,
        description: WeheatSensorDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialiseer sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="WeHeat OpenTherm",
            manufacturer="WeHeat",
            model="Flint",
        )

    @property
    def native_value(self) -> float | None:
        """Geef de sensorwaarde terug uit coordinator.data."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self.entity_description.data_key)


class WeheatOffsetSensor(WeheatSensor):
    """Diagnostische sensor voor één geleerde curve-offset (positie 1..5)."""

    @property
    def native_value(self) -> float | None:
        """Geef de offset terug voor het overeenkomstige curve-punt."""
        if self.coordinator.data is None:
            return None
        offsets = self.coordinator.data.get(KEY_OFFSETS)
        if not offsets:
            return 0.0
        idx = _OFFSET_INDEX_FROM_KEY.get(self.entity_description.key)
        if idx is None or idx >= len(offsets):
            return None
        return offsets[idx]
