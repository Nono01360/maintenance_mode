"""Contrôles de saisie : motif, fin, période, répétition, modèles. Les erreurs sont des `ServiceValidationError`."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

from homeassistant.util import dt as dt_util

from .errors import MaintenanceError
from .const import MAX_DURATION_MINUTES, MAX_REASON, MAX_TEMPLATES, REPEATS
from .window import Window, clean_pages, overlap, shift


class ValidationMixin:
    """Suppose `schedule` et `current` du gestionnaire."""

    def _find(self, window_id: str) -> Window:
        for window in self.schedule:
            if window.id == window_id:
                return window
        raise MaintenanceError("window_not_found")

    @staticmethod
    def _check_reason(reason: str) -> str:
        reason = (reason or "").strip()
        if len(reason) > MAX_REASON:
            raise MaintenanceError("reason_too_long", max=MAX_REASON)
        return reason

    @staticmethod
    def _check_repeat(repeat: str, start: datetime, end: datetime | None) -> str:
        if repeat not in REPEATS:
            raise MaintenanceError("invalid_repeat")
        if repeat != "none" and end is None:
            raise MaintenanceError("repeat_needs_end")
        if repeat != "none" and end is not None:
            next_start, _ = shift(start, end, repeat)
            if end > next_start:
                raise MaintenanceError("duration_exceeds_period")
        return repeat

    @staticmethod
    def _check_end(end: datetime | None) -> datetime | None:
        if end is None:
            return None
        end = dt_util.as_utc(end)
        if end <= dt_util.utcnow():
            raise MaintenanceError("end_in_past")
        return end

    def _check_window(self, start, end, *, ignore_id):
        start = dt_util.as_utc(start)
        end = dt_util.as_utc(end) if end else None
        if start <= dt_util.utcnow():
            raise MaintenanceError("start_in_past")
        if end is not None and end <= start:
            raise MaintenanceError("end_before_start")
        for other in self.schedule:
            if other.id != ignore_id and overlap(start, end, other.start, other.end):
                raise MaintenanceError("overlaps_scheduled")
        if self.current and self.current.end and overlap(start, end, self.current.start, self.current.end):
            raise MaintenanceError("overlaps_current")
        return start, end

    @staticmethod
    def _clean_templates(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for t in raw[:MAX_TEMPLATES]:
            name = str(t.get("name", "")).strip()[:40]
            if not name:
                continue
            duration = t.get("duration")
            repeat = t.get("repeat", "none")
            out.append(
                {
                    "id": str(t.get("id") or uuid.uuid4().hex[:8])[:12],
                    "name": name,
                    "reason": str(t.get("reason", "")).strip()[:MAX_REASON],
                    "pages": clean_pages(t.get("pages", [])),
                    "pause_automations": bool(t.get("pause_automations", True)),
                    "duration": int(duration) if duration else None,
                    "max_minutes": ValidationMixin._clean_max(t.get("max_minutes")),
                    "repeat": repeat if repeat in REPEATS else "none",
                }
            )
        return out

    # ------------------------------------------------------------------ durée maximale
    @staticmethod
    def _clean_max(value: Any) -> int | None:
        """`None` = valeur par défaut des réglages ; 0 = sans limite ; sinon minutes bornées."""
        if value is None or value == "":
            return None
        return max(0, min(MAX_DURATION_MINUTES, int(value)))

    def _max_cap(self, max_minutes: int | None) -> timedelta | None:
        """Durée maximale effective (la maintenance, sinon le réglage) ; None = sans limite."""
        minutes = max_minutes if max_minutes is not None else self.config["max_duration_minutes"]
        return timedelta(minutes=minutes) if minutes else None

    def _check_max_duration(self, start: datetime, end: datetime | None, max_minutes: int | None) -> None:
        """Refuse une fin explicite qui dépasse la durée maximale (une fin absente est ramenée au démarrage)."""
        cap = self._max_cap(max_minutes)
        if cap and end is not None and end - start > cap:
            raise MaintenanceError("max_duration_exceeded", max=int(cap.total_seconds() // 60))

    def _apply_max_duration(self, window: Window) -> None:
        """Sans fin, ou fin au-delà du maximum : la fin devient début + durée maximale (marquée `capped`)."""
        cap = self._max_cap(window.max_minutes)
        if cap and (window.end is None or window.end - window.start > cap):
            window.end = window.start + cap
            window.capped = True
