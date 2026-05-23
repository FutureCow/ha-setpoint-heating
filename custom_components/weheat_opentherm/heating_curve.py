"""Stooklijn (heating curve) berekeningen met lineaire interpolatie."""
from __future__ import annotations

import bisect


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
