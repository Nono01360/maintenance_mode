"""9.4 — hooks avant / après (scripts et scènes) : ordre, délai maximum, politique d'échec, historique, boucles."""
import asyncio

import pytest
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import async_capture_events, async_mock_service

from custom_components.maintenance_mode.errors import MaintenanceError
from custom_components.maintenance_mode.hooks import clean_hooks

from .test_maintenance import _setup


def _h(when, entity, **kw):
    return {"id": f"{when}-{entity}", "name": kw.pop("name", entity), "when": when, "entity_id": entity,
            "timeout": kw.pop("timeout", 30), "on_failure": kw.pop("on_failure", "continue"), **kw}


async def _scripts(hass):
    ev = lambda n: {"event": "hook_ran", "event_data": {"n": n}}  # noqa: E731
    assert await async_setup_component(hass, "script", {"script": {
        "one": {"sequence": [ev("one")]}, "two": {"sequence": [ev("two")]},
        "three": {"sequence": [ev("three")]}, "four": {"sequence": [ev("four")]},
        "bad": {"sequence": [{"service": "nonexistent_domain.nothing"}]},
        "evil": {"sequence": [{"service": "maintenance_mode.stop"}]},
    }})


def test_clean_hooks():
    out = clean_hooks([
        {"name": "ok", "when": "before_start", "entity_id": "script.a", "timeout": 999, "on_failure": "abort"},
        {"when": "after_start", "entity_id": "script.b", "on_failure": "abort"},       # abort : avant le début seulement
        {"when": "bidon", "entity_id": "script.c"}, {"when": "after_end", "entity_id": "light.x"},
        {"when": "after_end", "entity_id": "scene.s", "timeout": 0},
    ] + [{"when": "after_end", "entity_id": "script.z"}] * 50)
    assert [h["entity_id"] for h in out][:3] == ["script.a", "script.b", "scene.s"] and len(out) == 20
    assert out[0]["timeout"] == 120 and out[0]["on_failure"] == "abort"
    assert out[1]["on_failure"] == "continue" and out[2]["timeout"] == 1


async def test_order_and_results_in_history(hass):
    await _scripts(hass)
    _, m = await _setup(hass)
    seen = async_capture_events(hass, "hook_ran")
    m.config["hooks"] = [_h("before_end", "script.three"), _h("after_start", "script.two"), _h("before_start", "script.one"),
                         _h("after_end", "script.four"), _h("after_start", "script.bad")]
    await m.async_start_now(end=None, reason="h", pages=[], pause=True)
    await m.async_stop()
    await hass.async_block_till_done()
    assert [e.data["n"] for e in seen] == ["one", "two", "three", "four"], "ordre : avant début, après début, avant fin, après fin"
    res = m.history[-1]["hooks"]
    assert [(r["when"], r["status"]) for r in res] == [("before_start", "ok"), ("after_start", "ok"), ("after_start", "failed"),
                                                        ("before_end", "ok"), ("after_end", "ok")]
    assert res[2]["error"] and m.hook_results == []


async def test_before_start_abort_cancels_start(hass):
    await _scripts(hass)
    _, m = await _setup(hass)
    m.config["hooks"] = [_h("before_start", "script.bad", on_failure="abort"), _h("before_start", "script.one")]
    seen = async_capture_events(hass, "hook_ran")
    with pytest.raises(MaintenanceError) as err:
        await m.async_start_now(end=None, reason="", pages=[], pause=True)
    assert err.value.code == "hook_aborted" and m.current is None and seen == []
    assert hass.states.get("automation.a1").state == "on", "rien n'est suspendu"
    m.config["hooks"] = [_h("before_start", "script.bad", on_failure="continue"), _h("before_start", "script.one")]
    await m.async_start_now(end=None, reason="", pages=[], pause=True)
    assert m.current is not None and len(seen) == 1, "politique « continuer » : le hook suivant est exécuté"


async def test_timeout_and_missing_entity(hass):
    _, m = await _setup(hass)
    hass.states.async_set("script.slow", "off")
    hass.states.async_set("scene.s1", "unknown")
    async def slow(call):
        await asyncio.sleep(5)
    hass.services.async_register("script", "slow", slow)
    scene = async_mock_service(hass, "scene", "turn_on")
    m.config["hooks"] = [_h("after_start", "script.slow", timeout=0.05), _h("after_start", "script.absent"),
                         _h("after_start", "scene.s1")]
    await m.async_start_now(end=None, reason="", pages=[], pause=False)
    assert [r["status"] for r in m.hook_results] == ["timeout", "missing", "ok"]
    assert scene[0].data == {"entity_id": "scene.s1"}


async def test_hook_cannot_call_back_into_the_integration(hass):
    await _scripts(hass)
    _, m = await _setup(hass)
    m.config["hooks"] = [_h("after_start", "script.evil", timeout=30)]
    await asyncio.wait_for(m.async_start_now(end=None, reason="", pages=[], pause=False), 10)
    assert m.current is not None, "le hook n'a pas pu arrêter la maintenance"
    assert m.hook_results[0]["status"] == "failed"


async def test_hooks_persist_and_do_not_rerun_on_recovery(hass):
    await _scripts(hass)
    entry, m = await _setup(hass)
    m.config["hooks"] = [_h("after_start", "script.one")]
    await m.async_start_now(end=None, reason="", pages=[], pause=True)
    seen = async_capture_events(hass, "hook_ran")
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.runtime_data.config["hooks"][0]["entity_id"] == "script.one" and seen == []
    assert entry.runtime_data.hook_results[0]["status"] == "ok"


async def test_hooks_are_admin_only(hass, hass_ws_client, hass_access_token, hass_read_only_access_token, hass_read_only_user,
                                    hass_admin_user):
    """Exécuter des scripts est réservé aux administrateurs HA, même avec l'autorisation « settings »."""
    from .test_roles import _ws_call

    _, m = await _setup(hass)
    await m.async_update_config({"roles": [{"name": "Réglages", "permissions": ["settings"]}]})
    rid = m.config["roles"][0]["id"]
    await m.async_update_config({"panel_access": {hass_read_only_user.id: rid}})
    hook = {"when": "after_start", "entity_id": "script.one", "name": "x"}
    user = await hass_ws_client(hass, hass_read_only_access_token)
    r = await _ws_call(user, 1, type="maintenance_mode/update_config", hooks=[hook])
    assert not r["success"] and r["error"]["code"] == "unauthorized" and m.config["hooks"] == []
    assert "hooks" not in m.state_for(hass_read_only_user)["config"], "non-administrateur : les hooks ne sont pas exposés"
    admin = await hass_ws_client(hass, hass_access_token)
    r = await _ws_call(admin, 1, type="maintenance_mode/update_config", hooks=[hook])
    assert r["success"] and r["result"]["config"]["hooks"][0]["entity_id"] == "script.one"
    r = await _ws_call(admin, 2, type="maintenance_mode/update_config", hooks=[{**hook, "when": "bidon"}])
    assert not r["success"], "moment inconnu refusé par le schéma"
