"""Adaptieve stooklijn: leert offsets per curve-punt uit werkelijke kamer-afwijking."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

_STORAGE_VERSION = 1

# Tuning constants
_LEARNING_INTERVAL = timedelta(hours=1)
_BUCKET_MIN_SAMPLES = 30          # min observaties per buitentemp-bucket
_BUCKET_MAX_AGE = timedelta(days=7)
_ERROR_DEADBAND = 0.3             # °C — geen aanpassing binnen deze afwijking
_MAX_OFFSET = 5.0                 # °C — maximale drift t.o.v. originele curve
_STABLE_TARGET_MIN = 60           # min — geen doeltemp-wijziging in deze periode
_STABLE_OUTDOOR_RATE = 1.0        # °C/uur — max buitentemp-veranderingssnelheid
_OUTDOOR_REF_INTERVAL = timedelta(minutes=10)
_SAVE_DEBOUNCE = 300              # seconden — debounce voor disk writes


class LearningEngine:
    """Beheert het leerproces voor de 5 stooklijn-offsets.

    Werking:
      1. Elke coordinator-tick: indien stabiel (geen doeltemp-wijziging, trage
         buitentemp), bewaar (kamer_error) in de bucket van afgeronde buitentemp.
      2. Eén keer per uur: per curve-punt het dichtstbijzijnde bucket bekijken,
         en bij persistente afwijking >0.3°C de offset met learning_rate aanpassen.
      3. Offsets begrensd op ±5°C t.o.v. originele curve.
      4. Curve-verandering door gebruiker → offsets + buckets gereset.
    """

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Initialiseer engine met persistent storage."""
        self._hass = hass
        self._store: Store = Store(
            hass, _STORAGE_VERSION, f"weheat_opentherm/{entry_id}_learning"
        )
        self._loaded = False
        self._data: dict[str, Any] = self._default_data()

    @staticmethod
    def _default_data() -> dict[str, Any]:
        """Lege beginstaat."""
        return {
            "offsets": [0.0, 0.0, 0.0, 0.0, 0.0],
            "buckets": {},
            "curve_signature": None,
            "last_target_temp": None,
            "last_target_change_iso": None,
            "last_outdoor_temp": None,
            "last_outdoor_iso": None,
            "last_learn_iso": None,
        }

    async def async_load(self) -> None:
        """Laad de geserialiseerde staat (idempotent)."""
        if self._loaded:
            return
        stored = await self._store.async_load()
        if stored:
            merged = self._default_data()
            merged.update(stored)
            # Sanity check: offsets altijd 5 elementen
            offsets = merged.get("offsets") or []
            if len(offsets) != 5:
                merged["offsets"] = [0.0] * 5
            self._data = merged
        self._loaded = True

    @property
    def offsets(self) -> list[float]:
        """Huidige offsets per curve-punt (sorted by outdoor temp)."""
        return list(self._data["offsets"])

    def apply_offsets(self, curve_points: list[list[float]]) -> list[list[float]]:
        """Pas geleerde offsets toe op de 5 curve-punten (sorted by outdoor temp)."""
        sorted_points = sorted(curve_points[:5], key=lambda p: p[0])
        offsets = self._data["offsets"]
        return [
            [p[0], p[1] + (offsets[i] if i < len(offsets) else 0.0)]
            for i, p in enumerate(sorted_points)
        ]

    async def async_reset(self) -> None:
        """Reset alle geleerde offsets en bucket-data."""
        self._data = self._default_data()
        await self._store.async_save(self._data)
        _LOGGER.info("Adaptieve stooklijn gereset")

    async def async_tick(
        self,
        outdoor_temp: float,
        room_temp: float,
        target_temp: float,
        curve_points: list[list[float]],
        learning_rate: float,
    ) -> None:
        """Voer één observatie-cyclus uit en mogelijk een leerstap."""
        await self.async_load()
        now = dt_util.utcnow()

        # Detecteer curve-wijziging door gebruiker → reset
        sig = self._curve_signature(curve_points)
        if (
            self._data["curve_signature"] is not None
            and self._data["curve_signature"] != sig
        ):
            _LOGGER.info("Stooklijn handmatig gewijzigd; offsets gereset")
            self._data["offsets"] = [0.0] * 5
            self._data["buckets"] = {}
        self._data["curve_signature"] = sig

        # Bewaak doeltemp-wijziging
        if self._data["last_target_temp"] != target_temp:
            self._data["last_target_temp"] = target_temp
            self._data["last_target_change_iso"] = now.isoformat()

        if learning_rate <= 0.0:
            self._schedule_save()
            return

        # Stabiliteitschecks
        outdoor_stable = self._update_and_check_outdoor(outdoor_temp, now)
        target_stable = self._check_target_stable(now)

        # Observatie als alles stabiel is
        if outdoor_stable and target_stable:
            self._observe(outdoor_temp, target_temp - room_temp, now)

        # Eens per uur: leerstap
        last_learn_iso = self._data.get("last_learn_iso")
        if last_learn_iso is None:
            self._data["last_learn_iso"] = now.isoformat()
        else:
            last_learn = dt_util.parse_datetime(last_learn_iso)
            if last_learn and (now - last_learn) >= _LEARNING_INTERVAL:
                self._run_learn_step(curve_points, learning_rate, now)
                self._data["last_learn_iso"] = now.isoformat()

        self._schedule_save()

    @staticmethod
    def _curve_signature(curve_points: list[list[float]]) -> str:
        """Stabiele hash van de buitentemp-punten in de curve."""
        sorted_x = sorted(p[0] for p in curve_points[:5])
        return ",".join(f"{x:.1f}" for x in sorted_x)

    def _observe(self, outdoor_temp: float, error: float, now) -> None:
        """Voeg observatie toe aan het juiste bucket."""
        bucket = int(round(outdoor_temp))
        key = str(bucket)
        b = self._data["buckets"].setdefault(
            key, {"sum": 0.0, "count": 0, "last_iso": now.isoformat()}
        )
        b["sum"] += error
        b["count"] += 1
        b["last_iso"] = now.isoformat()

    def _update_and_check_outdoor(self, outdoor_temp: float, now) -> bool:
        """True als buitentemp ≥10 min stabiel is met rate <1°C/u."""
        last = self._data.get("last_outdoor_temp")
        last_iso = self._data.get("last_outdoor_iso")

        if last is None or last_iso is None:
            self._data["last_outdoor_temp"] = outdoor_temp
            self._data["last_outdoor_iso"] = now.isoformat()
            return False

        last_dt = dt_util.parse_datetime(last_iso)
        if last_dt is None:
            return False

        delta = now - last_dt
        if delta < _OUTDOOR_REF_INTERVAL:
            return False  # te kort referentievenster

        rate_per_hour = abs(outdoor_temp - last) / delta.total_seconds() * 3600
        # Verschuif referentie voor volgende cyclus
        self._data["last_outdoor_temp"] = outdoor_temp
        self._data["last_outdoor_iso"] = now.isoformat()
        return rate_per_hour < _STABLE_OUTDOOR_RATE

    def _check_target_stable(self, now) -> bool:
        """True als de doeltemperatuur ≥60 min ongewijzigd is."""
        last_change = self._data.get("last_target_change_iso")
        if not last_change:
            return False
        last_dt = dt_util.parse_datetime(last_change)
        if last_dt is None:
            return False
        return (now - last_dt) >= timedelta(minutes=_STABLE_TARGET_MIN)

    def _run_learn_step(
        self,
        curve_points: list[list[float]],
        learning_rate: float,
        now,
    ) -> None:
        """Pas offsets aan op basis van bucket-statistieken."""
        buckets = self._data["buckets"]

        # Verwijder verouderde buckets
        cutoff = now - _BUCKET_MAX_AGE
        for key in list(buckets.keys()):
            last_iso = buckets[key].get("last_iso")
            if last_iso:
                ts = dt_util.parse_datetime(last_iso)
                if ts and ts < cutoff:
                    del buckets[key]

        if not buckets:
            return

        sorted_x = sorted(p[0] for p in curve_points[:5])
        per_curve_errors: dict[int, list[float]] = {i: [] for i in range(len(sorted_x))}

        for key, b in buckets.items():
            if b["count"] < _BUCKET_MIN_SAMPLES:
                continue
            mean_err = b["sum"] / b["count"]
            bucket_temp = float(key)
            closest_idx = min(
                range(len(sorted_x)),
                key=lambda i: abs(sorted_x[i] - bucket_temp),
            )
            per_curve_errors[closest_idx].append(mean_err)

        offsets = list(self._data["offsets"])
        changed = False
        for idx, errors in per_curve_errors.items():
            if not errors:
                continue
            avg_err = sum(errors) / len(errors)
            if abs(avg_err) < _ERROR_DEADBAND:
                continue
            # error > 0 → kamer te koud → flow temp omhoog
            delta = learning_rate if avg_err > 0 else -learning_rate
            new_offset = max(-_MAX_OFFSET, min(_MAX_OFFSET, offsets[idx] + delta))
            new_offset = round(new_offset, 2)
            if new_offset != offsets[idx]:
                offsets[idx] = new_offset
                changed = True

        self._data["offsets"] = offsets

        # Decay buckets: recente data weegt zwaarder
        for b in buckets.values():
            b["sum"] *= 0.5
            b["count"] = max(1, int(b["count"] * 0.5))

        if changed:
            _LOGGER.info(
                "Adaptieve stooklijn: nieuwe offsets %s op basis van %d buckets",
                offsets,
                len(buckets),
            )

    def _schedule_save(self) -> None:
        """Vraag debounced save aan (max 1× per 5 min)."""
        self._store.async_delay_save(lambda: self._data, _SAVE_DEBOUNCE)
