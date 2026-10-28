"""0.7.0 — tests de caractérisation du gestionnaire.

Ils figent le comportement ACTUEL de `manager.py` avant son découpage (0.7.1 et suivantes) : ils décrivent
ce que fait le code, pas ce qu'il « devrait » faire. Si un de ces tests échoue après un découpage, c'est
que le comportement a changé : il faut corriger le découpage, pas le test.
"""
from datetime import timedelta

import pytest
from homeassistant.exceptions import ServiceValidationError
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_capture_events,
    async_fire_time_changed,
)

from custom_components.maintenance_mode.const import (
    DOMAIN,
    MAX_HISTORY,
    MAX_PAGES,
    MAX_REASON,
    MAX_ROLES,
    MAX_TEMPLATES,
    MAX_WINDOWS,
)
from custom_components.maintenance_mode.manager import MaintenanceManager, Window

from .test_maintenance import _setup, _state


def _key(entry):
    return f"{DOMAIN}.{entry.entry_id}"


# ------------------------------------------------------------------ saisies : nettoyage et bornes
async def test_pages_are_normalised_and_bounded(hass):
    _, m = await _setup(hass)
    await m.async_start_now(end=None, reason="", pages=[" /map/ ", "map", "", "config/devices"], pause=False)
    assert m.current.pages == ["map", "config/devices"]          # espaces et « / » retirés, doublons et vides ignorés
    with pytest.raises(ServiceValidationError):
        await m.async_start_now(end=None, reason="", pages=[f"p{i}" for i in range(MAX_PAGES + 1)], pause=False)


async def test_reason_is_trimmed_and_bounded(hass):
    _, m = await _setup(hass)
    await m.async_start_now(end=None, reason="  motif  ", pages=[], pause=False)
    assert m.current.reason == "motif"
    with pytest.raises(ServiceValidationError):
        await m.async_start_now(end=None, reason="x" * (MAX_REASON + 1), pages=[], pause=False)
    assert m.current.reason == "motif"                           # l'échec ne change rien


async def test_end_must_be_in_the_future(hass):
    _, m = await _setup(hass)
    with pytest.raises(ServiceValidationError):
        await m.async_start_now(end=dt_util.utcnow() - timedelta(minutes=1), reason="", pages=[], pause=False)
    assert m.current is None


async def test_schedule_is_capped(hass):
    _, m = await _setup(hass)
    base = dt_util.utcnow() + timedelta(days=1)
    for i in range(MAX_WINDOWS):
        await m.async_add_window(start=base + timedelta(hours=2 * i), end=base + timedelta(hours=2 * i + 1),
                                 reason="", pages=[], pause=False)
    with pytest.raises(ServiceValidationError):
        await m.async_add_window(start=base + timedelta(days=30), end=None, reason="", pages=[], pause=False)
    assert len(m.schedule) == MAX_WINDOWS


async def test_window_cannot_overlap_the_current_maintenance(hass):
    _, m = await _setup(hass)
    now = dt_util.utcnow()
    await m.async_start_now(end=now + timedelta(hours=2), reason="", pages=[], pause=False)
    with pytest.raises(ServiceValidationError):
        await m.async_add_window(start=now + timedelta(hours=1), end=now + timedelta(hours=3), reason="", pages=[], pause=False)
    await m.async_add_window(start=now + timedelta(hours=3), end=now + timedelta(hours=4), reason="", pages=[], pause=False)
    with pytest.raises(ServiceValidationError):                   # prolonger la maintenance en cours jusqu'à la suivante
        await m.async_update_current(end=now + timedelta(hours=3, minutes=30), reason="", pages=[])


async def test_update_current_requires_a_running_maintenance(hass):
    _, m = await _setup(hass)
    with pytest.raises(ServiceValidationError):
        await m.async_update_current(end=None, reason="x", pages=[])


async def test_update_window_unknown_id(hass):
    _, m = await _setup(hass)
    now = dt_util.utcnow()
    with pytest.raises(ServiceValidationError):
        await m.async_update_window("inconnu", start=now + timedelta(hours=1), end=None, reason="", pages=[], pause=False)
    with pytest.raises(ServiceValidationError):
        await m.async_delete_window("inconnu")


