"""Réapplication de la suspension (redémarrage / rechargement) et confidentialité de `started_by`."""
from unittest.mock import patch

from homeassistant.components import automation
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.maintenance_mode.const import DOMAIN


def _auto(alias, **extra):
    return {"alias": alias, "trigger": {"platform": "event", "event_type": f"ev_{alias}"}, "action": [], **extra}


async def _setup_with(hass, autos):
    assert await async_setup_component(hass, "automation", {"automation": autos})
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry, entry.runtime_data


def _state(hass, eid):
    s = hass.states.get(eid)
    return s.state if s else None


async def _reload(hass, autos):
    with patch("homeassistant.config.load_yaml_config_file", autospec=True,
               return_value={automation.DOMAIN: autos}):
        await hass.services.async_call(automation.DOMAIN, "reload", blocking=True)
    await hass.async_block_till_done()


# ------------------------------------------------------------------ réapplication
async def test_reapplied_after_automation_reload(hass):
    """`initial_state: true` écrase l'état restauré : l'automatisation redevient active malgré la maintenance."""
    autos = [_auto("a1", initial_state=True), _auto("a2")]
    _, m = await _setup_with(hass, autos)
    await m.async_start_now(end=None, reason="", pages=[], pause=True)
    assert _state(hass, "automation.a1") == "off" and _state(hass, "automation.a2") == "off"

    # rechargement : a1 et a2 MODIFIÉES (une automatisation inchangée n'est pas recréée par HA et garde son état),
    # plus une NOUVELLE automatisation a3
    await _reload(hass, [_auto("a1", initial_state=True, description="modifiée"), _auto("a2", description="modifiée"), _auto("a3")])
    assert _state(hass, "automation.a1") == "off", "a1 doit être remise en pause après le rechargement"
    assert _state(hass, "automation.a2") == "off", "sans initial_state, HA restaure l'état éteint (comportement observé)"
    assert _state(hass, "automation.a3") == "on", "une automatisation créée pendant la maintenance n'est pas suspendue (instantané)"

    # fin de maintenance : on réactive ce qu'on avait suspendu, pas a3 (déjà active)
    await m.async_stop()
    await hass.async_block_till_done()
    assert all(_state(hass, f"automation.a{i}") == "on" for i in (1, 2, 3))


async def test_reapplied_at_startup(hass):
    _, m = await _setup_with(hass, [_auto("a1"), _auto("a2")])
    await m.async_start_now(end=None, reason="", pages=[], pause=True)
    # simulation d'un redémarrage : HA remet a1 en marche (initial_state, état non restauré…)
    await hass.services.async_call("automation", "turn_on", {"entity_id": "automation.a1"}, blocking=True)
    assert _state(hass, "automation.a1") == "on"
    await m._async_resume()
    await hass.async_block_till_done()
    assert _state(hass, "automation.a1") == "off"
    assert _state(hass, "automation.a2") == "off"


async def test_no_reapply_when_automations_not_paused_or_no_maintenance(hass):
    _, m = await _setup_with(hass, [_auto("a1", initial_state=True)])
    await _reload(hass, [_auto("a1", initial_state=True)])          # aucune maintenance
    assert _state(hass, "automation.a1") == "on"
    await m.async_start_now(end=None, reason="", pages=["map"], pause=False)   # maintenance sans suspension
    await _reload(hass, [_auto("a1", initial_state=True)])
    assert _state(hass, "automation.a1") == "on"
    await m.async_stop()
    # maintenance terminée : un rechargement ne remet rien en pause
    await _reload(hass, [_auto("a1", initial_state=True)])
    assert _state(hass, "automation.a1") == "on"


async def test_selected_automations_only_are_reapplied(hass):
    _, m = await _setup_with(hass, [_auto("a1", initial_state=True), _auto("a2", initial_state=True)])
    await m.async_update_config({"automations": ["automation.a1"]})
    await m.async_start_now(end=None, reason="", pages=[], pause=True)
    await _reload(hass, [_auto("a1", initial_state=True), _auto("a2", initial_state=True)])
    assert _state(hass, "automation.a1") == "off"
    assert _state(hass, "automation.a2") == "on"      # jamais concernée


async def test_reload_listener_removed_on_unload(hass):
    entry, m = await _setup_with(hass, [_auto("a1", initial_state=True)])
    await m.async_start_now(end=None, reason="", pages=[], pause=True)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    # entrée déchargée : on rallume a1 puis on recharge, rien ne doit la remettre en pause
    await hass.services.async_call("automation", "turn_on", {"entity_id": "automation.a1"}, blocking=True)
    await _reload(hass, [_auto("a1", initial_state=True)])
    assert _state(hass, "automation.a1") == "on"


# ------------------------------------------------------------------ confidentialité
async def test_started_by_is_not_public(hass, hass_read_only_user):
    _, m = await _setup_with(hass, [_auto("a1")])
    await m.async_start_now(end=None, reason="r", pages=[], pause=False, by="Nolann")
    attrs = hass.states.get("switch.mode_maintenance").attributes
    assert attrs["current"]["reason"] == "r" and "started_by" not in attrs["current"]
    assert "Nolann" not in str(dict(attrs))

    from datetime import timedelta
    from homeassistant.util import dt as dt_util
    await m.async_add_window(start=dt_util.utcnow() + timedelta(hours=1), end=None, reason="x", pages=[], pause=False)
    attrs = hass.states.get("switch.mode_maintenance").attributes
    assert attrs["next"] is not None and "started_by" not in attrs["next"]

    # lecteur simple : ni current ni upcoming ne contiennent l'initiateur
    state = m.state_for(hass_read_only_user)
    assert "started_by" not in state["current"] and all("started_by" not in w for w in state["upcoming"])
    assert "Nolann" not in str(state)

    # l'historique, lui, reste réservé à l'autorisation « history » et conserve l'initiateur
    await m.async_stop()
    await m.async_update_config({"roles": [{"name": "Hist", "permissions": ["history"]}]})
    rid = m.config["roles"][0]["id"]
    await m.async_update_config({"panel_access": {hass_read_only_user.id: rid}})
    assert m.state_for(hass_read_only_user)["history"][0]["started_by"] == "Nolann"
    await m.async_update_config({"panel_access": {}})
    assert "history" not in m.state_for(hass_read_only_user)


async def test_bus_events_keep_started_by(hass):
    """Les évènements du bus ne sont pas lisibles par les non-administrateurs : l'initiateur y reste utile."""
    from pytest_homeassistant_custom_component.common import async_capture_events
    _, m = await _setup_with(hass, [_auto("a1")])
    started = async_capture_events(hass, "maintenance_mode_started")
    await m.async_start_now(end=None, reason="", pages=[], pause=False, by="Nolann")
    await hass.async_block_till_done()
    assert started[0].data["started_by"] == "Nolann"
