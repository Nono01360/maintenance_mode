"""9.2 — réconciliation : écarts détectés, alerte « Réparations » avec bouton « Réparer », réparation testée."""
from unittest.mock import patch

from homeassistant.core import ServiceRegistry
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir

from custom_components.maintenance_mode.const import DOMAIN
from custom_components.maintenance_mode.repairs import async_create_fix_flow

from .test_maintenance import _setup, _state


def _issue(hass, key):
    return ir.async_get(hass).async_get_issue(DOMAIN, key)


async def _fix(hass, key):
    """Parcourt le flux de réparation comme l'interface : formulaire de confirmation puis validation."""
    flow = await async_create_fix_flow(hass, key, None)
    flow.hass = hass
    flow.handler = DOMAIN
    flow.issue_id = key
    result = await flow.async_step_init()
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "confirm"
    result = await flow.async_step_confirm({})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()


async def test_missing_selection_is_fixable_and_repair_cleans_the_list(hass):
    _, m = await _setup(hass)
    await m.async_update_config({"automations": ["automation.n_existe_pas", "automation.a1"]})
    issue = _issue(hass, "missing_automations")
    assert issue and issue.is_fixable
    await _fix(hass, "missing_automations")
    assert m.config["automations"] == ["automation.a1"]
    assert _issue(hass, "missing_automations") is None


async def test_suspended_automation_that_disappeared(hass):
    _, m = await _setup(hass)
    await m.async_start_now(end=None, reason="", pages=[], pause=True)
    assert _issue(hass, "missing_suspended") is None
    hass.states.async_remove("automation.a1")                  # supprimée pendant la maintenance
    await m._commit()
    issue = _issue(hass, "missing_suspended")
    assert issue and issue.is_fixable and "automation.a1" in issue.translation_placeholders["entities"]
    await _fix(hass, "missing_suspended")
    assert m.disabled == ["automation.a2"]
    assert _issue(hass, "missing_suspended") is None
    await m.async_stop()
    assert _state(hass, "automation.a2") == "on"            # la fin ne tente plus de réactiver l'absente


async def test_reapply_failure_then_repair(hass):
    _, m = await _setup(hass)
    await m.async_start_now(end=None, reason="", pages=[], pause=True)
    await hass.services.async_call("automation", "turn_on", {"entity_id": "automation.a1"}, blocking=True)
    real = ServiceRegistry.async_call

    async def failing(reg, domain, service, *a, **kw):
        if domain == "automation" and service == "turn_off":
            raise HomeAssistantError("boom")
        return await real(reg, domain, service, *a, **kw)

    with patch.object(ServiceRegistry, "async_call", failing):
        async with m._lock:
            await m._reapply_suspension()
            m._update_issues()
    issue = _issue(hass, "reapply_failed")
    assert issue and issue.is_fixable and "automation.a1" in issue.translation_placeholders["entities"]
    assert _state(hass, "automation.a1") == "on"
    await _fix(hass, "reapply_failed")                        # le service fonctionne de nouveau
    assert _state(hass, "automation.a1") == "off"
    assert _issue(hass, "reapply_failed") is None


async def test_reapply_success_leaves_no_issue(hass):
    _, m = await _setup(hass)
    await m.async_start_now(end=None, reason="", pages=[], pause=True)
    await hass.services.async_call("automation", "turn_on", {"entity_id": "automation.a1"}, blocking=True)
    async with m._lock:
        await m._reapply_suspension()
    await m._commit()
    assert _issue(hass, "reapply_failed") is None and _state(hass, "automation.a1") == "off"


async def test_repair_with_nothing_to_fix_is_harmless(hass):
    _, m = await _setup(hass)
    for key in ("missing_automations", "missing_suspended", "reapply_failed"):
        await _fix(hass, key)
    assert m.current is None and m.disabled == []


async def test_issues_removed_on_unload_and_removal(hass):
    entry, m = await _setup(hass)
    await m.async_start_now(end=None, reason="", pages=[], pause=True)
    hass.states.async_remove("automation.a1")
    await m.async_update_config({"automations": ["automation.n_existe_pas"]})
    assert _issue(hass, "missing_suspended") and _issue(hass, "missing_automations")
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert not any(_issue(hass, k) for k in ("missing_suspended", "missing_automations", "reapply_failed"))


async def test_repairs_http_flow(hass, hass_client):
    """Bout en bout côté serveur : l'API des Réparations démarre notre flux et le termine."""
    from homeassistant.setup import async_setup_component

    assert await async_setup_component(hass, "repairs", {})
    _, m = await _setup(hass)
    await m.async_update_config({"automations": ["automation.n_existe_pas"]})
    client = await hass_client()
    resp = await client.post("/api/repairs/issues/fix", json={"handler": DOMAIN, "issue_id": "missing_automations"})
    data = await resp.json()
    assert resp.status == 200 and data["step_id"] == "confirm", data
    resp = await client.post(f"/api/repairs/issues/fix/{data['flow_id']}", json={})
    data = await resp.json()
    assert data["type"] == "create_entry", data
    assert m.config["automations"] == []


def test_fixable_issue_translations_follow_the_hassfest_rule():
    """Régression (0.9.10) : pour une alerte réparable, hassfest interdit « description » ET « fix_flow » ensemble
    (« two or more values in the same group of exclusion 'fixable' ») : la CI « Validate » échouait."""
    import json
    from pathlib import Path

    from custom_components.maintenance_mode.const import RECONCILE_ISSUES

    for lang in ("fr", "en"):
        issues = json.loads((Path(__file__).parent.parent / "custom_components" / "maintenance_mode" / "translations"
                             / f"{lang}.json").read_text(encoding="utf-8"))["issues"]
        for key in RECONCILE_ISSUES:
            assert "fix_flow" in issues[key] and "description" not in issues[key], (lang, key)
            step = issues[key]["fix_flow"]["step"]["confirm"]
            assert step["title"] and "{entities}" in step["description"], (lang, key)
