"""Planification : échéances (début, fin, préavis), rattrapage au démarrage et minuterie unique."""
from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util import dt as dt_util


class PlanningMixin:
    """Suppose `hass`, `config`, `current`, `schedule`, `notified`, `_lock`, `_timer`, `_unloaded`, `_commit`,
    `_activate`, `_deactivate` et `_reapply_suspension` du gestionnaire."""

    async def _process_due(self) -> None:
        """Termine / démarre ce qui est arrivé à échéance (idempotent)."""
        now = dt_util.utcnow()
        if self.current and self.current.end and self.current.end <= now:
            await self._deactivate("auto")
        while self.schedule and self.schedule[0].start <= now:
            window = self.schedule.pop(0)
            if window.repeat != "none":  # la série continue : prochaine occurrence
                self.schedule.append(window.next_occurrence(now))
                self.schedule.sort(key=lambda w: w.start)
            if window.end and window.end <= now:
                continue  # entièrement passée (ex. HA éteint)
            if self.current:
                await self._deactivate("replaced")
            window.started_by = window.started_by or "planification"
            await self._activate(window)

    async def _async_resume(self, _hass: HomeAssistant | None = None) -> None:
        if self._unloaded:
            return
        async with self._lock:
            await self._process_due()
            await self._reapply_suspension()   # HA vient de (re)démarrer
            await self._commit(now=True)

    async def _async_timer_cb(self, _now: datetime) -> None:
        if self._unloaded:
            return
        async with self._lock:
            await self._process_due()
            await self._commit(now=True)

    def _cancel_timer(self) -> None:
        if self._timer:
            self._timer()
            self._timer = None

    @callback
    def _reschedule(self) -> None:
        self._cancel_timer()
        if self._unloaded:
            return
        now = dt_util.utcnow()
        due: list[datetime] = []
        if self.current and self.current.end:
            due.append(self.current.end)
        if self.schedule:
            due.append(self.schedule[0].start)
        if self.config["notify_services"]:
            kinds = self.config["notify_kinds"]
            if "pre" in kinds:
                warn = timedelta(minutes=self.config["warn_minutes"])
                due += [
                    w.start - warn for w in self.schedule
                    if w.start - warn > now and f"{w.id}:pre" not in self.notified
                ]
            if "end_soon" in kinds and self.current and self.current.end:
                t = self.current.end - timedelta(minutes=self.config["end_soon_minutes"])
                if t > now and f"{self.current.id}:end_soon" not in self.notified:
                    due.append(t)
        if due:
            self._timer = async_track_point_in_utc_time(self.hass, self._async_timer_cb, min(due))
