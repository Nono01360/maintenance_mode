"""Capteur : début de la prochaine maintenance planifiée."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import EntityCategory
from homeassistant.util import dt as dt_util

from .entity import MaintenanceEntity
from .window import iso


async def async_setup_entry(hass, entry, async_add_entities):
    m = entry.runtime_data
    async_add_entities([NextMaintenanceSensor(m), SuspendedCountSensor(m), LastReapplySensor(m), LastHookFailureSensor(m)])


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


class _HealthSensor(MaintenanceEntity, SensorEntity):
    """Capteurs de santé (catégorie « diagnostic »)."""
    _attr_entity_category = EntityCategory.DIAGNOSTIC


class SuspendedCountSensor(_HealthSensor):
    """Nombre d'automatisations actuellement suspendues par la maintenance."""
    _attr_translation_key = "suspended"
    _attr_icon = "mdi:robot-off"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, manager) -> None:
        super().__init__(manager, "suspended")

    @property
    def native_value(self) -> int:
        return len(self.manager.disabled)


class LastReapplySensor(_HealthSensor):
    """Dernière remise en pause d'automatisations (redémarrage, rechargement, « Réparer »)."""
    _attr_translation_key = "last_reapply"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, manager) -> None:
        super().__init__(manager, "last_reapply")

    @property
    def native_value(self) -> datetime | None:
        return dt_util.parse_datetime(self.manager.health.get("last_reapply") or "")


class LastHookFailureSensor(_HealthSensor):
    """Dernier hook qui n'a pas réussi (échec, délai dépassé, introuvable, ignoré)."""
    _attr_translation_key = "last_hook_failure"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, manager) -> None:
        super().__init__(manager, "last_hook_failure")

    @property
    def native_value(self) -> datetime | None:
        failure = self.manager.health.get("last_hook_failure") or {}
        return dt_util.parse_datetime(failure.get("at") or "")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        failure = self.manager.health.get("last_hook_failure") or {}
        return {k: failure.get(k) for k in ("name", "when", "entity_id", "status")}
