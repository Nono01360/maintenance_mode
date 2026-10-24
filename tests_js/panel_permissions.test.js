const path = require("path");
const WWW = path.join(__dirname, "..", "custom_components", "maintenance_mode", "www");
const { JSDOM } = require("jsdom");
const fs = require("fs");
const SRC = fs.readFileSync(path.join(WWW, "panel.js"), "utf8");
let fail = 0; const ok = (c, m) => { if (!c) { fail++; console.log("FAIL:", m); } else console.log("ok  :", m); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const ALL = ["view", "history", "history_delete", "control", "schedule", "templates", "settings", "access"];
const now = Date.now();

const mkState = (perms, extra = {}) => {
  let p = perms.includes("view") || !perms.length ? perms : ["view", ...perms];
  if (p.includes("history_delete") && !p.includes("history")) p = [...p, "history"];   // comme le serveur
  const cfg = {};
  if (p.includes("settings")) Object.assign(cfg, { automations: [], allowed_users: [], warn_minutes: 15, end_soon_minutes: 10, message: "msg",
    notify_services: [], notify_kinds: ["pre"], banner_mode: "bar", banner_scroll: true });
  if (p.some((x) => ["templates", "schedule", "control"].includes(x))) cfg.templates = [{ id: "t1", name: "MAJ", reason: "", pages: [], pause_automations: true, duration: 60, repeat: "none" }];
  if (p.includes("access")) Object.assign(cfg, { roles: [{ id: "r1", name: "Opérateur", permissions: ["view", "control"] }, { id: "r2", name: "Super", permissions: ["view", "settings"] }], panel_access: {} });
  const st = { role: "x", permissions: p, now: new Date().toISOString(), active: false, current: null, message: "m",
    upcoming: [{ id: "w1", start: new Date(now + 36e5).toISOString(), end: new Date(now + 72e5).toISOString(), reason: "Raison", pages: [], pause_automations: true, repeat: "none", started_by: "" }], ...extra };
  if (Object.keys(cfg).length) st.config = cfg;
  if (p.some((x) => ["settings", "access"].includes(x))) st.users = [
    { id: "u1", name: "Nolann", is_owner: true, is_admin: true, role: "admin", explicit: false },
    { id: "u2", name: "Invité", is_owner: false, is_admin: false, role: "viewer", explicit: false }];
  if (p.includes("history")) st.history = [{ hid: "h2", id: "h", start: new Date(now - 9e6).toISOString(), ended_at: new Date(now - 8e6).toISOString(), ended_by: "manual", started_by: "N", reason: "Ancienne", pages: [], repeat: "none" }, { hid: "h1", id: "h", start: new Date(now - 7e6).toISOString(), ended_at: new Date(now - 36e5).toISOString(), ended_by: "auto", started_by: "N", reason: "Passée", pages: [], repeat: "none" }];
  if (!p.length) return { role: "none", permissions: [] };
  return st;
};

async function panel(perms, fn, extra = {}) {
  const dom = new JSDOM("<!doctype html><body></body>", { url: "http://ha.local/maintenance", runScripts: "outside-only", pretendToBeVisual: true });
  const w = dom.window; const calls = []; let cb; const state = mkState(perms, extra);
  const hass = { themes: {}, locale: { language: "fr" }, localize: () => "", panels: {},
    services: { notify: { mobile_app_pixel: {}, notify: {}, send_message: {}, persistent_notification: {} } },
    states: { "automation.a1": { entity_id: "automation.a1", state: "on", attributes: { friendly_name: "A1" } } },
    connection: { subscribeMessage: async (c) => { cb = c; c(state); return () => {}; } },
    callWS: async (m) => { calls.push(m); return state; } };
  w.eval(SRC);
  const el = w.document.createElement("maintenance-mode-panel"); w.document.body.appendChild(el); el.hass = hass;
  await sleep(40);
  await fn({ w, sr: el.shadowRoot, calls, push: (s) => cb(s) });
  el.remove(); w.close();
}
const has = (sr, sel) => !!sr.querySelector(sel);
const tabs = (sr) => [...sr.querySelectorAll(".tab")].map((t) => t.dataset.tab).join();

(async () => {
  await panel(ALL, async ({ sr }) => {
    ok(tabs(sr) === "list,settings,access", "toutes permissions : 3 onglets");
    ok(has(sr, "[data-action=open-add]") && has(sr, "[data-action=start-now]") && has(sr, "[data-action=edit-item]") && sr.textContent.includes("Historique"), "toutes permissions : actions + historique");
  });
  // ---- suppression de l'historique
  await panel(["history"], async ({ sr }) => {
    ok(sr.textContent.includes("Passée") && !has(sr, "[data-action=delete-history]") && !has(sr, "[data-action=clear-history]"), "historique visible sans droit de suppression : aucun bouton de suppression");
  });
  await panel(["history", "history_delete"], async ({ sr, calls }) => {
    ok(sr.querySelectorAll("[data-action=delete-history]").length === 2 && has(sr, "[data-action=clear-history]"), "droit de suppression : un bouton par entrée + « Tout effacer »");
    sr.querySelector("[data-action=delete-history][data-hid='h1']").click(); await sleep(10);
    ok(sr.querySelector("[data-action=delete-history][data-hid='h1']").textContent.includes("Confirmer") && !calls.some((c) => c.type === "maintenance_mode/delete_history"), "suppression d'une entrée : confirmation d'abord, rien d'envoyé");
    sr.querySelector("[data-action=delete-history][data-hid='h1']").click(); await sleep(15);
    const del = calls.find((c) => c.type === "maintenance_mode/delete_history");
    ok(del && del.history_id === "h1" && del.id === undefined, "confirmation : delete_history avec history_id (et pas id)");
    sr.querySelector("[data-action=clear-history]").click(); await sleep(10);
    ok(sr.querySelector("[data-action=clear-history]").textContent.includes("Confirmer") && !calls.some((c) => c.type === "maintenance_mode/clear_history"), "« Tout effacer » : confirmation d'abord");
    sr.querySelector("[data-action=clear-history]").click(); await sleep(15);
    ok(calls.some((c) => c.type === "maintenance_mode/clear_history"), "confirmation : clear_history envoyé");
  });
  await panel(["history_delete"], async ({ sr }) => {
    ok(has(sr, "[data-action=delete-history]"), "« supprimer l'historique » seul : implique la vue de l'historique côté serveur (état fourni)");
  });
  await panel(["view"], async ({ sr }) => {
    ok(!has(sr, ".tabs") && !has(sr, "[data-action=open-add]") && !has(sr, "[data-action=start-now]") && !has(sr, "[data-action=edit-item]") && !sr.textContent.includes("Historique"), "lecture seule : aucun onglet, aucune action, pas d'historique");
    ok(sr.textContent.includes("Maintenances planifiées"), "lecture seule : voit le planning");
  });
  await panel([], async ({ sr }) => {
    ok(sr.textContent.includes("pas accès") && !has(sr, ".tabs"), "aucune permission : « pas accès »");
  });
  await panel(["control"], async ({ sr }) => {
    ok(has(sr, "[data-action=start-now]") && !has(sr, "[data-action=open-add]") && !has(sr, "[data-action=edit-item]") && !has(sr, ".tabs"), "contrôle seul : démarrer oui, planifier/modifier non, pas d'onglet");
  });
  await panel(["control"], async ({ sr }) => {
    ok(has(sr, "[data-action=edit-current]") && has(sr, "[data-action=stop-current]"), "contrôle : modifier/terminer la maintenance en cours");
  }, { active: true, current: { id: "c", start: new Date(now - 6e4).toISOString(), end: null, reason: "", pages: [], pause_automations: true, repeat: "none" } });
  await panel(["schedule"], async ({ sr }) => {
    ok(has(sr, "[data-action=open-add]") && has(sr, "[data-action=edit-item]") && has(sr, "[data-action=duplicate-item]") && has(sr, "[data-action=delete-item]") && !has(sr, "[data-action=start-now]"), "planification seule : planifier/modifier/supprimer oui, démarrer non");
    sr.querySelector("[data-action=open-add]").click(); await new Promise((r) => setTimeout(r, 10));
    ok(has(sr, "select[data-action=apply-template]") && !has(sr, "[data-action=save-template]"), "formulaire : applique les modèles mais ne peut pas en créer (pas de droit « modèles »)");
  });
  await panel(["templates"], async ({ sr }) => {
    ok(tabs(sr) === "list,settings", "modèles seuls : onglet Paramètres visible, pas Accès");
    sr.querySelector("[data-tab=settings]").click(); await sleep(10);
    ok(sr.textContent.includes("Modèles") && !has(sr, "[data-field='draft.message']") && !has(sr, "[data-action=save-settings]"), "modèles seuls : uniquement la carte des modèles");
  });
  await panel(["settings"], async ({ sr, calls, w }) => {
    ok(tabs(sr) === "list,settings", "paramètres seuls : onglet Paramètres, pas Accès");
    sr.querySelector("[data-tab=settings]").click(); await sleep(10);
    ok(has(sr, "[data-field='draft.message']") && !sr.textContent.includes("Modèles"), "paramètres seuls : réglages sans modèles");
    ok(sr.textContent.includes("notify.mobile_app_pixel") && sr.textContent.includes("notify.persistent_notification")
       && !sr.textContent.includes("notify.notify") && !sr.textContent.includes("notify.send_message"), "services notify : « notify.notify » et « send_message » absents");
    // bandeau : mode + défilement
    const sel = sr.querySelector("select[data-action=banner-mode]");
    ok(sel && sel.value === "bar", "option d'affichage : bandeau sélectionné par défaut");
    sel.value = "card"; sel.dispatchEvent(new w.Event("change", { bubbles: true })); await sleep(10);
    const sc = sr.querySelector("input[data-action=toggle-banner-scroll]"); sc.checked = false; sc.dispatchEvent(new w.Event("change", { bubbles: true })); await sleep(10);
    sr.querySelector("[data-action=save-settings]").click(); await sleep(20);
    const cfg = calls.filter((c) => c.type === "maintenance_mode/update_config" && "banner_mode" in c).pop();
    ok(cfg && cfg.banner_mode === "card" && cfg.banner_scroll === false, "enregistrement : banner_mode=card, banner_scroll=false");
  });
  await panel(["access"], async ({ sr, calls, w }) => {
    ok(tabs(sr) === "list,access", "accès seul : onglet Accès, pas Paramètres");
    sr.querySelector("[data-tab=access]").click(); await sleep(10);
    ok(sr.textContent.includes("Rôles personnalisés") && sr.querySelector("[data-field='role.name']").value === "Opérateur", "éditeur de rôles affiché");
    // le rôle « Super » (settings) ne peut pas être attribué : l'utilisateur n'a pas ce droit
    const opts = [...sr.querySelectorAll("select[data-action=set-user-role] option")];
    const byName = (n) => opts.find((o) => o.textContent.includes(n));
    ok(byName("Super").disabled && byName("Opérateur").disabled && byName("Vue administrateur").disabled, "rôles dépassant ses droits : non attribuables");
    ok(!byName("Vue utilisateur").disabled && !byName("Aucun accès").disabled, "rôles dans ses droits : attribuables");
    // cases de permissions : celles qu'il n'a pas sont verrouillées
    const box = (i, p) => sr.querySelector(`input[data-action=toggle-role-perm][data-idx="${i}"][data-perm="${p}"]`);
    ok(box(0, "settings").disabled && !box(0, "access").disabled, "cases : droit qu'il n'a pas = verrouillé, droit qu'il a = libre");
    // « Supprimer l'historique » rend « Voir l'historique » implicite
    box(0, "history_delete") && ok(!!box(0, "history_delete"), "case « Supprimer l'historique » présente dans l'éditeur de rôles");
    // créer un rôle
    sr.querySelector("[data-action=add-role]").click(); await sleep(10);
    const idx = sr.querySelectorAll("[data-field='role.name']").length - 1;
    const nm = sr.querySelectorAll("[data-field='role.name']")[idx]; nm.value = "Gestionnaire"; nm.dispatchEvent(new w.Event("input", { bubbles: true }));
    box(idx, "access").click(); await sleep(10);
    ok(box(idx, "view").checked && box(idx, "view").disabled, "« Voir » devient implicite dès qu'un autre droit est coché");
    sr.querySelector("[data-action=save-roles]").click(); await sleep(20);
    const call = calls.filter((c) => c.type === "maintenance_mode/update_config" && c.roles).pop();
    const neu = call.roles.find((r) => r.name === "Gestionnaire");
    ok(call.roles.length === 3 && neu && !("id" in neu) && neu.permissions.includes("access") && call.roles[0].id === "r1", "update_config : nouveau rôle sans id, anciens avec id");
    // suppression en deux clics
    sr.querySelector("[data-action=delete-role][data-idx='0']").click(); await sleep(10);
    ok(sr.querySelector("[data-action=delete-role][data-idx='0']").textContent.includes("Confirmer"), "suppression de rôle : confirmation demandée");
    sr.querySelector("[data-action=delete-role][data-idx='0']").click(); await sleep(10);
    ok(![...sr.querySelectorAll("[data-field='role.name']")].some((i) => i.value === "Opérateur"), "suppression de rôle : retiré après confirmation");
    // affectation d'un rôle personnalisé
    const sel = sr.querySelector("select[data-action=set-user-role]"); sel.value = "none"; sel.dispatchEvent(new w.Event("change", { bubbles: true })); await sleep(10);
    ok(calls.some((c) => c.panel_access && c.panel_access.u2 === "none"), "affectation envoyée (panel_access)");
  });
  // anglais
  console.log(fail ? `\n${fail} ÉCHEC(S)` : "\nTOUT PASSE"); process.exit(fail ? 1 : 0);
})();
