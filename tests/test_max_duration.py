"""0.8.4 — durée maximale (par défaut, par modèle, par maintenance) : fin imposée, rappel avant, arrêt automatique."""
from datetime import timedelta

import pytest
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed, async_mock_service

from custom_components.maintenance_mode.errors import MaintenanceError

from .test_maintenance import _setup
from .test_roles import _ws_call


def _minutes(w):
    return round((w.end - w.start).total_seconds() / 60)


async def test_default_is_no_limit(hass):
    _, m = await _setup(hass)
    assert m.config["max_duration_minutes"] == 0
    await m.async_start_now(end=None, reason="", pages=[], pause=False)
    assert m.current.end is None and m.current.capped is False


async def test_open_ended_maintenance_gets_the_default_maximum(hass):
    _, m = await _setup(hass)
    await m.async_update_config({"max_duration_minutes": 90})
    await m.async_start_now(end=None, reason="", pages=[], pause=False)
    assert _minutes(m.current) == 90 and m.current.capped is True
    assert hass.states.get("switch.mode_maintenance").attributes["current"]["capped"] is True


async def test_explicit_end_within_the_maximum_is_kept(hass):
    _, m = await _setup(hass)
    await m.async_update_config({"max_duration_minutes": 90})
    end = dt_util.utcnow() + timedelta(minutes=30)
    await m.async_start_now(end=end, reason="", pages=[], pause=False)
    assert m.current.end == end and m.current.capped is False


async def test_explicit_end_beyond_the_maximum_is_refused(hass):
    _, m = await _setup(hass)
    await m.async_update_config({"max_duration_minutes": 60})
    with pytest.raises(MaintenanceError) as exc:
        await m.async_start_now(end=dt_util.utcnow() + timedelta(hours=3), reason="", pages=[], pause=False)
    assert exc.value.code == "max_duration_exceeded" and exc.value.placeholders == {"max": "60"}
    assert m.current is None
    now = dt_util.utcnow()
    with pytest.raises(MaintenanceError):
        await m.async_add_window(start=now + timedelta(hours=1), end=now + timedelta(hours=5), reason="", pages=[], pause=False)
    assert m.schedule == []


async def test_per_maintenance_value_overrides_the_default(hass):
    _, m = await _setup(hass)
    await m.async_update_config({"max_duration_minutes": 60})
    await m.async_start_now(end=dt_util.utcnow() + timedelta(hours=5), reason="", pages=[], pause=False, max_minutes=0)   # sans limite
    assert _minutes(m.current) in (299, 300) and m.current.capped is False
    await m.async_update_config({"max_duration_minutes": 0})
    await m.async_start_now(end=None, reason="", pages=[], pause=False, max_minutes=30)                                     # plus strict
    assert _minutes(m.current) == 30 and m.current.capped is True


async def test_scheduled_open_ended_window_is_capped_when_it_starts(hass, freezer):
    _, m = await _setup(hass)
    now = dt_util.utcnow()
    await m.async_update_config({"max_duration_minutes": 45})
    await m.async_add_window(start=now + timedelta(hours=1), end=None, reason="", pages=[], pause=False)
    assert m.schedule[0].end is None                                          # le plan reste tel que saisi
    freezer.move_to(now + timedelta(hours=1, minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert m.current is not None and _minutes(m.current) == 45 and m.current.capped is True


async def test_lowering_the_maximum_later_caps_silently_at_start(hass, freezer):
    _, m = await _setup(hass)
    now = dt_util.utcnow()
    await m.async_add_window(start=now + timedelta(hours=1), end=now + timedelta(hours=6), reason="", pages=[], pause=False)
    await m.async_update_config({"max_duration_minutes": 120})
    freezer.move_to(now + timedelta(hours=1, minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert _minutes(m.current) == 120 and m.current.capped is True


async def test_reminder_then_automatic_stop_with_notification(hass, freezer):
    hass.config.language = "fr"
    calls = async_mock_service(hass, "notify", "test_phone")
    _, m = await _setup(hass)
    await m.async_update_config({"max_duration_minutes": 60, "notify_services": ["test_phone"], "end_soon_minutes": 10})
    now = dt_util.utcnow()
    await m.async_start_now(end=None, reason="", pages=[], pause=True)
    freezer.move_to(now + timedelta(minutes=51))                                  # rappel 10 min avant le maximum
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert calls[-1].data["title"] == "La maintenance se termine bientôt" and m.current is not None
    freezer.move_to(now + timedelta(minutes=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert m.current is None and m.history[-1]["ended_by"] == "max_duration" and m.history[-1]["capped"] is True
    assert calls[-1].data["title"] == "Maintenance terminée"


async def test_normal_automatic_end_is_still_auto(hass, freezer):
    _, m = await _setup(hass)
    await m.async_update_config({"max_duration_minutes": 120})
    now = dt_util.utcnow()
    await m.async_start_now(end=now + timedelta(minutes=10), reason="", pages=[], pause=False)
    freezer.move_to(now + timedelta(minutes=11))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert m.history[-1]["ended_by"] == "auto"


async def test_update_current_cannot_exceed_nor_remove_the_maximum(hass):
    _, m = await _setup(hass)
    await m.async_update_config({"max_duration_minutes": 60})
    await m.async_start_now(end=dt_util.utcnow() + timedelta(minutes=20), reason="", pages=[], pause=False)
    with pytest.raises(MaintenanceError):
        await m.async_update_current(end=dt_util.utcnow() + timedelta(hours=2), reason="", pages=[])
    await m.async_update_current(end=None, reason="", pages=[])                  # fin retirée : ramenée au maximum
    assert _minutes(m.current) == 60 and m.current.capped is True


async def test_template_keeps_max_minutes_and_ws_validates_the_range(hass, hass_ws_client, hass_access_token):
    _, m = await _setup(hass)
    await m.async_update_config({"templates": [{"name": "T", "max_minutes": "45"}, {"name": "U"}, {"name": "V", "max_minutes": 0}]})
    assert [t["max_minutes"] for t in m.config["templates"]] == [45, None, 0]
    c = await hass_ws_client(hass, hass_access_token)
    r = await _ws_call(c, 1, type="maintenance_mode/start", max_minutes=20, reason="ws")
    assert r["success"] and r["result"]["current"]["max_minutes"] == 20
    r = await _ws_call(c, 2, type="maintenance_mode/start", max_minutes=-1)
    assert not r["success"] and r["error"]["code"] == "invalid_format"
    r = await _ws_call(c, 3, type="maintenance_mode/update_config", max_duration_minutes=999999999)
    assert not r["success"] and r["error"]["code"] == "invalid_format"
    r = await _ws_call(c, 4, type="maintenance_mode/update_config", max_duration_minutes=120)
    assert r["success"] and m.config["max_duration_minutes"] == 120


async def test_service_accepts_max_minutes(hass):
    _, m = await _setup(hass)
    await hass.services.async_call("maintenance_mode", "start", {"pause_automations": False, "max_minutes": 15}, blocking=True)
    assert _minutes(m.current) == 15 and m.current.capped
