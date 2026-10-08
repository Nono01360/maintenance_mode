"""Capteur : début de la prochaine maintenance planifiée."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity

from .entity import MaintenanceEntity
from .manager import iso


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([NextMaintenanceSensor(entry.runtime_data)])


class NextMaintenanceSensor(MaintenanceEntity, SensorEntity):
    _attr_name = "Prochaine maintenance"
    _attr_icon = "mdi:calendar-clock"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, manager) -> None:
        super().__init__(manager, "next")

    @property
    def native_value(self) -> datetime | None:
        window = self.manager.next_window
        return window.start if window else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        window = self.manager.next_window
        return {
            "end": iso(window.end) if window else None,
            "reason": window.reason if window else None,
            "pages": window.pages if window else [],
            "scheduled_count": len(self.manager.schedule),
        }
