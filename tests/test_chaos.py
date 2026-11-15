"""9.1 — bascule transactionnelle : arrêt brutal simulé à CHAQUE étape d'une bascule, puis redémarrage.

On compte les « points d'entrée/sortie » d'une bascule (appels à `automation.turn_on/turn_off` et écritures du
stockage). Pour chaque point k, on fait planter la bascule juste AVANT lui (exception `Crash`, qui n'est pas une
`Exception` : aucun `except Exception` du code ne peut l'avaler, comme un vrai arrêt), puis on recrée un gestionnaire
à partir de ce qui est réellement « sur le disque » et on vérifie l'état.
"""
from unittest.mock import patch

import pytest
from homeassistant.core import ServiceRegistry

from custom_components.maintenance_mode.const import DOMAIN
from custom_components.maintenance_mode.manager import MaintenanceManager

from .test_maintenance import _setup

AUTOS = ("automation.a1", "automation.a2")


class Crash(BaseException):
    """Arrêt brutal simulé."""


class Injector:
    def __init__(self, hass, manager, crash_at):
        self.n, self.crash_at, self.fired = 0, crash_at, False
        real_call = ServiceRegistry.async_call
        real_save = manager._store.async_save

        async def call(reg, domain, service, *args, **kwargs):
            if domain == "automation" and service in ("turn_on", "turn_off"):
                self.tick()
            return await real_call(reg, domain, service, *args, **kwargs)

        async def save(data, *args, **kwargs):
            self.tick()
            return await real_save(data, *args, **kwargs)

        self._patch = patch.object(ServiceRegistry, "async_call", call)
        manager._store.async_save = save

    def tick(self):
        self.n += 1
        if self.n == self.crash_at:
            self.fired = True
            raise Crash

    def __enter__(self):
        self._patch.start()
        return self

    def __exit__(self, *exc):
        self._patch.stop()
        return False


def _off(hass):
    return {e for e in AUTOS if hass.states.get(e).state == "off"}


async def _restart(hass, entry, old):
    """Redémarrage : plus rien de l'ancien gestionnaire (pas d'écriture de sortie), un nouveau lit le disque."""
    old.async_unload()
    new = MaintenanceManager(hass, entry)
    await new.async_load()
    entry.runtime_data = new
    await hass.async_block_till_done()
    await new._async_resume()            # une seconde reprise ne doit rien changer (idempotence)
    await hass.async_block_till_done()
    return new


def _assert_consistent(hass, m):
    assert m.pending is None, "plus de bascule en cours après la reprise"
    if m.current is None:
        assert not _off(hass), "aucune maintenance : rien ne doit rester suspendu"
        assert m.disabled == []
    else:
        assert _off(hass) == set(m.disabled) == set(AUTOS), "maintenance : exactement ses automatisations sont suspendues"


@pytest.mark.parametrize("crash_at", range(1, 6))
async def test_crash_during_start(hass, hass_storage, crash_at):
    entry, m = await _setup(hass)
    with Injector(hass, m, crash_at) as inj:
        try:
            await m.async_start_now(end=None, reason="chaos", pages=[], pause=True)
        except Crash:
            pass
    m2 = await _restart(hass, entry, m)
    _assert_consistent(hass, m2)
    if not inj.fired:
        assert m2.current and m2.current.reason == "chaos"


@pytest.mark.parametrize("crash_at", range(1, 6))
async def test_crash_during_stop(hass, hass_storage, crash_at):
    entry, m = await _setup(hass)
    await m.async_start_now(end=None, reason="chaos", pages=[], pause=True)
    with Injector(hass, m, crash_at) as inj:
        try:
            await m.async_stop()
        except Crash:
            pass
    m2 = await _restart(hass, entry, m)
    _assert_consistent(hass, m2)
    if not inj.fired or inj.crash_at > 1:       # le marqueur est écrit (point 1) : la fin est menée à terme
        assert m2.current is None and m2.history[-1]["reason"] == "chaos"
        assert all(hass.states.get(e).state == "on" for e in AUTOS)


@pytest.mark.parametrize("crash_at", range(1, 8))
async def test_crash_during_replacement(hass, hass_storage, crash_at):
    entry, m = await _setup(hass)
    await m.async_start_now(end=None, reason="première", pages=[], pause=True)
    with Injector(hass, m, crash_at) as inj:
        try:
            await m.async_start_now(end=None, reason="seconde", pages=[], pause=True)
        except Crash:
            pass
    m2 = await _restart(hass, entry, m)
    _assert_consistent(hass, m2)
    if not inj.fired:
        assert m2.current.reason == "seconde" and [h["ended_by"] for h in m2.history] == ["replaced"]


async def test_marker_is_written_before_and_cleared_after(hass, hass_storage):
    entry, m = await _setup(hass)
    key = f"{DOMAIN}.{entry.entry_id}"
    seen = []
    real_save = m._store.async_save

    async def spy(data, *a, **kw):
        seen.append((data["pending"] or {}).get("op"))
        return await real_save(data, *a, **kw)

    m._store.async_save = spy
    await m.async_start_now(end=None, reason="x", pages=[], pause=True)
    assert seen == ["activate", None], "marqueur écrit d'abord, effacé par l'enregistrement final"
    assert hass_storage[key]["data"]["pending"] is None
    seen.clear()
    await m.async_stop()
    assert seen == ["deactivate", None]


async def test_no_extra_write_when_nothing_is_suspended(hass, hass_storage):
    """Sans automatisation à suspendre, aucun marqueur : pas d'écriture supplémentaire."""
    entry, m = await _setup(hass)
    seen = []
    real_save = m._store.async_save

    async def spy(data, *a, **kw):
        seen.append(data["pending"])
        return await real_save(data, *a, **kw)

    m._store.async_save = spy
    await m.async_start_now(end=None, reason="x", pages=["map"], pause=False)
    await m.async_stop()
    assert seen == [None, None]


async def test_unreadable_marker_goes_to_safe_mode(hass, hass_storage):
    from custom_components.maintenance_mode.storage import check_data

    data, problems = check_data({"pending": {"op": "bidon"}, "disabled": ["automation.a1"]})
    assert "pending" in problems and "pending" not in data and data["disabled"] == ["automation.a1"]
    data, problems = check_data({"pending": {"op": "activate"}})
    assert problems == [] and data["pending"] == {"op": "activate"}
    data, problems = check_data({"pending": "oops"})
    assert problems == ["pending"]
