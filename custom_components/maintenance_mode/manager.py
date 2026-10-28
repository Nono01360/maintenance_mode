"""Cœur de l'intégration : maintenances planifiées, état courant, droits, notifications."""
from __future__ import annotations

import asyncio
import logging
import re
import uuid
from datetime import datetime, timedelta
from typing import Any


from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .access import AccessMixin
from .storage import STORAGE_VERSION, StorageMixin, default_config
from .planning import PlanningMixin
from .validation import ValidationMixin
from .suspension import SuspensionMixin
from .notifications import NotificationsMixin
from .window import (
    Window,
    clean_pages,
    overlap,
    parse_iso,
)
from .const import (
    DEFAULT_MESSAGE,
    DOMAIN,
    FORBIDDEN_NOTIFY,
    BANNER_MODES,
    MAX_WINDOWS,
    NOTIFY_KINDS,
    SAVE_DELAY,
    SIGNAL_STATE_UPDATED,
)

_LOGGER = logging.getLogger(__name__)
_NOTIFY_NAME = re.compile(r"^[a-z0-9_]+$")
# « notify.notify » est un alias hérité dont le comportement dépend de la plateforme qui
# l'enregistre (aucun, un seul ou tous les appareils) : on le refuse, de même que
# « send_message » (service par entité). Choisis un service précis (notify.mobile_app_…).


# --------------------------------------------------------------------- utilitaires
def get_manager(hass: HomeAssistant) -> MaintenanceManager | None:
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is ConfigEntryState.LOADED:
            return entry.runtime_data
    return None