async def test_update_window_keeps_its_own_slot_but_not_others(hass):
    _, m = await _setup(hass)
    now = dt_util.utcnow()
    a = await m.async_add_window(start=now + timedelta(hours=1), end=now + timedelta(hours=2), reason="a", pages=[], pause=False)
    await m.async_add_window(start=now + timedelta(hours=5), end=now + timedelta(hours=6), reason="b", pages=[], pause=False)
    await m.async_update_window(a.id, start=now + timedelta(hours=1, minutes=30), end=now + timedelta(hours=2, minutes=30),
                                reason="a2", pages=["map"], pause=True)     # recouvre son ancien créneau : permis
    assert [w.reason for w in m.schedule] == ["a2", "b"] and m.schedule[0].pages == ["map"]
    with pytest.raises(ServiceValidationError):
        await m.async_update_window(a.id, start=now + timedelta(hours=5, minutes=30), end=None, reason="", pages=[], pause=False)


async def test_repeat_needs_an_end_and_a_short_enough_duration(hass):
    _, m = await _setup(hass)
    now = dt_util.utcnow()
    with pytest.raises(ServiceValidationError):
        await m.async_add_window(start=now + timedelta(hours=1), end=None, reason="", pages=[], pause=False, repeat="weekly")
    with pytest.raises(ServiceValidationError):
        await m.async_add_window(start=now + timedelta(hours=1), end=now + timedelta(days=8), reason="", pages=[], pause=False, repeat="weekly")
    with pytest.raises(ServiceValidationError):
        await m.async_add_window(start=now + timedelta(hours=1), end=now + timedelta(hours=2), reason="", pages=[], pause=False, repeat="yearly")


# ------------------------------------------------------------------ réglages
async def test_settings_are_clamped_and_cleaned(hass, hass_admin_user):
    _, m = await _setup(hass)
    await m.async_update_config({
        "warn_minutes": 99999, "end_soon_minutes": 0, "message": "  " + "x" * 400,
        "automations": ["automation.a1", "light.salon", 3, "automation.a1"],
        "allowed_users": [hass_admin_user.id, "inconnu", hass_admin_user.id],
        "notify_kinds": ["ended", "bidon", "pre"],
        "banner_mode": "card", "banner_scroll": 0,
    })
    c = m.config
    assert c["warn_minutes"] == 1440 and c["end_soon_minutes"] == 1
    assert len(c["message"]) == 255
    assert c["automations"] == ["automation.a1"]                  # triées, dédoublonnées, seules les automatisations
    assert c["allowed_users"] == [hass_admin_user.id]
    assert c["notify_kinds"] == ["pre", "ended"]                  # ordre canonique, valeurs inconnues retirées
    assert c["banner_mode"] == "card" and c["banner_scroll"] is False


async def test_empty_message_falls_back_to_default(hass):
    from custom_components.maintenance_mode.const import DEFAULT_MESSAGE
    _, m = await _setup(hass)
    await m.async_update_config({"message": "   "})
    assert m.config["message"] == DEFAULT_MESSAGE


async def test_notify_services_are_capped_and_filtered(hass):
    _, m = await _setup(hass)
    await m.async_update_config({"notify_services": [f"svc_{i}" for i in range(30)] + ["Mauvais Nom"]})
    assert len(m.config["notify_services"]) == 20 and "Mauvais Nom" not in m.config["notify_services"]


async def test_templates_are_cleaned_and_bounded(hass):
    _, m = await _setup(hass)
    await m.async_update_config({"templates": [{"name": f"T{i}"} for i in range(MAX_TEMPLATES + 5)]})
    assert len(m.config["templates"]) == MAX_TEMPLATES
    await m.async_update_config({"templates": [
        {"name": "N" * 80, "reason": "r", "duration": "45", "repeat": "bidon", "pause_automations": 0},
    ]})
    t = m.config["templates"][0]
    assert len(t["name"]) == 40 and t["duration"] == 45 and t["repeat"] == "none" and t["pause_automations"] is False


async def test_roles_are_capped(hass):
    _, m = await _setup(hass)
    await m.async_update_config({"roles": [{"name": f"R{i}", "permissions": ["control"]} for i in range(MAX_ROLES + 3)]})
    assert len(m.config["roles"]) == MAX_ROLES


