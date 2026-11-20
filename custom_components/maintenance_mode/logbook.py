"""Journal de Home Assistant : « Maintenance démarrée » / « Maintenance terminée » avec l'auteur et le motif.

Décrit les deux évènements déjà émis sur le bus (`maintenance_mode_started` / `_ended`) : rien n'est ajouté à
l'écriture, et la ligne du Journal est rattachée à l'interrupteur de l'intégration.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, EVENT_ENDED, EVENT_STARTED

_TEXT = {
    "fr": {
        "started": "Maintenance démarrée", "ended": "Maintenance terminée", "by": "par {who}", "reason": "Motif : {reason}",
        "who": {"service": "un service", "interrupteur": "l'interrupteur", "planification": "la planification"},
        "cause": {"manual": "arrêtée à la main", "auto": "terminée automatiquement", "replaced": "remplacée par une autre",
                  "max_duration": "durée maximale atteinte"},
    },
    "en": {
        "started": "Maintenance started", "ended": "Maintenance ended", "by": "by {who}", "reason": "Reason: {reason}",
        "who": {"service": "a service", "interrupteur": "the switch", "planification": "the schedule"},
        "cause": {"manual": "stopped manually", "auto": "ended automatically", "replaced": "replaced by another",
                  "max_duration": "maximum duration reached"},
    },
}


@callback
def async_describe_events(hass: HomeAssistant, async_describe_event: Callable[[str, str, Callable[[Event], dict[str, Any]]], None]) -> None:
    def text() -> dict[str, Any]:
        return _TEXT["en" if (hass.config.language or "fr").startswith("en") else "fr"]

    def entity_id() -> str | None:
        for entry in hass.config_entries.async_entries(DOMAIN):
            return er.async_get(hass).async_get_entity_id("switch", DOMAIN, f"{entry.entry_id}_switch")
        return None

    def describe(kind: str) -> Callable[[Event], dict[str, Any]]:
        def describer(event: Event) -> dict[str, Any]:
            t, data = text(), event.data
            head = t["started"] if kind == "started" else t["ended"]
            if kind == "ended" and data.get("ended_by"):
                head += f" ({t['cause'].get(data['ended_by'], data['ended_by'])})"
            parts = [head]
            if who := str(data.get("started_by") or ""):
                parts.append(t["by"].format(who=t["who"].get(who, who)))
            if reason := str(data.get("reason") or ""):
                parts.append(t["reason"].format(reason=reason))
            out: dict[str, Any] = {"name": "Mode maintenance", "message": " · ".join(parts)}
            if eid := entity_id():
                out["entity_id"] = eid
            return out

        return describer

    async_describe_event(DOMAIN, EVENT_STARTED, describe("started"))
    async_describe_event(DOMAIN, EVENT_ENDED, describe("ended"))
