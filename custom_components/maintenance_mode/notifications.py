"""Notifications push : textes (fr / en) et envoi aux services `notify.*` choisis."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import FORBIDDEN_NOTIFY
from .window import Window

_LOGGER = logging.getLogger(__name__)


def fmt_local(value: datetime) -> str:
    local = dt_util.as_local(value)
    if local.date() == dt_util.as_local(dt_util.utcnow()).date():
        return local.strftime("%H:%M")
    return local.strftime("%d/%m %H:%M")


def notification_text(hass: HomeAssistant, kind: str, w: Window) -> tuple[str, str]:
    en = (hass.config.language or "fr").startswith("en")
    reason = f" {w.reason}" if w.reason else ""
    if kind == "pre":
        mins = max(0, int((w.start - dt_util.utcnow()).total_seconds() // 60))
        if en:
            return "Scheduled maintenance", f"Starts in {mins} min ({fmt_local(w.start)}).{reason}"
        return "Maintenance prévue", f"Début dans {mins} min ({fmt_local(w.start)}).{reason}"
    if kind == "started":
        end = fmt_local(w.end) if w.end else None
        if en:
            return "Maintenance started", (f"Expected end: {end}." if end else "Home Assistant will be available as soon as possible.") + reason
        return "Maintenance en cours", (f"Fin prévue à {end}." if end else "Home Assistant sera disponible dès que possible.") + reason
    if kind == "end_soon":
        end = fmt_local(w.end) if w.end else "?"
        if en:
            return "Maintenance ending soon", f"Expected end: {end}."
        return "La maintenance se termine bientôt", f"Fin prévue à {end}."
    if en:
        return "Maintenance finished", "Home Assistant is available again."
    return "Maintenance terminée", "Home Assistant est de nouveau disponible."


class NotificationsMixin:
    """Envoi des notifications ; suppose `hass`, `config`, `notified` et `schedule`/`current` du gestionnaire."""

    async def _notify(self, kind: str, window: Window) -> None:
        key = f"{window.id}:{kind}"
        if key in self.notified:
            return
        self.notified = [*self.notified, key][-200:]
        services = self.config["notify_services"]
        if not services or kind not in self.config["notify_kinds"]:
            return
        title, message = notification_text(self.hass, kind, window)
        for name in services:
            if name in FORBIDDEN_NOTIFY or not self.hass.services.has_service("notify", name):
                continue
            try:
                await self.hass.services.async_call(
                    "notify", name, {"title": title, "message": message}, blocking=False
                )
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Échec de la notification via notify.%s", name)

    async def _send_due_notifications(self, now: datetime) -> None:
        kinds = self.config["notify_kinds"]
        if not self.config["notify_services"]:
            return
        if "pre" in kinds:
            warn = timedelta(minutes=self.config["warn_minutes"])
            for w in list(self.schedule):
                if w.start - warn <= now < w.start:
                    await self._notify("pre", w)
        if "end_soon" in kinds and self.current and self.current.end:
            soon = timedelta(minutes=self.config["end_soon_minutes"])
            if self.current.end - soon <= now < self.current.end:
                await self._notify("end_soon", self.current)
