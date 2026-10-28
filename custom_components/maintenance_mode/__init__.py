"""Intégration Mode maintenance."""
from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.storage import Store

from . import errors, services, websocket_api
from .const import (
    DOMAIN,
    OVERLAY_JS,
    PANEL_ELEMENT,
    PANEL_JS,
    PANEL_URL_PATH,
    PLATFORMS,
    STATIC_BASE,
    VERSION,
)
from .manager import MaintenanceManager
from .storage import STORAGE_VERSION, MaintenanceStore

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

# unique_id des entités conservées ; les autres (v0.2) sont supprimées
_KEPT_SUFFIXES = ("_switch", "_next")


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    www = Path(__file__).parent / "www"
    await hass.http.async_register_static_paths(
        [StaticPathConfig(STATIC_BASE, str(www), False)]
    )
    add_extra_js_url(hass, f"{OVERLAY_JS}?v={VERSION}")
    websocket_api.async_register(hass)
    services.async_register(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # Nettoyage des entités de la v0.2 (datetime / text / button)
    registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if not (entity.unique_id or "").endswith(_KEPT_SUFFIXES):
            registry.async_remove(entity.entity_id)

    errors.set_language(hass.config.language)   # langue des messages côté serveur
    manager = MaintenanceManager(hass, entry)
    await manager.async_load()
    entry.runtime_data = manager

    frontend.async_remove_panel(hass, PANEL_URL_PATH, warn_if_unknown=False)
    await panel_custom.async_register_panel(
        hass,
        webcomponent_name=PANEL_ELEMENT,
        frontend_url_path=PANEL_URL_PATH,
        module_url=f"{PANEL_JS}?v={VERSION}",
        sidebar_title="Maintenance",
        sidebar_icon="mdi:wrench-clock",
        require_admin=False,  # les droits fins sont vérifiés côté serveur
        config={},
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        manager = entry.runtime_data
        manager.async_unload()
        await manager.async_flush()          # termine l'écriture éventuellement en attente
        frontend.async_remove_panel(hass, PANEL_URL_PATH, warn_if_unknown=False)
        return True
    return False


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Suppression définitive de l'intégration : on ne laisse rien derrière soi.

    Appelée seulement à la suppression (jamais pour un rechargement ni un arrêt de HA, qui ne doivent
    surtout pas réactiver les automatisations). Si une maintenance était en cours, les automatisations
    qu'ELLE avait suspendues sont réactivées ; celles que l'utilisateur avait coupées lui-même ne sont
    pas touchées.
    """
    store: Store = MaintenanceStore(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}")
    try:
        data = await store.async_load() or {}
    except Exception:  # noqa: BLE001 - fichier plus récent ou illisible : on ne bloque jamais la suppression
        _LOGGER.exception("Stockage illisible à la suppression : rien à réactiver")
        data = {}
    if not isinstance(data, dict):
        data = {}
    suspended = data.get("disabled") or []
    if not (isinstance(suspended, list) and all(isinstance(x, str) for x in suspended)):
        suspended = []
    if data.get("current") and suspended:
        try:
            await hass.services.async_call(
                "automation", "turn_on", {"entity_id": suspended}, blocking=True
            )
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Impossible de réactiver les automatisations à la suppression")
    await store.async_remove()
    for suffix in ("backup_v1", "unreadable"):          # copies de sécurité de la migration / du mode sûr
        await Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.{suffix}").async_remove()
    for issue in ("missing_automations", "storage_unreadable"):
        ir.async_delete_issue(hass, DOMAIN, issue)
