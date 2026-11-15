"""Suspension / réactivation PAR LOTS : le travail est découpé, chaque lot a un délai d'attente, un lot en échec
n'empêche pas les suivants (reprise partielle) et la progression est visible dans le panneau.

Pourquoi : un seul appel pour des centaines d'automatisations peut durer longtemps (chacune arrête ses actions en
cours) et, s'il échoue ou se bloque, tout est perdu d'un coup. Par lots, la boucle d'évènements respire entre deux
lots, un blocage est borné (`BATCH_TIMEOUT`) et seules les automatisations du lot en échec restent à traiter.
"""
from __future__ import annotations

import asyncio
import logging

from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import BATCH_PAUSE, BATCH_SIZE, BATCH_TIMEOUT, SIGNAL_STATE_UPDATED

_LOGGER = logging.getLogger(__name__)


class BatchingMixin:
    """Suppose `hass` et `progress` du gestionnaire."""

    async def _call_batched(
        self, service: str, entities: list[str], *, phase: str, stop_actions: bool = False, size: int | None = None
    ) -> list[str]:
        """Appelle `automation.<service>` par lots ; renvoie les entités des lots en échec (erreur ou délai dépassé).

        La progression n'est publiée que si le travail dépasse un lot (sinon elle n'aurait pas le temps d'être vue).
        """
        size = size or BATCH_SIZE
        total, done, failed = len(entities), 0, []
        visible = total > BATCH_SIZE
        for start in range(0, total, size):
            chunk = entities[start:start + size]
            data = {"entity_id": chunk, **({"stop_actions": True} if stop_actions else {})}
            try:
                async with asyncio.timeout(BATCH_TIMEOUT):
                    await self.hass.services.async_call("automation", service, data, blocking=True)
            except Exception:  # noqa: BLE001 - TimeoutError comprise ; un lot en échec ne bloque pas les autres
                _LOGGER.exception("Lot de %d automatisation(s) en échec (%s)", len(chunk), service)
                failed += chunk
            done += len(chunk)
            if visible:
                self.progress = {"phase": phase, "done": done, "total": total}
                async_dispatcher_send(self.hass, SIGNAL_STATE_UPDATED)
            await asyncio.sleep(BATCH_PAUSE)        # laisse la boucle d'évènements respirer entre deux lots
        self.progress = None
        return failed
