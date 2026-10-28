"""Suspension des automatisations pendant une maintenance (instantané, remise en pause, réactivation)."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.const import STATE_ON
from homeassistant.util import dt as dt_util

from .const import EVENT_ENDED, EVENT_STARTED, MAX_HISTORY
from .window import Window, iso
import uuid

_LOGGER = logging.getLogger(__name__)


class SuspensionMixin:
    """Démarre / termine une maintenance. Suppose `hass`, `config`, `current`, `disabled`, `history`, `_lock`
    et `_notify` du gestionnaire."""

    def _targets(self) -> list[str]:
        """Automatisations à couper : celles choisies, ou toutes si aucune choisie."""
        selected = self.config["automations"]
        candidates = selected or self.hass.states.async_entity_ids("automation")
        return [
            e for e in candidates
            if (state := self.hass.states.get(e)) and state.state == STATE_ON
        ]

    async def _activate(self, window: Window) -> None:
        targets = self._targets() if window.pause_automations else []
        if targets:
            try:
                await self.hass.services.async_call(
                    "automation", "turn_off",
                    {"entity_id": targets, "stop_actions": True}, blocking=True,
                )
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Impossible de désactiver les automatisations")
        self.disabled = targets
        self.current = window
        self.hass.bus.async_fire(EVENT_STARTED, window.as_dict())
        await self._notify("started", window)

    async def _deactivate(self, ended_by: str = "manual") -> None:
        window = self.current
        if self.disabled:
            try:
                await self.hass.services.async_call(
                    "automation", "turn_on", {"entity_id": self.disabled}, blocking=True
                )
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Impossible de réactiver les automatisations")
        self.disabled = []
        self.current = None
        if window:
            now = dt_util.utcnow()
            self.history.append(
                {**window.as_dict(), "hid": uuid.uuid4().hex[:8], "ended_at": iso(now), "ended_by": ended_by}
            )
            self.history = self.history[-MAX_HISTORY:]
            self.hass.bus.async_fire(EVENT_ENDED, {**window.as_dict(), "ended_by": ended_by})
            if ended_by != "replaced":
                await self._notify("ended", window)

    async def _reapply_suspension(self) -> None:
        """Remet en pause les automatisations de l'instantané redevenues actives.

        Cas réels : redémarrage de HA (`initial_state: true` écrase l'état restauré ; après un
        arrêt brutal l'état est celui de la dernière sauvegarde) ou rechargement des automatisations
        modifiées. On ne touche qu'à l'instantané : une automatisation créée pendant la maintenance
        n'est pas suspendue, et si aucune maintenance ne suspend rien, on ne fait rien.
        """
        if not self.current or not self.disabled:
            return
        again = [
            e for e in self.disabled
            if (state := self.hass.states.get(e)) and state.state == STATE_ON
        ]
        if not again:
            return
        _LOGGER.info("Maintenance en cours : %d automatisation(s) remises en pause", len(again))
        try:
            await self.hass.services.async_call(
                "automation", "turn_off", {"entity_id": again, "stop_actions": True}, blocking=True
            )
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Impossible de remettre les automatisations en pause")

    async def _async_on_automation_reload(self, _event: Any) -> None:
        if self._unloaded or not self.current or not self.disabled:
            return
        async with self._lock:
            await self._reapply_suspension()
