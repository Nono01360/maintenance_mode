"""Suppression manuelle de l'historique."""
from datetime import timedelta

import pytest
from homeassistant.exceptions import ServiceValidationError
from homeassistant.util import dt as dt_util

from custom_components.maintenance_mode.const import DOMAIN

from .test_maintenance import _setup
from .test_roles import _ws_call


async def _make_history(m, n=3):
    for i in range(n):
        await m.async_start_now(end=None, reason=f"m{i}", pages=[], pause=False)
        await m.async_stop()


async def test_delete_one_entry(hass):
    _, m = await _setup(hass)
    await _make_history(m)
    assert [h["reason"] for h in m.history] == ["m0", "m1", "m2"]
    assert all(h["hid"] for h in m.history) and len({h["hid"] for h in m.history}) == 3
    victim = m.history[1]["hid"]
    await m.async_delete_history(victim)
    assert [h["reason"] for h in m.history] == ["m0", "m2"]
    with pytest.raises(ServiceValidationError):
        await m.async_delete_history("inconnu")
    with pytest.raises(ServiceValidationError):
        await m.async_delete_history(victim)  # déjà supprimée


async def test_clear_all_and_older_than(hass):
    _, m = await _setup(hass)
    await _make_history(m)
    # on vieillit artificiellement les deux premières entrées
    old = (dt_util.utcnow() - timedelta(days=40)).isoformat()
    m.history[0]["ended_at"] = old
    m.history[1]["ended_at"] = old
    assert await m.async_clear_history(timedelta(days=30)) == 2
    assert [h["reason"] for h in m.history] == ["m2"]
    assert await m.async_clear_history(timedelta(days=30)) == 0   # rien de plus ancien
    assert await m.async_clear_history() == 1
    assert m.history == []


async def test_history_deletion_persists_and_old_entries_get_an_id(hass):
    entry, m = await _setup(hass)
    await _make_history(m, 2)
    # entrées créées avant la v0.6 : pas d'identifiant
    for h in m.history:
        h.pop("hid")
    await m._commit()
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    m2 = entry.runtime_data
    assert all(h["hid"] for h in m2.history)
    await m2.async_delete_history(m2.history[0]["hid"])
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert [h["reason"] for h in entry.runtime_data.history] == ["m1"]   # la suppression est durable


async def test_service_clear_history(hass):
    _, m = await _setup(hass)
    await _make_history(m)
    m.history[0]["ended_at"] = (dt_util.utcnow() - timedelta(days=10)).isoformat()
    await hass.services.async_call(DOMAIN, "clear_history", {"older_than": {"days": 5}}, blocking=True)
    assert [h["reason"] for h in m.history] == ["m1", "m2"]
    await hass.services.async_call(DOMAIN, "clear_history", {}, blocking=True)
    assert m.history == []


async def test_permission_history_delete_implies_history(hass):
    _, m = await _setup(hass)
    await m.async_update_config({"roles": [
        {"name": "Suppr", "permissions": ["history_delete"]},
        {"name": "Lecture", "permissions": ["history"]},
    ]})
    perms = {r["name"]: r["permissions"] for r in m.config["roles"]}
    assert perms["Suppr"] == ["view", "history", "history_delete"]
    assert perms["Lecture"] == ["view", "history"]


async def test_ws_history_permissions(hass, hass_ws_client, hass_read_only_access_token, hass_read_only_user,
                                      hass_access_token):
    _, m = await _setup(hass)
    await _make_history(m)
    await m.async_update_config({"roles": [
        {"name": "Lecture", "permissions": ["history"]},
        {"name": "Suppr", "permissions": ["history_delete"]},
    ]})
    ids = {r["name"]: r["id"] for r in m.config["roles"]}
    user = await hass_ws_client(hass, hass_read_only_access_token)

    # lecture seule de l'historique : suppression refusée côté serveur
    await m.async_update_config({"panel_access": {hass_read_only_user.id: ids["Lecture"]}})
    hid = m.history[0]["hid"]
    r = await _ws_call(user, 1, type="maintenance_mode/delete_history", history_id=hid)
    assert not r["success"] and r["error"]["code"] == "unauthorized"
    r = await _ws_call(user, 2, type="maintenance_mode/clear_history")
    assert not r["success"] and r["error"]["code"] == "unauthorized"
    assert len(m.history) == 3

    # droit de suppression : une entrée puis tout
    await m.async_update_config({"panel_access": {hass_read_only_user.id: ids["Suppr"]}})
    r = await _ws_call(user, 3, type="maintenance_mode/delete_history", history_id=hid)
    assert r["success"] and len(r["result"]["history"]) == 2 and hid not in [h["hid"] for h in r["result"]["history"]]
    r = await _ws_call(user, 4, type="maintenance_mode/delete_history", history_id="inconnu")
    assert not r["success"] and r["error"]["translation_key"] == "history_not_found"
    r = await _ws_call(user, 5, type="maintenance_mode/clear_history")
    assert r["success"] and r["result"]["history"] == [] and m.history == []
