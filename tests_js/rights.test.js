const path = require("path");
const WWW = path.join(__dirname, "..", "custom_components", "maintenance_mode", "www");
const { JSDOM } = require("jsdom");
const fs = require("fs");
const SRC = fs.readFileSync(path.join(WWW, "overlay.js"), "utf8");
let fail = 0; const ok = (c, m, e) => { if (!c) { fail++; console.log("FAIL:", m, e ?? ""); } else console.log("ok  :", m); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function env({ user, answer, rev = "r1" }) {
  const dom = new JSDOM("<!doctype html><body></body>", { url: "http://ha.local/lovelace/0", runScripts: "outside-only", pretendToBeVisual: true });
  const w = dom.window; w.scrollTo = () => {};
  const ha = w.document.createElement("home-assistant");
  const cur = { id: "c", start: new Date(Date.now() - 6e4).toISOString(), end: null, reason: "R", pages: [], pause_automations: true };
  const calls = []; const state = { attrs: { maintenance_mode_entity: true, rights_rev: rev, current: cur, next: null, banner_mode: "bar", banner_scroll: false, message: "M" } };
  const hass = { user, locale: { language: "fr" }, config: {}, panels: {}, localize: () => "",
    callWS: async (m) => { calls.push(m.type); const a = await answer(m); return a; },
    states: { get "switch.m"() { return { entity_id: "switch.m", state: "on", attributes: state.attrs }; } } };
  ha.hass = hass; w.document.body.appendChild(ha);
  w.eval(SRC);
  return { w, calls, state, q: (id) => w.document.getElementById(id) };
}

(async () => {
  // utilisateur ordinaire : demande ses droits une seule fois, puis affiche selon la réponse
  let e = env({ user: { id: "bob", is_owner: false }, answer: async () => ({ exempt: false, panel_hidden: false }) });
  await sleep(300);
  ok(e.calls.filter((c) => c === "maintenance_mode/get_client").length === 1, "droits demandés au serveur (une fois)");
  ok(!!e.q("maintenance-overlay"), "non exempté : page de maintenance, affichée dès la réponse (sans attendre le tick suivant)");
  await sleep(2500);
  ok(e.calls.filter((c) => c === "maintenance_mode/get_client").length === 1, "pas de nouvel appel tant que l'empreinte ne change pas");
  e.state.attrs = { ...e.state.attrs, rights_rev: "r2" }; await sleep(1300);
  ok(e.calls.filter((c) => c === "maintenance_mode/get_client").length === 2, "l'empreinte change : droits redemandés");
  e.w.close();

  // exempté
  e = env({ user: { id: "adm", is_owner: false }, answer: async () => ({ exempt: true, panel_hidden: false }) });
  await sleep(400);
  ok(!e.q("maintenance-overlay") && !!e.q("maintenance-bar"), "exempté : bandeau et pas de blocage");
  e.w.close();

  // propriétaire : droits connus localement, aucun appel
  e = env({ user: { id: "own", is_owner: true }, answer: async () => { throw new Error("ne devrait pas être appelé"); } });
  await sleep(300);
  ok(!e.calls.includes("maintenance_mode/get_client") && !!e.q("maintenance-bar"), "propriétaire : aucune demande de droits au serveur, jamais bloqué");
  e.w.close();

  // réponse lente : rien n'est affiché en attendant (ni blocage ni bandeau)
  let release; const gate = new Promise((r) => { release = r; });
  e = env({ user: { id: "bob", is_owner: false }, answer: async () => { await gate; return { exempt: false, panel_hidden: false }; } });
  await sleep(1300);
  ok(!e.q("maintenance-overlay") && !e.q("maintenance-bar"), "réponse attendue : rien affiché pour l'instant");
  release(); await sleep(200);
  ok(!!e.q("maintenance-overlay"), "réponse reçue : page de maintenance affichée");
  e.w.close();

  // échec du serveur : par prudence, traité comme non exempté ; nouvel essai plus tard
  let n = 0;
  e = env({ user: { id: "bob", is_owner: false }, answer: async () => { n++; if (n === 1) throw new Error("hors ligne"); return { exempt: true, panel_hidden: false }; } });
  await sleep(300);
  ok(!!e.q("maintenance-overlay"), "échec de la demande : l'utilisateur est bloqué par prudence");
  await sleep(5600);
  ok(n >= 2 && !e.q("maintenance-overlay") && !!e.q("maintenance-bar"), "nouvel essai après quelques secondes : droits corrects appliqués", n);
  e.w.close();

  console.log(fail ? `\n${fail} ÉCHEC(S)` : "\nTOUT PASSE"); process.exit(fail ? 1 : 0);
})();
