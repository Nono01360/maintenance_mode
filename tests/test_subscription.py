"""6.2.5 — l'abonnement du panneau survit au rechargement de l'intégration."""
import asyncio

from .test_maintenance import _setup


async def _recv(client, timeout=3):
    return await asyncio.wait_for(client.receive_json(), timeout)


async def _subscribe(client, mid=1):
    await client.send_json({"id": mid, "type": "maintenance_mode/subscribe"})
    while True:
        msg = await _recv(client)
        if msg.get("type") == "result" and msg.get("id") == mid:
            return


async def _events_until(client, predicate, attempts=15):
    """Lit les évènements poussés jusqu'à ce que `predicate(event)` soit vrai (sinon TimeoutError)."""
    for _ in range(attempts):
        msg = await _recv(client)
        if msg.get("type") == "event" and predicate(msg["event"]):
            return msg["event"]
    raise AssertionError("évènement attendu jamais reçu")


async def test_subscription_survives_reload(hass, hass_ws_client, hass_access_token):
    entry, m1 = await _setup(hass)
    client = await hass_ws_client(hass, hass_access_token)
    await _subscribe(client)

    # rechargement de l'intégration : un NOUVEAU gestionnaire remplace l'ancien
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    m2 = entry.runtime_data
    assert m2 is not m1

    # le panneau (qui n'a rien refait) reçoit les changements du nouveau gestionnaire
    await m2.async_start_now(end=None, reason="après rechargement", pages=[], pause=False)
    event = await _events_until(client, lambda e: bool(e.get("current")))
    assert event["current"]["reason"] == "après rechargement"


async def test_unload_does_not_crash_open_panels(hass, hass_ws_client, hass_access_token):
    entry, m = await _setup(hass)
    client = await hass_ws_client(hass, hass_access_token)
    await _subscribe(client)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    await client.send_json({"id": 2, "type": "maintenance_mode/get_state"})
    res = await _recv(client)
    assert not res["success"] and res["error"]["code"] == "not_loaded"


async def test_unsubscribe_cleans_up(hass, hass_ws_client, hass_access_token):
    entry, m = await _setup(hass)
    client = await hass_ws_client(hass, hass_access_token)
    await _subscribe(client)
    await client.send_json({"id": 2, "type": "unsubscribe_events", "subscription": 1})
    res = await _recv(client)
    assert res["success"]
    # après désabonnement, un changement n'envoie rien et ne lève rien
    await m.async_start_now(end=None, reason="x", pages=[], pause=False)
    await hass.async_block_till_done()
    try:
        await asyncio.wait_for(client.receive_json(), 0.5)
        raise AssertionError("aucun message ne devait arriver après le désabonnement")
    except asyncio.TimeoutError:
        pass
