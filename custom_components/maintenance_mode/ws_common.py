"""Outils communs des commandes websocket : vérification des droits côté serveur et erreurs à code stable."""
from __future__ import annotations

from typing import Any

from homeassistant.components import websocket_api
from homeassistant.exceptions import HomeAssistantError, Unauthorized

from . import errors
from .const import DOMAIN
from .manager import get_manager


def _send_error(connection, msg_id: int, code: str, key: str, **placeholders: Any) -> None:
    """Erreur avec code stable : le panneau traduit `translation_key` dans la langue de l'utilisateur."""
    connection.send_error(
        msg_id, code, errors.message(key, **placeholders),
        translation_key=key, translation_domain=DOMAIN,
        translation_placeholders={k: str(v) for k, v in placeholders.items()} or None,
    )


def _command(perm: str | None = None):
    """Vérifie côté serveur que l'appelant possède l'autorisation `perm` (None = tout rôle)."""

    def decorator(func):
        async def wrapper(hass, connection, msg, *_):
            manager = get_manager(hass)
            if manager is None:
                _send_error(connection, msg["id"], "not_loaded", "not_loaded")
                return
            if perm and perm not in manager.perms_for(connection.user):
                _send_error(connection, msg["id"], websocket_api.ERR_UNAUTHORIZED, "access_denied")
                return
            try:
                result = await func(hass, connection, msg, manager)
            except Unauthorized:
                _send_error(connection, msg["id"], websocket_api.ERR_UNAUTHORIZED, "access_denied")
                return
            except errors.MaintenanceError as err:
                _send_error(connection, msg["id"], "invalid", err.code, **err.placeholders)
                return
            except HomeAssistantError as err:
                connection.send_error(msg["id"], "invalid", str(err))
                return
            connection.send_result(msg["id"], result)

        return websocket_api.async_response(wrapper)

    return decorator
