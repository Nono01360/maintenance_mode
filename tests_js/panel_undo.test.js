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
  const base = () => ({ role: "admin", permissions: ["view", "schedule", "templates", "settings"], active: false, current: null, message: "m",
    upcoming: [{ id: "w1", start: new Date(now + 36e5).toISOString(), end: new Date(now + 72e5).toISOString(), reason: "R", pages: [], pause_automations: true, repeat: "none" }],
    config: { automations: [], allowed_users: [], warn_minutes: 15, end_soon_minutes: 10, message: "m", notify_services: [], notify_kinds: ["pre"], banner_mode: "bar", banner_scroll: true,
      compat_mode: false, max_duration_minutes: 0, confirm_threshold: 20, blackouts: [], excluded_automations: [], excluded_labels: [], selected_labels: [], selected_areas: [],
      templates: [{ id: "t1", name: "MAJ", reason: "", pages: [], pause_automations: true, duration: 30, repeat: "none" }] }, users: [] });
  const hass = { themes: {}, locale: { language: "fr" }, localize: () => "", panels: {}, services: { notify: {} }, states: {},
    connection: { subscribeMessage: async (c) => { c(base()); return () => {}; } },
    callWS: async (m) => {
      calls.push(m);
      if (m.type === "maintenance_mode/get_catalog") return { labels: [], areas: [] };
      if (m.type === "maintenance_mode/delete_window") return { ...base(), upcoming: [], undo: { token: "tok1", kind: "window", seconds: 1 } };
      if (m.type === "maintenance_mode/delete_template") { const s = base(); s.config.templates = []; return { ...s, undo: { token: "tok2", kind: "template", seconds: 10 } }; }
      return base();
    } };
  w.eval(SRC);
  const el = w.document.createElement("maintenance-mode-panel"); w.document.body.appendChild(el); el.hass = hass; await sleep(40);
  const sr = el.shadowRoot; const last = (t) => calls.filter((c) => c.type === "maintenance_mode/" + t).pop();
  // maintenance : suppression (2 clics) -> bandeau « Annuler »
  sr.querySelector("[data-action=delete-item]").click(); await sleep(10);
  sr.querySelector("[data-action=delete-item]").click(); await sleep(20);
  ok(last("delete_window").window_id === "w1", "suppression d'une maintenance : delete_window");
  ok(sr.textContent.includes("Maintenance supprimée.") && !!sr.querySelector("[data-action=undo-delete]"), "bandeau « Maintenance supprimée. » avec bouton Annuler");
  sr.querySelector("[data-action=undo-delete]").click(); await sleep(20);
  ok(last("undo_delete").token === "tok1" && !sr.querySelector("[data-action=undo-delete]"), "Annuler : undo_delete avec le jeton, bandeau retiré");
  // le bandeau disparaît tout seul après le délai
  calls.length = 0;
  // modèle
  sr.querySelector("[data-tab=settings]").click(); await sleep(30);
  sr.querySelector("[data-action=delete-template]").click(); await sleep(10);
  sr.querySelector("[data-action=delete-template]").click(); await sleep(20);
  ok(last("delete_template").template_id === "t1" && !calls.some((c) => c.type === "maintenance_mode/update_config"), "suppression d'un modèle : commande dédiée (plus update_config)");
  ok(sr.textContent.includes("Modèle supprimé."), "bandeau « Modèle supprimé. »");
  sr.querySelector("[data-action=undo-delete]").click(); await sleep(20);
  ok(last("undo_delete").token === "tok2", "annulation de la suppression du modèle");
  // expiration
  calls.length = 0;
  sr.querySelector("[data-tab=list]").click(); await sleep(20);
  sr.querySelector("[data-action=delete-item]").click(); await sleep(10); sr.querySelector("[data-action=delete-item]").click(); await sleep(20);
  ok(!!sr.querySelector("[data-action=undo-delete]"), "nouvelle suppression : bandeau présent");
  await sleep(1300);
  ok(!sr.querySelector("[data-action=undo-delete]"), "après le délai (1 s ici) : le bandeau disparaît");
  console.log(fail ? `\n${fail} ÉCHEC(S)` : "\nTOUT PASSE"); process.exit(fail ? 1 : 0);
})();