class MaintenanceManager(AccessMixin, NotificationsMixin, SuspensionMixin, ValidationMixin, PlanningMixin, StorageMixin):
    """Source de vérité unique ; entités, panneau, services et calendrier la reflètent."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.current: Window | None = None
        self.disabled: list[str] = []
        self.schedule: list[Window] = []
        self.history: list[dict[str, Any]] = []
        self.notified: list[str] = []
        self.config: dict[str, Any] = default_config()
        self.users: list[dict[str, Any]] = []
        self.owner_ids: list[str] = []
        self._store: Store = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}")
        self._listeners: list[CALLBACK_TYPE] = []
        self._timer: CALLBACK_TYPE | None = None
        self._unsub_reload: CALLBACK_TYPE | None = None
        self._lock = asyncio.Lock()
        self._unloaded = False

    # ------------------------------------------------------------------ chargement
    @callback
    def async_unload(self) -> None:
        self._unloaded = True
        self._cancel_timer()
        self._listeners.clear()
        if self._unsub_reload:
            self._unsub_reload()
            self._unsub_reload = None
        ir.async_delete_issue(self.hass, DOMAIN, "missing_automations")

    @callback
    def async_add_listener(self, update: CALLBACK_TYPE) -> CALLBACK_TYPE:
        self._listeners.append(update)

        @callback
        def remove() -> None:
            if update in self._listeners:
                self._listeners.remove(update)

        return remove

    # ------------------------------------------------------------------ lecture
    @property
    def next_window(self) -> Window | None:
        return self.schedule[0] if self.schedule else None

    # -- rôles et autorisations --
    # ------------------------------------------------------------------ actions
    async def async_start_now(
        self, *, end: datetime | None, reason: str, pages: list[str], pause: bool, by: str = ""
    ) -> None:
        async with self._lock:
            end = self._check_end(end)
            window = Window(
                id=uuid.uuid4().hex[:8],
                start=dt_util.utcnow(),
                end=end,
                reason=self._check_reason(reason),
                pages=clean_pages(pages),
                pause_automations=pause,
                started_by=by,
            )
            if self.current:
                await self._deactivate("replaced")
            await self._activate(window)
            await self._commit(now=True)

    async def async_stop(self) -> None:
        async with self._lock:
            if self.current:
                await self._deactivate("manual")
                await self._commit(now=True)

    async def async_update_current(
        self, *, end: datetime | None, reason: str, pages: list[str]
    ) -> None:
        async with self._lock:
            if not self.current:
                raise ServiceValidationError("Aucune maintenance en cours.")
            end = self._check_end(end)
            if end:
                for w in self.schedule:
                    if overlap(self.current.start, end, w.start, w.end):
                        raise ServiceValidationError("La fin chevauche une maintenance planifiée.")
            self.current.end = end
            self.current.reason = self._check_reason(reason)
            self.current.pages = clean_pages(pages)
            await self._commit()

    async def async_add_window(
        self,
        *,
        start: datetime,
        end: datetime | None,
        reason: str,
        pages: list[str],
        pause: bool,
        repeat: str = "none",
    ) -> Window:
        async with self._lock:
            if len(self.schedule) >= MAX_WINDOWS:
                raise ServiceValidationError(f"Maximum {MAX_WINDOWS} maintenances planifiées.")
            start, end = self._check_window(start, end, ignore_id=None)
            window = Window(
                id=uuid.uuid4().hex[:8],
                start=start,
                end=end,
                reason=self._check_reason(reason),
                pages=clean_pages(pages),
                pause_automations=pause,
                repeat=self._check_repeat(repeat, start, end),
                anchor_day=dt_util.as_local(start).day,
            )
            self.schedule.append(window)
            self.schedule.sort(key=lambda w: w.start)
            await self._commit()
            return window

    async def async_update_window(
        self,
        window_id: str,
        *,
        start: datetime,
        end: datetime | None,
        reason: str,
        pages: list[str],
        pause: bool,
        repeat: str = "none",
    ) -> None:
        async with self._lock:
            window = self._find(window_id)
            start, end = self._check_window(start, end, ignore_id=window_id)
            window.start, window.end = start, end
            window.reason = self._check_reason(reason)
            window.pages = clean_pages(pages)
            window.pause_automations = pause
            window.repeat = self._check_repeat(repeat, start, end)
            window.anchor_day = dt_util.as_local(start).day
            self.schedule.sort(key=lambda w: w.start)
            await self._commit()

    async def async_delete_window(self, window_id: str) -> None:
        async with self._lock:
            self.schedule.remove(self._find(window_id))
            await self._commit()

    async def async_delete_history(self, history_id: str) -> None:
        """Supprime une entrée de l'historique."""
        async with self._lock:
            kept = [h for h in self.history if h.get("hid") != history_id]
            if len(kept) == len(self.history):
                raise ServiceValidationError("Entrée d'historique introuvable.")
            self.history = kept
            await self._commit()

    async def async_clear_history(self, older_than: timedelta | None = None) -> int:
        """Efface tout l'historique, ou seulement les entrées terminées depuis plus de `older_than`."""
        async with self._lock:
            before = len(self.history)
            if older_than is None:
                self.history = []
            else:
                limit = dt_util.utcnow() - older_than
                self.history = [
                    h for h in self.history
                    if (ended := parse_iso(h.get("ended_at"))) is None or ended >= limit
                ]
            removed = before - len(self.history)
            if removed:
                await self._commit()
            return removed

    async def async_update_config(
        self, changes: dict[str, Any], actor_perms: set[str] | None = None
    ) -> None:
        """Applique des réglages. `actor_perms` : autorisations de l'appelant (None = tout)
        — il ne peut pas accorder à d'autres des droits qu'il n'a pas lui-même."""
        async with self._lock:
            await self._refresh_users()
            valid = {u["id"] for u in self.users}
            cfg = self.config
            if "automations" in changes:
                cfg["automations"] = sorted(
                    {e for e in changes["automations"] if isinstance(e, str) and e.startswith("automation.")}
                )
            if "allowed_users" in changes:
                cfg["allowed_users"] = [u for u in dict.fromkeys(changes["allowed_users"]) if u in valid]
            if "warn_minutes" in changes:
                cfg["warn_minutes"] = max(1, min(1440, int(changes["warn_minutes"])))
            if "end_soon_minutes" in changes:
                cfg["end_soon_minutes"] = max(1, min(1440, int(changes["end_soon_minutes"])))
            if "message" in changes:
                cfg["message"] = str(changes["message"]).strip()[:255] or DEFAULT_MESSAGE
            if "notify_services" in changes:
                cfg["notify_services"] = [
                    n
                    for n in dict.fromkeys(changes["notify_services"])
                    if _NOTIFY_NAME.match(n) and n not in FORBIDDEN_NOTIFY
                ][:20]
            if "notify_kinds" in changes:
                cfg["notify_kinds"] = [k for k in NOTIFY_KINDS if k in changes["notify_kinds"]]
            if "banner_mode" in changes and changes["banner_mode"] in BANNER_MODES:
                cfg["banner_mode"] = changes["banner_mode"]
            if "banner_scroll" in changes:
                cfg["banner_scroll"] = bool(changes["banner_scroll"])
            if "templates" in changes:
                cfg["templates"] = self._clean_templates(changes["templates"])

            # rôles puis affectations (les affectations sont validées avec les nouveaux rôles)
            roles = cfg["roles"]
            if "roles" in changes:
                roles = self._clean_roles(changes["roles"])
                if actor_perms is not None:
                    old = {r["id"]: r for r in cfg["roles"]}
                    for role in roles:
                        if old.get(role["id"]) != role and not set(role["permissions"]) <= actor_perms:
                            raise ServiceValidationError(
                                "Tu ne peux pas accorder des droits que tu n'as pas toi-même."
                            )
            access = dict(cfg["panel_access"])
            if "panel_access" in changes:
                access = {
                    uid: rid
                    for uid, rid in changes["panel_access"].items()
                    if uid in valid and self.role_exists(rid, roles)
                }
                if actor_perms is not None:
                    for uid, rid in access.items():
                        if cfg["panel_access"].get(uid) != rid and not self.role_perms(rid, roles) <= actor_perms:
                            raise ServiceValidationError(
                                "Tu ne peux pas accorder des droits que tu n'as pas toi-même."
                            )
            # un rôle supprimé : ses utilisateurs retombent sur le rôle par défaut
            cfg["panel_access"] = {u: r for u, r in access.items() if self.role_exists(r, roles)}
            cfg["roles"] = roles
            await self._commit()

    # ------------------------------------------------------------------ validation
    # ------------------------------------------------------------------ interne
    async def _refresh_users(self) -> None:
        users = await self.hass.auth.async_get_users()
        self.users = [
            {"id": u.id, "name": u.name or u.id, "is_owner": u.is_owner, "is_admin": u.is_admin}
            for u in users
            if u.is_active and not u.system_generated
        ]
        self.owner_ids = [u["id"] for u in self.users if u["is_owner"]]

    @callback
    def _update_issues(self) -> None:
        """Alertes dans Paramètres → Réparations."""
        if not self.hass.is_running:
            return
        missing = [e for e in self.config["automations"] if self.hass.states.get(e) is None]
        if missing:
            ir.async_create_issue(
                self.hass, DOMAIN, "missing_automations",
                is_fixable=False, severity=ir.IssueSeverity.WARNING,
                translation_key="missing_automations",
                translation_placeholders={"entities": ", ".join(missing)},
            )
        else:
            ir.async_delete_issue(self.hass, DOMAIN, "missing_automations")

    async def _commit(self, *, now: bool = False) -> None:
        """Applique et enregistre l'état.

        `now=True` : transitions de maintenance (démarrage, fin, échéances) — écriture IMMÉDIATE, car
        c'est ce qui doit survivre à un arrêt brutal. Sinon (réglages, planning, historique…), l'écriture
        est différée de quelques secondes et groupée : une rafale de modifications = une seule écriture.
        Rien n'est perdu : l'écriture en attente est terminée au déchargement et à l'arrêt de HA.
        """
        await self._refresh_users()
        await self._send_due_notifications(dt_util.utcnow())
        self._reschedule()
        self._update_issues()
        if now:
            await self._store.async_save(self._data_to_save())
        else:
            self._store.async_delay_save(self._data_to_save, SAVE_DELAY)
        for update in list(self._listeners):
            update()
        async_dispatcher_send(self.hass, SIGNAL_STATE_UPDATED)   # panneaux ouverts (toutes instances)
