"""Diagnostische sensoren voor elke correctieterm en het eindresultaat."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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
    CONF_T_MAX,
    CONF_T_MIN,
    DEFAULT_T_MAX,
    DEFAULT_T_MIN,
    DOMAIN,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    KEY_CURRENT_PRICE,
    KEY_EFFECTIVE_MODE,
    KEY_HVAC_MODE,
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


MODE_SENSOR = WeheatSensorDescription(
    key="actieve_modus",
    data_key=KEY_EFFECTIVE_MODE,
    translation_key="actieve_modus",
    icon="mdi:hvac",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Registreer diagnostische sensoren voor deze config entry."""
    coordinator: WeheatCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = []
    for description in SENSORS:
        cls = (
            WeheatSetpointSensor
            if description.key == "t_definitief"
            else WeheatSensor
        )
        entities.append(cls(coordinator, description, entry))
    entities.extend(
        WeheatOffsetSensor(coordinator, description, entry)
        for description in OFFSET_SENSORS
    )
    entities.append(WeheatModeSensor(coordinator, MODE_SENSOR, entry))
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


class WeheatModeSensor(WeheatSensor):
    """Toont de effectieve modus (heat/cool/off) — ESP leest deze."""

    @property
    def native_value(self) -> str | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(KEY_EFFECTIVE_MODE) or HVAC_MODE_OFF


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


def _fmt(value: float, signed: bool = False) -> str:
    """Compact getal-formaat voor weergave in de formule."""
    if signed and value > 0:
        return f"+{value:.2f}"
    return f"{value:.2f}"


class WeheatSetpointSensor(WeheatSensor):
    """Setpoint-sensor met volledige formule-opbouw als attributen."""

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Toon de opbouw van het berekende setpoint."""
        data = self.coordinator.data
        if data is None:
            return {}

        mode = data.get(KEY_HVAC_MODE, HVAC_MODE_HEAT)
        final = data.get(KEY_T_DEFINITIEF)
        s = float(data.get(KEY_T_STOOKLIJN) or 0.0)
        kc = float(data.get(KEY_T_KAMER_COMP) or 0.0)

        # OFF: alles uit
        if mode == HVAC_MODE_OFF:
            return {
                "modus": "uit",
                "formule": "warmtepomp uit — geen setpoint",
            }

        # COOL: simpel formaat, geen stooklijn/correcties
        if mode == HVAC_MODE_COOL:
            return {
                "modus": "koelen",
                "formule": (
                    f"koelaanvoer {s:.1f} {_fmt(-kc, signed=True)} (boost)"
                    f" = {final:.1f}"
                ),
                "koelaanvoer_basis": s,
                "kamer_boost": -kc,
                "min_supply": 15.0,
            }

        # HEAT: volledige opbouw met alle correcties
        w = float(data.get(KEY_T_WINDCHILL) or 0.0)
        z = float(data.get(KEY_T_ZON) or 0.0)
        p = float(data.get(KEY_T_PRIJS) or 0.0)
        raw_sum = round(s + kc + w - z + p, 2)
        opts = self.coordinator.entry.options
        t_min = float(opts.get(CONF_T_MIN, DEFAULT_T_MIN))
        t_max = float(opts.get(CONF_T_MAX, DEFAULT_T_MAX))
        was_clamped = final is not None and round(float(final), 2) != raw_sum

        offsets = data.get(KEY_OFFSETS) or []
        learned_adjustment = round(sum(offsets), 2) if offsets else 0.0

        formule = (
            f"{_fmt(s)} (stooklijn) "
            f"{_fmt(kc, signed=True)} (kamer) "
            f"{_fmt(w, signed=True)} (windchill) "
            f"{_fmt(-z, signed=True)} (zon) "
            f"{_fmt(p, signed=True)} (prijs) "
            f"= {raw_sum:.2f}"
        )
        if was_clamped:
            formule += f" → clamp[{t_min:.1f}, {t_max:.1f}] = {final:.1f}"

        return {
            "modus": "verwarmen",
            "formule": formule,
            "stooklijn_basis": s,
            "kamercompensatie": kc,
            "windchill_correctie": w,
            "zon_correctie": -z,
            "prijs_correctie": p,
            "som_voor_begrenzing": raw_sum,
            "t_min": t_min,
            "t_max": t_max,
            "begrensd": was_clamped,
            "geleerde_offset_totaal": learned_adjustment,
        }
