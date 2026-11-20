"""9.7 — capteurs de santé et binary_sensor « problème »."""
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import EntityCategory
from homeassistant.util import dt as dt_util

from custom_components.maintenance_mode.const import DOMAIN

from .test_hooks import _h, _scripts
from .test_maintenance import _setup


def _ent(hass, entry, platform, key):
    reg = er.async_get(hass)
    eid = reg.async_get_entity_id(platform, DOMAIN, f"{entry.entry_id}_{key}")
    assert eid, f"entité {platform}/{key} absente"
    return reg.async_get(eid), hass.states.get(eid)


async def test_entities_exist_and_are_diagnostic(hass):
    entry, m = await _setup(hass)
    for platform, key in (("sensor", "suspended"), ("sensor", "last_reapply"), ("sensor", "last_hook_failure"),
                          ("binary_sensor", "problem")):
        reg, state = _ent(hass, entry, platform, key)
        assert reg.entity_category is EntityCategory.DIAGNOSTIC and state is not None
    _, problem = _ent(hass, entry, "binary_sensor", "problem")
    assert problem.state == "off" and problem.attributes["device_class"] == "problem"


async def test_suspended_count(hass):
    entry, m = await _setup(hass)
    assert _ent(hass, entry, "sensor", "suspended")[1].state == "0"
    await m.async_start_now(end=None, reason="", pages=[], pause=True)
    assert _ent(hass, entry, "sensor", "suspended")[1].state == "2"
    await m.async_stop()
    assert _ent(hass, entry, "sensor", "suspended")[1].state == "0"


async def test_last_reapply_is_recorded_and_persists(hass):
    entry, m = await _setup(hass)
    assert _ent(hass, entry, "sensor", "last_reapply")[1].state == "unknown"
    await m.async_start_now(end=None, reason="", pages=[], pause=True)
    await hass.services.async_call("automation", "turn_on", {"entity_id": "automation.a1"}, blocking=True)
    before = dt_util.utcnow()
    await m._async_resume()
    state = _ent(hass, entry, "sensor", "last_reapply")[1].state
    assert dt_util.parse_datetime(state) >= before.replace(microsecond=0)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert _ent(hass, entry, "sensor", "last_reapply")[1].state == state


async def test_last_hook_failure_and_problem_flag(hass):
    await _scripts(hass)
    entry, m = await _setup(hass)
    m.config["hooks"] = [_h("after_start", "script.one"), _h("after_start", "script.bad", name="Sauvegarde")]
    assert _ent(hass, entry, "sensor", "last_hook_failure")[1].state == "unknown"
    await m.async_start_now(end=None, reason="", pages=[], pause=False)
    st = _ent(hass, entry, "sensor", "last_hook_failure")[1]
    assert st.state != "unknown" and st.attributes["name"] == "Sauvegarde" and st.attributes["status"] == "failed"
    assert st.attributes["when"] == "after_start" and st.attributes["entity_id"] == "script.bad"
    problem = _ent(hass, entry, "binary_sensor", "problem")[1]
    assert problem.state == "on" and problem.attributes["problems"] == ["hook_failed"]
    await m.async_stop()
    assert _ent(hass, entry, "binary_sensor", "problem")[1].state == "off", "le défaut de hook ne vaut que pour la maintenance en cours"
    assert _ent(hass, entry, "sensor", "last_hook_failure")[1].state != "unknown", "mais le dernier échec reste affiché"


async def test_problem_flag_follows_reconciliation(hass):
    entry, m = await _setup(hass)
    await m.async_update_config({"automations": ["automation.n_existe_pas"]})
    problem = _ent(hass, entry, "binary_sensor", "problem")[1]
    assert problem.state == "on" and problem.attributes["problems"] == ["missing_automations"]
    await m.async_repair("missing_automations")
    assert _ent(hass, entry, "binary_sensor", "problem")[1].state == "off"


async def test_entities_survive_a_reload_with_the_same_registry_id(hass):
    """Régression : « _calendar » manquait dans les suffixes conservés, l'entité du calendrier était supprimée à chaque chargement."""
    entry, m = await _setup(hass)
    reg = er.async_get(hass)
    before = {e.unique_id: e.id for e in er.async_entries_for_config_entry(reg, entry.entry_id)}
    assert any(u.endswith("_calendar") for u in before) and len(before) == 7
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    after = {e.unique_id: e.id for e in er.async_entries_for_config_entry(reg, entry.entry_id)}
    assert after == before
