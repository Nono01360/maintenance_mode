const path = require("path");
const WWW = path.join(__dirname, "..", "custom_components", "maintenance_mode", "www");
const { JSDOM } = require("jsdom");
const fs = require("fs");
const SRC = fs.readFileSync(path.join(WWW, "panel.js"), "utf8");
let fail = 0; const ok = (c, m, e) => { if (!c) { fail++; console.log("FAIL:", m, e ?? ""); } else console.log("ok  :", m); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const now = Date.now();

async function run(lang, rejection) {
  const dom = new JSDOM("<!doctype html><body></body>", { url: "http://ha.local/maintenance", runScripts: "outside-only", pretendToBeVisual: true });
  const w = dom.window; w.scrollTo = () => {};
  const state = { role: "admin", permissions: ["view", "control", "schedule"], active: false, current: null, message: "m",
    upcoming: [{ id: "w1", start: new Date(now + 36e5).toISOString(), end: new Date(now + 72e5).toISOString(), reason: "R", pages: [], pause_automations: true, repeat: "none" }], config: { templates: [] } };
  const hass = { themes: {}, locale: { language: lang }, localize: () => "", panels: {}, services: { notify: {} }, states: {},
    connection: { subscribeMessage: async (c) => { c(state); return () => {}; } },
    callWS: async () => { throw rejection; } };
  w.eval(SRC);
  const el = w.document.createElement("maintenance-mode-panel"); w.document.body.appendChild(el); el.hass = hass; await sleep(40);
  const sr = el.shadowRoot;
  sr.querySelector("[data-action=start-now]").click(); await sleep(15);
  sr.querySelector("[data-action=save-form]").click(); await sleep(20);
  const text = sr.querySelector(".banner.error")?.textContent.trim() ?? "";
  el.remove(); w.close(); return text;
}

(async () => {
  const err = { code: "invalid", message: "Message du serveur", translation_key: "reason_too_long", translation_domain: "maintenance_mode", translation_placeholders: { max: "200" } };
  ok(await run("fr", err) === "Motif trop long (200 caractères max).", "français : message traduit d'après le code, paramètre inséré");
  ok(await run("en", err) === "Reason too long (200 characters max).", "anglais : même code, autre langue");
  ok(await run("fr", { ...err, translation_key: "code_inconnu" }) === "Message du serveur", "code inconnu du panneau : texte du serveur affiché");
  ok(await run("fr", { code: "invalid", message: "Autre erreur" }) === "Autre erreur", "erreur sans code : texte du serveur affiché");
  ok(await run("en", { code: "unauthorized", message: "Access denied.", translation_key: "access_denied" }) === "Access denied.", "refus d'accès traduit");
  console.log(fail ? `\n${fail} ÉCHEC(S)` : "\nTOUT PASSE"); process.exit(fail ? 1 : 0);
})();
