"""API websocket utilisée par le panneau (droits vérifiés côté serveur)."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, ROLE_ADMIN, ROLES

DATETIME = vol.Any(None, cv.datetime)
PAGES = [cv.string]


def _get_manager(hass: HomeAssistant):
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is ConfigEntryState.LOADED:
            return entry.runtime_data
    return None


def _command(*, admin: bool):
    """Vérifie le rôle de l'appelant avant d'exécuter la commande."""

    def decorator(func):
        async def wrapper(hass, connection, msg):
            manager = _get_manager(hass)
            if manager is None:
                connection.send_error(msg["id"], "not_loaded", "Intégration non chargée.")
                return
            if admin and manager.role_for(connection.user) != ROLE_ADMIN:
                connection.send_error(
                    msg["id"], websocket_api.ERR_UNAUTHORIZED, "Accès refusé."
                )
                return
            try:
                result = await func(hass, connection, msg, manager)
            except HomeAssistantError as err:
                connection.send_error(msg["id"], "invalid", str(err))
                return
            connection.send_result(msg["id"], result)

        return websocket_api.async_response(wrapper)

    return decorator


@websocket_api.websocket_command({vol.Required("type"): "maintenance_mode/get_state"})
@_command(admin=False)
async def ws_get_state(hass, connection, msg, manager) -> dict[str, Any]:
    return manager.state_for(connection.user)


@websocket_api.websocket_command({vol.Required("type"): "maintenance_mode/subscribe"})
@_command(admin=False)
async def ws_subscribe(hass, connection, msg, manager) -> None:
    @callback
    def _forward() -> None:
        connection.send_message(
            websocket_api.event_message(msg["id"], manager.state_for(connection.user))
        )

    connection.subscriptions[msg["id"]] = manager.async_add_listener(_forward)
    _forward()
    return None


@websocket_api.websocket_command(
    {
        vol.Required("type"): "maintenance_mode/start",
        vol.Optional("end"): DATETIME,
        vol.Optional("reason", default=""): cv.string,
        vol.Optional("pages", default=[]): PAGES,
        vol.Optional("pause_automations", default=True): cv.boolean,
    }
)
@_command(admin=True)
async def ws_start(hass, connection, msg, manager) -> dict[str, Any]:
    await manager.async_start_now(
        end=msg.get("end"),
        reason=msg["reason"],
        pages=msg["pages"],
        pause=msg["pause_automations"],
    )
    return manager.state_for(connection.user)


@websocket_api.websocket_command({vol.Required("type"): "maintenance_mode/stop"})
@_command(admin=True)
async def ws_stop(hass, connection, msg, manager) -> dict[str, Any]:
    await manager.async_stop()
    return manager.state_for(connection.user)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "maintenance_mode/update_current",
        vol.Optional("end"): DATETIME,
        vol.Optional("reason", default=""): cv.string,
        vol.Optional("pages", default=[]): PAGES,
    }
)
@_command(admin=True)
async def ws_update_current(hass, connection, msg, manager) -> dict[str, Any]:
    await manager.async_update_current(
        end=msg.get("end"), reason=msg["reason"], pages=msg["pages"]
    )
    return manager.state_for(connection.user)


_WINDOW_FIELDS = {
    vol.Required("start"): cv.datetime,
    vol.Optional("end"): DATETIME,
    vol.Optional("reason", default=""): cv.string,
    vol.Optional("pages", default=[]): PAGES,
    vol.Optional("pause_automations", default=True): cv.boolean,
}


@websocket_api.websocket_command(
    {vol.Required("type"): "maintenance_mode/add_window", **_WINDOW_FIELDS}
)
@_command(admin=True)
async def ws_add_window(hass, connection, msg, manager) -> dict[str, Any]:
    await manager.async_add_window(
        start=msg["start"],
        end=msg.get("end"),
        reason=msg["reason"],
        pages=msg["pages"],
        pause=msg["pause_automations"],
    )
    return manager.state_for(connection.user)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "maintenance_mode/update_window",
        vol.Required("id"): cv.string,
        **_WINDOW_FIELDS,
    }
)
@_command(admin=True)
async def ws_update_window(hass, connection, msg, manager) -> dict[str, Any]:
    await manager.async_update_window(
        msg["id"],
        start=msg["start"],
        end=msg.get("end"),
        reason=msg["reason"],
        pages=msg["pages"],
        pause=msg["pause_automations"],
    )
    return manager.state_for(connection.user)


@websocket_api.websocket_command(
    {vol.Required("type"): "maintenance_mode/delete_window", vol.Required("id"): cv.string}
)
@_command(admin=True)
async def ws_delete_window(hass, connection, msg, manager) -> dict[str, Any]:
    await manager.async_delete_window(msg["id"])
    return manager.state_for(connection.user)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "maintenance_mode/update_config",
        vol.Optional("automations"): [cv.string],
        vol.Optional("allowed_users"): [cv.string],
        vol.Optional("warn_minutes"): vol.All(vol.Coerce(int), vol.Range(min=1, max=1440)),
        vol.Optional("message"): cv.string,
        vol.Optional("panel_access"): {cv.string: vol.In(ROLES)},
    }
)
@_command(admin=True)
async def ws_update_config(hass, connection, msg, manager) -> dict[str, Any]:
    changes = {k: v for k, v in msg.items() if k not in ("id", "type")}
    await manager.async_update_config(changes)
    return manager.state_for(connection.user)


COMMANDS = (
    ws_get_state,
    ws_subscribe,
    ws_start,
    ws_stop,
    ws_update_current,
    ws_add_window,
    ws_update_window,
    ws_delete_window,
    ws_update_config,
)


@callback
def async_register(hass: HomeAssistant) -> None:
    for command in COMMANDS:
        websocket_api.async_register_command(hass, command)
