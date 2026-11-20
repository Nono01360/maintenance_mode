"""Suspension des automatisations pendant une maintenance (instantané, remise en pause, réactivation)."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.const import STATE_ON
from homeassistant.util import dt as dt_util

from .errors import MaintenanceError
from .const import EVENT_ENDED, EVENT_STARTED, MAX_HISTORY
from .window import Window, iso
import uuid

_LOGGER = logging.getLogger(__name__)


class SuspensionMixin:
    """Démarre / termine une maintenance. Suppose `hass`, `config`, `current`, `disabled`, `history`, `_lock`
    et `_notify` du gestionnaire."""

    async def _activate(self, window: Window, targets: list[str] | None = None) -> None:
        """`targets` n'est donné que pour rejouer une bascule interrompue (liste déjà décidée avant l'arrêt)."""
        self._apply_max_duration(window)
        if targets is None:
            targets = self.plan_suspension()["suspend"] if window.pause_automations else []
        failed: list[str] = []
        if targets:
            await self._begin("activate", window=window.as_dict(), targets=targets)
            failed = await self._call_batched("turn_off", targets, phase="suspend", stop_actions=True)
        self.disabled = targets
        self._reapply_failed = failed      # lots en échec : alerte « Réparer » = réessayer (reconcile.py)
        self.current = window
        self._report_start()
        self.hass.bus.async_fire(EVENT_STARTED, window.as_dict())
        await self._notify("started", window)
        self.pending = None      # effacé par l'enregistrement qui suit

    async def _start_with_hooks(self, window: Window, *, scheduled: bool = False) -> None:
        """Démarre `window` : hooks « avant », (remplacement de la maintenance en cours), suspension, état écrit, hooks « après »."""
        before: list[dict] = []
        aborted_by = await self._run_hooks("before_start", before)
        if aborted_by:
            if not scheduled:
                raise MaintenanceError("hook_aborted", name=aborted_by)
            entry = {**window.as_dict(), "hid": uuid.uuid4().hex[:8], "ended_at": iso(dt_util.utcnow()),
                     "ended_by": "hook_aborted", "hooks": before}
            self.history = [*self.history, entry][-MAX_HISTORY:]
            return
        if self.current:
            await self._deactivate("replaced")
        self.hook_results = before
        await self._activate(window)
        await self._commit(now=True)            # l'état est écrit AVANT les hooks « après » (qui peuvent être longs)
        await self._run_hooks("after_start", self.hook_results)
        await self._commit()

    async def _deactivate(self, ended_by: str = "manual", *, hooks: bool = True) -> None:
        window = self.current
        if window and hooks:
            await self._run_hooks("before_end", self.hook_results)
        if self.disabled:
            await self._begin("deactivate", ended_by=ended_by)
            failed = await self._call_batched("turn_on", self.disabled, phase="resume")
            if failed:       # les lots en échec sont réessayés une par une
                failed = await self._call_batched("turn_on", failed, phase="resume", size=1)
            if failed:
                _LOGGER.error("Automatisations non réactivées : %s", ", ".join(failed))
        self.disabled = []
        self._reapply_failed = []
        self.current = None
        if window:
            now = dt_util.utcnow()
            self.history.append(
                {**window.as_dict(), "hid": uuid.uuid4().hex[:8], "ended_at": iso(now), "ended_by": ended_by}
            )
            entry = self.history[-1]
            entry["report"] = self._report_finish(window)
            if self.hook_results:
                entry["hooks"] = list(self.hook_results)
            self.history = self.history[-MAX_HISTORY:]
            self.hass.bus.async_fire(EVENT_ENDED, {**window.as_dict(), "ended_by": ended_by})
            if ended_by != "replaced":
                await self._notify("ended", window)
            if hooks:
                await self._run_hooks("after_end", self.hook_results)
                if self.hook_results:
                    entry["hooks"] = list(self.hook_results)
        self.hook_results = []
        self.pending = None      # effacé par l'enregistrement qui suit

    async def _reapply_suspension(self) -> None:
        """Remet en pause les automatisations de l'instantané redevenues actives.

        Cas réels : redémarrage de HA (`initial_state: true` écrase l'état restauré ; après un
        arrêt brutal l'état est celui de la dernière sauvegarde) ou rechargement des automatisations
        modifiées. On ne touche qu'à l'instantané : une automatisation créée pendant la maintenance
        n'est pas suspendue, et si aucune maintenance ne suspend rien, on ne fait rien.
        """
        again = [
            e for e in self.disabled
            if self.current and (state := self.hass.states.get(e)) and state.state == STATE_ON
        ]
        if not again:
            self._reapply_failed = []
            return
        _LOGGER.info("Maintenance en cours : %d automatisation(s) remises en pause", len(again))
        await self._call_batched("turn_off", again, phase="suspend", stop_actions=True)
        # celles qui restent actives : écart signalé dans Réparations (bouton « Réparer » = réessayer)
        self._reapply_failed = [
            e for e in again if (state := self.hass.states.get(e)) and state.state == STATE_ON
        ]

    async def _async_on_automation_reload(self, _event: Any) -> None:
        if self._unloaded or not self.current or not self.disabled:
            return
        async with self._lock:
            await self._reapply_suspension()
            self._update_issues()
