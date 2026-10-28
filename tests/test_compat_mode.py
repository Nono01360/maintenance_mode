"""0.7.12 — mode compatibilité : réglage serveur (le comportement côté navigateur est testé dans tests_js)."""
from .test_maintenance import _setup
from .test_roles import _ws_call


async def test_default_off_and_exposed_as_attribute(hass):
    _, m = await _setup(hass)
    assert m.config["compat_mode"] is False
    assert hass.states.get("switch.mode_maintenance").attributes["compat_mode"] is False
    await m.async_update_config({"compat_mode": 1})
    assert m.config["compat_mode"] is True
    assert hass.states.get("switch.mode_maintenance").attributes["compat_mode"] is True


async def test_old_stored_config_gets_the_default(hass, hass_storage):
    entry, m = await _setup(hass)
    m.config.pop("compat_mode")
    await m.async_flush()
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.runtime_data.config["compat_mode"] is False


async def test_ws_requires_settings_permission(hass, hass_ws_client, hass_read_only_access_token, hass_read_only_user,
                                              hass_access_token):
    _, m = await _setup(hass)
    user = await hass_ws_client(hass, hass_read_only_access_token)
    r = await _ws_call(user, 1, type="maintenance_mode/update_config", compat_mode=True)
    assert not r["success"] and r["error"]["code"] == "unauthorized" and m.config["compat_mode"] is False
    admin = await hass_ws_client(hass, hass_access_token)
    r = await _ws_call(admin, 1, type="maintenance_mode/update_config", compat_mode=True)
    assert r["success"] and r["result"]["config"]["compat_mode"] is True


async def test_visible_in_state_only_with_settings_permission(hass, hass_read_only_user, hass_admin_user):
    _, m = await _setup(hass)
    assert "compat_mode" in m.state_for(hass_admin_user)["config"]
    assert "config" not in m.state_for(hass_read_only_user)
