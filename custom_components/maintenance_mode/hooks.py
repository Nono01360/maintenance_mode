"""Hooks avant / après : un script ou une scène exécuté à un moment précis d'une maintenance.

Quatre moments : `before_start` (avant toute suspension), `after_start`, `before_end` (avant la réactivation, les
automatisations sont encore suspendues), `after_end`. Les hooks d'un moment s'exécutent UN PAR UN dans l'ordre de la
liste. Chacun a un délai maximum ; l'ensemble d'un moment a un budget (`HOOKS_PHASE_BUDGET`). Politique d'échec :
`continue` (défaut) ou `abort`, ce dernier seulement pour `before_start` : le démarrage est alors annulé (une maintenance
planifiée est abandonnée et notée dans l'historique). Les résultats sont gardés dans l'historique.

Protection contre les boucles : un hook s'exécute avec son propre contexte ; si le script rappelle un service de
l'intégration (start, stop…), l'appel est REFUSÉ au lieu d'attendre le verrou que le hook tient lui-même.
Pas d'éditeur d'actions : on désigne seulement un script ou une scène existants.
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any

from homeassistant.core import Context
from homeassistant.helpers import entity_registry as er

from .const import (
    DEFAULT_HOOK_TIMEOUT, HOOK_DOMAINS, HOOK_WHEN, HOOKS_PHASE_BUDGET, MAX_HOOK_TIMEOUT, MAX_HOOKS,
)
from .errors import MaintenanceError

_LOGGER = logging.getLogger(__name__)


def clean_hooks(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for r in raw:
        when, entity = r.get("when"), str(r.get("entity_id", "")).strip()
        if when not in HOOK_WHEN or "." not in entity or len(entity) > 255 or entity.split(".")[0] not in HOOK_DOMAINS:
            continue
        try:
            timeout = DEFAULT_HOOK_TIMEOUT if r.get("timeout") is None else float(r["timeout"])
        except (TypeError, ValueError):
            timeout = DEFAULT_HOOK_TIMEOUT
        out.append({
            "id": str(r.get("id") or uuid.uuid4().hex[:8])[:12],
            "name": (str(r.get("name", "")).strip() or entity)[:40],
            "when": when,
            "entity_id": entity,
            "timeout": max(1, min(MAX_HOOK_TIMEOUT, timeout)),
            "on_failure": "abort" if r.get("on_failure") == "abort" and when == "before_start" else "continue",
        })
        if len(out) >= MAX_HOOKS:
            break
    return out


class HooksMixin:
    """Suppose `hass`, `config`, `_hook_contexts`."""

    def check_not_in_hook(self, context: Context | None) -> None:
        """Refuse un appel venant d'un hook en cours (sinon : attente du verrou que ce hook tient = blocage)."""
        if context is not None and context.id in self._hook_contexts:
            raise MaintenanceError("hook_loop")

    async def _run_hooks(self, when: str, results: list[dict[str, Any]]) -> str | None:
        """Exécute les hooks de `when`, ajoute leurs résultats à `results` ; renvoie le nom du hook qui annule, sinon None."""
        deadline = time.monotonic() + HOOKS_PHASE_BUDGET
        for hook in (h for h in self.config["hooks"] if h["when"] == when):
            remaining = deadline - time.monotonic()
            res = {"id": hook["id"], "name": hook["name"], "when": when, "entity_id": hook["entity_id"]}
            if remaining <= 0:
                res.update(status="skipped", seconds=0)
            else:
                res.update(await self._run_one_hook(hook, min(hook["timeout"], remaining)))
            results.append(res)
            if res["status"] != "ok":
                _LOGGER.warning("Hook « %s » (%s) : %s %s", hook["name"], when, res["status"], res.get("error", ""))
                if hook["on_failure"] == "abort":
                    return hook["name"]
        return None

    async def _run_one_hook(self, hook: dict[str, Any], timeout: float) -> dict[str, Any]:
        entity_id = hook["entity_id"]
        domain, object_id = entity_id.split(".", 1)
        if self.hass.states.get(entity_id) is None:
            return {"status": "missing", "seconds": 0}
        if domain == "script":     # le service porte l'identifiant du script, qui peut différer de l'entité renommée
            entry = er.async_get(self.hass).async_get(entity_id)
            service, data = (entry.unique_id if entry and entry.unique_id else object_id), {}
        else:
            service, data = "turn_on", {"entity_id": entity_id}
        context = Context()
        self._hook_contexts.add(context.id)
        started, status, error = time.monotonic(), "ok", None
        try:
            async with asyncio.timeout(timeout):
                await self.hass.services.async_call(domain, service, data, blocking=True, context=context)
        except TimeoutError:
            status = "timeout"
        except Exception as err:  # noqa: BLE001 - un hook en échec ne doit jamais faire planter la bascule
            status, error = "failed", str(err)[:200]
        finally:
            self._hook_contexts.discard(context.id)
        res = {"status": status, "seconds": round(time.monotonic() - started, 1)}
        if error:
            res["error"] = error
        return res
