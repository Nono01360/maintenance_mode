"""Interrupteur du mode maintenance (démarrage / arrêt immédiat)."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity

from .entity import MaintenanceEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([MaintenanceSwitch(entry.runtime_data)])


class MaintenanceSwitch(MaintenanceEntity, SwitchEntity):
    _attr_name = None  # entité principale : nom de l'appareil
    _attr_icon = "mdi:wrench-clock"

    def __init__(self, manager) -> None:
        super().__init__(manager, "switch")

    @property
    def is_on(self) -> bool:
        return self.manager.current is not None

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.manager.async_start_now(end=None, reason="", pages=[], pause=True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.manager.async_stop()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        m = self.manager
        return {
            # Marqueur lu par le frontend : retrouve l'entité même renommée.
            "maintenance_mode_entity": True,
            "exempt_users": m.exempt_users,
            "message": m.config["message"],
            "warn_minutes": m.config["warn_minutes"],
            "current": m.current.as_dict() if m.current else None,
            "next": m.next_window.as_dict() if m.next_window else None,
            "scheduled_count": len(m.schedule),
            "disabled_automations": list(m.disabled),
        }
