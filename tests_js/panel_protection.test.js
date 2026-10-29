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
    config: { automations: ["automation.a1", "automation.a2"], allowed_users: [], warn_minutes: 15, end_soon_minutes: 10, message: "m", notify_services: [], notify_kinds: ["pre"],
      banner_mode: "bar", banner_scroll: true, compat_mode: false, excluded_automations: ["automation.a2"], excluded_labels: [] }, users: [] };
  const catalog = { labels: [{ id: "lab1", name: "Sécurité", automations: ["automation.a1"] }, { id: "lab2", name: "Autre", automations: [] }] };
  const hass = { themes: {}, locale: { language: "fr" }, localize: () => "", panels: {}, services: { notify: {} },
    states: { "automation.a1": { entity_id: "automation.a1", state: "on", attributes: { friendly_name: "A1" } }, "automation.a2": { entity_id: "automation.a2", state: "on", attributes: { friendly_name: "A2" } },
      "automation.a3": { entity_id: "automation.a3", state: "on", attributes: { friendly_name: "A3" } } },
    connection: { subscribeMessage: async (c) => { c(state); return () => {}; } },
    callWS: async (m) => { calls.push(m); return m.type === "maintenance_mode/get_catalog" ? catalog : state; } };
  w.eval(SRC);
  const el = w.document.createElement("maintenance-mode-panel"); w.document.body.appendChild(el); el.hass = hass; await sleep(40);
  const sr = el.shadowRoot;
  sr.querySelector("[data-tab=settings]").click(); await sleep(30);
  ok(calls.some((c) => c.type === "maintenance_mode/get_catalog"), "ouverture des paramètres : catalogue d'étiquettes demandé au serveur");
  ok(sr.textContent.includes("Protections") && sr.textContent.includes("Sécurité") && sr.textContent.includes("Autre"), "carte Protections avec les étiquettes");
  ok(sr.querySelector("input[data-action=toggle-excl-auto][data-id='automation.a2']").checked, "automatisation déjà protégée : cochée");
  ok(sr.textContent.includes("1 automatisation(s) sélectionnée(s) mais protégée(s)"), "avertissement : a2 est sélectionnée ET protégée");
  // protéger une étiquette : a1 (sélectionnée) devient protégée -> 2 conflits
  const box = sr.querySelector("input[data-action=toggle-excl-label][data-label='lab1']"); box.click(); await sleep(20);
  ok(sr.textContent.includes("2 automatisation(s) sélectionnée(s) mais protégée(s)"), "étiquette protégée : ses automatisations sélectionnées sont signalées");
  const chips = [...sr.querySelectorAll(".chip")].filter((c) => c.textContent.trim() === "protégée").length;
  ok(chips === 2, "badge « protégée » sur chaque automatisation concernée dans la liste de sélection", chips);
  sr.querySelector("[data-action=save-settings]").click(); await sleep(30);
  const cfg = calls.filter((c) => c.type === "maintenance_mode/update_config" && "excluded_labels" in c).pop();
  ok(cfg && cfg.excluded_labels.join() === "lab1" && cfg.excluded_automations.join() === "automation.a2", "enregistrement : excluded_labels et excluded_automations");
  console.log(fail ? `\n${fail} ÉCHEC(S)` : "\nTOUT PASSE"); process.exit(fail ? 1 : 0);
})();
