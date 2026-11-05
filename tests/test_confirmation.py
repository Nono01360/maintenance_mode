"""0.8.6 — confirmation renforcée pour les actions larges (beaucoup d'automatisations à suspendre)."""
from datetime import timedelta

from homeassistant.util import dt as dt_util

from .test_maintenance import _setup
from .test_roles import _ws_call

MANY = tuple(f"a{i}" for i in range(25))


async def _client(hass, hass_ws_client, hass_access_token):
    _, m = await _setup(hass, automations=MANY)
    return m, await hass_ws_client(hass, hass_access_token)


async def test_large_start_needs_explicit_confirmation(hass, hass_ws_client, hass_access_token):
    m, c = await _client(hass, hass_ws_client, hass_access_token)
    assert m.config["confirm_threshold"] == 20
    r = await _ws_call(c, 1, type="maintenance_mode/start", reason="x")
    assert not r["success"] and r["error"]["translation_key"] == "confirmation_required"
    assert r["error"]["translation_placeholders"] == {"count": "25"} and m.current is None
    assert all(hass.states.get(f"automation.a{i}").state == "on" for i in range(25))     # rien n'a bougé
    r = await _ws_call(c, 2, type="maintenance_mode/start", reason="x", confirm=True)
    assert r["success"] and len(m.disabled) == 25


async def test_small_or_unpausing_actions_need_no_confirmation(hass, hass_ws_client, hass_access_token):
    m, c = await _client(hass, hass_ws_client, hass_access_token)
    r = await _ws_call(c, 1, type="maintenance_mode/start", pause_automations=False)
    assert r["success"]
    await m.async_stop()
    await m.async_update_config({"automations": [f"automation.a{i}" for i in range(5)]})
    r = await _ws_call(c, 2, type="maintenance_mode/start")
    assert r["success"] and len(m.disabled) == 5


async def test_threshold_is_configurable_and_zero_disables(hass, hass_ws_client, hass_access_token):
    m, c = await _client(hass, hass_ws_client, hass_access_token)
    await m.async_update_config({"confirm_threshold": 30})
    assert (await _ws_call(c, 1, type="maintenance_mode/start"))["success"]
    await m.async_stop()
    await m.async_update_config({"confirm_threshold": 25})                     # seuil atteint : « à partir de »
    assert not (await _ws_call(c, 2, type="maintenance_mode/start"))["success"]
    await m.async_update_config({"confirm_threshold": 0})
    assert (await _ws_call(c, 3, type="maintenance_mode/start"))["success"]
    await m.async_update_config({"confirm_threshold": 99999999})
    assert m.config["confirm_threshold"] == 10000


async def test_protected_automations_are_not_counted(hass, hass_ws_client, hass_access_token):
    m, c = await _client(hass, hass_ws_client, hass_access_token)
    await m.async_update_config({"excluded_automations": [f"automation.a{i}" for i in range(10)]})   # 15 restent
    assert (await _ws_call(c, 1, type="maintenance_mode/start"))["success"] and len(m.disabled) == 15


async def test_scheduling_and_editing_need_confirmation_too(hass, hass_ws_client, hass_access_token):
    m, c = await _client(hass, hass_ws_client, hass_access_token)
    now = dt_util.utcnow()
    start, end = (now + timedelta(hours=2)).isoformat(), (now + timedelta(hours=3)).isoformat()
    r = await _ws_call(c, 1, type="maintenance_mode/add_window", start=start, end=end)
    assert not r["success"] and r["error"]["translation_key"] == "confirmation_required" and m.schedule == []
    r = await _ws_call(c, 2, type="maintenance_mode/add_window", start=start, end=end, confirm=True)
    assert r["success"]
    wid = m.schedule[0].id
    new_start = (now + timedelta(hours=4)).isoformat()
    r = await _ws_call(c, 3, type="maintenance_mode/update_window", window_id=wid, start=new_start, end=(now + timedelta(hours=5)).isoformat())
    assert not r["success"] and r["error"]["translation_key"] == "confirmation_required"
    r = await _ws_call(c, 4, type="maintenance_mode/update_window", window_id=wid, start=new_start, end=(now + timedelta(hours=5)).isoformat(), confirm=True)
    assert r["success"]


async def test_services_and_internal_calls_are_not_asked(hass):
    _, m = await _setup(hass, automations=MANY)
    await hass.services.async_call("maintenance_mode", "start", {}, blocking=True)       # appel explicite d'un administrateur
    assert len(m.disabled) == 25
    await m.async_stop()
    await m.async_start_now(end=None, reason="", pages=[], pause=True)                    # API interne : confirmée par défaut
    assert len(m.disabled) == 25
