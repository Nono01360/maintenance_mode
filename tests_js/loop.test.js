const path = require("path");
const WWW = path.join(__dirname, "..", "custom_components", "maintenance_mode", "www");
const { JSDOM } = require("jsdom");
const fs = require("fs");
const SRC = fs.readFileSync(process.env.OVERLAY || path.join(WWW, "overlay.js"), "utf8");
let fail = 0; const ok = (c, m, e) => { if (!c) { fail++; console.log("FAIL:", m, e ?? ""); } else console.log("ok  :", m); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function env({ state = "on", user = { id: "bob", is_owner: false }, attrs = {}, throwingShadow = false } = {}) {
  const dom = new JSDOM("<!doctype html><body></body>", { url: "http://ha.local/lovelace/0", runScripts: "outside-only", pretendToBeVisual: true });
  const w = dom.window; w.scrollTo = () => {};
  const ha = w.document.createElement("home-assistant");
  const cur = { id: "c", start: new Date(Date.now() - 6e4).toISOString(), end: new Date(Date.now() + 36e5).toISOString(), reason: "R", pages: [], pause_automations: true };
  const hass = { user, locale: { language: "fr" }, config: {}, panels: {}, localize: () => "", callWS: async () => null,
    states: { "switch.m": { entity_id: "switch.m", state, attributes: { maintenance_mode_entity: true, exempt_users: ["adm"], panel_hidden_for: [],
      current: state === "on" ? cur : null, next: null, banner_mode: "bar", banner_scroll: false, message: "M", ...attrs } } } };
  const counter = { n: 0 };
  Object.defineProperty(ha, "hass", { get() { counter.n++; return hass; } });
  if (throwingShadow) Object.defineProperty(ha, "shadowRoot", { get() { throw new Error("structure inattendue"); } });
  w.document.body.appendChild(ha);
  w.eval(SRC);
  return { w, ha, counter, q: (id) => w.document.getElementById(id) };
}

(async () => {
  // ---- A. une étape qui échoue n'empêche pas le blocage
  const warn = console.warn; let warns = 0; console.warn = () => { warns++; };
  let e = env({ attrs: { panel_hidden_for: ["bob"] }, throwingShadow: true });
  await sleep(300);
  ok(!!e.q("maintenance-overlay"), "la page de maintenance s'affiche même si la lecture de la structure de HA lève une erreur");
  await sleep(2500);
  console.warn = warn;
  ok(warns <= 2, "l'erreur n'est signalée qu'une fois (pas de flot dans la console)", warns);
  e.w.close();

  // ---- B. onglet masqué : la boucle s'arrête, et repart au retour
  e = env({ state: "off", attrs: { current: null } });
  await sleep(200);
  Object.defineProperty(e.w.document, "hidden", { configurable: true, get: () => true });
  await sleep(2300);                       // laisse passer le tick en cours, qui voit l'onglet masqué
  const before = e.counter.n;
  await sleep(4500);
  ok(e.counter.n === before, "onglet masqué : plus aucune lecture pendant 4,5 s", e.counter.n - before);
  Object.defineProperty(e.w.document, "hidden", { configurable: true, get: () => false });
  e.w.document.dispatchEvent(new e.w.Event("visibilitychange"));
  await sleep(100);
  ok(e.counter.n > before, "retour sur l'onglet : la boucle repart aussitôt");
  e.w.close();

  // ---- C. cadence : lente au repos, rapide quand quelque chose est affiché
  const idle = env({ state: "off", attrs: { current: null } });
  const busy = env({ state: "on", user: { id: "adm", is_owner: false } });       // exempté : bandeau affiché
  await sleep(4300);
  ok(idle.counter.n <= 3, `au repos : au plus 3 lectures en 4,3 s (2 s d'intervalle)`, idle.counter.n);
  ok(busy.counter.n >= 4, `maintenance active : au moins 4 lectures en 4,3 s (1 s d'intervalle)`, busy.counter.n);
  ok(!!busy.q("maintenance-bar"), "le bandeau est bien affiché dans le cas « occupé »");
  idle.w.close(); busy.w.close();

  // ---- D. réveil immédiat : focus et navigation
  e = env({ state: "off", attrs: { current: null } });
  await sleep(100);
  let n0 = e.counter.n;
  e.w.dispatchEvent(new e.w.Event("focus")); await sleep(30);
  ok(e.counter.n > n0, "le focus de la fenêtre relance immédiatement une vérification");
  n0 = e.counter.n;
  e.w.dispatchEvent(new e.w.CustomEvent("location-changed")); await sleep(30);
  ok(e.counter.n > n0, "un changement de page relance immédiatement une vérification");
  e.w.close();

  console.log(fail ? `\n${fail} ÉCHEC(S)` : "\nTOUT PASSE"); process.exit(fail ? 1 : 0);
})();
