"""API websocket utilisée par le panneau (droits vérifiés côté serveur)."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .limits import ID, PAGES, TEXT
from .const import MAX_DURATION_MINUTES, REPEATS, SIGNAL_STATE_UPDATED
from .manager import get_manager
from .ws_common import _command
from .ws_config import ws_update_config

DATETIME = vol.Any(None, cv.datetime)
MAX_MINUTES = vol.Any(None, vol.All(vol.Coerce(int), vol.Range(min=0, max=MAX_DURATION_MINUTES)))
# NB : le champ « id » est réservé au numéro de message websocket -> « window_id ».


@websocket_api.websocket_command({vol.Required("type"): "maintenance_mode/get_state"})
@_command()
async def ws_get_state(hass, connection, msg, manager) -> dict[str, Any]:
    return manager.state_for(connection.user)


@websocket_api.websocket_command({vol.Required("type"): "maintenance_mode/subscribe"})
@_command()
async def ws_subscribe(hass, connection, msg, manager) -> None:
    @callback
    def _forward() -> None:
        # On relit le gestionnaire COURANT à chaque envoi : après un rechargement de l'intégration,
        # l'abonnement du panneau (inchangé côté navigateur) suit le nouveau gestionnaire.
        current = get_manager(hass)
        if current is not None:
            connection.send_message(
                websocket_api.event_message(msg["id"], current.state_for(connection.user))
            )

    connection.subscriptions[msg["id"]] = async_dispatcher_connect(hass, SIGNAL_STATE_UPDATED, _forward)
    _forward()
    return None


@websocket_api.websocket_command({vol.Required("type"): "maintenance_mode/get_client"})
@_command()
async def ws_get_client(hass, connection, msg, manager) -> dict[str, bool]:
    """Droits d'affichage de l'appelant (bandeau, blocage, entrée de menu), lui seul."""
    return manager.client_rights(connection.user)


@websocket_api.websocket_command({vol.Required("type"): "maintenance_mode/get_catalog"})
@_command("settings")
async def ws_get_catalog(hass, connection, msg, manager) -> dict[str, Any]:
    """Étiquettes disponibles pour les protections (réservé à l'autorisation `settings`)."""
    return manager.catalog()


@websocket_api.websocket_command(
    {
        vol.Required("type"): "maintenance_mode/preview",
        vol.Optional("pages", default=[]): PAGES,
        vol.Optional("pause_automations", default=True): cv.boolean,
    }
)
@_command()
async def ws_preview(hass, connection, msg, manager) -> dict[str, Any]:
    """Aperçu / test à blanc : aucun effet. Réservé aux rôles qui peuvent démarrer ou planifier."""
    if not manager.perms_for(connection.user) & {"control", "schedule"}:
        raise Unauthorized
    return await manager.async_preview(pages=msg["pages"], pause=msg["pause_automations"])


@websocket_api.websocket_command(
    {
        vol.Required("type"): "maintenance_mode/start",
        vol.Optional("end"): DATETIME,
        vol.Optional("reason", default=""): TEXT,
        vol.Optional("pages", default=[]): PAGES,
        vol.Optional("pause_automations", default=True): cv.boolean,
        vol.Optional("max_minutes"): MAX_MINUTES,
        vol.Optional("override_blackout", default=False): cv.boolean,
    }
)
@_command("control")
async def ws_start(hass, connection, msg, manager) -> dict[str, Any]:
    await manager.async_start_now(
        end=msg.get("end"),
        reason=msg["reason"],
        pages=msg["pages"],
        pause=msg["pause_automations"],
        by=connection.user.name or "",
        max_minutes=msg.get("max_minutes"),
        override_blackout=_override(connection, msg),
    )
    return manager.state_for(connection.user)


@websocket_api.websocket_command({vol.Required("type"): "maintenance_mode/stop"})
@_command("control")
async def ws_stop(hass, connection, msg, manager) -> dict[str, Any]:
    await manager.async_stop()
    return manager.state_for(connection.user)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "maintenance_mode/update_current",
        vol.Optional("end"): DATETIME,
        vol.Optional("reason", default=""): TEXT,
        vol.Optional("pages", default=[]): PAGES,
    }
)
@_command("control")
async def ws_update_current(hass, connection, msg, manager) -> dict[str, Any]:
    await manager.async_update_current(
        end=msg.get("end"), reason=msg["reason"], pages=msg["pages"]
    )
    return manager.state_for(connection.user)


