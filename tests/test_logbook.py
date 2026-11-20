"""9.6 — « Maintenance démarrée / terminée » dans le Journal de Home Assistant, avec auteur et motif."""
import pytest
from pytest_homeassistant_custom_component.common import async_capture_events

from custom_components.maintenance_mode.const import EVENT_ENDED, EVENT_STARTED
from custom_components.maintenance_mode.logbook import async_describe_events

from .test_maintenance import _setup


def _describers(hass):
    found = {}
    async_describe_events(hass, lambda domain, event, fn: found.__setitem__(event, (domain, fn)))
    return found


async def test_both_events_are_described(hass):
    found = _describers(hass)
    assert set(found) == {EVENT_STARTED, EVENT_ENDED} and all(d == "maintenance_mode" for d, _ in found.values())


@pytest.mark.parametrize("lang,start_txt,end_txt,by_txt,reason_txt", [
    ("fr", "Maintenance démarrée", "Maintenance terminée (arrêtée à la main)", "par Nolann", "Motif : Refonte"),
    ("en", "Maintenance started", "Maintenance ended (stopped manually)", "by Nolann", "Reason: Refonte"),
])
async def test_message_author_reason_and_entity(hass, lang, start_txt, end_txt, by_txt, reason_txt):
    hass.config.language = lang
    _, m = await _setup(hass)
    found = _describers(hass)
    started = async_capture_events(hass, EVENT_STARTED)
    ended = async_capture_events(hass, EVENT_ENDED)
    await m.async_start_now(end=None, reason="Refonte", pages=[], pause=False, by="Nolann")
    await m.async_stop()
    await hass.async_block_till_done()
    s = found[EVENT_STARTED][1](started[0])
    assert s["name"] == "Mode maintenance" and s["entity_id"] == "switch.mode_maintenance"
    assert start_txt in s["message"] and by_txt in s["message"] and reason_txt in s["message"]
    e = found[EVENT_ENDED][1](ended[0])
    assert end_txt in e["message"] and reason_txt in e["message"] and e["entity_id"] == "switch.mode_maintenance"


async def test_known_authors_and_end_causes_are_translated(hass):
    hass.config.language = "fr"
    _, m = await _setup(hass)
    fn = _describers(hass)[EVENT_ENDED][1]
    from homeassistant.core import Event

    def msg(**data):
        return fn(Event(EVENT_ENDED, data))["message"]

    assert "terminée automatiquement" in msg(ended_by="auto")
    assert "remplacée par une autre" in msg(ended_by="replaced")
    assert "durée maximale atteinte" in msg(ended_by="max_duration")
    assert "par la planification" in msg(ended_by="auto", started_by="planification")
    assert "par l'interrupteur" in msg(ended_by="auto", started_by="interrupteur")
    assert "par un service" in msg(ended_by="auto", started_by="service")
    assert "par" not in msg(ended_by="auto", started_by="") and "Motif" not in msg(ended_by="auto")
    assert msg(ended_by="inconnue")           # une cause inconnue ne fait jamais planter le Journal
    assert fn(Event(EVENT_ENDED, {}))["message"]
