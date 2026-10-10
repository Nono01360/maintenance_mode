"""Services maintenance_mode.* (administrateurs uniquement)."""
from __future__ import annotations

from datetime import datetime

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.util import dt as dt_util

from .const import DOMAIN, REPEATS
from .manager import MaintenanceManager, get_manager

_COMMON = {
    vol.Optional("end"): cv.datetime,
    vol.Optional("duration"): cv.time_period,
    vol.Optional("reason", default=""): cv.string,
    vol.Optional("pages", default=[]): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional("pause_automations", default=True): cv.boolean,
}
START_SCHEMA = vol.Schema(_COMMON)
SCHEDULE_SCHEMA = vol.Schema(
    {
        vol.Required("start"): cv.datetime,
        **_COMMON,
        vol.Optional("repeat", default="none"): vol.In(REPEATS),
    }
)
CANCEL_SCHEMA = vol.Schema({vol.Required("window_id"): cv.string})


def _manager(hass: HomeAssistant) -> MaintenanceManager:
    manager = get_manager(hass)
    if manager is None:
        raise ServiceValidationError("L'intégration Mode maintenance n'est pas chargée.")
    return manager


def _end(data: dict, base: datetime) -> datetime | None:
    """`end` OU `duration` (durée à partir de `base`)."""
    if "end" in data and "duration" in data:
        raise ServiceValidationError("Indique soit `end`, soit `duration`, pas les deux.")
    if "duration" in data:
        return base + data["duration"]
    return data.get("end")


def async_register(hass: HomeAssistant) -> None:
    async def _start(call: ServiceCall) -> None:
        d = call.data
        await _manager(hass).async_start_now(
            end=_end(d, dt_util.utcnow()),
            reason=d["reason"], pages=d["pages"], pause=d["pause_automations"],
            by="service",
        )

    async def _stop(call: ServiceCall) -> None:
        await _manager(hass).async_stop()

    async def _schedule(call: ServiceCall) -> None:
        d = call.data
        start = dt_util.as_utc(d["start"])
        await _manager(hass).async_add_window(
            start=start, end=_end(d, start),
            reason=d["reason"], pages=d["pages"], pause=d["pause_automations"],
            repeat=d["repeat"],
        )

    async def _cancel(call: ServiceCall) -> None:
        await _manager(hass).async_delete_window(call.data["window_id"])

    async_register_admin_service(hass, DOMAIN, "start", _start, START_SCHEMA)
    async_register_admin_service(hass, DOMAIN, "stop", _stop, vol.Schema({}))
    async_register_admin_service(hass, DOMAIN, "schedule", _schedule, SCHEDULE_SCHEMA)
    async_register_admin_service(hass, DOMAIN, "cancel_schedule", _cancel, CANCEL_SCHEMA)
