"""0.7.9 — stockage versionné : migration, copie de sécurité, mode sûr."""
from datetime import timedelta

from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.maintenance_mode.const import DOMAIN
from custom_components.maintenance_mode.storage import STORAGE_VERSION, check_data, migrate_data

from .test_maintenance import _setup


def _key(entry):
    return f"{DOMAIN}.{entry.entry_id}"


async def _start_with(hass, hass_storage, stored, version=1):
    """Installe l'intégration avec un fichier de stockage préparé."""
    await async_setup_component(hass, "automation", {"automation": []})
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    hass_storage[_key(entry)] = {"version": version, "minor_version": 1, "key": _key(entry), "data": stored}
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry, entry.runtime_data


def _v1_file():
    now = dt_util.utcnow()
    return {
        "config": {"message": "Mon message", "warn_minutes": 30, "automations": ["automation.a1"]},
        "disabled": ["automation.a1"],
        "current": {"id": "c1", "start": (now - timedelta(minutes=5)).isoformat(), "end": None, "reason": "en cours",
                    "pages": [], "pause_automations": True, "repeat": "none", "started_by": "N"},
        "schedule": [{"id": "s1", "start": (now + timedelta(hours=3)).isoformat(), "end": (now + timedelta(hours=4)).isoformat(),
                      "reason": "plan", "pages": ["map"], "pause_automations": False, "repeat": "weekly", "anchor_day": 3}],
        "history": [{"hid": "h1", "id": "x", "start": now.isoformat(), "ended_at": now.isoformat(), "ended_by": "manual", "reason": "vieux"}],
        "notified": ["s1:pre"],
    }


async def test_v1_file_is_migrated_without_loss_and_backed_up(hass, hass_storage):
    original = _v1_file()
    entry, m = await _start_with(hass, hass_storage, original)
    assert STORAGE_VERSION == 2 and hass_storage[_key(entry)]["version"] == 2
    assert m.config["message"] == "Mon message" and m.config["warn_minutes"] == 30
    assert m.current.reason == "en cours" and m.disabled == ["automation.a1"]
    assert [w.reason for w in m.schedule] == ["plan"] and m.schedule[0].repeat == "weekly" and m.schedule[0].anchor_day == 3
    assert [h["reason"] for h in m.history] == ["vieux"] and m.notified == ["s1:pre"]
    # copie de sécurité de l'ancien fichier, identique à l'original
    assert hass_storage[f"{_key(entry)}.backup_v1"]["data"] == original
    assert ir.async_get(hass).async_get_issue(DOMAIN, "storage_unreadable") is None


async def test_backup_is_made_once_not_at_each_load(hass, hass_storage):
    entry, m = await _start_with(hass, hass_storage, _v1_file())
    backup = hass_storage[f"{_key(entry)}.backup_v1"]["data"]
    await m.async_update_config({"message": "changé"})
    await m.async_flush()
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass_storage[f"{_key(entry)}.backup_v1"]["data"] == backup          # inchangée
    assert entry.runtime_data.config["message"] == "changé"


async def test_fresh_install_writes_version_2_and_no_backup(hass, hass_storage):
    entry, m = await _setup(hass)
    await m.async_flush()
    assert hass_storage[_key(entry)]["version"] == 2
    assert f"{_key(entry)}.backup_v1" not in hass_storage and f"{_key(entry)}.unreadable" not in hass_storage


def test_migrate_data_is_pure_and_tolerant():
    assert migrate_data(None) is None and migrate_data([1]) == [1]
    old = {"history": [{"reason": "x"}, "pas un dict"], "active": True}
    out = migrate_data(old)
    assert "hid" in out["history"][0] and out["history"][1] == "pas un dict"
    assert "active" not in out and out["current"]["pause_automations"] is True and out["schedule"] == []
    assert "hid" not in old["history"][0]            # l'entrée d'origine n'est pas modifiée


def test_check_data_keeps_what_is_readable():
    assert check_data(None) == ({}, [])
    assert check_data([1, 2]) == ({}, ["racine"])
    data, problems = check_data({"config": "oups", "history": [{"a": 1}, 3], "schedule": [{"start": "n'importe quoi"}, {"id": "ok", "start": "2030-01-01T00:00:00+00:00"}],
                                 "current": {"id": "sans début"}, "disabled": ["automation.a1"], "notified": [1]})
    assert set(problems) == {"config", "history", "schedule", "current", "notified"}
    assert "config" not in data and data["history"] == [{"a": 1}] and len(data["schedule"]) == 1
    assert "current" not in data and data["disabled"] == ["automation.a1"]


async def test_unreadable_parts_start_in_safe_mode(hass, hass_storage):
    stored = _v1_file()
    stored["config"] = "corrompu"
    stored["schedule"] = ["n'importe quoi"]
    entry, m = await _start_with(hass, hass_storage, stored)
    assert m.config["message"] != "Mon message" and m.schedule == []            # illisible : défauts
    assert m.current.reason == "en cours" and [h["reason"] for h in m.history] == ["vieux"]   # lisible : conservé
    issue = ir.async_get(hass).async_get_issue(DOMAIN, "storage_unreadable")
    assert issue and "config" in issue.translation_placeholders["problems"]
    saved = hass_storage[f"{_key(entry)}.unreadable"]["data"]
    assert saved["raw"]["config"] == "corrompu" and "config" in saved["problems"]


async def test_non_dictionary_file_starts_with_defaults(hass, hass_storage):
    entry, m = await _start_with(hass, hass_storage, ["liste", "inattendue"])
    assert m.current is None and m.schedule == [] and m.history == []
    assert ir.async_get(hass).async_get_issue(DOMAIN, "storage_unreadable")


async def test_file_from_a_newer_version_is_kept_and_not_used(hass, hass_storage):
    entry, m = await _start_with(hass, hass_storage, {"nouveau": "format"}, version=3)
    assert m.current is None and m.schedule == []
    assert ir.async_get(hass).async_get_issue(DOMAIN, "storage_unreadable")
    assert hass_storage[f"{_key(entry)}.unreadable"]["data"]["raw"] == {"nouveau": "format"}


async def test_issue_disappears_once_the_file_is_readable_again(hass, hass_storage):
    entry, m = await _start_with(hass, hass_storage, {"config": 12})
    assert ir.async_get(hass).async_get_issue(DOMAIN, "storage_unreadable")
    await m.async_flush()                                  # le mode sûr réécrit un fichier propre
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert ir.async_get(hass).async_get_issue(DOMAIN, "storage_unreadable") is None


async def test_removal_deletes_backup_unreadable_copy_and_issue(hass, hass_storage):
    entry, m = await _start_with(hass, hass_storage, {**_v1_file(), "schedule": "oups"})
    key = _key(entry)
    assert f"{key}.backup_v1" in hass_storage and f"{key}.unreadable" in hass_storage
    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert not [k for k in hass_storage if k.startswith(key)]
    assert ir.async_get(hass).async_get_issue(DOMAIN, "storage_unreadable") is None


async def test_removal_survives_a_newer_unreadable_file(hass, hass_storage):
    entry, m = await _start_with(hass, hass_storage, {"nouveau": "format"}, version=3)
    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert not [k for k in hass_storage if k.startswith(_key(entry))]
