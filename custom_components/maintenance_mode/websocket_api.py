"""API websocket utilisée par le panneau (droits vérifiés côté serveur)."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, Unauthorized
from homeassistant.helpers import config_validation as cv

from .const import BANNER_MODES, NOTIFY_KINDS, PERMISSIONS, REPEATS
from .manager import get_manager

DATETIME = vol.Any(None, cv.datetime)
PAGES = [cv.string]
# NB : le champ « id » est réservé au numéro de message websocket -> « window_id ».


def _command(perm: str | None = None):
    """Vérifie côté serveur que l'appelant possède l'autorisation `perm` (None = tout rôle)."""

    def decorator(func):
        async def wrapper(hass, connection, msg):
            manager = get_manager(hass)
            if manager is None:
                connection.send_error(msg["id"], "not_loaded", "Intégration non chargée.")
                return
            if perm and perm not in manager.perms_for(connection.user):
                connection.send_error(msg["id"], websocket_api.ERR_UNAUTHORIZED, "Accès refusé.")
                return
            try:
                result = await func(hass, connection, msg, manager)
            except Unauthorized:
                connection.send_error(msg["id"], websocket_api.ERR_UNAUTHORIZED, "Accès refusé.")
                return
            except HomeAssistantError as err:
                connection.send_error(msg["id"], "invalid", str(err))
                return
            connection.send_result(msg["id"], result)

        return websocket_api.async_response(wrapper)

    return decorator


@websocket_api.websocket_command({vol.Required("type"): "maintenance_mode/get_state"})
@_command()
async def ws_get_state(hass, connection, msg, manager) -> dict[str, Any]:
    return manager.state_for(connection.user)


@websocket_api.websocket_command({vol.Required("type"): "maintenance_mode/subscribe"})
@_command()
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
@_command("control")
async def ws_start(hass, connection, msg, manager) -> dict[str, Any]:
    await manager.async_start_now(
        end=msg.get("end"),
        reason=msg["reason"],
        pages=msg["pages"],
        pause=msg["pause_automations"],
        by=connection.user.name or "",
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
        vol.Optional("reason", default=""): cv.string,
        vol.Optional("pages", default=[]): PAGES,
    }
)
@_command("control")
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
    vol.Optional("repeat", default="none"): vol.In(REPEATS),
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
    )
    return manager.state_for(connection.user)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "maintenance_mode/update_window",
        vol.Required("window_id"): cv.string,
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
    )
    return manager.state_for(connection.user)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "maintenance_mode/delete_window",
        vol.Required("window_id"): cv.string,
    }
)
@_command("schedule")
async def ws_delete_window(hass, connection, msg, manager) -> dict[str, Any]:
    await manager.async_delete_window(msg["window_id"])
    return manager.state_for(connection.user)


_TEMPLATE = vol.Schema(
    {
        vol.Optional("id"): cv.string,
        vol.Required("name"): cv.string,
        vol.Optional("reason", default=""): cv.string,
        vol.Optional("pages", default=[]): PAGES,
        vol.Optional("pause_automations", default=True): cv.boolean,
        vol.Optional("duration"): vol.Any(None, vol.All(vol.Coerce(int), vol.Range(min=1, max=525600))),
        vol.Optional("repeat", default="none"): vol.In(REPEATS),
    }
)
_ROLE = vol.Schema(
    {
        vol.Optional("id"): cv.string,
        vol.Required("name"): cv.string,
        vol.Optional("permissions", default=[]): [vol.In(PERMISSIONS)],
    }
)

# Autorisation requise pour chaque réglage
_CONFIG_PERMS = {
    "automations": "settings",
    "allowed_users": "settings",
    "warn_minutes": "settings",
    "end_soon_minutes": "settings",
    "message": "settings",
    "notify_services": "settings",
    "notify_kinds": "settings",
    "banner_mode": "settings",
    "banner_scroll": "settings",
    "templates": "templates",
    "roles": "access",
    "panel_access": "access",
}


@websocket_api.websocket_command(
    {
        vol.Required("type"): "maintenance_mode/update_config",
        vol.Optional("automations"): [cv.string],
        vol.Optional("allowed_users"): [cv.string],
        vol.Optional("warn_minutes"): vol.All(vol.Coerce(int), vol.Range(min=1, max=1440)),
        vol.Optional("end_soon_minutes"): vol.All(vol.Coerce(int), vol.Range(min=1, max=1440)),
        vol.Optional("message"): cv.string,
        vol.Optional("notify_services"): [cv.string],
        vol.Optional("notify_kinds"): [vol.In(NOTIFY_KINDS)],
        vol.Optional("banner_mode"): vol.In(BANNER_MODES),
        vol.Optional("banner_scroll"): cv.boolean,
        vol.Optional("templates"): [_TEMPLATE],
        vol.Optional("roles"): [_ROLE],
        vol.Optional("panel_access"): {cv.string: cv.string},
    }
)
@_command()
async def ws_update_config(hass, connection, msg, manager) -> dict[str, Any]:
    changes = {k: v for k, v in msg.items() if k not in ("id", "type")}
    perms = manager.perms_for(connection.user)
    if not {_CONFIG_PERMS[k] for k in changes} <= perms:
        raise Unauthorized
    await manager.async_update_config(changes, actor_perms=perms)
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
