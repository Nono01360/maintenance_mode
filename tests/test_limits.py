"""0.7.14 — tailles maximales des saisies et limitation douce des modifications."""
from datetime import timedelta

import pytest
import voluptuous as vol

from custom_components.maintenance_mode.const import CONFIG_WRITES_PER_MINUTE, DOMAIN
from custom_components.maintenance_mode.limits import RateLimiter

from .test_maintenance import _setup
from .test_roles import _ws_call


def test_rate_limiter_sliding_window(freezer):
    limiter = RateLimiter(3, 10)
    assert [limiter.allow() for _ in range(4)] == [True, True, True, False]
    freezer.tick(timedelta(seconds=9))
    assert limiter.allow() is False
    freezer.tick(timedelta(seconds=2))
    assert limiter.allow() is True


async def _admin(hass, hass_ws_client, hass_access_token):
    _, m = await _setup(hass)
    return m, await hass_ws_client(hass, hass_access_token)


async def test_oversized_inputs_are_refused_by_the_schema(hass, hass_ws_client, hass_access_token):
    m, c = await _admin(hass, hass_ws_client, hass_access_token)
    cases = [
        dict(type="maintenance_mode/start", reason="x" * 1001),
        dict(type="maintenance_mode/start", pages=[f"p{i}" for i in range(101)]),
        dict(type="maintenance_mode/start", pages=["p" * 201]),
        dict(type="maintenance_mode/delete_window", window_id="i" * 65),
        dict(type="maintenance_mode/delete_history", history_id="i" * 65),
        dict(type="maintenance_mode/update_config", message="m" * 1001),
        dict(type="maintenance_mode/update_config", automations=["automation." + "a" * 300]),
        dict(type="maintenance_mode/update_config", automations=["automation.a"] * 2001),
        dict(type="maintenance_mode/update_config", allowed_users=["u" * 65]),
        dict(type="maintenance_mode/update_config", notify_services=["s"] * 101),
        dict(type="maintenance_mode/update_config", templates=[{"name": "n"}] * 101),
        dict(type="maintenance_mode/update_config", roles=[{"name": "r" * 1001}]),
        dict(type="maintenance_mode/update_config", panel_access={"u" * 65: "admin"}),
    ]
    for i, payload in enumerate(cases, 1):
        r = await _ws_call(c, i, **payload)
        assert not r["success"] and r["error"]["code"] == "invalid_format", payload["type"] + str(list(payload)[1:])
    assert m.current is None and m.config["message"] != "m" * 1001


async def test_reasonable_inputs_still_accepted_and_trimmed_by_the_manager(hass, hass_ws_client, hass_access_token):
    m, c = await _admin(hass, hass_ws_client, hass_access_token)
    r = await _ws_call(c, 1, type="maintenance_mode/update_config", message="m" * 900)
    assert r["success"] and len(m.config["message"]) == 255          # le gestionnaire borne à 255, le schéma n'en refuse pas 900
    r = await _ws_call(c, 2, type="maintenance_mode/start", reason="r" * 201)
    assert not r["success"] and r["error"]["translation_key"] == "reason_too_long"   # message clair du gestionnaire


async def test_service_schemas_are_bounded(hass):
    await _setup(hass)
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(DOMAIN, "start", {"reason": "x" * 1001}, blocking=True)
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(DOMAIN, "cancel_schedule", {"window_id": "i" * 65}, blocking=True)


async def test_config_writes_are_softly_limited(hass, hass_ws_client, hass_access_token, freezer):
    m, c = await _admin(hass, hass_ws_client, hass_access_token)
    for i in range(CONFIG_WRITES_PER_MINUTE):
        r = await _ws_call(c, i + 1, type="maintenance_mode/update_config", message=f"m{i}")
        assert r["success"], i
    r = await _ws_call(c, 999, type="maintenance_mode/update_config", message="de trop")
    assert not r["success"] and r["error"]["translation_key"] == "rate_limited"
    assert m.config["message"] == f"m{CONFIG_WRITES_PER_MINUTE - 1}"
    # les autres commandes ne sont pas concernées
    r = await _ws_call(c, 1000, type="maintenance_mode/get_state")
    assert r["success"]
    freezer.tick(timedelta(seconds=61))
    r = await _ws_call(c, 1001, type="maintenance_mode/update_config", message="de nouveau")
    assert r["success"] and m.config["message"] == "de nouveau"