# ------------------------------------------------------------------ droits : vue d'état et anti-escalade
async def test_owner_and_admin_views(hass, hass_owner_user, hass_admin_user, hass_read_only_user):
    _, m = await _setup(hass)
    assert m.role_for(hass_owner_user) == "admin"
    await m.async_update_config({"panel_access": {hass_owner_user.id: "none"}})
    assert m.role_for(hass_owner_user) == "admin"                 # le propriétaire ne peut pas être rétrogradé
    assert m.role_for(hass_admin_user) == "admin" and m.role_for(hass_read_only_user) == "viewer"
    assert m.state_for(hass_read_only_user).keys() >= {"role", "permissions", "active", "current", "upcoming", "message"}


async def test_no_view_state_is_minimal(hass, hass_read_only_user):
    _, m = await _setup(hass)
    await m.async_update_config({"panel_access": {hass_read_only_user.id: "none"}})
    assert m.state_for(hass_read_only_user) == {"role": "none", "role_name": None, "permissions": []}


async def test_history_is_capped_and_view_is_limited_to_20(hass, hass_admin_user):
    _, m = await _setup(hass)
    for i in range(MAX_HISTORY + 5):
        await m.async_start_now(end=None, reason=f"h{i}", pages=[], pause=False)
        await m.async_stop()
    assert len(m.history) == MAX_HISTORY and m.history[-1]["reason"] == f"h{MAX_HISTORY + 4}"
    view = m.state_for(hass_admin_user)["history"]
    assert len(view) == 20 and view[0]["reason"] == f"h{MAX_HISTORY + 4}"   # les plus récentes d'abord


# ------------------------------------------------------------------ transitions
async def test_replacing_a_maintenance_restores_then_pauses_again(hass):
    _, m = await _setup(hass)
    started = async_capture_events(hass, "maintenance_mode_started")
    ended = async_capture_events(hass, "maintenance_mode_ended")
    await m.async_start_now(end=None, reason="un", pages=[], pause=True)
    first = m.current.id
    await m.async_start_now(end=None, reason="deux", pages=[], pause=True)
    await hass.async_block_till_done()
    assert m.current.reason == "deux" and m.current.id != first
    assert _state(hass, "automation.a1") == "off" and m.disabled == ["automation.a1", "automation.a2"]
    assert [e.data["ended_by"] for e in ended] == ["replaced"] and len(started) == 2
    assert [h["ended_by"] for h in m.history] == ["replaced"]


async def test_stop_without_maintenance_is_a_noop(hass, hass_storage):
    entry, m = await _setup(hass)
    ended = async_capture_events(hass, "maintenance_mode_ended")
    await m.async_stop()
    await hass.async_block_till_done()
    assert ended == [] and m.history == []


async def test_automatic_end_is_recorded(hass, freezer):
    _, m = await _setup(hass)
    now = dt_util.utcnow()
    await m.async_start_now(end=now + timedelta(minutes=5), reason="", pages=[], pause=True)
    freezer.move_to(now + timedelta(minutes=6))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert m.current is None and m.history[-1]["ended_by"] == "auto"
    assert _state(hass, "automation.a1") == "on"


