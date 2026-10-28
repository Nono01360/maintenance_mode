"""Stockage : chargement, migration depuis les anciens formats, écriture de l'état."""
from __future__ import annotations

import logging
import uuid
from typing import Any

from homeassistant.components.automation import EVENT_AUTOMATION_RELOADED
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
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

STORAGE_VERSION = 2   # v1 : jusqu'à la 0.7.8 ; v2 : migrée, intégrité vérifiée au chargement
_LOGGER = logging.getLogger(__name__)


class StorageTooNewError(Exception):
    """Le fichier a été écrit par une version plus récente de l'intégration (retour en arrière)."""

    def __init__(self, version: int, data: Any) -> None:
        super().__init__(f"format {version} inconnu (cette version comprend jusqu'au format {STORAGE_VERSION})")
        self.data = data


class MaintenanceStore(Store):
    """Stockage versionné : une copie de l'ancien fichier est conservée avant toute migration."""

    async def _async_migrate_func(self, old_major_version, old_minor_version, old_data):
        if old_major_version > STORAGE_VERSION:
            raise StorageTooNewError(old_major_version, old_data)
        await Store(self.hass, 1, f"{self.key}.backup_v{old_major_version}").async_save(old_data)
        return migrate_data(old_data)


def migrate_data(old: Any) -> Any:
    """Format 1 -> 2 : convertit les formats antérieurs (0.2 : `active`, `start_armed`) vers le format courant.

    Une donnée qui n'est pas un dictionnaire est rendue telle quelle (la vérification d'intégrité la traitera).
    """
    if not isinstance(old, dict):
        return old
    data = dict(old)
    now = dt_util.utcnow()
    if not data.get("current") and data.get("active"):
        data["current"] = Window(uuid.uuid4().hex[:8], now, parse_iso(data.get("end"))).as_dict()
    legacy_start = parse_iso(data.get("start"))
    if "schedule" not in data:
        data["schedule"] = []
        if data.get("start_armed") and legacy_start and legacy_start > now:
            data["schedule"] = [Window(uuid.uuid4().hex[:8], legacy_start, parse_iso(data.get("end"))).as_dict()]
    for legacy in ("active", "start_armed", "start", "end"):
        data.pop(legacy, None)
    history = data.get("history")
    if isinstance(history, list):       # copies : l'original (sauvegardé) n'est pas modifié
        data["history"] = [
            {"hid": uuid.uuid4().hex[:8], **item} if isinstance(item, dict) else item for item in history
        ]
    return data


def check_data(raw: Any) -> tuple[dict[str, Any], list[str]]:
    """Vérifie l'intégrité des données lues. Renvoie (données utilisables, problèmes trouvés).

    Mode sûr : ce qui est illisible est écarté, le reste est conservé ; rien ne lève jamais d'exception.
    """
    if raw is None:
        return {}, []
    if not isinstance(raw, dict):
        return {}, ["racine"]
    data = dict(raw)
    problems: list[str] = []

    def bad(key: str) -> None:
        problems.append(key)
        data.pop(key, None)

    if "config" in data and not isinstance(data["config"], dict):
        bad("config")
    for key in ("disabled", "history", "notified", "schedule"):
        if key in data and not isinstance(data[key], list):
            bad(key)
    if data.get("current") is not None and "current" in data and not isinstance(data["current"], dict):
        bad("current")
    if isinstance(data.get("disabled"), list) and not all(isinstance(x, str) for x in data["disabled"]):
        bad("disabled")
    if isinstance(data.get("notified"), list) and not all(isinstance(x, str) for x in data["notified"]):
        bad("notified")
    if isinstance(data.get("history"), list) and not all(isinstance(x, dict) for x in data["history"]):
        data["history"] = [x for x in data["history"] if isinstance(x, dict)]
        problems.append("history")
    if isinstance(data.get("schedule"), list):
        good = [x for x in data["schedule"] if isinstance(x, dict) and Window.from_dict(x)]
        if len(good) != len(data["schedule"]):
            problems.append("schedule")
        data["schedule"] = good
    if isinstance(data.get("current"), dict) and Window.from_dict(data["current"]) is None:
        bad("current")
    return data, problems


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
        problems: list[str] = []
        raw: Any = None
        try:
            raw = await self._store.async_load()
        except StorageTooNewError as err:
            raw = err.data
            problems.append(str(err))
            data: dict[str, Any] = {}
        else:
            data, found = check_data(raw)
            problems += found
        await self._async_report_integrity(raw, problems)
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
        for item in self.history:
            item.setdefault("hid", uuid.uuid4().hex[:8])   # filet de sécurité : toute entrée a un identifiant
        self.notified = list(data.get("notified", []))[-200:]

        self.current = Window.from_dict(data["current"]) if data.get("current") else None
        self.schedule = [w for d in data.get("schedule", []) if (w := Window.from_dict(d))]
        self.schedule.sort(key=lambda w: w.start)

        await self._refresh_users()
        # Un rechargement des automatisations (`automation.reload`) peut en rallumer certaines
        self._unsub_reload = self.hass.bus.async_listen(
            EVENT_AUTOMATION_RELOADED, self._async_on_automation_reload
        )
        async_at_started(self.hass, self._async_resume)

    async def _async_report_integrity(self, raw: Any, problems: list[str]) -> None:
        """Mode sûr : on démarre avec ce qui est lisible, on garde une copie de l'original et on alerte."""
        if not problems:
            ir.async_delete_issue(self.hass, DOMAIN, "storage_unreadable")
            return
        _LOGGER.error("Stockage de Mode maintenance partiellement illisible (%s) : démarrage en mode sûr", ", ".join(problems))
        await Store(self.hass, 1, f"{self._store.key}.unreadable").async_save(
            {"at": dt_util.utcnow().isoformat(), "problems": problems, "raw": raw}
        )
        ir.async_create_issue(
            self.hass, DOMAIN, "storage_unreadable",
            is_fixable=False, severity=ir.IssueSeverity.ERROR,
            translation_key="storage_unreadable",
            translation_placeholders={"problems": ", ".join(problems)},
        )

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
