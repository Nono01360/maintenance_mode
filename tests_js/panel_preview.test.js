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
  const state = { role: "admin", permissions: ["view", "control", "schedule"], active: false, current: null, message: "m", upcoming: [], config: { templates: [] } };
  const result = { pause_automations: true, scope: "all", pages: [], suspend: ["automation.a1"], protected: ["automation.a2"], inactive: ["automation.a3"],
    blocked_users: ["Bob"], notifications: { services: 2, kinds: ["pre"] } };
  const hass = { themes: {}, locale: { language: "fr" }, localize: () => "", panels: { map: { url_path: "map", title: "map" } }, services: { notify: {} },
    states: { "automation.a1": { entity_id: "automation.a1", state: "on", attributes: { friendly_name: "Lumières salon" } } },
    connection: { subscribeMessage: async (c) => { c(state); return () => {}; } },
    callWS: async (m) => { calls.push(m); if (m.type === "maintenance_mode/preview") return result; return state; } };
  w.eval(SRC);
  const el = w.document.createElement("maintenance-mode-panel"); w.document.body.appendChild(el); el.hass = hass; await sleep(40);
  const sr = el.shadowRoot;
  sr.querySelector("[data-action=start-now]").click(); await sleep(15);
  ok(!sr.textContent.includes("Aperçu — aucun effet"), "aucun aperçu tant qu'on ne le demande pas");
  sr.querySelector("[data-action=preview-form]").click(); await sleep(30);
  const call = calls.find((c) => c.type === "maintenance_mode/preview");
  ok(call && call.pause_automations === true && call.pages.length === 0, "aperçu demandé avec la portée et l'option du formulaire");
  ok(!calls.some((c) => c.type === "maintenance_mode/start"), "l'aperçu ne démarre rien");
  const t = sr.textContent;
  ok(t.includes("Seront suspendues (1)") && t.includes("Lumières salon") && t.includes("Protégées, jamais suspendues (1)") && t.includes("automation.a2") && t.includes("Déjà éteintes, laissées telles quelles (1)") && t.includes("Utilisateurs bloqués (1)") && t.includes("Bob"), "listes suspendues / protégées / éteintes / bloqués");
  ok(t.includes("Portée : tout Home Assistant") && t.includes("Notifications push : 2 service(s)"), "portée et notifications");
  // changer la portée invalide l'aperçu
  sr.querySelector("input[data-action=scope][value=pages]").click(); await sleep(20);
  ok(!sr.textContent.includes("Aperçu — aucun effet"), "changer la portée efface l'aperçu devenu faux");
  // sans suspension
  sr.querySelector("input[data-action=form-pause]").click(); await sleep(15);
  result.pause_automations = false; result.scope = "pages"; result.pages = ["map"];
  sr.querySelector("input[data-action=toggle-page][data-page=map]").click(); await sleep(15);
  sr.querySelector("[data-action=preview-form]").click(); await sleep(30);
  const c2 = calls.filter((c) => c.type === "maintenance_mode/preview").pop();
  ok(c2.pause_automations === false && c2.pages.join() === "map", "aperçu avec pages choisies et sans suspension");
  ok(sr.textContent.includes("ne seront pas suspendues") && sr.textContent.includes("Portée : map") && !sr.textContent.includes("Seront suspendues"), "texte adapté sans suspension");
  sr.querySelector("[data-action=cancel-form]").click(); await sleep(15);
  sr.querySelector("[data-action=start-now]").click(); await sleep(15);
  ok(!sr.textContent.includes("Aperçu — aucun effet"), "nouveau formulaire : aperçu effacé");
  console.log(fail ? `\n${fail} ÉCHEC(S)` : "\nTOUT PASSE"); process.exit(fail ? 1 : 0);
})();