async def test_scheduled_start_records_the_initiator(hass, freezer):
    _, m = await _setup(hass)
    now = dt_util.utcnow()
    await m.async_add_window(start=now + timedelta(hours=1), end=now + timedelta(hours=2), reason="", pages=[], pause=False)
    freezer.move_to(now + timedelta(hours=1, minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert m.current.started_by == "planification"


async def test_scheduled_window_replaces_an_open_ended_maintenance(hass, freezer):
    _, m = await _setup(hass)
    now = dt_util.utcnow()
    await m.async_start_now(end=None, reason="manuelle", pages=[], pause=False)
    await m.async_add_window(start=now + timedelta(hours=1), end=now + timedelta(hours=2), reason="plan", pages=[], pause=False)
    freezer.move_to(now + timedelta(hours=1, minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert m.current.reason == "plan" and m.history[-1]["reason"] == "manuelle" and m.history[-1]["ended_by"] == "replaced"


async def test_fully_missed_window_is_dropped_silently(hass):
    _, m = await _setup(hass)
    now = dt_util.utcnow()
    m.schedule = [Window("old", now - timedelta(hours=3), now - timedelta(hours=2), "vieux")]
    await m._async_resume()
    assert m.current is None and m.schedule == [] and m.history == []


# ------------------------------------------------------------------ stockage : format et migration depuis 0.2
async def test_stored_format(hass, hass_storage):
    entry, m = await _setup(hass)
    await m.async_start_now(end=None, reason="r", pages=["map"], pause=True)
    stored = hass_storage[_key(entry)]
    assert stored["version"] == 1
    assert set(stored["data"]) == {"config", "disabled", "current", "schedule", "history", "notified"}
    assert set(stored["data"]["config"]) == {
        "automations", "allowed_users", "warn_minutes", "message", "panel_access", "notify_services", "notify_kinds",
        "end_soon_minutes", "templates", "roles", "banner_mode", "banner_scroll",
    }
    assert set(stored["data"]["current"]) == {
        "id", "start", "end", "reason", "pages", "pause_automations", "repeat", "anchor_day", "started_by",
    }


async def test_migration_from_v02_options_and_message(hass, hass_storage):
    from homeassistant.setup import async_setup_component
    await async_setup_component(hass, "automation", {"automation": []})
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={
        "automations": ["automation.x"], "allowed_users": ["u1"], "warn_minutes": 20,
    })
    entry.add_to_hass(hass)
    hass_storage[_key(entry)] = {"version": 1, "minor_version": 1, "key": _key(entry), "data": {"message": "Ancien message"}}
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    c = entry.runtime_data.config
    assert c["automations"] == ["automation.x"] and c["warn_minutes"] == 20 and c["message"] == "Ancien message"
    assert c["allowed_users"] == ["u1"]                           # repris tel quel : aucune vérification au chargement
    assert c["banner_mode"] == "bar" and c["templates"] == []


async def test_load_from_old_active_format(hass, hass_storage):
    from homeassistant.setup import async_setup_component
    await async_setup_component(hass, "automation", {"automation": []})
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    end = (dt_util.utcnow() + timedelta(hours=1)).isoformat()
    hass_storage[_key(entry)] = {"version": 1, "minor_version": 1, "key": _key(entry),
                                 "data": {"active": True, "end": end, "message": "m"}}
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    cur = entry.runtime_data.current
    assert cur is not None and cur.end is not None and cur.pause_automations is True


async def test_load_from_old_armed_start_format(hass, hass_storage):
    from homeassistant.setup import async_setup_component
    await async_setup_component(hass, "automation", {"automation": []})
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    start = (dt_util.utcnow() + timedelta(hours=2)).isoformat()
    hass_storage[_key(entry)] = {"version": 1, "minor_version": 1, "key": _key(entry),
                                 "data": {"start_armed": True, "start": start}}
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    m = entry.runtime_data
    assert m.current is None and len(m.schedule) == 1 and m.schedule[0].start > dt_util.utcnow()


async def test_history_entries_without_id_get_one_on_load(hass, hass_storage):
    from homeassistant.setup import async_setup_component
    await async_setup_component(hass, "automation", {"automation": []})
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    hass_storage[_key(entry)] = {"version": 1, "minor_version": 1, "key": _key(entry),
                                 "data": {"config": {}, "history": [{"reason": "ancienne"}]}}
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.runtime_data.history[0]["hid"]


# ------------------------------------------------------------------ attributs publics (état 0.6.9, à réduire en 0.7)
async def test_public_attributes_snapshot(hass):
    """Fige la liste des attributs lisibles par tous. 0.7 (confidentialité) la fera évoluer volontairement."""
    _, m = await _setup(hass)
    attrs = hass.states.get("switch.mode_maintenance").attributes
    assert set(attrs) - {"friendly_name", "icon"} == {
        "maintenance_mode_entity", "exempt_users", "panel_hidden_for", "message", "banner_mode", "banner_scroll",
        "warn_minutes", "current", "next", "scheduled_count", "disabled_automations",
    }
