"""Bascule transactionnelle : un marqueur « bascule en cours » est écrit AVANT de toucher aux automatisations.

Démarrer ou terminer une maintenance suspend / réactive des automatisations (effet hors du fichier de stockage), puis
enregistre l'état. Un arrêt brutal entre les deux laisserait des automatisations coupées sans trace. On écrit donc
d'abord un marqueur (`pending`) avec ce qu'on s'apprête à faire ; l'enregistrement final de l'état l'efface. Au
démarrage, un marqueur encore présent signale une bascule interrompue : elle est REJOUÉE jusqu'au bout (chaque étape
est idempotente : éteindre une automatisation éteinte ou rallumer une automatisation allumée ne change rien).

Garantie : après un arrêt brutal à n'importe quelle étape, l'état est cohérent (maintenance en cours ET exactement ses
automatisations suspendues, ou aucune maintenance ET rien de suspendu par nous). Les évènements du bus et les
notifications d'une bascule rejouée peuvent être émis une seconde fois (les notifications sont dédoublonnées).
"""
from __future__ import annotations

import logging

from .window import Window

_LOGGER = logging.getLogger(__name__)
PENDING_OPS = ("activate", "deactivate")


class TransactionMixin:
    """Suppose `hass`, `pending`, `current`, `disabled`, `_store`, `_data_to_save`, `_activate` et `_deactivate`."""

    async def _begin(self, op: str, **data) -> None:
        """Écrit tout de suite le marqueur (et l'état courant) avant la première action sur les automatisations."""
        self.pending = {"op": op, **data}
        await self._store.async_save(self._data_to_save())

    async def _async_recover(self) -> None:
        """Termine une bascule interrompue (appelé au démarrage, avant le rattrapage des échéances)."""
        pending, self.pending = self.pending, None
        if not pending:
            return
        _LOGGER.warning("Bascule interrompue (%s) : reprise", pending.get("op"))
        if pending["op"] == "activate":
            window = Window.from_dict(pending.get("window") or {})
            if window is None:
                return
            targets = [e for e in pending.get("targets", []) if self.hass.states.get(e)]
            await self._activate(window, targets)
        else:
            await self._deactivate(pending.get("ended_by", "manual"))
