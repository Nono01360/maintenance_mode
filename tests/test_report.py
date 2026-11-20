"""9.5 — bilan de fin : durée réelle, entités devenues indisponibles, erreurs du journal (limitées)."""
import logging
from datetime import timedelta


from custom_components.maintenance_mode.report import MAX_REPORT_ERRORS, MAX_REPORT_ENTITIES

from .test_maintenance import _setup

LOG = logging.getLogger("homeassistant.components.demo_report")


def _handlers():
    return [h for h in logging.getLogger().handlers if type(h).__name__ == "ErrorCollector"]


async def test_report_duration_unavailable_and_errors(hass, freezer):
    _, m = await _setup(hass)
    hass.states.async_set("sensor.deja_hs", "unavailable")
    hass.states.async_set("sensor.tombe", "21")
    hass.states.async_set("sensor.stable", "1")
    await m.async_start_now(end=None, reason="bilan", pages=[], pause=False)
    assert len(_handlers()) == 1
    hass.states.async_set("sensor.tombe", "unavailable")
    LOG.error("boom %s", 1); LOG.error("boom %s", 1); LOG.warning("ignoré")
    logging.getLogger("custom_components.maintenance_mode.x").error("nos propres erreurs sont ignorées")
    freezer.tick(timedelta(minutes=90))
    await m.async_stop()
    r = m.history[-1]["report"]
    assert r["duration"] == 5400
    assert r["unavailable"] == ["sensor.tombe"] and r["unavailable_total"] == 1
    assert r["errors"] == [{"logger": "homeassistant.components.demo_report", "message": "boom 1", "count": 2}]
    assert r["errors_total"] == 2
    assert _handlers() == [], "le collecteur est retiré à la fin"
    LOG.error("après la fin")
    assert m.report == {}, "plus rien n'est collecté hors maintenance"


async def test_report_is_bounded(hass):
    _, m = await _setup(hass)
    for i in range(MAX_REPORT_ENTITIES + 15):
        hass.states.async_set(f"sensor.s{i:03d}", "1")
    await m.async_start_now(end=None, reason="", pages=[], pause=False)
    for i in range(MAX_REPORT_ENTITIES + 15):
        hass.states.async_set(f"sensor.s{i:03d}", "unavailable")
    for i in range(MAX_REPORT_ERRORS + 7):
        LOG.error("erreur distincte %d " + "x" * 400, i)
    await m.async_stop()
    r = m.history[-1]["report"]
    assert len(r["unavailable"]) == MAX_REPORT_ENTITIES and r["unavailable_total"] == MAX_REPORT_ENTITIES + 15
    assert len(r["errors"]) == MAX_REPORT_ERRORS and r["errors_total"] == MAX_REPORT_ERRORS + 7
    assert all(len(e["message"]) <= 200 for e in r["errors"])


async def test_report_survives_reload_and_replacement(hass):
    entry, m = await _setup(hass)
    hass.states.async_set("sensor.x", "1")
    await m.async_start_now(end=None, reason="a", pages=[], pause=False)
    hass.states.async_set("sensor.x", "unavailable")
    LOG.error("avant rechargement")
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    m2 = entry.runtime_data
    assert len(_handlers()) == 1, "collecteur de nouveau en place après le rechargement (un seul)"
    LOG.error("après rechargement")
    await m2.async_start_now(end=None, reason="b", pages=[], pause=False)      # remplacement : la 1re est close
    r = m2.history[-1]["report"]
    assert r["unavailable"] == ["sensor.x"] and r["errors_total"] == 2
    assert m2.history[-1]["ended_by"] == "replaced" and len(_handlers()) == 1
    await m2.async_stop()
    assert m2.history[-1]["report"]["errors_total"] == 0 and _handlers() == []


async def test_unload_removes_collector(hass):
    entry, m = await _setup(hass)
    await m.async_start_now(end=None, reason="", pages=[], pause=False)
    assert len(_handlers()) == 1
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert _handlers() == []
