"""Config flow en options flow voor WeHeat OpenTherm."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, FlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_CHEAP_PREHEAT_DELTA,
    CONF_COMPENSATION_FACTOR,
    CONF_CURVE_POINTS,
    CONF_EXPENSIVE_SAVING_DELTA,
    CONF_FORECAST_HOURS,
    CONF_MAX_PRICE_CORRECTION,
    CONF_OUTDOOR_TEMP_SENSOR,
    CONF_PRICE_SENSOR,
    CONF_ROOM_TEMP_SENSOR,
    CONF_SETPOINT_ENTITY,
    CONF_SUN_PARTLYCLOUDY,
    CONF_SUN_SUNNY,
    CONF_T_MAX,
    CONF_T_MIN,
    CONF_TARGET_TEMP,
    CONF_WEATHER_ENTITY,
    DEFAULT_CHEAP_PREHEAT_DELTA,
    DEFAULT_COMPENSATION_FACTOR,
    DEFAULT_CURVE_POINTS,
    DEFAULT_EXPENSIVE_SAVING_DELTA,
    DEFAULT_FORECAST_HOURS,
    DEFAULT_MAX_PRICE_CORRECTION,
    DEFAULT_SUN_PARTLYCLOUDY,
    DEFAULT_SUN_SUNNY,
    DEFAULT_T_MAX,
    DEFAULT_T_MIN,
    DEFAULT_TARGET_TEMP,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class WeheatConfigFlow(ConfigFlow, domain=DOMAIN):
    """Installatiewizard voor WeHeat OpenTherm."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Eerste stap: sensor-entiteiten configureren."""
        if user_input is not None:
            # Verwijder lege optionele velden
            cleaned = {k: v for k, v in user_input.items() if v}
            return self.async_create_entry(title="WeHeat OpenTherm", data=cleaned)

        schema = vol.Schema(
            {
                vol.Required(CONF_ROOM_TEMP_SENSOR): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor",
                        device_class="temperature",
                    )
                ),
                vol.Required(CONF_OUTDOOR_TEMP_SENSOR): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor",
                        device_class="temperature",
                    )
                ),
                vol.Optional(CONF_WEATHER_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="weather")
                ),
                vol.Optional(CONF_PRICE_SENSOR): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(CONF_SETPOINT_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="input_number")
                ),
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> WeheatOptionsFlow:
        """Maak de options flow aan."""
        return WeheatOptionsFlow()


class WeheatOptionsFlow(OptionsFlow):
    """Options flow: temperatuurinstellingen en stooklijn."""

    def __init__(self) -> None:
        """Initialiseer tijdelijke opslag voor multi-stap flow."""
        self._pending: dict[str, Any] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Stap 1: Temperatuurinstellingen en correctiefactoren."""
        if user_input is not None:
            self._pending.update(user_input)
            return await self.async_step_curve()

        opts = self.config_entry.options

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_TARGET_TEMP,
                    default=opts.get(CONF_TARGET_TEMP, DEFAULT_TARGET_TEMP),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=10.0, max=30.0, step=0.5, mode="slider",
                        unit_of_measurement="°C",
                    )
                ),
                vol.Required(
                    CONF_T_MIN,
                    default=opts.get(CONF_T_MIN, DEFAULT_T_MIN),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=10.0, max=35.0, step=0.5, mode="slider",
                        unit_of_measurement="°C",
                    )
                ),
                vol.Required(
                    CONF_T_MAX,
                    default=opts.get(CONF_T_MAX, DEFAULT_T_MAX),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=25.0, max=65.0, step=0.5, mode="slider",
                        unit_of_measurement="°C",
                    )
                ),
                vol.Required(
                    CONF_COMPENSATION_FACTOR,
                    default=opts.get(CONF_COMPENSATION_FACTOR, DEFAULT_COMPENSATION_FACTOR),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0.0, max=10.0, step=0.1, mode="slider")
                ),
                vol.Required(
                    CONF_FORECAST_HOURS,
                    default=opts.get(CONF_FORECAST_HOURS, DEFAULT_FORECAST_HOURS),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1.0, max=6.0, step=1.0, mode="slider",
                        unit_of_measurement="h",
                    )
                ),
                vol.Required(
                    CONF_MAX_PRICE_CORRECTION,
                    default=opts.get(CONF_MAX_PRICE_CORRECTION, DEFAULT_MAX_PRICE_CORRECTION),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0.0, max=5.0, step=0.5, mode="slider",
                        unit_of_measurement="°C",
                    )
                ),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)

    async def async_step_curve(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Stap 2: Stooklijn-punten configureren."""
        if user_input is not None:
            curve = [
                [float(user_input[f"p{i}_outdoor"]), float(user_input[f"p{i}_flow"])]
                for i in range(1, 6)
            ]
            self._pending[CONF_CURVE_POINTS] = curve
            return await self.async_step_advanced()

        raw = self.config_entry.options.get(CONF_CURVE_POINTS, DEFAULT_CURVE_POINTS)
        # Zorg altijd voor precies 5 punten; vul op met defaults als nodig
        stored = [
            raw[i] if i < len(raw) else DEFAULT_CURVE_POINTS[i]
            for i in range(5)
        ]

        fields: dict[Any, Any] = {}
        for i, point in enumerate(stored, start=1):
            fields[
                vol.Required(f"p{i}_outdoor", default=float(point[0]))
            ] = selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=-20.0, max=20.0, step=0.5, mode="box",
                    unit_of_measurement="°C",
                )
            )
            fields[
                vol.Required(f"p{i}_flow", default=float(point[1]))
            ] = selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=15.0, max=65.0, step=0.5, mode="box",
                    unit_of_measurement="°C",
                )
            )

        return self.async_show_form(
            step_id="curve",
            data_schema=vol.Schema(fields),
        )

    async def async_step_advanced(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Stap 3: Geavanceerde correctie-instellingen."""
        if user_input is not None:
            self._pending.update(user_input)
            return self.async_create_entry(title="", data=self._pending)

        opts = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_CHEAP_PREHEAT_DELTA,
                    default=opts.get(CONF_CHEAP_PREHEAT_DELTA, DEFAULT_CHEAP_PREHEAT_DELTA),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0.0, max=5.0, step=0.5, mode="slider",
                        unit_of_measurement="°C",
                    )
                ),
                vol.Required(
                    CONF_EXPENSIVE_SAVING_DELTA,
                    default=opts.get(CONF_EXPENSIVE_SAVING_DELTA, DEFAULT_EXPENSIVE_SAVING_DELTA),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0.0, max=5.0, step=0.5, mode="slider",
                        unit_of_measurement="°C",
                    )
                ),
                vol.Required(
                    CONF_SUN_SUNNY,
                    default=opts.get(CONF_SUN_SUNNY, DEFAULT_SUN_SUNNY),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0.0, max=6.0, step=0.5, mode="slider",
                        unit_of_measurement="°C",
                    )
                ),
                vol.Required(
                    CONF_SUN_PARTLYCLOUDY,
                    default=opts.get(CONF_SUN_PARTLYCLOUDY, DEFAULT_SUN_PARTLYCLOUDY),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0.0, max=6.0, step=0.5, mode="slider",
                        unit_of_measurement="°C",
                    )
                ),
            }
        )

        return self.async_show_form(step_id="advanced", data_schema=schema)