def _override(connection, msg) -> bool:
    """Dérogation à une plage interdite : réservée au propriétaire."""
    if msg.get("override_blackout") and not connection.user.is_owner:
        raise Unauthorized
    return bool(msg.get("override_blackout"))


_WINDOW_FIELDS = {
    vol.Required("start"): cv.datetime,
    vol.Optional("end"): DATETIME,
    vol.Optional("reason", default=""): TEXT,
    vol.Optional("pages", default=[]): PAGES,
    vol.Optional("pause_automations", default=True): cv.boolean,
    vol.Optional("repeat", default="none"): vol.In(REPEATS),
    vol.Optional("max_minutes"): MAX_MINUTES,
    vol.Optional("override_blackout", default=False): cv.boolean,
}


@websocket_api.websocket_command(
    {vol.Required("type"): "maintenance_mode/add_window", **_WINDOW_FIELDS}
)
@_command("schedule")
async def ws_add_window(hass, connection, msg, manager) -> dict[str, Any]:
    await manager.async_add_window(
        start=msg["start"],
        end=msg.get("end"),
        reason=msg["reason"],
        pages=msg["pages"],
        pause=msg["pause_automations"],
        repeat=msg["repeat"],
        max_minutes=msg.get("max_minutes"),
        override_blackout=_override(connection, msg),
    )
    return manager.state_for(connection.user)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "maintenance_mode/update_window",
        vol.Required("window_id"): ID,
        **_WINDOW_FIELDS,
    }
)
@_command("schedule")
async def ws_update_window(hass, connection, msg, manager) -> dict[str, Any]:
    await manager.async_update_window(
        msg["window_id"],
        start=msg["start"],
        end=msg.get("end"),
        reason=msg["reason"],
        pages=msg["pages"],
        pause=msg["pause_automations"],
        repeat=msg["repeat"],
        max_minutes=msg.get("max_minutes"),
        override_blackout=_override(connection, msg),
    )
    return manager.state_for(connection.user)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "maintenance_mode/delete_window",
        vol.Required("window_id"): ID,
    }
)
@_command("schedule")
async def ws_delete_window(hass, connection, msg, manager) -> dict[str, Any]:
    await manager.async_delete_window(msg["window_id"])
    return manager.state_for(connection.user)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "maintenance_mode/delete_history",
        vol.Required("history_id"): ID,  # (« id » est réservé au numéro de message)
    }
)
@_command("history_delete")
async def ws_delete_history(hass, connection, msg, manager) -> dict[str, Any]:
    await manager.async_delete_history(msg["history_id"])
    return manager.state_for(connection.user)


@websocket_api.websocket_command({vol.Required("type"): "maintenance_mode/clear_history"})
@_command("history_delete")
async def ws_clear_history(hass, connection, msg, manager) -> dict[str, Any]:
    await manager.async_clear_history()
    return manager.state_for(connection.user)


COMMANDS = (
    ws_get_state,
    ws_get_client,
    ws_get_catalog,
    ws_subscribe,
    ws_preview,
    ws_start,
    ws_stop,
    ws_update_current,
    ws_add_window,
    ws_update_window,
    ws_delete_window,
    ws_delete_history,
    ws_clear_history,
    ws_update_config,
)


@callback
def async_register(hass: HomeAssistant) -> None:
    for command in COMMANDS:
        websocket_api.async_register_command(hass, command)
