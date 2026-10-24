"""6.2.4 — désinstallation propre, même pendant une maintenance."""
from homeassistant.helpers import issue_registry as ir

from custom_components.maintenance_mode.const import DOMAIN

from .test_maintenance import _setup, _state


def _key(entry):
    return f"{DOMAIN}.{entry.entry_id}"


async def test_removal_during_maintenance_restores_automations(hass, hass_storage):
    entry, m = await _setup(hass)
    await hass.services.async_call("automation", "turn_off", {"entity_id": "automation.a2"}, blocking=True)  # coupée par l'utilisateur
    await m.async_start_now(end=None, reason="", pages=[], pause=True)
    assert _state(hass, "automation.a1") == "off"
    assert _key(entry) in hass_storage

    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert _state(hass, "automation.a1") == "on", "ce que NOUS avons suspendu est réactivé"
    assert _state(hass, "automation.a2") == "off", "ce que l'utilisateur avait coupé lui-même reste coupé"
    assert _key(entry) not in hass_storage, "le fichier de stockage est supprimé"
    assert "maintenance" not in hass.data["frontend_panels"], "le panneau est retiré"
    assert hass.states.get("switch.mode_maintenance") is None


async def test_removal_without_maintenance_touches_nothing(hass, hass_storage):
    entry, m = await _setup(hass)
    await hass.services.async_call("automation", "turn_off", {"entity_id": "automation.a1"}, blocking=True)
    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert _state(hass, "automation.a1") == "off" and _state(hass, "automation.a2") == "on"
    assert _key(entry) not in hass_storage


async def test_removal_when_automations_were_not_paused(hass, hass_storage):
    entry, m = await _setup(hass)
    await hass.services.async_call("automation", "turn_off", {"entity_id": "automation.a1"}, blocking=True)
    await m.async_start_now(end=None, reason="", pages=["map"], pause=False)     # maintenance sans suspension
    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert _state(hass, "automation.a1") == "off"     # on ne rallume rien qu'on n'ait pas suspendu


async def test_removal_clears_repair_issue(hass, hass_storage):
    entry, m = await _setup(hass)
    await m.async_update_config({"automations": ["automation.n_existe_pas"]})
    registry = ir.async_get(hass)
    assert registry.async_get_issue(DOMAIN, "missing_automations")
    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert registry.async_get_issue(DOMAIN, "missing_automations") is None


async def test_reload_keeps_the_maintenance(hass, hass_storage):
    """Régression : recharger (ou arrêter HA) ne doit PAS réactiver les automatisations."""
    entry, m = await _setup(hass)
    await m.async_start_now(end=None, reason="", pages=[], pause=True)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert _state(hass, "automation.a1") == "off" and entry.runtime_data.current is not None
    assert _key(entry) in hass_storage
