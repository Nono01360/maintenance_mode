"""Annulation d'une suppression pendant quelques secondes (maintenance planifiée, modèle).

L'élément supprimé est gardé EN MÉMOIRE seulement (jamais écrit sur le disque) pendant `UNDO_SECONDS` ; l'annuler le
remet à l'identique (même identifiant, mêmes champs).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

from homeassistant.exceptions import Unauthorized
from homeassistant.util import dt as dt_util

from .const import MAX_TEMPLATES
from .errors import MaintenanceError
from .window import Window, overlap

UNDO_SECONDS = 10
_NEEDS = {"window": "schedule", "template": "templates"}   # autorisation requise pour annuler chaque type
_KEEP = 5


class TrashMixin:
    """Suppose `config`, `schedule`, `_lock` et `_commit` du gestionnaire, et `_trash` (dict) initialisé par lui."""

    def _stash(self, kind: str, item: Any, index: int) -> dict[str, Any]:
        now = dt_util.utcnow()
        self._trash = {t: v for t, v in self._trash.items() if v["expires"] > now}
        token = uuid.uuid4().hex[:8]
        self._trash[token] = {"kind": kind, "item": item, "index": index, "expires": now + timedelta(seconds=UNDO_SECONDS)}
        for old in list(self._trash)[:-_KEEP]:
            del self._trash[old]
        return {"token": token, "kind": kind, "seconds": UNDO_SECONDS}

    async def async_delete_template(self, template_id: str) -> dict[str, Any]:
        async with self._lock:
            templates = self.config["templates"]
            for i, t in enumerate(templates):
                if t["id"] == template_id:
                    del templates[i]
                    undo = self._stash("template", t, i)
                    await self._commit()
                    return undo
            raise MaintenanceError("template_not_found")

    async def async_undo(self, token: str, perms: set[str]) -> str:
        """Restaure l'élément supprimé ; renvoie son type. Refuse si le délai est passé ou si l'appelant n'en a pas le droit."""
        async with self._lock:
            now = dt_util.utcnow()
            entry = self._trash.get(token)
            if entry is None or entry["expires"] <= now:
                self._trash.pop(token, None)
                raise MaintenanceError("undo_expired")
            if _NEEDS[entry["kind"]] not in perms:
                raise Unauthorized
            kind, item, index = entry["kind"], entry["item"], entry["index"]
            if kind == "window":
                self._restore_window(item, now)
            else:
                templates = self.config["templates"]
                if len(templates) >= MAX_TEMPLATES:
                    raise MaintenanceError("undo_expired")
                templates.insert(min(index, len(templates)), item)
            del self._trash[token]
            await self._commit()
            return kind

    def _restore_window(self, window: Window, now: datetime) -> None:
        """Remet la maintenance dans le planning si rien ne s'y oppose (début passé ou créneau pris depuis)."""
        if window.start <= now:
            raise MaintenanceError("undo_expired")
        for other in self.schedule:
            if overlap(window.start, window.end, other.start, other.end):
                raise MaintenanceError("overlaps_scheduled")
        if self.current and self.current.end and overlap(window.start, window.end, self.current.start, self.current.end):
            raise MaintenanceError("overlaps_current")
        self.schedule.append(window)
        self.schedule.sort(key=lambda w: w.start)
