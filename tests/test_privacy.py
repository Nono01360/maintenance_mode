"""0.7.10 — confidentialité : rien de personnel dans les attributs lisibles par tous."""
from homeassistant.util import dt as dt_util
from datetime import timedelta

from .test_maintenance import _setup
from .test_roles import _ws_call


def _attrs(hass):
    return hass.states.get("switch.mode_maintenance").attributes


async def test_public_attributes_hold_no_identifier_nor_automation_name(hass, hass_admin_user, hass_owner_user, hass_read_only_user):
    _, m = await _setup(hass)
    await m.async_update_config({
        "allowed_users": [hass_admin_user.id], "automations": ["automation.a1"],
        "panel_access": {hass_read_only_user.id: "none"}, "notify_services": ["mobile_app_secret"],
    })
    await m.async_start_now(end=None, reason="r", pages=[], pause=True, by="Nolann")
    await m.async_add_window(start=dt_util.utcnow() + timedelta(hours=2), end=None, reason="p", pages=[], pause=False)
    text = str(dict(_attrs(hass)))
    for secret in (hass_admin_user.id, hass_owner_user.id, hass_read_only_user.id, "automation.a1", "automation.a2",
                   "mobile_app_secret", "Nolann"):
        assert secret not in text, secret
    for gone in ("exempt_users", "panel_hidden_for", "disabled_automations"):
        assert gone not in _attrs(hass)


async def test_rights_revision_changes_only_when_rights_change(hass, hass_admin_user):
    _, m = await _setup(hass)
    first = _attrs(hass)["rights_rev"]
    await m.async_update_config({"message": "autre"})
    assert _attrs(hass)["rights_rev"] == first                       # un simple réglage ne le change pas
    await m.async_update_config({"allowed_users": [hass_admin_user.id]})
    second = _attrs(hass)["rights_rev"]
    assert second != first and hass_admin_user.id not in second
    await m.async_update_config({"panel_access": {hass_admin_user.id: "none"}})
    assert _attrs(hass)["rights_rev"] not in (first, second)


async def test_ws_get_client_returns_only_the_callers_rights(hass, hass_ws_client, hass_read_only_access_token,
                                                            hass_access_token, hass_read_only_user, hass_admin_user):
    _, m = await _setup(hass)
    await m.async_update_config({"allowed_users": [hass_read_only_user.id], "panel_access": {hass_admin_user.id: "none"}})
    reader = await hass_ws_client(hass, hass_read_only_access_token)
    r = await _ws_call(reader, 1, type="maintenance_mode/get_client")
    assert r["success"] and r["result"] == {"exempt": True, "panel_hidden": False}
    admin = await hass_ws_client(hass, hass_access_token)
    r = await _ws_call(admin, 1, type="maintenance_mode/get_client")
    assert r["success"] and r["result"] == {"exempt": False, "panel_hidden": True}
    assert hass_read_only_user.id not in str(r) and hass_admin_user.id not in str(r)
