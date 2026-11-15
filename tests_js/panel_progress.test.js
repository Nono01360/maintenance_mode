const path = require("path");
const WWW = path.join(__dirname, "..", "custom_components", "maintenance_mode", "www");
const { JSDOM } = require("jsdom");
const fs = require("fs");
const SRC = fs.readFileSync(path.join(WWW, "panel.js"), "utf8");
let fail = 0; const ok = (c, m, e) => { if (!c) { fail++; console.log("FAIL:", m, e ?? ""); } else console.log("ok  :", m); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function run(lang, fn) {
  const dom = new JSDOM("<!doctype html><body></body>", { url: "http://ha.local/maintenance", runScripts: "outside-only", pretendToBeVisual: true });
  const w = dom.window; w.scrollTo = () => {}; let cb;
  const base = (progress) => ({ role: "admin", permissions: ["view", "control"], active: false, current: null, message: "m", upcoming: [], disabled_count: 0, ...(progress ? { progress } : {}) });
  const hass = { themes: {}, locale: { language: lang }, localize: () => "", panels: {}, services: { notify: {} }, states: {},
    connection: { subscribeMessage: async (c) => { cb = c; c(base(null)); return () => {}; } }, callWS: async () => base(null) };
  w.eval(SRC);
  const el = w.document.createElement("maintenance-mode-panel"); w.document.body.appendChild(el); el.hass = hass; await sleep(40);
  await fn({ sr: el.shadowRoot, push: async (p) => { cb(base(p)); await sleep(20); } });
  el.remove(); w.close();
}

(async () => {
  await run("fr", async ({ sr, push }) => {
    ok(!sr.querySelector("[data-role=progress]"), "sans progression : aucune carte");
    await push({ phase: "suspend", done: 80, total: 200 });
    const card = sr.querySelector("[data-role=progress]");
    const bar = card && card.querySelector("progress");
    ok(card && bar && bar.max === 200 && bar.value === 80, "progression : barre 80 / 200");
    ok(card.textContent.includes("Suspension des automatisations : 80 / 200"), "texte de suspension (fr)");
    ok(!!bar.getAttribute("aria-label"), "barre étiquetée pour les lecteurs d'écran");
    await push({ phase: "suspend", done: 120, total: 200 });
    ok(sr.querySelector("[data-role=progress] progress").value === 120, "mise à jour poussée : 120 / 200");
    await push({ phase: "resume", done: 40, total: 100 });
    ok(sr.querySelector("[data-role=progress]").textContent.includes("Réactivation des automatisations : 40 / 100"), "texte de réactivation (fr)");
    await push(null);
    ok(!sr.querySelector("[data-role=progress]"), "fin : la carte disparaît");
  });
  await run("en", async ({ sr, push }) => {
    await push({ phase: "suspend", done: 20, total: 60 });
    ok(sr.querySelector("[data-role=progress]").textContent.includes("Pausing automations: 20 / 60"), "texte de suspension (en)");
    await push({ phase: "resume", done: 20, total: 60 });
    ok(sr.querySelector("[data-role=progress]").textContent.includes("Re-enabling automations: 20 / 60"), "texte de réactivation (en)");
  });
  console.log(fail ? `\n${fail} ÉCHEC(S)` : "\nTOUT PASSE"); process.exit(fail ? 1 : 0);
})();
