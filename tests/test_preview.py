"""0.8.3 — aperçu avant démarrage et test à blanc : aucun effet, et identique à la réalité."""
import pytest
from homeassistant.exceptions import Unauthorized

from custom_components.maintenance_mode.const import DOMAIN

from .test_maintenance import _state
from .test_protection import _label, _setup_with_ids
from .test_roles import _ws_call


def _snapshot(hass, m):
    return (
        [_state(hass, f"automation.a{i}") for i in (1, 2, 3)], m.current, list(m.disabled), list(m.history),
        len(m.schedule), dict(m.config),
    )


async def test_preview_changes_nothing(hass):
    _, m = await _setup_with_ids(hass)
    await m.async_update_config({"notify_services": ["mobile_app_x"], "excluded_automations": ["automation.a3"]})
    before = _snapshot(hass, m)
    result = await m.async_preview(pages=["map"], pause=True)
    assert _snapshot(hass, m) == before
    assert result["suspend"] == ["automation.a1", "automation.a2"] and result["protected"] == ["automation.a3"]
    assert result["scope"] == "pages" and result["pages"] == ["map"]
    assert result["notifications"] == {"services": 1, "kinds": ["pre", "started", "end_soon", "ended"]}


async def test_preview_without_pause_touches_nothing_to_report(hass):
    _, m = await _setup_with_ids(hass)
    result = await m.async_preview(pages=[], pause=False)
    assert result["suspend"] == [] and result["protected"] == [] and result["inactive"] == [] and result["scope"] == "all"


@pytest.mark.parametrize("config", [
    {},
    {"automations": ["automation.a1", "automation.a2"]},
    {"excluded_automations": ["automation.a2"]},
    {"automations": ["automation.a1", "automation.a3"], "excluded_automations": ["automation.a3"]},
])
async def test_preview_equals_reality(hass, config):
    _, m = await _setup_with_ids(hass)
    await hass.services.async_call("automation", "turn_off", {"entity_id": "automation.a2"}, blocking=True)   # déjà coupée
    await m.async_update_config(config)
    preview = await m.async_preview(pages=[], pause=True)
    before = {f"automation.a{i}": _state(hass, f"automation.a{i}") for i in (1, 2, 3)}
    await m.async_start_now(end=None, reason="", pages=[], pause=True)
    assert preview["suspend"] == m.disabled                                   # ce qui a vraiment été suspendu
    assert all(_state(hass, e) == "off" for e in preview["suspend"])
    assert all(_state(hass, e) == before[e] for e in preview["protected"])   # protégées : intactes
    assert "automation.a2" not in preview["suspend"]                          # déjà coupée : jamais « suspendue » par nous
    assert ("automation.a2" in preview["inactive"]) == (config in ({}, {"automations": ["automation.a1", "automation.a2"]}))


async def test_preview_equals_reality_with_labels_and_areas(hass):
    _, m = await _setup_with_ids(hass)
    label = _label(hass, "L", "automation.a1")
    await m.async_update_config({"selected_labels": [label]})
    preview = await m.async_preview(pages=[], pause=True)
    await m.async_start_now(end=None, reason="", pages=[], pause=True)
    assert preview["suspend"] == m.disabled == ["automation.a1"]


async def test_blocked_users_are_the_non_exempt_ones(hass, hass_admin_user, hass_read_only_user, hass_owner_user):
    _, m = await _setup_with_ids(hass)
    hass_read_only_user.name, hass_admin_user.name, hass_owner_user.name = "Lecteur", "Admin", "Proprio"
    await m.async_update_config({"allowed_users": [hass_admin_user.id]})
    result = await m.async_preview(pages=[], pause=False)
    names = result["blocked_users"]
    assert "Lecteur" in names and "Admin" not in names and "Proprio" not in names


async def test_ws_preview_permissions(hass, hass_ws_client, hass_access_token, hass_read_only_access_token, hass_read_only_user):
    _, m = await _setup_with_ids(hass)
    admin = await hass_ws_client(hass, hass_access_token)
    r = await _ws_call(admin, 1, type="maintenance_mode/preview", pages=["map"])
    assert r["success"] and r["result"]["suspend"] and m.current is None
    user = await hass_ws_client(hass, hass_read_only_access_token)
    r = await _ws_call(user, 1, type="maintenance_mode/preview")
    assert not r["success"] and r["error"]["code"] == "unauthorized"
    await m.async_update_config({"roles": [{"name": "Op", "permissions": ["control"]}]})
    rid = m.config["roles"][0]["id"]
    await m.async_update_config({"panel_access": {hass_read_only_user.id: rid}})
    r = await _ws_call(user, 2, type="maintenance_mode/preview")
    assert r["success"]


async def test_service_returns_the_preview_and_changes_nothing(hass):
    _, m = await _setup_with_ids(hass)
    response = await hass.services.async_call(DOMAIN, "preview", {"pages": ["map"]}, blocking=True, return_response=True)
    assert response["suspend"] == ["automation.a1", "automation.a2", "automation.a3"] and m.current is None


async def test_service_refuses_non_admin_callers(hass, hass_read_only_user):
    from homeassistant.core import Context
    await _setup_with_ids(hass)
    with pytest.raises(Unauthorized):
        await hass.services.async_call(DOMAIN, "preview", {}, blocking=True, return_response=True,
                                       context=Context(user_id=hass_read_only_user.id))
