"""Tests de l'intégration Mode maintenance."""
from datetime import timedelta

import pytest
from homeassistant.exceptions import ServiceValidationError
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.maintenance_mode.const import DOMAIN


async def _setup(hass, automations=("a1", "a2")):
    await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {"alias": a, "trigger": {"platform": "event", "event_type": f"ev_{a}"}, "action": []}
                for a in automations
            ]
        },
    )
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry, entry.runtime_data


def _state(hass, eid):
    return hass.states.get(eid).state


async def test_start_stop_all_automations_when_none_selected(hass):
    _, m = await _setup(hass)
    assert _state(hass, "automation.a1") == "on"
    await m.async_start_now(end=None, reason="test", pages=[], pause=True)
    await hass.async_block_till_done()
    # aucune sélection -> tout est coupé
    assert _state(hass, "automation.a1") == "off"
    assert _state(hass, "automation.a2") == "off"
    assert hass.states.get("switch.mode_maintenance").state == "on"
    await m.async_stop()
    await hass.async_block_till_done()
    assert _state(hass, "automation.a1") == "on"
    assert _state(hass, "automation.a2") == "on"
    assert hass.states.get("switch.mode_maintenance").state == "off"


async def test_only_selected_automations_are_paused(hass):
    _, m = await _setup(hass)
    await m.async_update_config({"automations": ["automation.a1"]})
    await m.async_start_now(end=None, reason="", pages=[], pause=True)
    await hass.async_block_till_done()
    assert _state(hass, "automation.a1") == "off"
    assert _state(hass, "automation.a2") == "on"


async def test_pause_false_keeps_automations(hass):
    _, m = await _setup(hass)
    await m.async_start_now(end=None, reason="", pages=["config/devices"], pause=False)
    await hass.async_block_till_done()
    assert _state(hass, "automation.a1") == "on"
    attrs = hass.states.get("switch.mode_maintenance").attributes
    assert attrs["current"]["pages"] == ["config/devices"]


async def test_manual_off_automation_not_reactivated(hass):
    _, m = await _setup(hass)
    await hass.services.async_call("automation", "turn_off", {"entity_id": "automation.a2"}, blocking=True)
    await m.async_start_now(end=None, reason="", pages=[], pause=True)
    await m.async_stop()
    await hass.async_block_till_done()
    assert _state(hass, "automation.a1") == "on"
    assert _state(hass, "automation.a2") == "off"  # déjà coupée par l'utilisateur


async def test_validation(hass):
    _, m = await _setup(hass)
    now = dt_util.utcnow()
    with pytest.raises(ServiceValidationError):  # début dans le passé
        await m.async_add_window(start=now - timedelta(minutes=1), end=None, reason="", pages=[], pause=True)
    with pytest.raises(ServiceValidationError):  # fin avant début
        await m.async_add_window(start=now + timedelta(hours=2), end=now + timedelta(hours=1), reason="", pages=[], pause=True)
    await m.async_add_window(start=now + timedelta(hours=1), end=now + timedelta(hours=3), reason="a", pages=[], pause=True)
    with pytest.raises(ServiceValidationError):  # chevauchement
        await m.async_add_window(start=now + timedelta(hours=2), end=now + timedelta(hours=4), reason="b", pages=[], pause=True)
    # plusieurs maintenances, triées
    await m.async_add_window(start=now + timedelta(days=1), end=now + timedelta(days=1, hours=2), reason="c", pages=["lovelace"], pause=True)
    await m.async_add_window(start=now + timedelta(hours=4), end=now + timedelta(hours=5), reason="d", pages=[], pause=True)
    assert [w.reason for w in m.schedule] == ["a", "d", "c"]
    assert hass.states.get("sensor.mode_maintenance_prochaine_maintenance").state != "unknown"


