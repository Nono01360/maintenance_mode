"""9.3 — suspension / réactivation par lots : délais d'attente, reprise partielle, progression visible."""
import asyncio
import math
from unittest.mock import patch

from homeassistant.core import ServiceRegistry
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from custom_components.maintenance_mode import batching
from custom_components.maintenance_mode.const import DOMAIN, SIGNAL_STATE_UPDATED

from .test_maintenance import _setup

N = 200
NAMES = tuple(f"a{i}" for i in range(N))


def _states(hass, wanted):
    return [e for e in (f"automation.{n}" for n in NAMES) if hass.states.get(e).state == wanted]


class Calls:
    """Enregistre les appels `automation.turn_on/turn_off` ; `behave(index, service, ids)` peut les perturber."""

    def __init__(self, behave=None):
        self.log, self.behave, self._real = [], behave, ServiceRegistry.async_call

    def __enter__(self):
        outer = self

        async def call(reg, domain, service, data=None, *a, **kw):
            if domain == "automation" and service in ("turn_on", "turn_off"):
                ids = list(data["entity_id"])
                outer.log.append((service, ids))
                if outer.behave:
                    await outer.behave(len(outer.log), service, ids)
            return await outer._real(reg, domain, service, data, *a, **kw)

        self._p = patch.object(ServiceRegistry, "async_call", call)
        self._p.start()
        return self

    def __exit__(self, *exc):
        self._p.stop()
        return False

    def of(self, service):
        return [ids for s, ids in self.log if s == service]


async def test_200_automations_in_batches_without_blocking_the_loop(hass, hass_admin_user, hass_read_only_user):
    _, m = await _setup(hass, NAMES)
    snapshots, ticks = [], 0

    def on_update():
        nonlocal snapshots
        snapshots.append((m.progress and dict(m.progress), "progress" in m.state_for(hass_admin_user),
                          "progress" in m.state_for(hass_read_only_user)))

    async_dispatcher_connect(hass, SIGNAL_STATE_UPDATED, on_update)

    async def heartbeat():
        nonlocal ticks
        while True:
            ticks += 1
            await asyncio.sleep(0)

    beat = hass.async_create_task(heartbeat())
    with Calls() as calls:
        await m.async_start_now(end=None, reason="gros", pages=[], pause=True)
    beat.cancel()
    batches = math.ceil(N / batching.BATCH_SIZE)
    assert [len(x) for x in calls.of("turn_off")] == [batching.BATCH_SIZE] * batches
    assert len(_states(hass, "off")) == N and len(m.disabled) == N
    assert ticks >= batches, "la boucle d'évènements reprend la main entre les lots"
    done = [s[0]["done"] for s in snapshots if s[0]]
    assert done == [batching.BATCH_SIZE * (i + 1) for i in range(batches)], done
    assert all(s[0]["phase"] == "suspend" and s[0]["total"] == N for s in snapshots if s[0])
    assert all(s[1] for s in snapshots if s[0]), "l'administrateur voit la progression"
    assert not any(s[2] for s in snapshots), "un simple lecteur ne la voit jamais"
    assert m.progress is None and "progress" not in m.state_for(hass_admin_user) or m.state_for(hass_admin_user)["progress"] is None


async def test_small_suspension_has_no_progress(hass):
    _, m = await _setup(hass, ("a1", "a2"))
    seen = []
    async_dispatcher_connect(hass, SIGNAL_STATE_UPDATED, lambda: seen.append(m.progress))
    await m.async_start_now(end=None, reason="", pages=[], pause=True)
    assert all(p is None for p in seen)


async def test_failed_batch_does_not_stop_the_others_then_repair(hass):
    _, m = await _setup(hass, NAMES)

    async def behave(index, service, ids):
        if index == 2:
            raise HomeAssistantError("boom")

    with Calls(behave) as calls:
        await m.async_start_now(end=None, reason="", pages=[], pause=True)
    batches = math.ceil(N / batching.BATCH_SIZE)
    assert len(calls.of("turn_off")) == batches, "les lots suivants sont tentés malgré l'échec du 2e"
    failed = calls.of("turn_off")[1]
    assert set(_states(hass, "on")) == set(failed) and m.current is not None
    assert set(m._reapply_failed) == set(failed)
    issue = ir.async_get(hass).async_get_issue(DOMAIN, "reapply_failed")
    assert issue and issue.is_fixable                                 # reprise partielle : « Réparer » réessaie
    await m.async_repair("reapply_failed")
    assert _states(hass, "on") == [] and ir.async_get(hass).async_get_issue(DOMAIN, "reapply_failed") is None


async def test_batch_timeout_counts_as_failure(hass, monkeypatch):
    monkeypatch.setattr(batching, "BATCH_TIMEOUT", 0.05)
    _, m = await _setup(hass, NAMES)

    async def behave(index, service, ids):
        if index == 1:
            await asyncio.sleep(5)

    with Calls(behave) as calls:
        await m.async_start_now(end=None, reason="", pages=[], pause=True)
    assert len(calls.of("turn_off")) == math.ceil(N / batching.BATCH_SIZE)
    assert set(_states(hass, "on")) == set(calls.of("turn_off")[0])
    assert m.current is not None


async def test_stop_in_batches_and_individual_retry(hass):
    _, m = await _setup(hass, NAMES)
    await m.async_start_now(end=None, reason="", pages=[], pause=True)

    async def behave(index, service, ids):
        if index == 3 and len(ids) > 1:
            raise HomeAssistantError("boom")

    with Calls(behave) as calls:
        await m.async_stop()
    on = calls.of("turn_on")
    assert all(len(x) <= batching.BATCH_SIZE for x in on)
    assert _states(hass, "off") == [] and m.current is None, "le lot en échec est réessayé automatiquement un par un"
    assert sum(1 for x in on if len(x) == 1) == batching.BATCH_SIZE


async def test_reapply_is_batched_too(hass):
    _, m = await _setup(hass, NAMES)
    await m.async_start_now(end=None, reason="", pages=[], pause=True)
    await hass.services.async_call("automation", "turn_on", {"entity_id": [f"automation.{n}" for n in NAMES]}, blocking=True)
    with Calls() as calls:
        async with m._lock:
            await m._reapply_suspension()
    assert [len(x) for x in calls.of("turn_off")] == [batching.BATCH_SIZE] * math.ceil(N / batching.BATCH_SIZE)
    assert _states(hass, "on") == []
