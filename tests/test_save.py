"""6.2.6 — écritures disque groupées, sans perte (arrêt, rechargement, désinstallation)."""
from datetime import timedelta
from unittest.mock import AsyncMock

from homeassistant.const import EVENT_HOMEASSISTANT_FINAL_WRITE
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.maintenance_mode.const import DOMAIN

from .test_maintenance import _setup


def _disk(hass_storage, entry):
    return hass_storage[f"{DOMAIN}.{entry.entry_id}"]["data"]


async def test_config_changes_are_written_later_in_one_go(hass, hass_storage, freezer):
    entry, m = await _setup(hass)
    m._store.async_save = AsyncMock(wraps=m._store.async_save)
    default_message = _disk(hass_storage, entry)["config"]["message"]

    for i in range(10):                                   # rafale de réglages
        await m.async_update_config({"message": f"Message {i}"})
    assert m._store.async_save.await_count == 0, "aucune écriture immédiate pour de simples réglages"
    assert _disk(hass_storage, entry)["config"]["message"] == default_message, "pas encore sur le disque"

    freezer.tick(timedelta(seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert _disk(hass_storage, entry)["config"]["message"] == "Message 9", "la dernière valeur est écrite d'un coup"


async def test_critical_transitions_are_written_immediately(hass, hass_storage):
    entry, m = await _setup(hass)
    await m.async_start_now(end=None, reason="critique", pages=[], pause=True)
    disk = _disk(hass_storage, entry)
    assert disk["current"]["reason"] == "critique" and len(disk["disabled"]) == 2
    await m.async_stop()
    disk = _disk(hass_storage, entry)
    assert disk["current"] is None and disk["disabled"] == []
    assert disk["history"][-1]["reason"] == "critique"


async def test_scheduled_start_is_written_immediately(hass, hass_storage, freezer):
    entry, m = await _setup(hass)
    now = dt_util.utcnow()
    await m.async_add_window(start=now + timedelta(hours=1), end=now + timedelta(hours=2), reason="auto", pages=[], pause=True)
    freezer.move_to(now + timedelta(hours=1, minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert _disk(hass_storage, entry)["current"]["reason"] == "auto"


async def test_unload_flushes_pending_changes(hass, hass_storage):
    entry, m = await _setup(hass)
    await m.async_update_config({"message": "dernier mot", "warn_minutes": 42})
    assert _disk(hass_storage, entry)["config"]["message"] != "dernier mot"      # toujours en attente
    assert await hass.config_entries.async_reload(entry.entry_id)                 # déchargement immédiat
    await hass.async_block_till_done()
    assert entry.runtime_data.config["message"] == "dernier mot"                  # rien n'est perdu
    assert entry.runtime_data.config["warn_minutes"] == 42


async def test_home_assistant_stop_flushes_pending_changes(hass, hass_storage):
    entry, m = await _setup(hass)
    await m.async_update_config({"message": "avant l'arrêt"})
    assert _disk(hass_storage, entry)["config"]["message"] != "avant l'arrêt"
    hass.bus.async_fire(EVENT_HOMEASSISTANT_FINAL_WRITE)                          # arrêt de HA
    await hass.async_block_till_done()
    assert _disk(hass_storage, entry)["config"]["message"] == "avant l'arrêt"


async def test_immediate_write_supersedes_pending_one(hass, hass_storage, freezer):
    entry, m = await _setup(hass)
    await m.async_update_config({"message": "en attente"})
    await m.async_start_now(end=None, reason="x", pages=[], pause=False)          # écriture immédiate : emporte tout l'état
    assert _disk(hass_storage, entry)["config"]["message"] == "en attente"
    freezer.tick(timedelta(seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert _disk(hass_storage, entry)["current"]["reason"] == "x"                 # l'écriture différée n'écrase pas par du plus ancien
