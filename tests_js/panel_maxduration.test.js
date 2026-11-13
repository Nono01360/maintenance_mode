const path = require("path");
const WWW = path.join(__dirname, "..", "custom_components", "maintenance_mode", "www");
const { JSDOM } = require("jsdom");
const fs = require("fs");
const SRC = fs.readFileSync(path.join(WWW, "panel.js"), "utf8");
let fail = 0; const ok = (c, m, e) => { if (!c) { fail++; console.log("FAIL:", m, e ?? ""); } else console.log("ok  :", m); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const now = Date.now();

(async () => {
  const dom = new JSDOM("<!doctype html><body></body>", { url: "http://ha.local/maintenance", runScripts: "outside-only", pretendToBeVisual: true });
  const w = dom.window; w.scrollTo = () => {}; const calls = [];
  const state = { role: "admin", permissions: ["view", "control", "schedule", "templates", "settings", "history"], active: false, current: null, message: "m",
    upcoming: [{ id: "w1", start: new Date(now + 36e5).toISOString(), end: new Date(now + 72e5).toISOString(), reason: "R", pages: [], pause_automations: true, repeat: "none", max_minutes: 45 }],
    config: { automations: [], allowed_users: [], warn_minutes: 15, end_soon_minutes: 10, message: "m", notify_services: [], notify_kinds: ["pre"], banner_mode: "bar",
      banner_scroll: true, compat_mode: false, max_duration_minutes: 120, excluded_automations: [], excluded_labels: [], selected_labels: [], selected_areas: [],
      templates: [{ id: "t1", name: "MAJ", reason: "", pages: [], pause_automations: true, duration: 30, repeat: "none", max_minutes: 20 }] },
    users: [], history: [{ hid: "h1", id: "x", start: new Date(now - 9e6).toISOString(), ended_at: new Date(now - 8e6).toISOString(), ended_by: "max_duration", started_by: "N", reason: "Longue", pages: [], repeat: "none" }] };
  const hass = { themes: {}, locale: { language: "fr" }, localize: () => "", panels: {}, services: { notify: {} }, states: {},
    connection: { subscribeMessage: async (c) => { c(state); return () => {}; } },
    callWS: async (m) => { calls.push(m); return m.type === "maintenance_mode/get_catalog" ? { labels: [], areas: [] } : state; } };
  w.eval(SRC);
  const el = w.document.createElement("maintenance-mode-panel"); w.document.body.appendChild(el); el.hass = hass; await sleep(40);
  const sr = el.shadowRoot; const last = (t) => calls.filter((c) => c.type === "maintenance_mode/" + t).pop();
  ok(sr.textContent.includes("arrêtée à la durée maximale"), "historique : fin par durée maximale libellée");
  // démarrer : champ vide -> null ; valeur -> nombre
  sr.querySelector("[data-action=start-now]").click(); await sleep(15);
  ok(sr.querySelector("[data-field='form.max']").value === "", "formulaire : durée maximale vide par défaut");
  sr.querySelector("[data-action=save-form]").click(); await sleep(20);
  ok(last("start").max_minutes === null, "vide : max_minutes=null (valeur par défaut des paramètres)");
  sr.querySelector("[data-action=start-now]").click(); await sleep(15);
  const f = sr.querySelector("[data-field='form.max']"); f.value = "0"; f.dispatchEvent(new w.Event("input", { bubbles: true }));
  sr.querySelector("[data-action=save-form]").click(); await sleep(20);
  ok(last("start").max_minutes === 0, "0 : sans limite");
  // modifier une maintenance planifiée : la valeur existante est reprise
  sr.querySelector("[data-action=edit-item]").click(); await sleep(15);
  ok(sr.querySelector("[data-field='form.max']").value === "45", "édition : durée maximale existante affichée");
  sr.querySelector("[data-action=save-form]").click(); await sleep(20);
  ok(last("update_window").max_minutes === 45, "édition sans changement : max_minutes conservé");
  // modèle : appliqué puis enregistré
  sr.querySelector("[data-action=start-now]").click(); await sleep(15);
  const sel = sr.querySelector("select[data-action=apply-template]"); sel.value = "t1"; sel.dispatchEvent(new w.Event("change", { bubbles: true })); await sleep(15);
  ok(sr.querySelector("[data-field='form.max']").value === "20", "modèle appliqué : durée maximale du modèle");
  const name = sr.querySelector("[data-field='form.tplName']"); name.value = "Copie"; name.dispatchEvent(new w.Event("input", { bubbles: true }));
  sr.querySelector("[data-action=save-template]").click(); await sleep(20);
  const tpls = last("update_config").templates; ok(tpls.some((t) => t.name === "Copie" && t.max_minutes === 20), "enregistrer comme modèle : max_minutes inclus");
  sr.querySelector("[data-action=cancel-form]").click(); await sleep(10);
  // paramètres
  sr.querySelector("[data-tab=settings]").click(); await sleep(30);
  const d = sr.querySelector("[data-field='draft.maxdur']"); ok(d && d.value === "120", "paramètres : durée maximale par défaut affichée");
  d.value = "60"; d.dispatchEvent(new w.Event("input", { bubbles: true }));
  sr.querySelector("[data-action=save-block][data-block=page]").click(); await sleep(30);
  ok(last("update_config").max_duration_minutes === 60, "paramètres : max_duration_minutes enregistré");
  console.log(fail ? `\n${fail} ÉCHEC(S)` : "\nTOUT PASSE"); process.exit(fail ? 1 : 0);
})();
