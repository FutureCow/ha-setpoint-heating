"""Instelbare number-entiteiten voor veelgebruikte parameters."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_COMPENSATION_FACTOR,
    CONF_COOLING_SUPPLY_TEMP,
    CONF_FORECAST_HOURS,
    CONF_KOELGRENS,
    CONF_LEARNING_RATE,
    CONF_MAX_PRICE_CORRECTION,
    CONF_STOOKGRENS,
    CONF_T_MAX,
    CONF_T_MIN,
    DEFAULT_COMPENSATION_FACTOR,
    DEFAULT_COOLING_SUPPLY_TEMP,
    DEFAULT_FORECAST_HOURS,
    DEFAULT_KOELGRENS,
    DEFAULT_LEARNING_RATE,
    DEFAULT_MAX_PRICE_CORRECTION,
    DEFAULT_STOOKGRENS,
    DEFAULT_T_MAX,
    DEFAULT_T_MIN,
    DOMAIN,
)
from .coordinator import WeheatCoordinator


@dataclass(frozen=True, kw_only=True)
class WeheatNumberDescription(NumberEntityDescription):
    """Uitgebreide beschrijving met options-sleutel en standaardwaarde."""

    option_key: str = ""
    default: float = 0.0


NUMBERS: tuple[WeheatNumberDescription, ...] = (
    WeheatNumberDescription(
        key="compensation_factor",
        option_key=CONF_COMPENSATION_FACTOR,
        translation_key="compensation_factor",
        native_min_value=0.0,
        native_max_value=10.0,
        native_step=0.1,
        mode=NumberMode.SLIDER,
        default=DEFAULT_COMPENSATION_FACTOR,
        entity_category=EntityCategory.CONFIG,
    ),
    WeheatNumberDescription(
        key="t_min",
        option_key=CONF_T_MIN,
        translation_key="t_min",
        native_min_value=10.0,
        native_max_value=35.0,
        native_step=0.5,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
        default=DEFAULT_T_MIN,
        entity_category=EntityCategory.CONFIG,
    ),
    WeheatNumberDescription(
        key="t_max",
        option_key=CONF_T_MAX,
        translation_key="t_max",
        native_min_value=25.0,
        native_max_value=65.0,
        native_step=0.5,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
        default=DEFAULT_T_MAX,
        entity_category=EntityCategory.CONFIG,
    ),
    WeheatNumberDescription(
        key="forecast_hours",
        option_key=CONF_FORECAST_HOURS,
        translation_key="forecast_hours",
        native_min_value=1.0,
        native_max_value=6.0,
        native_step=1.0,
        native_unit_of_measurement="h",
        mode=NumberMode.SLIDER,
        default=float(DEFAULT_FORECAST_HOURS),
        entity_category=EntityCategory.CONFIG,
    ),
    WeheatNumberDescription(
        key="max_price_correction",
        option_key=CONF_MAX_PRICE_CORRECTION,
        translation_key="max_price_correction",
        native_min_value=0.0,
        native_max_value=5.0,
        native_step=0.5,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.SLIDER,
        default=DEFAULT_MAX_PRICE_CORRECTION,
        entity_category=EntityCategory.CONFIG,
    ),
    WeheatNumberDescription(
        key="learning_rate",
        option_key=CONF_LEARNING_RATE,
        translation_key="learning_rate",
        native_min_value=0.0,
        native_max_value=0.5,
        native_step=0.05,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.SLIDER,
        default=DEFAULT_LEARNING_RATE,
        entity_category=EntityCategory.CONFIG,
    ),
    WeheatNumberDescription(
        key="cooling_supply_temp",
        option_key=CONF_COOLING_SUPPLY_TEMP,
        translation_key="cooling_supply_temp",
        native_min_value=15.0,
        native_max_value=25.0,
        native_step=0.5,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.SLIDER,
        default=DEFAULT_COOLING_SUPPLY_TEMP,
        entity_category=EntityCategory.CONFIG,
    ),
    WeheatNumberDescription(
        key="stookgrens",
        option_key=CONF_STOOKGRENS,
        translation_key="stookgrens",
        native_min_value=10.0,
        native_max_value=25.0,
        native_step=0.5,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.SLIDER,
        default=DEFAULT_STOOKGRENS,
        entity_category=EntityCategory.CONFIG,
    ),
    WeheatNumberDescription(
        key="koelgrens",
        option_key=CONF_KOELGRENS,
        translation_key="koelgrens",
        native_min_value=15.0,
        native_max_value=30.0,
        native_step=0.5,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.SLIDER,
        default=DEFAULT_KOELGRENS,
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Registreer instelbare number-entiteiten."""
    coordinator: WeheatCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        WeheatNumber(coordinator, description, entry) for description in NUMBERS
    )


class WeheatNumber(CoordinatorEntity[WeheatCoordinator], NumberEntity):
    """Instelbare parameter opgeslagen in de config entry options.

    Wijzigingen worden direct geschreven naar entry.options en triggeren
    een coordinator refresh, zodat het setpoint meteen herberekend wordt.
    """

    entity_description: WeheatNumberDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: WeheatCoordinator,
        description: WeheatNumberDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialiseer number-entiteit."""
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="WeHeat OpenTherm",
            manufacturer="WeHeat",
            model="Flint",
        )

    @property
    def native_value(self) -> float:
        """Huidige waarde uit de config entry options."""
        return float(
            self._entry.options.get(
                self.entity_description.option_key,
                self.entity_description.default,
            )
        )

    async def async_set_native_value(self, value: float) -> None:
        """Sla nieuwe waarde op in entry.options en ververs de coordinator."""
        new_options = {
            **self._entry.options,
            self.entity_description.option_key: value,
        }
        self.hass.config_entries.async_update_entry(self._entry, options=new_options)
        self.async_write_ha_state()
