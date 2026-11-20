const path = require("path");
const WWW = path.join(__dirname, "..", "custom_components", "maintenance_mode", "www");
const { JSDOM } = require("jsdom");
const fs = require("fs");
const SRC = fs.readFileSync(path.join(WWW, "panel.js"), "utf8");
let fail = 0; const ok = (c, m, e) => { if (!c) { fail++; console.log("FAIL:", m, e ?? ""); } else console.log("ok  :", m); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function run(lang, report, fn) {
  const dom = new JSDOM("<!doctype html><body></body>", { url: "http://ha.local/maintenance", runScripts: "outside-only", pretendToBeVisual: true });
  const w = dom.window; w.scrollTo = () => {};
  const h = { hid: "x", start: new Date(Date.now() - 9e6).toISOString(), ended_at: new Date(Date.now() - 8e6).toISOString(), ended_by: "manual", reason: "R", pages: [], repeat: "none" };
  if (report) h.report = report;
  const state = { role: "admin", permissions: ["view", "history"], active: false, current: null, message: "m", upcoming: [], history: [h] };
  const hass = { themes: {}, locale: { language: lang }, localize: () => "", panels: {}, services: { notify: {} }, states: {},
    connection: { subscribeMessage: async (c) => { c(state); return () => {}; } }, callWS: async () => state };
  w.eval(SRC);
  const el = w.document.createElement("maintenance-mode-panel"); w.document.body.appendChild(el); el.hass = hass; await sleep(40);
  await fn(el.shadowRoot); el.remove(); w.close();
}
(async () => {
  await run("fr", { duration: 4320, unavailable: ["sensor.a", "sensor.<b>"], unavailable_total: 25, errors: [{ logger: "homeassistant.x", message: "<img src=x onerror=alert(1)>", count: 3 }], errors_total: 3 }, async (sr) => {
    const d = sr.querySelector("[data-role=report]");
    ok(d && d.querySelector("summary").textContent === "Durée réelle : 1 h 12 · 25 entité(s) devenue(s) indisponible(s) · 3 erreur(s) dans le journal", "résumé du bilan (fr)", d && d.querySelector("summary").textContent);
    ok(d.textContent.includes("sensor.a") && d.textContent.includes("limitée"), "liste d'entités, avec mention de la limite");
    ok(d.textContent.includes("×3") && !d.querySelector("img"), "erreur comptée ×3 et texte échappé (pas d'injection HTML)");
  });
  await run("fr", { duration: 120, unavailable: [], unavailable_total: 0, errors: [], errors_total: 0 }, async (sr) => {
    ok(sr.querySelector("[data-role=report] summary").textContent === "Durée réelle : 2 min · rien à signaler", "bilan vide : « rien à signaler »");
  });
  await run("en", { duration: 60, unavailable: ["sensor.a"], unavailable_total: 1, errors: [], errors_total: 0 }, async (sr) => {
    ok(sr.querySelector("[data-role=report] summary").textContent.startsWith("Actual duration: 1 min · 1 entit"), "résumé du bilan (en)");
  });
  await run("fr", null, async (sr) => { ok(!sr.querySelector("[data-role=report]"), "ancienne entrée sans bilan : rien d'affiché"); });
  console.log(fail ? `\n${fail} ÉCHEC(S)` : "\nTOUT PASSE"); process.exit(fail ? 1 : 0);
})();
