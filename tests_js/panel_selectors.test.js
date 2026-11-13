const path = require("path");
const WWW = path.join(__dirname, "..", "custom_components", "maintenance_mode", "www");
const { JSDOM } = require("jsdom");
const fs = require("fs");
const SRC = fs.readFileSync(path.join(WWW, "panel.js"), "utf8");
let fail = 0; const ok = (c, m, e) => { if (!c) { fail++; console.log("FAIL:", m, e ?? ""); } else console.log("ok  :", m); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  const dom = new JSDOM("<!doctype html><body></body>", { url: "http://ha.local/maintenance", runScripts: "outside-only", pretendToBeVisual: true });
  const w = dom.window; w.scrollTo = () => {}; const calls = [];
  const state = { role: "admin", permissions: ["view", "settings"], active: false, current: null, message: "m", upcoming: [],
    config: { automations: [], allowed_users: [], warn_minutes: 15, end_soon_minutes: 10, message: "m", notify_services: [], notify_kinds: ["pre"],
      banner_mode: "bar", banner_scroll: true, compat_mode: false, excluded_automations: [], excluded_labels: [], selected_labels: [], selected_areas: ["area1"] }, users: [] };
  const catalog = { labels: [{ id: "lab1", name: "Confort", automations: ["automation.a1"] }], areas: [{ id: "area1", name: "Salon", automations: ["automation.a1", "automation.a2"] }, { id: "area2", name: "Cuisine", automations: [] }] };
  const hass = { themes: {}, locale: { language: "fr" }, localize: () => "", panels: {}, services: { notify: {} },
    states: { "automation.a1": { entity_id: "automation.a1", state: "on", attributes: { friendly_name: "A1" } } },
    connection: { subscribeMessage: async (c) => { c(state); return () => {}; } },
    callWS: async (m) => { calls.push(m); return m.type === "maintenance_mode/get_catalog" ? catalog : state; } };
  w.eval(SRC);
  const el = w.document.createElement("maintenance-mode-panel"); w.document.body.appendChild(el); el.hass = hass; await sleep(40);
  const sr = el.shadowRoot;
  sr.querySelector("[data-tab=settings]").click(); await sleep(30);
  ok(sr.textContent.includes("Étiquettes visées") && sr.textContent.includes("Zones visées") && sr.textContent.includes("Cuisine") && sr.textContent.includes("Confort"), "carte Sélecteurs : étiquettes et zones du catalogue");
  ok(sr.querySelector("input[data-action=toggle-sel-area][data-area=area1]").checked && !sr.querySelector("input[data-action=toggle-sel-area][data-area=area2]").checked, "zone déjà visée : cochée");
  ok(sr.textContent.includes("Aucune sélection individuelle") && !sr.textContent.includes("toutes les automatisations sont coupées"), "message : la zone visée remplace « toutes »");
  sr.querySelector("input[data-action=toggle-sel-area][data-area=area1]").click(); await sleep(20);
  ok(sr.textContent.includes("toutes") && !sr.textContent.includes("Aucune sélection individuelle"), "plus aucun sélecteur : retour au message « toutes »");
  sr.querySelector("input[data-action=toggle-sel-label][data-label=lab1]").click(); await sleep(20);
  sr.querySelector("input[data-action=toggle-sel-area][data-area=area2]").click(); await sleep(20);
  sr.querySelector("[data-action=save-block][data-block=select]").click(); await sleep(30);
  const cfg = calls.filter((c) => c.type === "maintenance_mode/update_config" && "selected_labels" in c).pop();
  ok(cfg && cfg.selected_labels.join() === "lab1" && cfg.selected_areas.join() === "area2", "enregistrement : selected_labels et selected_areas");
  console.log(fail ? `\n${fail} ÉCHEC(S)` : "\nTOUT PASSE"); process.exit(fail ? 1 : 0);
})();
