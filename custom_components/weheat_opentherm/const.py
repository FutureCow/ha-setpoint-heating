"""Constants for WeHeat OpenTherm integration."""
from __future__ import annotations

DOMAIN = "weheat_opentherm"
PLATFORMS = ["button", "climate", "number", "sensor"]

# Config entry data keys (sensor entity IDs — set at setup)
CONF_ROOM_TEMP_SENSOR = "room_temp_sensor"
CONF_OUTDOOR_TEMP_SENSOR = "outdoor_temp_sensor"
CONF_WEATHER_ENTITY = "weather_entity"
CONF_PRICE_SENSOR = "price_sensor"
CONF_SETPOINT_ENTITY = "setpoint_entity"

# Options keys (editable via options flow or number entities)
CONF_TARGET_TEMP = "target_temp"
CONF_T_MIN = "t_min"
CONF_T_MAX = "t_max"
CONF_COMPENSATION_FACTOR = "compensation_factor"
CONF_FORECAST_HOURS = "forecast_hours"
CONF_MAX_PRICE_CORRECTION = "max_price_correction"
CONF_CURVE_POINTS = "curve_points"
CONF_LEARNING_RATE = "learning_rate"

# Geavanceerde correcties
CONF_CHEAP_PREHEAT_DELTA = "cheap_preheat_delta"
CONF_EXPENSIVE_SAVING_DELTA = "expensive_saving_delta"
CONF_SUN_SUNNY = "sun_sunny"
CONF_SUN_PARTLYCLOUDY = "sun_partlycloudy"

# HVAC modus (heat / off) — koelen gaat via interne stooklijn van de warmtepomp
CONF_HVAC_MODE = "hvac_mode"
CONF_STOOKGRENS = "stookgrens"

# Toegestane HVAC-modus waarden
HVAC_MODE_HEAT = "heat"
HVAC_MODE_OFF = "off"

# Default values
DEFAULT_TARGET_TEMP = 20.0
DEFAULT_T_MIN = 15.0
DEFAULT_T_MAX = 45.0
DEFAULT_COMPENSATION_FACTOR = 2.0
DEFAULT_FORECAST_HOURS = 3
DEFAULT_MAX_PRICE_CORRECTION = 3.0
DEFAULT_SETPOINT_ENTITY = "input_number.ot_setpoint"
DEFAULT_LEARNING_RATE = 0.1  # °C per leerstap (1×/uur); 0 = uit
DEFAULT_CHEAP_PREHEAT_DELTA = 2.0   # °C bij goedkope stroom
DEFAULT_EXPENSIVE_SAVING_DELTA = 2.0  # °C bij dure stroom (positieve waarde, intern negatief)
DEFAULT_SUN_SUNNY = 3.0   # °C reductie bij condition "sunny"
DEFAULT_SUN_PARTLYCLOUDY = 2.0  # °C reductie bij condition "partlycloudy"
DEFAULT_HVAC_MODE = HVAC_MODE_HEAT
DEFAULT_STOOKGRENS = 17.0  # °C buiten — boven deze drempel niet meer verwarmen

# Default heating curve: list of [outdoor_temp, flow_temp] pairs
DEFAULT_CURVE_POINTS: list[list[float]] = [
    [-10.0, 37.0],
    [-5.0, 34.0],
    [0.0, 29.0],
    [5.0, 26.0],
    [15.0, 21.0],
]

# Keys used in coordinator data dict
KEY_OUTDOOR_TEMP = "outdoor_temp"
KEY_ROOM_TEMP = "room_temp"
KEY_T_STOOKLIJN = "t_stooklijn"
KEY_T_KAMER_COMP = "t_kamer_comp"
KEY_T_WINDCHILL = "t_windchill"
KEY_T_ZON = "t_zon"
KEY_T_PRIJS = "t_prijs"
KEY_T_DEFINITIEF = "t_definitief"
KEY_CURRENT_PRICE = "current_price"
KEY_OFFSETS = "curve_offsets"  # list[float] van 5 leer-offsets
KEY_HVAC_MODE = "hvac_mode"             # door gebruiker gekozen
KEY_EFFECTIVE_MODE = "effective_mode"   # daadwerkelijk actief (heat/cool/off na grenscheck)