async def test_schedule_fires_and_ends(hass, freezer):
    _, m = await _setup(hass)
    now = dt_util.utcnow()
    await m.async_add_window(start=now + timedelta(hours=1), end=now + timedelta(hours=2), reason="x", pages=[], pause=True)
    await m.async_add_window(start=now + timedelta(hours=5), end=now + timedelta(hours=6), reason="y", pages=[], pause=True)
    assert m.current is None
    freezer.move_to(now + timedelta(hours=1, minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert m.current and m.current.reason == "x"
    assert _state(hass, "automation.a1") == "off"
    assert len(m.schedule) == 1
    freezer.move_to(now + timedelta(hours=2, minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert m.current is None
    assert _state(hass, "automation.a1") == "on"
    freezer.move_to(now + timedelta(hours=5, minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert m.current and m.current.reason == "y"


async def test_exempt_users_default_is_owner_only(hass, hass_owner_user, hass_admin_user):
    _, m = await _setup(hass)
    attrs = hass.states.get("switch.mode_maintenance").attributes
    assert attrs["exempt_users"] == [hass_owner_user.id]
    await m.async_update_config({"allowed_users": [hass_admin_user.id]})
    attrs = hass.states.get("switch.mode_maintenance").attributes
    assert set(attrs["exempt_users"]) == {hass_owner_user.id, hass_admin_user.id}


async def test_persistence_across_reload(hass):
    entry, m = await _setup(hass)
    now = dt_util.utcnow()
    await m.async_add_window(start=now + timedelta(hours=1), end=None, reason="persist", pages=["map"], pause=True)
    await m.async_update_config({"message": "Coucou", "warn_minutes": 30})
    await m.async_start_now(end=None, reason="en cours", pages=[], pause=True)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    m2 = entry.runtime_data
    assert m2 is not m
    assert m2.config["message"] == "Coucou" and m2.config["warn_minutes"] == 30
    assert [w.reason for w in m2.schedule] == ["persist"]
    assert m2.current and m2.current.reason == "en cours"
    assert _state(hass, "automation.a1") == "off"  # toujours suspendue


async def test_resume_catches_up_missed_window(hass):
    entry, m = await _setup(hass)
    now = dt_util.utcnow()
    from custom_components.maintenance_mode.manager import Window

    # fenêtre dont la fin est déjà passée + fenêtre déjà commencée
    m.schedule = [
        Window("old", now - timedelta(hours=3), now - timedelta(hours=2), "old"),
        Window("live", now - timedelta(minutes=5), now + timedelta(hours=1), "live"),
    ]
    await m._async_resume()
    await hass.async_block_till_done()
    assert m.current and m.current.id == "live"
    assert m.schedule == []


# ------------------------------ websocket / droits ------------------------------
async def test_ws_roles(hass, hass_ws_client, hass_access_token, hass_admin_user, hass_read_only_user, hass_owner_user):
    _, m = await _setup(hass)
    client = await hass_ws_client(hass, hass_access_token)  # utilisateur « admin » de test

    # l'admin de test n'est pas owner mais admin -> vue admin par défaut
    await client.send_json({"id": 1, "type": "maintenance_mode/get_state"})
    res = await client.receive_json()
    assert res["success"] and res["result"]["role"] == "admin"
    assert "config" in res["result"] and "users" in res["result"]

    # planification via websocket
    start = (dt_util.utcnow() + timedelta(hours=1)).isoformat()
    end = (dt_util.utcnow() + timedelta(hours=2)).isoformat()
    await client.send_json({"id": 2, "type": "maintenance_mode/add_window", "start": start, "end": end,
                            "reason": "ws", "pages": ["config/devices"]})
    res = await client.receive_json()
    assert res["success"], res
    assert res["result"]["upcoming"][0]["pages"] == ["config/devices"]
    wid = res["result"]["upcoming"][0]["id"]

    # erreur de validation remontée proprement
    await client.send_json({"id": 3, "type": "maintenance_mode/add_window", "start": start, "end": end})
    res = await client.receive_json()
    assert not res["success"] and "chevauche" in res["error"]["message"]

    # on retire les droits admin à cet utilisateur -> vue utilisateur
    await m.async_update_config({"panel_access": {hass_admin_user.id: "viewer"}})
    await client.send_json({"id": 4, "type": "maintenance_mode/get_state"})
    res = await client.receive_json()
    assert res["result"]["role"] == "viewer"
    assert "config" not in res["result"] and "users" not in res["result"]
    await client.send_json({"id": 6, "type": "maintenance_mode/stop"})
    res = await client.receive_json()
    assert not res["success"] and res["error"]["code"] == "unauthorized"

    # aucun accès
    await m.async_update_config({"panel_access": {hass_admin_user.id: "none"}})
    await client.send_json({"id": 7, "type": "maintenance_mode/get_state"})
    res = await client.receive_json()
    assert res["result"] == {"role": "none"}
    await client.send_json({"id": 8, "type": "maintenance_mode/update_config", "message": "pirate"})
    res = await client.receive_json()
    assert not res["success"] and res["error"]["code"] == "unauthorized"
    assert m.config["message"] != "pirate"


async def test_ws_subscribe_pushes_updates(hass, hass_ws_client, hass_access_token):
    _, m = await _setup(hass)
    client = await hass_ws_client(hass, hass_access_token)
    await client.send_json({"id": 1, "type": "maintenance_mode/subscribe"})
    first = await client.receive_json()
    assert first["type"] in ("event", "result")
    msgs = [first]
    # on draine jusqu'au résultat
    while not any(x["type"] == "result" for x in msgs):
        msgs.append(await client.receive_json())
    await m.async_start_now(end=None, reason="push", pages=[], pause=False)
    ev = await client.receive_json()
    assert ev["type"] == "event" and ev["event"]["current"]["reason"] == "push"


async def test_panel_registered_and_static(hass, hass_client):
    await _setup(hass)
    assert "maintenance" in hass.data["frontend_panels"]
    client = await hass_client()
    for path in ("overlay.js", "panel.js"):
        resp = await client.get(f"/maintenance_mode_static/{path}")
        assert resp.status == 200


async def test_ws_update_and_delete_window(hass, hass_ws_client, hass_access_token):
    """Régression : l'identifiant de maintenance ne doit pas s'appeler « id »
    (champ réservé du message websocket, réécrit par le client JS)."""
    _, m = await _setup(hass)
    client = await hass_ws_client(hass, hass_access_token)
    s = dt_util.utcnow() + timedelta(hours=1)
    e = dt_util.utcnow() + timedelta(hours=2)
    await client.send_json({"id": 1, "type": "maintenance_mode/add_window",
                            "start": s.isoformat(), "end": e.isoformat(), "reason": "avant"})
    res = await client.receive_json()
    assert res["success"], res
    wid = res["result"]["upcoming"][0]["id"]

    await client.send_json({"id": 2, "type": "maintenance_mode/update_window", "window_id": wid,
                            "start": (s + timedelta(hours=1)).isoformat(),
                            "end": (e + timedelta(hours=1)).isoformat(),
                            "reason": "après", "pages": ["map"], "pause_automations": False})
    res = await client.receive_json()
    assert res["success"], res
    w = res["result"]["upcoming"][0]
    assert w["id"] == wid and w["reason"] == "après" and w["pages"] == ["map"] and w["pause_automations"] is False

    await client.send_json({"id": 3, "type": "maintenance_mode/delete_window", "window_id": wid})
    res = await client.receive_json()
    assert res["success"], res
    assert res["result"]["upcoming"] == [] and m.schedule == []

    await client.send_json({"id": 4, "type": "maintenance_mode/delete_window", "window_id": "inconnu"})
    res = await client.receive_json()
    assert not res["success"] and "introuvable" in res["error"]["message"]


async def test_panel_hidden_attribute(hass, hass_admin_user, hass_owner_user):
    _, m = await _setup(hass)
    attrs = hass.states.get("switch.mode_maintenance").attributes
    assert attrs["panel_hidden_for"] == []
    await m.async_update_config({"panel_access": {hass_admin_user.id: "none", hass_owner_user.id: "none"}})
    attrs = hass.states.get("switch.mode_maintenance").attributes
    # le propriétaire garde toujours la vue administrateur
    assert attrs["panel_hidden_for"] == [hass_admin_user.id]
