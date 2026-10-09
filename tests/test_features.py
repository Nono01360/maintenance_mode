"""Tests des améliorations : répétition, notifications, évènements, services,
calendrier, historique, modèles, réparations, diagnostics, middleware API."""
from datetime import timedelta
from pathlib import Path

import pytest
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_capture_events,
    async_fire_time_changed,
    async_mock_service,
)
from homeassistant.setup import async_setup_component

from custom_components.maintenance_mode.const import DOMAIN

from .test_maintenance import _setup, _state


# ------------------------------------------------------------------ répétition
async def test_weekly_repeat_creates_next_occurrence(hass, freezer):
    _, m = await _setup(hass)
    now = dt_util.utcnow()
    await m.async_add_window(start=now + timedelta(hours=1), end=now + timedelta(hours=2),
                             reason="hebdo", pages=[], pause=True, repeat="weekly")
    freezer.move_to(now + timedelta(hours=1, minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert m.current and m.current.reason == "hebdo"
    assert len(m.schedule) == 1
    nxt = m.schedule[0]
    assert abs((nxt.start - (now + timedelta(hours=1) + timedelta(days=7))).total_seconds()) < 3700  # DST toléré
    assert nxt.repeat == "weekly" and nxt.id != m.current.id
    # fin : la série continue
    freezer.move_to(now + timedelta(hours=2, minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert m.current is None and len(m.schedule) == 1
    # supprimer l'occurrence suivante arrête la série
    await m.async_delete_window(m.schedule[0].id)
    assert m.schedule == []


async def test_repeat_validation(hass):
    _, m = await _setup(hass)
    now = dt_util.utcnow()
    with pytest.raises(ServiceValidationError):  # pas de fin
        await m.async_add_window(start=now + timedelta(hours=1), end=None, reason="", pages=[], pause=True, repeat="daily")
    with pytest.raises(ServiceValidationError):  # durée > période
        await m.async_add_window(start=now + timedelta(hours=1), end=now + timedelta(days=2), reason="", pages=[], pause=True, repeat="daily")


async def test_missed_repeating_window_skips_to_future(hass):
    _, m = await _setup(hass)
    from custom_components.maintenance_mode.manager import Window
    now = dt_util.utcnow()
    m.schedule = [Window("old", now - timedelta(days=20), now - timedelta(days=20) + timedelta(hours=1), "vieux", repeat="weekly")]
    await m._async_resume()
    assert m.current is None  # entièrement passée
    assert len(m.schedule) == 1 and m.schedule[0].start > now


# ------------------------------------------------------------------ évènements + historique
async def test_events_and_history(hass):
    _, m = await _setup(hass)
    started = async_capture_events(hass, "maintenance_mode_started")
    ended = async_capture_events(hass, "maintenance_mode_ended")
    await m.async_start_now(end=None, reason="evt", pages=["map"], pause=False, by="Nolann")
    await m.async_stop()
    await hass.async_block_till_done()
    assert len(started) == 1 and started[0].data["reason"] == "evt" and started[0].data["pages"] == ["map"]
    assert len(ended) == 1 and ended[0].data["ended_by"] == "manual"
    assert m.history[-1]["started_by"] == "Nolann" and m.history[-1]["ended_by"] == "manual"
    # remplacement
    await m.async_start_now(end=None, reason="a", pages=[], pause=False)
    await m.async_start_now(end=None, reason="b", pages=[], pause=False)
    assert m.history[-1]["ended_by"] == "replaced" and m.current.reason == "b"


# ------------------------------------------------------------------ notifications
async def test_notifications(hass, freezer):
    hass.config.language = "fr"
    calls = async_mock_service(hass, "notify", "test_phone")
    _, m = await _setup(hass)
    await m.async_update_config({"notify_services": ["test_phone", "send_message", "Bad Name"]})
    assert m.config["notify_services"] == ["test_phone"]
    now = dt_util.utcnow()

    # « avant le début » : fenêtre dans 10 min, préavis 15 min -> immédiat, et une seule fois
    await m.async_add_window(start=now + timedelta(minutes=10), end=now + timedelta(minutes=40), reason="MAJ", pages=[], pause=False)
    await hass.async_block_till_done()
    assert [c.data["title"] for c in calls] == ["Maintenance prévue"]
    assert "MAJ" in calls[0].data["message"]
    await m.async_update_config({"message": "x"})
    assert len(calls) == 1  # dédoublonné

    # démarrage
    freezer.move_to(now + timedelta(minutes=11))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert calls[-1].data["title"] == "Maintenance en cours"

    # rappel avant la fin (10 min par défaut) : fin dans 29 min -> au bout de 19 min
    freezer.move_to(now + timedelta(minutes=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert calls[-1].data["title"] == "La maintenance se termine bientôt"

    # fin
    freezer.move_to(now + timedelta(minutes=41))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert calls[-1].data["title"] == "Maintenance terminée"
    assert [c.data["title"] for c in calls].count("Maintenance prévue") == 1


async def test_notify_kinds_filter(hass):
    hass.config.language = "fr"
    calls = async_mock_service(hass, "notify", "test_phone")
    _, m = await _setup(hass)
    await m.async_update_config({"notify_services": ["test_phone"], "notify_kinds": ["ended"]})
    await m.async_start_now(end=None, reason="", pages=[], pause=False)
    assert calls == []
    await m.async_stop()
    await hass.async_block_till_done()
    assert [c.data["title"] for c in calls] == ["Maintenance terminée"]


# ------------------------------------------------------------------ services
async def test_services(hass):
    _, m = await _setup(hass)
    await hass.services.async_call(DOMAIN, "start", {"duration": "01:00:00", "reason": "svc", "pause_automations": False}, blocking=True)
    assert m.current.reason == "svc" and m.current.started_by == "service"
    assert abs((m.current.end - m.current.start).total_seconds() - 3600) < 5
    await hass.services.async_call(DOMAIN, "stop", {}, blocking=True)
    assert m.current is None

    start = (dt_util.utcnow() + timedelta(days=1)).isoformat()
    await hass.services.async_call(DOMAIN, "schedule", {"start": start, "duration": "02:00:00", "repeat": "weekly", "pages": ["map"]}, blocking=True)
    w = m.schedule[0]
    assert w.repeat == "weekly" and w.pages == ["map"] and (w.end - w.start) == timedelta(hours=2)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "start", {"duration": "01:00:00", "end": start}, blocking=True)
    await hass.services.async_call(DOMAIN, "cancel_schedule", {"window_id": w.id}, blocking=True)
    assert m.schedule == []


# ------------------------------------------------------------------ calendrier
async def test_calendar(hass):
    _, m = await _setup(hass)
    now = dt_util.utcnow()
    await m.async_add_window(start=now + timedelta(hours=1), end=now + timedelta(hours=2), reason="cal", pages=[], pause=False, repeat="weekly")
    state = hass.states.get("calendar.mode_maintenance_planning")
    assert state is not None and state.state == "off"
    assert state.attributes["message"] == "Maintenance — cal"
    entity = hass.data["calendar"].get_entity("calendar.mode_maintenance_planning")
    events = await entity.async_get_events(hass, now, now + timedelta(days=30))
    assert len(events) == 5  # série hebdomadaire sur 30 jours
    assert all(e.summary == "Maintenance — cal" for e in events)


# ------------------------------------------------------------------ modèles / réparations / diagnostics
async def test_templates(hass):
    _, m = await _setup(hass)
    await m.async_update_config({"templates": [
        {"name": "Mise à jour", "reason": "MAJ", "pages": ["config/devices", "/map/"], "duration": 90, "repeat": "none"},
        {"name": "   "},  # ignoré
    ]})
    t = m.config["templates"]
    assert len(t) == 1 and t[0]["name"] == "Mise à jour" and t[0]["pages"] == ["config/devices", "map"]
    assert t[0]["duration"] == 90 and t[0]["id"]


async def test_repair_issue_for_missing_automation(hass):
    _, m = await _setup(hass)
    registry = ir.async_get(hass)
    await m.async_update_config({"automations": ["automation.n_existe_pas", "automation.a1"]})
    issue = registry.async_get_issue(DOMAIN, "missing_automations")
    assert issue and "n_existe_pas" in issue.translation_placeholders["entities"]
    await m.async_update_config({"automations": ["automation.a1"]})
    assert registry.async_get_issue(DOMAIN, "missing_automations") is None


async def test_diagnostics_redacted(hass, hass_admin_user):
    entry, m = await _setup(hass)
    await m.async_update_config({"allowed_users": [hass_admin_user.id], "notify_services": ["x"]})
    from custom_components.maintenance_mode.diagnostics import async_get_config_entry_diagnostics
    diag = await async_get_config_entry_diagnostics(hass, entry)
    assert diag["config"]["allowed_users"] == "**REDACTED**"
    assert diag["config"]["notify_services"] == "**REDACTED**"
    assert hass_admin_user.id not in str(diag)


def test_brand_icons_present():
    base = Path(__file__).parent.parent / "custom_components" / "maintenance_mode" / "brand"
    assert (base / "icon.png").exists() and (base / "icon@2x.png").exists()
