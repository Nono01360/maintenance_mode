const path = require("path");
const WWW = path.join(__dirname, "..", "custom_components", "maintenance_mode", "www");
const { JSDOM } = require("jsdom");
const fs = require("fs");
const SRC = fs.readFileSync(path.join(WWW, "overlay.js"), "utf8");
let fail = 0; const ok = (c, m, e) => { if (!c) { fail++; console.log("FAIL:", m, e ?? ""); } else console.log("ok  :", m); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function env({ compat }) {
  const dom = new JSDOM("<!doctype html><body></body>", { url: "http://ha.local/lovelace/0", runScripts: "outside-only", pretendToBeVisual: true });
  const w = dom.window; w.scrollTo = () => {};
  const ha = w.document.createElement("home-assistant");
  const cur = { id: "c", start: new Date(Date.now() - 6e4).toISOString(), end: null, reason: "R", pages: [], pause_automations: true };
  const st = { attrs: { maintenance_mode_entity: true, rights_rev: "r1", current: cur, next: null, banner_mode: "bar", banner_scroll: false, message: "M", compat_mode: compat } };
  ha.hass = { user: { id: "adm", is_owner: false }, locale: { language: "fr" }, config: {}, panels: {}, localize: () => "",
    callWS: async (m) => (m.type === "maintenance_mode/get_client" ? { exempt: true, panel_hidden: true } : { value: null }),
    states: { get "switch.m"() { return { entity_id: "switch.m", state: "on", attributes: st.attrs }; } } };
  ha.style.setProperty("direction", "ltr");
  w.document.body.appendChild(ha);
  w.Element.prototype.getBoundingClientRect = function () { return { height: this.id === "maintenance-bar" ? 40 : 0, width: 0, left: 0, right: 0, top: 0, bottom: 0 }; };
  const hsr = ha.attachShadow({ mode: "open" }); const main = w.document.createElement("home-assistant-main"); hsr.appendChild(main);
  const msr = main.attachShadow({ mode: "open" }); const sb = w.document.createElement("ha-sidebar"); msr.appendChild(sb);
  const ssr = sb.attachShadow({ mode: "open" }); ssr.innerHTML = '<a data-panel="maintenance" href="/maintenance">M</a><a data-panel="map" href="/map">Carte</a>';
  w.eval(SRC);
  return { w, ha, main, ssr, st, q: (id) => w.document.getElementById(id) };
}
const untouched = (e) => e.ha.style.position === "" && e.ha.style.transform === "" && e.ha.style.display === "" && e.main.style.overflow === "" && e.w.document.documentElement.style.overflow === "";

(async () => {
  // mode normal : la page est décalée, le menu masqué, le diagnostic le dit
  let e = env({ compat: false });
  await sleep(1300);
  ok(!!e.q("maintenance-bar") && e.ha.style.position === "fixed", "mode normal : bandeau et page décalée");
  ok(e.ssr.querySelector('[data-panel="maintenance"]').style.display === "none", "mode normal : entrée de menu masquée");
  let d = e.w.__maintenanceModeCompat;
  ok(d && d.enabled === true && d.main === true && d.sidebar === true && d.pushed === true && d.menuHidden === true, "diagnostic : structure reconnue, page décalée, menu masqué", JSON.stringify(d));

  // bascule en cours de route vers le mode compatibilité : tout est restauré
  e.st.attrs = { ...e.st.attrs, compat_mode: true };
  await sleep(1300);
  ok(untouched(e) && e.ha.style.getPropertyValue("direction") === "ltr", "passage en mode compatibilité : styles d'origine restaurés (et ceux de HA conservés)");
  ok(e.ssr.querySelector('[data-panel="maintenance"]').style.display === "", "passage en mode compatibilité : entrée de menu réaffichée");
  ok(!e.q("maintenance-bar") && !!e.q("maintenance-banner"), "passage en mode compatibilité : petite carte à la place du bandeau");
  d = e.w.__maintenanceModeCompat;
  ok(d.enabled === false && d.main === null && d.pushed === false && d.menuHidden === false, "diagnostic : mode compatibilité actif, rien d'appliqué", JSON.stringify(d));
  // retour
  e.st.attrs = { ...e.st.attrs, compat_mode: false };
  await sleep(1300);
  ok(!!e.q("maintenance-bar") && e.ha.style.position === "fixed", "retour au mode normal : bandeau et décalage de nouveau appliqués");
  e.w.close();

  // démarrage direct en mode compatibilité : la structure de HA n'est jamais touchée
  e = env({ compat: true });
  await sleep(1300);
  ok(untouched(e) && e.ssr.querySelector('[data-panel="maintenance"]').style.display === "" && !!e.q("maintenance-banner") && !e.q("maintenance-bar"),
     "démarrage en mode compatibilité : aucune modification du DOM de Home Assistant, carte affichée");
  e.w.close();

  console.log(fail ? `\n${fail} ÉCHEC(S)` : "\nTOUT PASSE"); process.exit(fail ? 1 : 0);
})();
