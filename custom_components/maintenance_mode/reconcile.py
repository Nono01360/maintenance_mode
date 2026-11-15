"""Réconciliation : écarts entre ce que l'intégration croit et l'état réel, alertes « Réparations » réparables.

Trois écarts sont surveillés (à chaque enregistrement, au démarrage et après un rechargement des automatisations) :
- `missing_automations` : une automatisation SÉLECTIONNÉE n'existe plus -> « Réparer » la retire de la sélection ;
- `missing_suspended`   : une automatisation suspendue par la maintenance en cours a disparu -> « Réparer » l'oublie
                          (la fin de la maintenance n'essaiera plus de la réactiver) ;
- `reapply_failed`      : la remise en pause après un redémarrage / rechargement a échoué -> « Réparer » réessaie.
Une réparation sans rien à corriger est sans effet (idempotente).
"""
from __future__ import annotations

from homeassistant.const import STATE_ON
from homeassistant.core import callback
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN, RECONCILE_ISSUES


class ReconcileMixin:
    """Suppose `hass`, `config`, `current`, `disabled`, `_reapply_failed`, `_lock`, `_commit` et `_reapply_suspension`."""

    def _gone(self, entity_id: str) -> bool:
        return self.hass.states.get(entity_id) is None

    def find_discrepancies(self) -> dict[str, list[str]]:
        """Les entités concernées par chaque écart (liste vide = pas d'écart)."""
        on = lambda e: (s := self.hass.states.get(e)) is not None and s.state == STATE_ON  # noqa: E731
        return {
            "missing_automations": [e for e in self.config["automations"] if self._gone(e)],
            "missing_suspended": [e for e in self.disabled if self._gone(e)] if self.current else [],
            "reapply_failed": [e for e in self._reapply_failed if on(e)] if self.current else [],
        }

    @callback
    def _update_issues(self) -> None:
        """Alertes dans Paramètres → Réparations."""
        if not self.hass.is_running:
            return
        for key, entities in self.find_discrepancies().items():
            if entities:
                ir.async_create_issue(
                    self.hass, DOMAIN, key,
                    is_fixable=True,
                    severity=ir.IssueSeverity.ERROR if key == "reapply_failed" else ir.IssueSeverity.WARNING,
                    translation_key=key,
                    translation_placeholders={"entities": ", ".join(entities)},
                )
            else:
                ir.async_delete_issue(self.hass, DOMAIN, key)

    @callback
    def _clear_issues(self) -> None:
        for key in RECONCILE_ISSUES:
            ir.async_delete_issue(self.hass, DOMAIN, key)

    async def async_repair(self, issue_id: str) -> None:
        """Corrige l'écart (bouton « Réparer »)."""
        async with self._lock:
            if issue_id == "missing_automations":
                self.config["automations"] = [e for e in self.config["automations"] if not self._gone(e)]
            elif issue_id == "missing_suspended":
                self.disabled = [e for e in self.disabled if not self._gone(e)]
            elif issue_id == "reapply_failed":
                await self._reapply_suspension()
            await self._commit(now=issue_id != "missing_automations")
