"""Flux « Réparer » des alertes de réconciliation (Paramètres → Réparations)."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant

from .manager import get_manager


class MaintenanceRepairFlow(RepairsFlow):
    """Une confirmation, puis la réparation (voir `ReconcileMixin.async_repair`)."""

    def __init__(self, issue_id: str) -> None:
        self._issue_id = issue_id

    async def async_step_init(self, user_input=None):
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input=None):
        if user_input is None:
            return self.async_show_form(step_id="confirm", data_schema=vol.Schema({}))
        manager = get_manager(self.hass)
        if manager is None:
            return self.async_abort(reason="not_loaded")
        await manager.async_repair(self._issue_id)
        return self.async_create_entry(data={})


async def async_create_fix_flow(hass: HomeAssistant, issue_id: str, data) -> RepairsFlow:
    return MaintenanceRepairFlow(issue_id)
