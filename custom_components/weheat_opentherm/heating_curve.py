"""Stooklijn (heating curve) berekeningen met lineaire interpolatie."""
from __future__ import annotations

import bisect

# Windchill: welk deel van het gevoelstemperatuur-verschil telt mee voor het
# warmteverlies van het huis. De gevoelstemperatuur is bedoeld voor huid; een
# gebouw verliest door wind veel minder extra warmte (infiltratie, buitenwand).
_WINDCHILL_WEIGHT = 0.5
_MAX_WINDCHILL_CORRECTION = 4.0  # °C aanvoer


def calculate_heating_curve(
    outdoor_temp: float,
    curve_points: list[list[float]],
) -> float:
    """Bereken aanvoertemperatuur via lineaire interpolatie op de stooklijn.

    Args:
        outdoor_temp: Huidige buitentemperatuur in °C.
        curve_points: Lijst van [buitentemp, aanvoertemp] koppels, gesorteerd
            of ongesorteerd; worden intern gesorteerd op buitentemperatuur.

    Returns:
        Berekende aanvoertemperatuur in °C.
    """
    if not curve_points:
        return 30.0  # Veilige terugvalwaarde als er geen punten zijn

    sorted_points = sorted(curve_points, key=lambda p: p[0])
    outdoor_temps = [p[0] for p in sorted_points]
    flow_temps = [p[1] for p in sorted_points]

    if len(sorted_points) == 1:
        return flow_temps[0]

    if outdoor_temp <= outdoor_temps[0]:
        return flow_temps[0]
    if outdoor_temp >= outdoor_temps[-1]:
        return flow_temps[-1]

    idx = bisect.bisect_right(outdoor_temps, outdoor_temp)
    x0, y0 = sorted_points[idx - 1]
    x1, y1 = sorted_points[idx]

    ratio = (outdoor_temp - x0) / (x1 - x0)
    return round(y0 + ratio * (y1 - y0), 2)


def calculate_room_compensation(
    target_temp: float,
    room_temp: float,
    factor: float,
) -> float:
    """Bereken kamercompensatie, begrensd op ±5°C.

    Args:
        target_temp: Gewenste kamertemperatuur in °C.
        room_temp: Actuele kamertemperatuur in °C.
        factor: Compensatiefactor (standaard 2,0).

    Returns:
        Correctie in °C, altijd binnen [-5, +5].
    """
    correction = (target_temp - room_temp) * factor
    return round(max(-5.0, min(5.0, correction)), 2)


def _curve_slope(outdoor_temp: float, curve_points: list[list[float]]) -> float:
    """Helling van de stooklijn (°C aanvoer per °C buiten, ≥ 0) rond outdoor_temp.

    Buiten het bereik van de punten geldt de helling van het buitenste stuk,
    zodat ook voorbij het koudste punt wind nog meetelt.
    """
    if len(curve_points) < 2:
        return 0.0
    pts = sorted(curve_points, key=lambda p: p[0])
    xs = [p[0] for p in pts]
    idx = bisect.bisect_right(xs, outdoor_temp)
    idx = max(1, min(len(pts) - 1, idx))
    (x0, y0), (x1, y1) = pts[idx - 1], pts[idx]
    if x1 == x0:
        return 0.0
    return max(0.0, (y0 - y1) / (x1 - x0))


def calculate_windchill_correction(
    outdoor_temp: float,
    windchill_delta: float,
    curve_points: list[list[float]],
) -> float:
    """Zet een windchill-verschil (buiten-°C) om naar een aanvoer-correctie.

    Het huis gedraagt zich alsof het buiten _WINDCHILL_WEIGHT × delta kouder
    is; dat wordt via de lokale helling van de stooklijn omgerekend naar
    aanvoer-°C, in plaats van een buitengraad als aanvoergraad op te tellen.

    Args:
        outdoor_temp: Huidige buitentemperatuur in °C.
        windchill_delta: Lucht- minus gevoelstemperatuur in °C (≥ 0).
        curve_points: Stooklijn-punten (incl. geleerde offsets).

    Returns:
        Correctie in °C aanvoer, binnen [0, +4].
    """
    if windchill_delta <= 0.0:
        return 0.0
    slope = _curve_slope(outdoor_temp, curve_points)
    correction = slope * _WINDCHILL_WEIGHT * windchill_delta
    return round(min(_MAX_WINDCHILL_CORRECTION, correction), 2)
