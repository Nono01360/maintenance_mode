"""Limites : tailles maximales des saisies et limitation douce des modifications de réglages."""
from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta

import voluptuous as vol

from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

# Plafonds « techniques » du schéma : refusent d'emblée une charge absurde. Les règles métier plus fines
# (motif de 200 caractères, 30 pages, 20 modèles…) restent vérifiées par le gestionnaire, avec un message clair.
MAX_TEXT = 1000          # motif, message, nom
MAX_ID = 64              # identifiants (maintenance, historique, utilisateur, rôle, modèle)
MAX_PAGE_PATH = 200
MAX_LIST = 100           # pages, services de notification, rôles, modèles…
MAX_ENTITIES = 2000      # automatisations sélectionnées
MAX_USERS = 1000

TEXT = vol.All(cv.string, vol.Length(max=MAX_TEXT))
ID = vol.All(cv.string, vol.Length(max=MAX_ID))
PAGE = vol.All(cv.string, vol.Length(max=MAX_PAGE_PATH))
PAGES = vol.All([PAGE], vol.Length(max=MAX_LIST))


def bounded_list(item: vol.Schema | type, maximum: int):
    return vol.All([item], vol.Length(max=maximum))


class RateLimiter:
    """Au plus `maximum` évènements par fenêtre glissante de `seconds` secondes (horloge de Home Assistant)."""

    def __init__(self, maximum: int, seconds: int) -> None:
        self.maximum = maximum
        self.window = timedelta(seconds=seconds)
        self._hits: deque[datetime] = deque()

    def allow(self) -> bool:
        now = dt_util.utcnow()
        while self._hits and now - self._hits[0] >= self.window:
            self._hits.popleft()
        if len(self._hits) >= self.maximum:
            return False
        self._hits.append(now)
        return True
