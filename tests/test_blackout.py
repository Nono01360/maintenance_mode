"""0.8.5 — plages interdites : refus expliqué, dérogation du propriétaire journalisée."""
import logging
from datetime import timedelta

import pytest
from homeassistant.util import dt as dt_util

from custom_components.maintenance_mode.blackout import clean_blackouts, matching_rule
from custom_components.maintenance_mode.errors import MaintenanceError

from .test_maintenance import _setup
from .test_roles import _ws_call


def _rule(start, end, days=None, name="Nuit"):
    return {"id": "r", "name": name, "days": days if days is not None else list(range(7)), "start": start, "end": end}


def _local(y, mo, d, h, mi=0):
    return dt_util.as_utc(dt_util.as_local(dt_util.utcnow()).replace(year=y, month=mo, day=d, hour=h, minute=mi, second=0, microsecond=0))


def test_matching_same_day_overnight_and_weekdays():
    day = _rule("09:00", "17:00", days=[0, 1, 2, 3, 4])                     # lundi–vendredi, heures de bureau
    assert matching_rule([day], _local(2027, 3, 1, 10)) is day              # lundi 10 h
    assert matching_rule([day], _local(2027, 3, 1, 17)) is None             # fin exclusive
    assert matching_rule([day], _local(2027, 3, 6, 10)) is None             # samedi
    night = _rule("22:00", "06:00", days=[4])                               # nuit du vendredi au samedi
    assert matching_rule([night], _local(2027, 3, 5, 23)) is night          # vendredi 23 h
    assert matching_rule([night], _local(2027, 3, 6, 5, 59)) is night       # samedi 5 h 59 : suite de la nuit du vendredi
    assert matching_rule([night], _local(2027, 3, 6, 6)) is None
    assert matching_rule([night], _local(2027, 3, 6, 23)) is None           # samedi soir : pas concerné
    assert matching_rule([night], _local(2027, 3, 7, 3)) is None            # dimanche 3 h : suite d'un samedi non interdit


def test_cleaning():
    out = clean_blackouts([
        {"name": " " + "n" * 80, "days": [6, 0, "x", 9, 0], "start": "22:00", "end": "06:00"},
        {"start": "10:00", "end": "10:00"},                                 # vide : ignorée
        {"start": "25:00", "end": "26:00"},                                 # invalide : ignorée
        {"name": "Tous jours", "start": "08:00", "end": "09:00"},
    ])
    assert len(out) == 2 and out[0]["days"] == [0, 6] and len(out[0]["name"]) == 40
    assert out[1]["days"] == list(range(7)) and out[1]["id"]
    assert len(clean_blackouts([{"start": "01:00", "end": "02:00"}] * 50)) == 20


async def _around_now(m, offset_h=(-1, 1), name="Fermé"):
    local = dt_util.as_local(dt_util.utcnow())
    a, b = local + timedelta(hours=offset_h[0]), local + timedelta(hours=offset_h[1])
    await m.async_update_config({"blackouts": [{"name": name, "start": a.strftime("%H:%M"), "end": b.strftime("%H:%M")}]})


async def test_start_now_is_refused_inside_a_blackout(hass):
    _, m = await _setup(hass)
    await _around_now(m)
    with pytest.raises(MaintenanceError) as exc:
        await m.async_start_now(end=None, reason="", pages=[], pause=False)
    assert exc.value.code == "blackout_period" and exc.value.placeholders == {"name": "Fermé"} and m.current is None


async def test_outside_the_blackout_everything_works(hass):
    _, m = await _setup(hass)
    await _around_now(m, offset_h=(2, 3))
    await m.async_start_now(end=None, reason="", pages=[], pause=False)
    assert m.current and m.current.blackout_override is False


async def test_scheduling_checks_the_start_instant(hass):
    _, m = await _setup(hass)
    now = dt_util.utcnow()
    await _around_now(m, offset_h=(1, 3))                                      # interdit de +1 h à +3 h
    with pytest.raises(MaintenanceError):
        await m.async_add_window(start=now + timedelta(hours=2), end=now + timedelta(hours=2, minutes=30), reason="", pages=[], pause=False)
    ok = await m.async_add_window(start=now + timedelta(hours=4), end=now + timedelta(hours=5), reason="", pages=[], pause=False)
    with pytest.raises(MaintenanceError):                                       # déplacer vers la plage interdite
        await m.async_update_window(ok.id, start=now + timedelta(hours=2), end=now + timedelta(hours=2, minutes=20), reason="", pages=[], pause=False)
    assert m.schedule[0].start == ok.start


async def test_owner_override_is_logged_and_kept_in_history(hass, caplog):
    _, m = await _setup(hass)
    await _around_now(m)
    with caplog.at_level(logging.WARNING):
        await m.async_start_now(end=None, reason="urgence", pages=[], pause=False, by="Nolann", override_blackout=True)
    assert m.current.blackout_override is True
    assert "Plage interdite" in caplog.text and "Nolann" in caplog.text
    await m.async_stop()
    assert m.history[-1]["blackout_override"] is True


async def test_ws_override_is_for_the_owner_only(hass, hass_ws_client, hass_access_token, hass_admin_user):
    _, m = await _setup(hass)
    await _around_now(m)
    admin = await hass_ws_client(hass, hass_access_token)                         # administrateur, pas propriétaire
    r = await _ws_call(admin, 1, type="maintenance_mode/start", reason="x")
    assert not r["success"] and r["error"]["translation_key"] == "blackout_period"
    r = await _ws_call(admin, 2, type="maintenance_mode/start", reason="x", override_blackout=True)
    assert not r["success"] and r["error"]["code"] == "unauthorized" and m.current is None
    hass_admin_user.is_owner = True                                               # même appelant, devenu propriétaire
    r = await _ws_call(admin, 3, type="maintenance_mode/start", reason="x", override_blackout=True)
    assert r["success"] and r["result"]["current"]["reason"] == "x" and m.current.blackout_override is True


async def test_service_cannot_override(hass):
    _, m = await _setup(hass)
    await _around_now(m)
    with pytest.raises(MaintenanceError):
        await hass.services.async_call("maintenance_mode", "start", {}, blocking=True)


async def test_config_is_admin_only_and_bounded(hass, hass_ws_client, hass_access_token):
    _, m = await _setup(hass)
    c = await hass_ws_client(hass, hass_access_token)
    r = await _ws_call(c, 1, type="maintenance_mode/update_config", blackouts=[{"name": "Nuit", "days": [4, 5], "start": "22:00", "end": "06:00"}])
    assert r["success"] and m.config["blackouts"][0]["days"] == [4, 5]
    assert r["result"]["config"]["blackouts"][0]["name"] == "Nuit"
    r = await _ws_call(c, 2, type="maintenance_mode/update_config", blackouts=[{"start": "22:00", "end": "06:00", "days": [9]}])
    assert not r["success"] and r["error"]["code"] == "invalid_format"
