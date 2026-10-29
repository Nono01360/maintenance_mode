"""0.8.1 — exclusions : une automatisation protégée n'est jamais suspendue, même sélectionnée."""
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import label_registry as lr
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.maintenance_mode.const import DOMAIN

from .test_maintenance import _state
from .test_roles import _ws_call


async def _setup_with_ids(hass, names=("a1", "a2", "a3")):
    """Automatisations avec un `id` (donc présentes dans le registre des entités, donc étiquetables)."""
    await async_setup_component(hass, "automation", {"automation": [
        {"id": f"id_{n}", "alias": n, "trigger": {"platform": "event", "event_type": f"ev_{n}"}, "action": []} for n in names]})
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry, entry.runtime_data


def _label(hass, name, *entity_ids):
    label = lr.async_get(hass).async_create(name)
    reg = er.async_get(hass)
    for entity_id in entity_ids:
        reg.async_update_entity(entity_id, labels={*reg.async_get(entity_id).labels, label.label_id})
    return label.label_id


async def test_excluded_automation_stays_active_even_when_selected(hass):
    _, m = await _setup_with_ids(hass)
    await m.async_update_config({"automations": ["automation.a1", "automation.a2"], "excluded_automations": ["automation.a1"]})
    await m.async_start_now(end=None, reason="", pages=[], pause=True)
    assert _state(hass, "automation.a1") == "on" and _state(hass, "automation.a2") == "off"
    assert m.disabled == ["automation.a2"]
    await m.async_stop()
    assert _state(hass, "automation.a1") == "on" and _state(hass, "automation.a2") == "on"


async def test_exclusion_also_applies_when_everything_is_targeted(hass):
    _, m = await _setup_with_ids(hass)
    await m.async_update_config({"excluded_automations": ["automation.a3"]})        # aucune sélection = toutes
    await m.async_start_now(end=None, reason="", pages=[], pause=True)
    assert [_state(hass, f"automation.a{i}") for i in (1, 2, 3)] == ["off", "off", "on"]


async def test_label_exclusion(hass):
    _, m = await _setup_with_ids(hass)
    label = _label(hass, "Sécurité", "automation.a1", "automation.a3")
    await m.async_update_config({"excluded_labels": [label]})
    await m.async_start_now(end=None, reason="", pages=[], pause=True)
    assert [_state(hass, f"automation.a{i}") for i in (1, 2, 3)] == ["on", "off", "on"]


async def test_label_added_after_start_does_not_change_the_snapshot(hass):
    _, m = await _setup_with_ids(hass)
    label = _label(hass, "Plus tard")
    await m.async_update_config({"excluded_labels": [label]})
    await m.async_start_now(end=None, reason="", pages=[], pause=True)
    assert _state(hass, "automation.a1") == "off"
    _label_members = er.async_get(hass)
    _label_members.async_update_entity("automation.a1", labels={label})
    await m.async_stop()                                    # fin : on réactive ce qu'on avait suspendu, étiquette ou non
    assert _state(hass, "automation.a1") == "on"


async def test_plan_lists_suspended_protected_and_inactive(hass):
    _, m = await _setup_with_ids(hass)
    await hass.services.async_call("automation", "turn_off", {"entity_id": "automation.a2"}, blocking=True)
    await m.async_update_config({"excluded_automations": ["automation.a3"]})
    assert m.plan_suspension() == {"suspend": ["automation.a1"], "protected": ["automation.a3"], "inactive": ["automation.a2"]}
    assert _state(hass, "automation.a1") == "on"            # le plan ne change rien


async def test_exclusions_are_cleaned(hass):
    _, m = await _setup_with_ids(hass)
    await m.async_update_config({"excluded_automations": ["light.salon", "automation.b", "automation.a", "automation.b", 3],
                                 "excluded_labels": ["z", "a", "a", ""]})
    assert m.config["excluded_automations"] == ["automation.a", "automation.b"]
    assert m.config["excluded_labels"] == ["a", "z"]


async def test_ws_catalog_lists_labels_with_their_automations(hass, hass_ws_client, hass_access_token, hass_read_only_access_token):
    _, m = await _setup_with_ids(hass)
    _label(hass, "Critique", "automation.a2")
    _label(hass, "Vide")
    admin = await hass_ws_client(hass, hass_access_token)
    r = await _ws_call(admin, 1, type="maintenance_mode/get_catalog")
    assert r["success"]
    by_name = {x["name"]: x for x in r["result"]["labels"]}
    assert by_name["Critique"]["automations"] == ["automation.a2"] and by_name["Vide"]["automations"] == []
    reader = await hass_ws_client(hass, hass_read_only_access_token)
    r = await _ws_call(reader, 1, type="maintenance_mode/get_catalog")
    assert not r["success"] and r["error"]["code"] == "unauthorized"


async def test_ws_update_config_needs_settings_for_exclusions(hass, hass_ws_client, hass_read_only_access_token):
    _, m = await _setup_with_ids(hass)
    user = await hass_ws_client(hass, hass_read_only_access_token)
    r = await _ws_call(user, 1, type="maintenance_mode/update_config", excluded_automations=["automation.a1"])
    assert not r["success"] and r["error"]["code"] == "unauthorized" and m.config["excluded_automations"] == []
