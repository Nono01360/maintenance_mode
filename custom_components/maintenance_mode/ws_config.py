"""Commande websocket de mise à jour des réglages (une autorisation par réglage, anti-escalade côté gestionnaire)."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers import config_validation as cv

from .const import BANNER_MODES, NOTIFY_KINDS, PERMISSIONS, REPEATS
from .limits import ID, MAX_ENTITIES, MAX_LIST, MAX_USERS, PAGES, TEXT, bounded_list
from .ws_common import _command


_TEMPLATE = vol.Schema(
    {
        vol.Optional("id"): ID,
        vol.Required("name"): TEXT,
        vol.Optional("reason", default=""): TEXT,
        vol.Optional("pages", default=[]): PAGES,
        vol.Optional("pause_automations", default=True): cv.boolean,
        vol.Optional("duration"): vol.Any(None, vol.All(vol.Coerce(int), vol.Range(min=1, max=525600))),
        vol.Optional("repeat", default="none"): vol.In(REPEATS),
    }
)
_ROLE = vol.Schema(
    {
        vol.Optional("id"): ID,
        vol.Required("name"): TEXT,
        vol.Optional("permissions", default=[]): bounded_list(vol.In(PERMISSIONS), len(PERMISSIONS)),
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
    "compat_mode": "settings",
    "templates": "templates",
    "roles": "access",
    "panel_access": "access",
}


@websocket_api.websocket_command(
    {
        vol.Required("type"): "maintenance_mode/update_config",
        vol.Optional("automations"): bounded_list(vol.All(cv.string, vol.Length(max=255)), MAX_ENTITIES),
        vol.Optional("allowed_users"): bounded_list(ID, MAX_USERS),
        vol.Optional("warn_minutes"): vol.All(vol.Coerce(int), vol.Range(min=1, max=1440)),
        vol.Optional("end_soon_minutes"): vol.All(vol.Coerce(int), vol.Range(min=1, max=1440)),
        vol.Optional("message"): TEXT,
        vol.Optional("notify_services"): bounded_list(vol.All(cv.string, vol.Length(max=100)), MAX_LIST),
        vol.Optional("notify_kinds"): bounded_list(vol.In(NOTIFY_KINDS), len(NOTIFY_KINDS)),
        vol.Optional("banner_mode"): vol.In(BANNER_MODES),
        vol.Optional("banner_scroll"): cv.boolean,
        vol.Optional("compat_mode"): cv.boolean,
        vol.Optional("templates"): bounded_list(_TEMPLATE, MAX_LIST),
        vol.Optional("roles"): bounded_list(_ROLE, MAX_LIST),
        vol.Optional("panel_access"): vol.All({ID: ID}, vol.Length(max=MAX_USERS)),
    }
)
@_command()
async def ws_update_config(hass, connection, msg, manager) -> dict[str, Any]:
    changes = {k: v for k, v in msg.items() if k not in ("id", "type")}
    perms = manager.perms_for(connection.user)
    if not {_CONFIG_PERMS[k] for k in changes} <= perms:
        raise Unauthorized
    manager.check_config_rate()
    await manager.async_update_config(changes, actor_perms=perms)
    return manager.state_for(connection.user)
