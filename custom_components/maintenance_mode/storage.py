"""Stockage : chargement, migration depuis les anciens formats, écriture de l'état."""
from __future__ import annotations

import uuid
from typing import Any

from homeassistant.components.automation import EVENT_AUTOMATION_RELOADED
from homeassistant.helpers.start import async_at_started
from homeassistant.util import dt as dt_util

from .const import (
    DEFAULT_END_SOON_MINUTES,
    DEFAULT_MESSAGE,
    DEFAULT_WARN_MINUTES,
    FORBIDDEN_NOTIFY,
    LEGACY_ALLOWED_USERS,
    LEGACY_AUTOMATIONS,
    LEGACY_WARN_MINUTES,
    MAX_HISTORY,
    NOTIFY_KINDS,
)
from .window import Window, parse_iso

STORAGE_VERSION = 1


def default_config() -> dict[str, Any]:
    return {
        "automations": [],       # vide = toutes les automatisations
        "allowed_users": [],     # exemptés ; vide = seul le propriétaire
        "warn_minutes": DEFAULT_WARN_MINUTES,
        "message": DEFAULT_MESSAGE,
        "panel_access": {},      # {user_id: rôle}
        "notify_services": [],   # noms de services notify.* (ex. mobile_app_pixel)
        "notify_kinds": list(NOTIFY_KINDS),
        "end_soon_minutes": DEFAULT_END_SOON_MINUTES,
        "templates": [],
        "roles": [],             # rôles personnalisés : [{id, name, permissions}]
        "banner_mode": "bar",    # "bar" (bandeau en haut de la page) ou "card"
        "banner_scroll": True,   # défilement du texte s'il dépasse la fenêtre
    }


class StorageMixin:
    """Suppose `hass`, `entry`, `_store` et les champs d'état du gestionnaire."""

    async def async_load(self) -> None:
        data: dict[str, Any] = await self._store.async_load() or {}
        cfg = data.get("config")
        if cfg is None:  # migration depuis la v0.2
            cfg = {}
            opts = self.entry.options
            if opts.get(LEGACY_AUTOMATIONS):
                cfg["automations"] = list(opts[LEGACY_AUTOMATIONS])
            if opts.get(LEGACY_ALLOWED_USERS):
                cfg["allowed_users"] = list(opts[LEGACY_ALLOWED_USERS])
            if opts.get(LEGACY_WARN_MINUTES):
                cfg["warn_minutes"] = int(opts[LEGACY_WARN_MINUTES])
            if data.get("message"):
                cfg["message"] = data["message"]
        self.config = {**default_config(), **cfg}
        self.config["notify_services"] = [
            n for n in self.config["notify_services"] if n not in FORBIDDEN_NOTIFY
        ]
        self.disabled = list(data.get("disabled", []))
        self.history = list(data.get("history", []))[-MAX_HISTORY:]
        for entry in self.history:
            entry.setdefault("hid", uuid.uuid4().hex[:8])  # entrées créées avant la v0.6
        self.notified = list(data.get("notified", []))[-200:]

        if data.get("current"):
            self.current = Window.from_dict(data["current"])
        elif data.get("active"):  # ancien format
            self.current = Window(uuid.uuid4().hex[:8], dt_util.utcnow(), parse_iso(data.get("end")))
        self.schedule = [w for d in data.get("schedule", []) if (w := Window.from_dict(d))]
        legacy_start = parse_iso(data.get("start"))
        if (
            "schedule" not in data
            and data.get("start_armed")
            and legacy_start
            and legacy_start > dt_util.utcnow()
        ):
            self.schedule = [Window(uuid.uuid4().hex[:8], legacy_start, parse_iso(data.get("end")))]
        self.schedule.sort(key=lambda w: w.start)

        await self._refresh_users()
        # Un rechargement des automatisations (`automation.reload`) peut en rallumer certaines
        self._unsub_reload = self.hass.bus.async_listen(
            EVENT_AUTOMATION_RELOADED, self._async_on_automation_reload
        )
        async_at_started(self.hass, self._async_resume)

    def _data_to_save(self) -> dict[str, Any]:
        return {
            "config": self.config,
            "disabled": self.disabled,
            "current": self.current.as_dict() if self.current else None,
            "schedule": [w.as_dict() for w in self.schedule],
            "history": self.history,
            "notified": self.notified,
        }

    async def async_flush(self) -> None:
        """Écrit tout de suite l'état courant (déchargement de l'intégration)."""
        await self._store.async_save(self._data_to_save())
