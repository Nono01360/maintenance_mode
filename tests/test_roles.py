"""Rôles personnalisés, autorisations, anti-escalade, notify.notify, bandeau."""
from datetime import timedelta

from homeassistant.util import dt as dt_util

from .test_maintenance import _setup


async def _ws_call(client, mid, **payload):
    await client.send_json({"id": mid, **payload})
    return await client.receive_json()


def _role_id(m, name):
    return next(r["id"] for r in m.config["roles"] if r["name"] == name)


async def test_builtin_permissions(hass, hass_owner_user, hass_admin_user, hass_read_only_user):
    _, m = await _setup(hass)
    assert m.perms_for(hass_owner_user) >= {"view", "access", "settings"}
    assert m.perms_for(hass_admin_user) == {"view", "history", "control", "schedule", "templates", "settings", "access"}
    assert m.perms_for(hass_read_only_user) == {"view"}


async def test_custom_role_normalisation_and_cleanup(hass, hass_read_only_user):
    _, m = await _setup(hass)
    await m.async_update_config({"roles": [
        {"name": "Opérateur", "permissions": ["control", "bidon"]},
        {"name": "  ", "permissions": ["view"]},          # nom vide : ignoré
        {"name": "Vide", "permissions": []},
        {"id": "viewer", "name": "Pirate", "permissions": ["access"]},  # id intégré : régénéré
    ]})
    names = [r["name"] for r in m.config["roles"]]
    assert names == ["Opérateur", "Vide", "Pirate"]
    op = next(r for r in m.config["roles"] if r["name"] == "Opérateur")
    assert op["permissions"] == ["view", "control"]            # « view » implicite, valeur inconnue retirée
    assert next(r for r in m.config["roles"] if r["name"] == "Vide")["permissions"] == []
    assert all(r["id"] not in ("viewer", "admin", "none") for r in m.config["roles"])

    # affectation puis suppression du rôle -> retour au rôle par défaut
    await m.async_update_config({"panel_access": {hass_read_only_user.id: op["id"], "inconnu": "admin"}})
    assert m.config["panel_access"] == {hass_read_only_user.id: op["id"]}
    assert m.perms_for(hass_read_only_user) == {"view", "control"}
    await m.async_update_config({"roles": [r for r in m.config["roles"] if r["id"] != op["id"]]})
    assert m.config["panel_access"] == {}
    assert m.perms_for(hass_read_only_user) == {"view"}


async def test_panel_hidden_for_roles_without_view(hass, hass_read_only_user, hass_admin_user):
    _, m = await _setup(hass)
    await m.async_update_config({"roles": [{"name": "Rien", "permissions": []}, {"name": "Lecture", "permissions": ["history"]}]})
    rien, lecture = _role_id(m, "Rien"), _role_id(m, "Lecture")
    await m.async_update_config({"panel_access": {hass_read_only_user.id: rien, hass_admin_user.id: "none"}})
    attrs = hass.states.get("switch.mode_maintenance").attributes
    assert set(attrs["panel_hidden_for"]) == {hass_read_only_user.id, hass_admin_user.id}
    await m.async_update_config({"panel_access": {hass_read_only_user.id: lecture, hass_admin_user.id: "none"}})
    attrs = hass.states.get("switch.mode_maintenance").attributes
    assert attrs["panel_hidden_for"] == [hass_admin_user.id]  # « Lecture » inclut « view »


async def test_state_is_filtered_by_permissions(hass, hass_read_only_user):
    _, m = await _setup(hass)
    await m.async_update_config({"roles": [
        {"name": "Hist", "permissions": ["history"]},
        {"name": "Tpl", "permissions": ["templates"]},
        {"name": "Cfg", "permissions": ["settings"]},
    ]})
    ids = {r["name"]: r["id"] for r in m.config["roles"]}
    await m.async_start_now(end=None, reason="x", pages=[], pause=False)
    await m.async_stop()

    async def state(role):
        await m.async_update_config({"panel_access": {hass_read_only_user.id: ids[role]}})
        return m.state_for(hass_read_only_user)

    s = await state("Hist")
    assert "history" in s and "config" not in s and "users" not in s
    s = await state("Tpl")
    assert "history" not in s and list(s["config"]) == ["templates"]
    s = await state("Cfg")
    assert "automations" in s["config"] and "roles" not in s["config"] and "users" in s and "templates" not in s["config"]


