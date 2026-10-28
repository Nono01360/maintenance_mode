"""Rôles et autorisations : qui voit et peut faire quoi, et vue d'état filtrée pour le panneau."""
from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from homeassistant.util import dt as dt_util

from .const import (
    BUILTIN_ROLE_PERMISSIONS,
    MAX_ROLE_NAME,
    MAX_ROLES,
    PERMISSIONS,
    ROLE_ADMIN,
    ROLE_VIEWER,
)
from .window import iso

_SETTINGS_KEYS = (
    "automations", "allowed_users", "warn_minutes", "end_soon_minutes", "message",
    "notify_services", "notify_kinds", "banner_mode", "banner_scroll",
)


class AccessMixin:
    """Suppose `config`, `users`, `owner_ids`, `current`, `schedule`, `history` et `disabled` du gestionnaire."""

    @property
    def exempt_users(self) -> list[str]:
        """Utilisateurs jamais bloqués : exemptés choisis + propriétaire(s)."""
        return sorted({*self.config["allowed_users"], *self.owner_ids})

    def client_rights(self, user: Any) -> dict[str, bool]:
        """Ce que le navigateur de CET utilisateur a besoin de savoir (jamais celui des autres)."""
        return {
            "exempt": bool(user.is_owner or user.id in self.config["allowed_users"]),
            "panel_hidden": bool(not user.is_owner and "view" not in self.perms_for(user)),
        }

    @property
    def rights_revision(self) -> str:
        """Empreinte (sans identifiant lisible) de ce qui détermine les droits d'affichage : le navigateur ne
        redemande les siens au serveur que lorsqu'elle change."""
        raw = json.dumps([self.exempt_users, self.hidden_panel_users], sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()[:10]

    @property
    def hidden_panel_users(self) -> list[str]:
        """Utilisateurs sans accès au panneau (son entrée de menu est masquée)."""
        return [
            u["id"]
            for u in self.users
            if "view" not in self.role_perms(
                self.effective_role(u["id"], u["is_owner"], u["is_admin"])
            )
        ]

    @staticmethod
    def _normalize_perms(perms) -> list[str]:
        wanted = {p for p in perms if p in PERMISSIONS}
        if wanted:
            wanted.add("view")  # sans « view » les autres droits seraient inutilisables
        if "history_delete" in wanted:
            wanted.add("history")  # on ne supprime pas ce qu'on ne peut pas voir
        return [p for p in PERMISSIONS if p in wanted]

    def role_perms(self, role_id: str, roles: list[dict[str, Any]] | None = None) -> set[str]:
        if role_id in BUILTIN_ROLE_PERMISSIONS:
            return set(BUILTIN_ROLE_PERMISSIONS[role_id])
        for role in self.config["roles"] if roles is None else roles:
            if role["id"] == role_id:
                return set(role["permissions"])
        return set()

    def role_exists(self, role_id: str, roles: list[dict[str, Any]] | None = None) -> bool:
        return role_id in BUILTIN_ROLE_PERMISSIONS or any(
            r["id"] == role_id for r in (self.config["roles"] if roles is None else roles)
        )

    def role_name(self, role_id: str) -> str | None:
        for role in self.config["roles"]:
            if role["id"] == role_id:
                return role["name"]
        return None  # rôle intégré : le panneau le traduit

    def effective_role(self, user_id: str, is_owner: bool, is_admin: bool) -> str:
        if is_owner:
            return ROLE_ADMIN
        role = self.config["panel_access"].get(user_id)
        if role and self.role_exists(role):
            return role
        return ROLE_ADMIN if is_admin else ROLE_VIEWER

    def role_for(self, user: Any) -> str:
        return self.effective_role(user.id, user.is_owner, user.is_admin)

    def perms_for(self, user: Any) -> set[str]:
        return self.role_perms(self.role_for(user))

    def state_for(self, user: Any) -> dict[str, Any]:
        """Données envoyées au panneau, filtrées selon les autorisations."""
        role = self.role_for(user)
        perms = self.role_perms(role)
        if "view" not in perms:
            return {"role": role, "role_name": self.role_name(role), "permissions": []}
        data: dict[str, Any] = {
            "role": role,
            "role_name": self.role_name(role),
            "permissions": [p for p in PERMISSIONS if p in perms],
            "now": iso(dt_util.utcnow()),
            "active": self.current is not None,
            "current": self.current.as_dict(public=True) if self.current else None,
            "upcoming": [w.as_dict(public=True) for w in self.schedule],
            "message": self.config["message"],
        }
        cfg: dict[str, Any] = {}
        if "settings" in perms:
            for key in _SETTINGS_KEYS:
                value = self.config[key]
                cfg[key] = list(value) if isinstance(value, list) else value
        if perms & {"templates", "schedule", "control"}:
            cfg["templates"] = [dict(t) for t in self.config["templates"]]
        if "access" in perms:
            cfg["roles"] = [dict(r) for r in self.config["roles"]]
            cfg["panel_access"] = dict(self.config["panel_access"])
        if cfg:
            data["config"] = cfg
        if perms & {"settings", "access"}:
            access = self.config["panel_access"]
            data["users"] = [
                {
                    **u,
                    "role": self.effective_role(u["id"], u["is_owner"], u["is_admin"]),
                    "explicit": u["id"] in access,
                }
                for u in self.users
            ]
        if perms & {"control", "settings"}:
            data["disabled_count"] = len(self.disabled)
        if "history" in perms:
            data["history"] = list(reversed(self.history))[:20]
        return data

    def _clean_roles(self, raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
        existing = {r["id"] for r in self.config["roles"]}
        out: list[dict[str, Any]] = []
        used: set[str] = set()
        for r in raw[:MAX_ROLES]:
            name = str(r.get("name", "")).strip()[:MAX_ROLE_NAME]
            if not name:
                continue
            rid = str(r.get("id") or "")
            if rid in BUILTIN_ROLE_PERMISSIONS or rid in used or (rid and rid not in existing):
                rid = ""  # identifiant inconnu ou déjà pris : on en génère un
            rid = rid or f"r{uuid.uuid4().hex[:6]}"
            used.add(rid)
            out.append(
                {"id": rid, "name": name, "permissions": self._normalize_perms(r.get("permissions", []))}
            )
        return out
