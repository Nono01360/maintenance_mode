"""0.8.2 — étiquettes et zones comme sélecteurs : (automatisations ∪ étiquettes ∪ zones) − exclusions, instantané au démarrage."""
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .test_maintenance import _state
from .test_protection import _label, _setup_with_ids
from .test_roles import _ws_call


def _area(hass, name, *entity_ids):
    area = ar.async_get(hass).async_get_or_create(name)
    reg = er.async_get(hass)
    for entity_id in entity_ids:
        reg.async_update_entity(entity_id, area_id=area.id)
    return area.id


def _states(hass):
    return [_state(hass, f"automation.a{i}") for i in (1, 2, 3)]


async def test_no_selector_means_everything(hass):
    _, m = await _setup_with_ids(hass)
    assert m.selected_automations() is None
    await m.async_start_now(end=None, reason="", pages=[], pause=True)
    assert _states(hass) == ["off", "off", "off"]


async def test_label_selector_targets_only_labelled_automations(hass):
    _, m = await _setup_with_ids(hass)
    label = _label(hass, "Confort", "automation.a1", "automation.a3")
    await m.async_update_config({"selected_labels": [label]})
    await m.async_start_now(end=None, reason="", pages=[], pause=True)
    assert _states(hass) == ["off", "on", "off"]


async def test_area_selector_uses_entity_area_then_device_area(hass):
    entry, m = await _setup_with_ids(hass)
    reg = er.async_get(hass)
    area = ar.async_get(hass).async_get_or_create("Salon")
    reg.async_update_entity("automation.a1", area_id=area.id)                        # zone de l'entité
    device = dr.async_get(hass).async_get_or_create(config_entry_id=entry.entry_id, identifiers={("t", "d")}, name="Boîtier")
    dr.async_get(hass).async_update_device(device.id, area_id=area.id)
    reg.async_update_entity("automation.a2", device_id=device.id)                    # zone héritée de l'appareil
    await m.async_update_config({"selected_areas": [area.id]})
    assert m.selected_automations() == ["automation.a1", "automation.a2"]
    await m.async_start_now(end=None, reason="", pages=[], pause=True)
    assert _states(hass) == ["off", "off", "on"]


async def test_union_of_selectors_minus_exclusions(hass):
    _, m = await _setup_with_ids(hass)
    label = _label(hass, "L", "automation.a2")
    area = _area(hass, "Z", "automation.a3")
    await m.async_update_config({
        "automations": ["automation.a1"], "selected_labels": [label], "selected_areas": [area],
        "excluded_automations": ["automation.a3"],
    })
    assert m.selected_automations() == ["automation.a1", "automation.a2", "automation.a3"]
    await m.async_start_now(end=None, reason="", pages=[], pause=True)
    assert _states(hass) == ["off", "off", "on"]          # a3 : sélectionnée par sa zone, mais protégée


async def test_selection_is_a_snapshot_taken_at_start(hass):
    _, m = await _setup_with_ids(hass)
    label = _label(hass, "Plus tard")
    await m.async_update_config({"selected_labels": [label]})
    await m.async_start_now(end=None, reason="", pages=[], pause=True)
    assert m.disabled == [] and _states(hass) == ["on", "on", "on"]                  # l'étiquette ne portait rien à ce moment
    er.async_get(hass).async_update_entity("automation.a1", labels={label})
    assert m.disabled == []                                                          # rien ne change après coup
    await m.async_stop()
    assert _states(hass) == ["on", "on", "on"]


async def test_selectors_are_cleaned_and_listed_in_catalog(hass, hass_ws_client, hass_access_token, hass_read_only_access_token):
    _, m = await _setup_with_ids(hass)
    area = _area(hass, "Cuisine", "automation.a2")
    await m.async_update_config({"selected_labels": ["b", "a", "a", ""], "selected_areas": [area, area]})
    assert m.config["selected_labels"] == ["a", "b"] and m.config["selected_areas"] == [area]
    admin = await hass_ws_client(hass, hass_access_token)
    r = await _ws_call(admin, 1, type="maintenance_mode/get_catalog")
    assert r["success"] and r["result"]["areas"] == [{"id": area, "name": "Cuisine", "automations": ["automation.a2"]}]
    r = await _ws_call(admin, 2, type="maintenance_mode/update_config", selected_labels=["x"], selected_areas=["y"])
    assert r["success"] and m.config["selected_areas"] == ["y"]
    user = await hass_ws_client(hass, hass_read_only_access_token)
    r = await _ws_call(user, 1, type="maintenance_mode/update_config", selected_areas=["z"])
    assert not r["success"] and r["error"]["code"] == "unauthorized"