async def test_ws_permissions_and_no_escalation(hass, hass_ws_client, hass_read_only_access_token,
                                               hass_read_only_user, hass_access_token):
    _, m = await _setup(hass)
    admin = await hass_ws_client(hass, hass_access_token)
    r = await _ws_call(admin, 1, type="maintenance_mode/update_config", roles=[
        {"name": "Opérateur", "permissions": ["control"]},
        {"name": "Gestion accès", "permissions": ["access"]},
        {"name": "Modèles", "permissions": ["templates"]},
    ])
    assert r["success"], r
    ids = {x["name"]: x["id"] for x in m.config["roles"]}

    # --- opérateur : peut démarrer/arrêter, ni planifier ni régler
    await m.async_update_config({"panel_access": {hass_read_only_user.id: ids["Opérateur"]}})
    user = await hass_ws_client(hass, hass_read_only_access_token)
    r = await _ws_call(user, 1, type="maintenance_mode/start", reason="op")
    assert r["success"] and r["result"]["current"]["reason"] == "op"
    assert r["result"]["permissions"] == ["view", "control"]
    r = await _ws_call(user, 2, type="maintenance_mode/stop")
    assert r["success"]
    start = (dt_util.utcnow() + timedelta(hours=1)).isoformat()
    r = await _ws_call(user, 3, type="maintenance_mode/add_window", start=start)
    assert not r["success"] and r["error"]["code"] == "unauthorized"
    r = await _ws_call(user, 4, type="maintenance_mode/update_config", message="x")
    assert not r["success"] and r["error"]["code"] == "unauthorized"

    # --- « Modèles » : modèles oui, message non
    await m.async_update_config({"panel_access": {hass_read_only_user.id: ids["Modèles"]}})
    r = await _ws_call(user, 5, type="maintenance_mode/update_config", templates=[{"name": "T1"}])
    assert r["success"] and m.config["templates"][0]["name"] == "T1"
    r = await _ws_call(user, 6, type="maintenance_mode/update_config", message="x")
    assert not r["success"] and r["error"]["code"] == "unauthorized"

    # --- « Gestion accès » : peut créer un rôle limité à ses droits, pas plus
    await m.async_update_config({"panel_access": {hass_read_only_user.id: ids["Gestion accès"]}})
    roles = [{"id": x["id"], "name": x["name"], "permissions": x["permissions"]} for x in m.config["roles"]]
    r = await _ws_call(user, 7, type="maintenance_mode/update_config",
                       roles=roles + [{"name": "Sous-rôle", "permissions": ["access"]}])
    assert r["success"], r
    r = await _ws_call(user, 8, type="maintenance_mode/update_config",
                       roles=roles + [{"name": "Trop", "permissions": ["settings"]}])
    assert not r["success"] and "pas toi-même" in r["error"]["message"]
    # s'auto-promouvoir administrateur est refusé
    r = await _ws_call(user, 9, type="maintenance_mode/update_config", panel_access={hass_read_only_user.id: "admin"})
    assert not r["success"] and "pas toi-même" in r["error"]["message"]
    assert m.config["panel_access"][hass_read_only_user.id] == ids["Gestion accès"]


async def test_notify_notify_is_refused(hass):
    entry, m = await _setup(hass)
    await m.async_update_config({"notify_services": ["notify", "send_message", "mobile_app_pixel"]})
    assert m.config["notify_services"] == ["mobile_app_pixel"]
    # ancienne configuration déjà enregistrée : nettoyée au chargement
    m.config["notify_services"] = ["notify", "mobile_app_pixel"]
    await m._commit()
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.runtime_data.config["notify_services"] == ["mobile_app_pixel"]


async def test_banner_settings(hass):
    _, m = await _setup(hass)
    attrs = hass.states.get("switch.mode_maintenance").attributes
    assert attrs["banner_mode"] == "bar" and attrs["banner_scroll"] is True
    await m.async_update_config({"banner_mode": "card", "banner_scroll": False})
    attrs = hass.states.get("switch.mode_maintenance").attributes
    assert attrs["banner_mode"] == "card" and attrs["banner_scroll"] is False
    await m.async_update_config({"banner_mode": "n_importe_quoi"})
    assert m.config["banner_mode"] == "card"
