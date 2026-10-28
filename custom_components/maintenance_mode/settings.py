"""Réglages et historique : mise à jour des réglages (avec anti-escalade des droits) et suppression d'historique."""
from __future__ import annotations

import re
from typing import Any
from datetime import timedelta

from homeassistant.exceptions import ServiceValidationError
from homeassistant.util import dt as dt_util

from .const import BANNER_MODES, DEFAULT_MESSAGE, FORBIDDEN_NOTIFY, NOTIFY_KINDS
from .window import parse_iso

_NOTIFY_NAME = re.compile(r"^[a-z0-9_]+$")


class SettingsMixin:
    """Suppose `config`, `users`, `history`, `_lock`, `_commit`, `_refresh_users`, `_clean_templates`,
    `_clean_roles`, `role_exists` et `role_perms` du gestionnaire."""

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
            if "compat_mode" in changes:
                cfg["compat_mode"] = bool(changes["compat_mode"])
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
