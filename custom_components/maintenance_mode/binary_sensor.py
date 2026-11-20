"""Binary_sensor « Problème » : allumé quand l'intégration a repéré un écart ou un échec à regarder."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.const import EntityCategory

from .entity import MaintenanceEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([MaintenanceProblem(entry.runtime_data)])


class MaintenanceProblem(MaintenanceEntity, BinarySensorEntity):
    _attr_translation_key = "problem"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, manager) -> None:
        super().__init__(manager, "problem")

    @property
    def is_on(self) -> bool:
        return bool(self.manager.problems())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"problems": self.manager.problems()}
