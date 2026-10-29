"""Protections : quelles automatisations sont suspendues, lesquelles sont toujours épargnées."""
from __future__ import annotations

from typing import Any

from homeassistant.const import STATE_ON
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

    def plan_suspension(self) -> dict[str, list[str]]:
        """Ce qu'une maintenance avec suspension ferait, sans rien faire.

        - `suspend`   : actives et non protégées -> seront coupées ;
        - `protected` : concernées mais épargnées (exclusions) ;
        - `inactive`  : concernées, non protégées, mais déjà éteintes (laissées telles quelles).
        Sélection vide = toutes les automatisations.
        """
        selected = self.config["automations"]
        candidates = sorted(selected or self.hass.states.async_entity_ids("automation"))
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
        """Étiquettes (avec leurs automatisations) proposées dans les réglages de protection."""
        entities = er.async_get(self.hass)
        labels = []
        for label in sorted(lr.async_get(self.hass).async_list_labels(), key=lambda x: x.name.lower()):
            members = sorted(
                e.entity_id for e in er.async_entries_for_label(entities, label.label_id)
                if e.entity_id.startswith("automation.")
            )
            labels.append({"id": label.label_id, "name": label.name, "automations": members})
        return {"labels": labels}
