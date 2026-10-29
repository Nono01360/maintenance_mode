"""Protections : quelles automatisations sont suspendues, lesquelles sont toujours épargnées."""
from __future__ import annotations

from typing import Any

from homeassistant.const import STATE_ON
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import label_registry as lr


class ProtectionMixin:
    """Suppose `hass` et `config` du gestionnaire."""

    def is_protected(self, entity_id: str) -> bool:
        """Jamais suspendue, même si elle est sélectionnée : exclue par son nom ou par une étiquette."""
        cfg = self.config
        if entity_id in cfg["excluded_automations"]:
            return True
        excluded = set(cfg["excluded_labels"])
        if not excluded:
            return False
        entry = er.async_get(self.hass).async_get(entity_id)
        return bool(entry and excluded & set(entry.labels))

    def _area_of(self, entity_id: str) -> str | None:
        """Zone d'une entité : la sienne, sinon celle de son appareil."""
        entry = er.async_get(self.hass).async_get(entity_id)
        if not entry:
            return None
        if entry.area_id:
            return entry.area_id
        if entry.device_id and (device := dr.async_get(self.hass).async_get(entry.device_id)):
            return device.area_id
        return None

    def selected_automations(self) -> list[str] | None:
        """Automatisations visées : choisies une à une + portant une étiquette choisie + situées dans une zone choisie.

        `None` = aucun sélecteur : toutes les automatisations sont visées. Résolu au moment de l'appel (au démarrage
        d'une maintenance, c'est l'instantané de la suspension).
        """
        cfg = self.config
        labels, areas = set(cfg["selected_labels"]), set(cfg["selected_areas"])
        if not (cfg["automations"] or labels or areas):
            return None
        chosen = set(cfg["automations"])
        if labels or areas:
            registry = er.async_get(self.hass)
            for entity_id in self.hass.states.async_entity_ids("automation"):
                entry = registry.async_get(entity_id)
                if (entry and labels & set(entry.labels)) or (areas and self._area_of(entity_id) in areas):
                    chosen.add(entity_id)
        return sorted(chosen)

    def plan_suspension(self) -> dict[str, list[str]]:
        """Ce qu'une maintenance avec suspension ferait, sans rien faire.

        - `suspend`   : actives et non protégées -> seront coupées ;
        - `protected` : concernées mais épargnées (exclusions) ;
        - `inactive`  : concernées, non protégées, mais déjà éteintes (laissées telles quelles).
        Aucun sélecteur (automatisations, étiquettes, zones) = toutes les automatisations.
        """
        selected = self.selected_automations()
        candidates = sorted(self.hass.states.async_entity_ids("automation") if selected is None else selected)
        plan: dict[str, list[str]] = {"suspend": [], "protected": [], "inactive": []}
        for entity_id in candidates:
            if self.is_protected(entity_id):
                plan["protected"].append(entity_id)
            elif (state := self.hass.states.get(entity_id)) and state.state == STATE_ON:
                plan["suspend"].append(entity_id)
            else:
                plan["inactive"].append(entity_id)
        return plan

    def catalog(self) -> dict[str, Any]:
        """Étiquettes et zones (avec leurs automatisations) proposées dans les réglages de sélection et de protection."""
        entities = er.async_get(self.hass)
        labels = []
        for label in sorted(lr.async_get(self.hass).async_list_labels(), key=lambda x: x.name.lower()):
            members = sorted(
                e.entity_id for e in er.async_entries_for_label(entities, label.label_id)
                if e.entity_id.startswith("automation.")
            )
            labels.append({"id": label.label_id, "name": label.name, "automations": members})
        areas = []
        for area in sorted(ar.async_get(self.hass).async_list_areas(), key=lambda x: x.name.lower()):
            members = sorted(
                e for e in self.hass.states.async_entity_ids("automation") if self._area_of(e) == area.id
            )
            areas.append({"id": area.id, "name": area.name, "automations": members})
        return {"labels": labels, "areas": areas}
