const path = require("path");
const WWW = path.join(__dirname, "..", "custom_components", "maintenance_mode", "www");
const { JSDOM } = require("jsdom");
const fs = require("fs");
const SRC = fs.readFileSync(path.join(WWW, "panel.js"), "utf8");
let fail = 0; const ok = (c, m, e) => { if (!c) { fail++; console.log("FAIL:", m, e ?? ""); } else console.log("ok  :", m); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  const dom = new JSDOM("<!doctype html><body></body>", { url: "http://ha.local/maintenance", runScripts: "outside-only", pretendToBeVisual: true });
  const w = dom.window; w.scrollTo = () => {}; const starts = [];
  const state = { role: "admin", permissions: ["view", "control", "schedule", "settings"], active: false, current: null, message: "m", upcoming: [],
    config: { automations: [], allowed_users: [], warn_minutes: 15, end_soon_minutes: 10, message: "m", notify_services: [], notify_kinds: ["pre"], banner_mode: "bar", banner_scroll: true,
      compat_mode: false, max_duration_minutes: 0, confirm_threshold: 20, blackouts: [], excluded_automations: [], excluded_labels: [], selected_labels: [], selected_areas: [], templates: [] }, users: [] };
  const hass = { themes: {}, locale: { language: "fr" }, localize: () => "", panels: {}, services: { notify: {} }, states: {},
    connection: { subscribeMessage: async (c) => { c(state); return () => {}; } },
    callWS: async (m) => {
      if (m.type === "maintenance_mode/get_catalog") return { labels: [], areas: [] };
      if (m.type === "maintenance_mode/start") {
        starts.push(m);
        if (!m.confirm) { const e = new Error("serveur"); e.code = "invalid"; e.translation_key = "confirmation_required"; e.translation_placeholders = { count: "25" }; throw e; }
      }
      return state;
    } };
  w.eval(SRC);
  const el = w.document.createElement("maintenance-mode-panel"); w.document.body.appendChild(el); el.hass = hass; await sleep(40);
  const sr = el.shadowRoot;
  sr.querySelector("[data-action=start-now]").click(); await sleep(15);
  sr.querySelector("[data-action=save-form]").click(); await sleep(30);
  ok(starts.length === 1 && !starts[0].confirm, "premier envoi : sans confirmation");
  ok(sr.textContent.includes("25 automatisations seraient suspendues") && sr.querySelector("[data-action=save-form]").textContent.includes("Confirmer et enregistrer"), "encadré explicite avec le nombre, bouton « Confirmer et enregistrer »");
  ok(sr.querySelector("[data-field='form.reason']"), "le formulaire reste ouvert");
  // changer l'option invalide la confirmation attendue
  sr.querySelector("input[data-action=form-pause]").click(); await sleep(15);
  ok(!sr.textContent.includes("seraient suspendues") && sr.querySelector("[data-action=save-form]").textContent.includes("Enregistrer"), "changement d'option : la demande de confirmation disparaît");
  sr.querySelector("input[data-action=form-pause]").click(); await sleep(15);
  sr.querySelector("[data-action=save-form]").click(); await sleep(30);
  sr.querySelector("[data-action=save-form]").click(); await sleep(30);
  const last = starts[starts.length - 1];
  ok(last.confirm === true, "second clic : envoi avec confirm=true");
  ok(!sr.querySelector("[data-field='form.reason']"), "après confirmation : formulaire fermé");
  sr.querySelector("[data-tab=settings]").click(); await sleep(30);
  const t = sr.querySelector("[data-field='draft.confirm']"); ok(t && t.value === "20", "paramètres : seuil affiché");
  console.log(fail ? `\n${fail} ÉCHEC(S)` : "\nTOUT PASSE"); process.exit(fail ? 1 : 0);
})();
