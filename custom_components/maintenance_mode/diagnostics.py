"""Diagnostics (Paramètres → Appareils et services → Télécharger les diagnostics)."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

TO_REDACT = {"allowed_users", "panel_access", "notify_services", "started_by", "message"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    m = entry.runtime_data
    return {
        "config": async_redact_data(m.config, TO_REDACT),
        "current": async_redact_data(m.current.as_dict(), TO_REDACT) if m.current else None,
        "schedule": [async_redact_data(w.as_dict(), TO_REDACT) for w in m.schedule],
        "history": [async_redact_data(h, TO_REDACT) for h in m.history],
        "disabled_automations_count": len(m.disabled),
        "users_count": len(m.users),
    }
