"""0.8.7 — annuler une suppression pendant quelques secondes (maintenance planifiée, modèle)."""
from datetime import timedelta

import pytest
from homeassistant.exceptions import Unauthorized
from homeassistant.util import dt as dt_util

from custom_components.maintenance_mode.errors import MaintenanceError
from custom_components.maintenance_mode.trash import UNDO_SECONDS

from .test_maintenance import _setup
from .test_roles import _ws_call


async def _two_windows(m):
    now = dt_util.utcnow()
    a = await m.async_add_window(start=now + timedelta(hours=1), end=now + timedelta(hours=2), reason="a", pages=["map"], pause=False, repeat="weekly")
    b = await m.async_add_window(start=now + timedelta(hours=5), end=now + timedelta(hours=6), reason="b", pages=[], pause=True)
    return a, b


async def test_deleted_window_is_restored_identically(hass):
    _, m = await _setup(hass)
    a, b = await _two_windows(m)
    before = a.as_dict()
    undo = await m.async_delete_window(a.id)
    assert undo["kind"] == "window" and undo["seconds"] == UNDO_SECONDS and [w.reason for w in m.schedule] == ["b"]
    assert await m.async_undo(undo["token"], {"schedule"}) == "window"
    assert [w.reason for w in m.schedule] == ["a", "b"]
    assert m.schedule[0].as_dict() == before and m.schedule[0].id == a.id        # même identifiant, mêmes champs, même série


async def test_undo_expires_after_a_few_seconds_and_works_once(hass, freezer):
    _, m = await _setup(hass)
    a, _ = await _two_windows(m)
    undo = await m.async_delete_window(a.id)
    freezer.tick(timedelta(seconds=UNDO_SECONDS + 1))
    with pytest.raises(MaintenanceError) as exc:
        await m.async_undo(undo["token"], {"schedule"})
    assert exc.value.code == "undo_expired" and len(m.schedule) == 1
    undo = await m.async_delete_window(m.schedule[0].id)
    await m.async_undo(undo["token"], {"schedule"})
    with pytest.raises(MaintenanceError):
        await m.async_undo(undo["token"], {"schedule"})                           # déjà annulée
    with pytest.raises(MaintenanceError):
        await m.async_undo("inconnu", {"schedule"})


async def test_undo_refused_when_the_slot_was_taken_or_started(hass, freezer):
    _, m = await _setup(hass)
    now = dt_util.utcnow()
    a = await m.async_add_window(start=now + timedelta(minutes=30), end=now + timedelta(hours=1), reason="a", pages=[], pause=False)
    undo = await m.async_delete_window(a.id)
    await m.async_add_window(start=now + timedelta(minutes=40), end=now + timedelta(minutes=50), reason="pris", pages=[], pause=False)
    with pytest.raises(MaintenanceError) as exc:
        await m.async_undo(undo["token"], {"schedule"})
    assert exc.value.code == "overlaps_scheduled" and [w.reason for w in m.schedule] == ["pris"]


async def test_undo_needs_the_right_permission(hass):
    _, m = await _setup(hass)
    a, _ = await _two_windows(m)
    undo = await m.async_delete_window(a.id)
    with pytest.raises(Unauthorized):
        await m.async_undo(undo["token"], {"view", "control"})
    assert len(m.schedule) == 1
    await m.async_undo(undo["token"], {"schedule"})                                # le jeton reste valable pour qui a le droit
    assert len(m.schedule) == 2


async def test_template_delete_and_undo_keep_the_order(hass):
    _, m = await _setup(hass)
    await m.async_update_config({"templates": [{"name": "A"}, {"name": "B"}, {"name": "C"}]})
    ids = [t["id"] for t in m.config["templates"]]
    undo = await m.async_delete_template(ids[1])
    assert [t["name"] for t in m.config["templates"]] == ["A", "C"] and undo["kind"] == "template"
    await m.async_undo(undo["token"], {"templates"})
    assert [t["name"] for t in m.config["templates"]] == ["A", "B", "C"] and m.config["templates"][1]["id"] == ids[1]
    with pytest.raises(MaintenanceError) as exc:
        await m.async_delete_template("inconnu")
    assert exc.value.code == "template_not_found"


async def test_nothing_deleted_is_written_to_disk(hass, hass_storage):
    entry, m = await _setup(hass)
    a, _ = await _two_windows(m)
    await m.async_delete_window(a.id)
    await m.async_flush()
    assert "trash" not in str(hass_storage[f"maintenance_mode.{entry.entry_id}"]["data"].keys())
    assert [w["reason"] for w in hass_storage[f"maintenance_mode.{entry.entry_id}"]["data"]["schedule"]] == ["b"]


async def test_ws_flow(hass, hass_ws_client, hass_access_token, hass_read_only_access_token, hass_read_only_user):
    _, m = await _setup(hass)
    a, _ = await _two_windows(m)
    await m.async_update_config({"templates": [{"name": "T"}]})
    c = await hass_ws_client(hass, hass_access_token)
    r = await _ws_call(c, 1, type="maintenance_mode/delete_window", window_id=a.id)
    assert r["success"] and r["result"]["undo"]["kind"] == "window" and len(r["result"]["upcoming"]) == 1
    token = r["result"]["undo"]["token"]
    r = await _ws_call(c, 2, type="maintenance_mode/undo_delete", token=token)
    assert r["success"] and len(r["result"]["upcoming"]) == 2 and "undo" not in r["result"]
    r = await _ws_call(c, 3, type="maintenance_mode/delete_template", template_id=m.config["templates"][0]["id"])
    assert r["success"] and r["result"]["undo"]["kind"] == "template" and m.config["templates"] == []
    r = await _ws_call(c, 4, type="maintenance_mode/undo_delete", token=r["result"]["undo"]["token"])
    assert r["success"] and m.config["templates"][0]["name"] == "T"
    r = await _ws_call(c, 5, type="maintenance_mode/undo_delete", token="inconnu")
    assert not r["success"] and r["error"]["translation_key"] == "undo_expired"
    # un lecteur ne peut ni supprimer ni annuler la suppression d'un autre
    user = await hass_ws_client(hass, hass_read_only_access_token)
    r = await _ws_call(user, 1, type="maintenance_mode/delete_template", template_id="x")
    assert not r["success"] and r["error"]["code"] == "unauthorized"
    undo = await m.async_delete_window(a.id)
    r = await _ws_call(user, 2, type="maintenance_mode/undo_delete", token=undo["token"])
    assert not r["success"] and r["error"]["code"] == "unauthorized" and len(m.schedule) == 1


async def test_service_cancel_still_works(hass):
    _, m = await _setup(hass)
    a, _ = await _two_windows(m)
    await hass.services.async_call("maintenance_mode", "cancel_schedule", {"window_id": a.id}, blocking=True)
    assert [w.reason for w in m.schedule] == ["b"]
