const path = require("path");
const WWW = path.join(__dirname, "..", "custom_components", "maintenance_mode", "www");
const { JSDOM } = require("jsdom");
const fs = require("fs");
const SRC = fs.readFileSync(path.join(WWW, "overlay.js"), "utf8");
let fail = 0; const ok = (c, m) => { if (!c) { fail++; console.log("FAIL:", m); } else console.log("ok  :", m); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const tick = () => sleep(1150);

const cur = (o = {}) => ({ id: "c1", start: new Date(Date.now() - 6e4).toISOString(), end: new Date(Date.now() + 36e5).toISOString(), reason: "Refonte", pages: [], pause_automations: true, ...o });
const nxt = (o = {}) => ({ id: "n1", start: new Date(Date.now() + 5 * 6e4).toISOString(), end: new Date(Date.now() + 36e5).toISOString(), reason: "MAJ", pages: ["config/devices"], ...o });

function env({ attrs = {}, state = "on", user = { id: "adm", is_owner: false }, sidebar = null, wsCalls = [], userData = null, noMain = false } = {}) {
  const dom = new JSDOM("<!doctype html><body></body>", { url: "http://ha.local/lovelace/0", runScripts: "outside-only", pretendToBeVisual: true });
  const w = dom.window;
  const base = { maintenance_mode_entity: true, exempt_users: ["adm"], message: "M", warn_minutes: 15, current: cur(), next: null,
    panel_hidden_for: [], banner_mode: "bar", banner_scroll: true };
  const ha = w.document.createElement("home-assistant");
  const mkHass = (s, a, u = user) => ({ user: u, locale: { language: "fr" }, panels: { map: { url_path: "map", title: "map" } }, localize: (k) => (k === "panel.map" ? "Carte" : ""),
    states: { "switch.m": { entity_id: "switch.m", state: s, attributes: { ...base, ...a } } },
    callWS: async (m) => { wsCalls.push(m); if (m.type === "frontend/get_user_data") return { value: userData }; return null; } });
  ha.hass = mkHass(state, attrs);
  ha.style.setProperty("direction", "ltr");   // style posé par Home Assistant : doit survivre
  w.document.body.appendChild(ha);
  // hauteur simulée de la barre + largeurs pour le test de défilement
  w.__barH = 40; w.__scrollY = 0; w.__scrollCalls = []; w.__ro = [];
  w.Element.prototype.getBoundingClientRect = function () { return { height: this.id === "maintenance-bar" ? w.__barH : 0, width: 0, left: 0, right: 0, top: 0, bottom: 0 }; };
  w.ResizeObserver = class { constructor(cb) { this.cb = cb; w.__ro.push(this); } observe() {} disconnect() { this.off = true; } };
  Object.defineProperty(w, "scrollY", { configurable: true, get() { return w.__scrollY; } });
  w.scrollTo = (x, y) => { w.__scrollCalls.push([x, y]); w.__scrollY = 0; };
  const hsr = ha.attachShadow({ mode: "open" });
  const hmain = w.document.createElement("home-assistant-main"); hsr.appendChild(hmain);
  w.__main = hmain;
  if (noMain) hmain.remove();
  if (sidebar) sidebar(w, ha);
  w.eval(SRC);
  return { w, ha, set: (s, a, u) => { ha.hass = mkHass(s, a, u); w.dispatchEvent(new w.Event("focus")); }, q: (id) => w.document.getElementById(id) };
}

(async () => {
  // ------------------------------------------------ BANDEAU
  let e = env({ attrs: { current: cur({ pages: ["map"] }), banner_mode: "bar" } }); e.w.history.pushState(null, "", "/map");
  await tick();
  let bar = e.q("maintenance-bar");
  ok(bar && bar.classList.contains("active"), "mode bar : bandeau « actif » présent pour un utilisateur non bloqué");
  ok(bar.textContent.includes("Mode maintenance actif") && bar.textContent.includes("Motif : Refonte") && bar.textContent.includes("Fin prévue") && bar.textContent.includes("Carte"), "texte : état, motif, fin prévue, nom de page (pas le chemin)");
  ok(!e.q("maintenance-banner"), "pas de carte en mode bar");
  ok(e.ha.style.display === "block" && e.ha.style.position === "fixed" && e.ha.style.top === "40px" && e.ha.style.bottom === "0px" && /^translateZ\(0(px)?\)$/.test(e.ha.style.transform),
     "home-assistant devient une boîte fixe sous le bandeau (display:block, top:40px) — un élément « inline » ignorerait un transform");
  ok(bar.querySelector(".btn").style.display === "" , "bouton « Ouvrir le panneau » visible");
  ok(e.ha.style.overflow === "hidden" && e.w.document.documentElement.style.overflow === "hidden", "le document ne peut plus défiler (overflow masqué sur l'interface et la page)");
  const mainSt = e.w.__main.style;
  ok(mainSt.overflow === "auto" && mainSt.height === "100%" && mainSt.maxHeight === "100%" && mainSt.minHeight === "0px" && mainSt.display === "block",
     "le défilement passe dans home-assistant-main (le contenu reste défilable)");
  // la barre grandit (retour à la ligne, fenêtre étroite…) : le décalage suit immédiatement via ResizeObserver
  e.w.__barH = 90; e.w.__ro.forEach((r) => !r.off && r.cb()); 
  ok(e.ha.style.top === "90px", "taille de la barre modifiée : décalage recalé sans attendre");
  e.w.__barH = 40; e.w.__ro.forEach((r) => !r.off && r.cb());
  // le document a glissé sous le bandeau (molette, focus…) : on le remet en haut au tick suivant
  e.w.__scrollY = 35; await tick();
  ok(e.w.__scrollCalls.some(([x, y]) => x === 0 && y === 0) && e.w.__scrollY === 0, "document remis en haut s'il avait glissé sous le bandeau");

  // fin de maintenance -> le bandeau disparaît et la page retrouve sa place
  e.set("off", { current: null, next: null }); await tick();
  ok(!e.q("maintenance-bar") && e.ha.style.transform === "" && e.ha.style.position === "" && e.ha.style.display === "" && e.ha.style.top === "", "fin de maintenance : bandeau retiré, tous les styles d'origine restaurés");
  ok(e.ha.style.getPropertyValue("direction") === "ltr", "les styles posés par Home Assistant sont conservés");
  ok(e.w.__main.style.overflow === "" && e.w.__main.style.height === "" && e.w.__main.style.display === "", "home-assistant-main : styles d'origine restaurés");
  ok(e.ha.style.overflow === "" && e.w.document.documentElement.style.overflow === "" && e.w.__ro.every((r) => r.off), "styles d'origine restaurés, observateur arrêté");

  // préavis (maintenance à venir) en bandeau
  e.set("off", { current: null, next: nxt() }); await tick();
  bar = e.q("maintenance-bar");
  ok(bar && bar.classList.contains("upcoming") && bar.textContent.includes("Maintenance prévue") && bar.textContent.includes("Paramètres › Appareils"), "préavis en bandeau avec noms de pages");
  ok(!e.q("maintenance-toast"), "pas de petite carte en mode bar");
  // fermer
  bar.querySelector(".close").click(); await tick();
  ok(!e.q("maintenance-bar") && e.ha.style.transform === "", "fermeture : bandeau retiré et décalage annulé");
  ok(!e.q("maintenance-bar"), "…et il ne revient pas dans la session");
  e.w.close();

  // structure inconnue : le bandeau s'affiche mais la page n'est PAS touchée (rien ne casse)
  e = env({ noMain: true }); await tick();
  ok(e.q("maintenance-bar") && e.ha.style.position === "" && e.ha.style.display === "" && e.w.document.documentElement.style.overflow === "", "structure non reconnue : bandeau affiché, interface intacte");
  e.w.close();

  // mode carte
  e = env({ attrs: { banner_mode: "card" } }); await tick();
  ok(e.q("maintenance-banner") && !e.q("maintenance-bar") && e.ha.style.transform === "", "mode card : ancienne carte, aucun bandeau ni décalage");
  e.set("off", { banner_mode: "card", current: null, next: nxt() }); await tick();
  ok(e.q("maintenance-toast") && !e.q("maintenance-bar"), "mode card : préavis en petite carte");
  e.w.close();

  // utilisateur bloqué : blocage, pas de bandeau
  e = env({ user: { id: "bob", is_owner: false } }); await tick();
  ok(e.q("maintenance-overlay") && !e.q("maintenance-bar"), "utilisateur bloqué : page de maintenance, pas de bandeau");
  e.w.close();

  // ------------------------------------------------ DÉFILEMENT
  const withWidths = (trackW, viewW) => (w) => {
    Object.defineProperty(w.HTMLElement.prototype, "offsetWidth", { configurable: true, get() { return this.classList?.contains("track") ? trackW : 0; } });
    Object.defineProperty(w.HTMLElement.prototype, "clientWidth", { configurable: true, get() { return this.classList?.contains("viewport") ? viewW : 0; } });
  };
  for (const [label, scrollOpt, trackW, expected] of [
    ["texte trop long + défilement activé", true, 900, "scroll"],
    ["texte trop long + défilement désactivé", false, 900, "wrap"],
    ["texte qui tient", true, 100, "none"],
  ]) {
    e = env({ attrs: { banner_scroll: scrollOpt }, sidebar: (w) => withWidths(trackW, 400)(w) }); await tick();
    const vp = e.q("maintenance-bar").querySelector(".viewport");
    const got = vp.classList.contains("scroll") ? "scroll" : vp.classList.contains("wrap") ? "wrap" : "none";
    ok(got === expected, `${label} → ${expected}`);
    if (expected === "scroll") ok(vp.style.getPropertyValue("--dur") === "15s", "durée d'animation proportionnelle à la longueur (15 s)");
    e.w.close();
  }

  // ------------------------------------------------ BARRE LATÉRALE
  const buildSidebar = (variant) => (w, ha) => {
    const main = w.__main || ha.shadowRoot.querySelector("home-assistant-main") || (() => { const m = w.document.createElement("home-assistant-main"); ha.shadowRoot.appendChild(m); return m; })();
    const msr = main.shadowRoot || main.attachShadow({ mode: "open" });
    const drawer = w.document.createElement("ha-drawer"); msr.appendChild(drawer);
    const sb = w.document.createElement("ha-sidebar"); drawer.appendChild(sb);
    const ssr = sb.attachShadow({ mode: "open" });
    if (variant === "attr") ssr.innerHTML = '<a data-panel="maintenance" href="/maintenance">M</a><a data-panel="map" href="/map">Carte</a>';
    if (variant === "prop") {
      const it = w.document.createElement("ha-md-list-item"); it.href = "/maintenance"; ssr.appendChild(it);
      const other = w.document.createElement("ha-md-list-item"); other.href = "/map"; ssr.appendChild(other);
    }
    if (variant === "nested") {
      const wrap = w.document.createElement("ha-sidebar-list"); ssr.appendChild(wrap);
      const wsr = wrap.attachShadow({ mode: "open" });
      wsr.innerHTML = '<ha-md-list-item data-panel="maintenance"></ha-md-list-item><ha-md-list-item data-panel="map"></ha-md-list-item>';
    }
    w.__ssr = ssr;
  };
  const isHidden = (el) => el && el.style.display === "none";
  const items = (w) => [...w.__ssr.querySelectorAll("*")];

  for (const variant of ["attr", "prop", "nested"]) {
    e = env({ attrs: { panel_hidden_for: ["adm"] }, sidebar: buildSidebar(variant), state: "off", user: { id: "adm", is_owner: false } }); await tick();
    let list;
    if (variant === "nested") list = [...e.w.__ssr.querySelector("ha-sidebar-list").shadowRoot.children];
    else list = items(e.w);
    const mine = list.find((n) => n.getAttribute("data-panel") === "maintenance" || n.getAttribute("href") === "/maintenance" || n.href === "/maintenance");
    const other = list.find((n) => n.getAttribute("data-panel") === "map" || n.getAttribute("href") === "/map" || n.href === "/map");
    ok(isHidden(mine), `variante « ${variant} » : entrée Maintenance masquée`);
    ok(other && !isHidden(other), `variante « ${variant} » : les autres entrées restent visibles`);
    if (variant === "attr") {
      // le menu se re-rend (nouvel élément) -> toujours masqué
      e.w.__ssr.innerHTML = '<a data-panel="maintenance" href="/maintenance">M2</a><a data-panel="map" href="/map">Carte</a>';
      await sleep(50);
      ok(isHidden(e.w.__ssr.querySelector('[data-panel="maintenance"]')), "re-rendu du menu : l'entrée est de nouveau masquée (MutationObserver)");
      // l'utilisateur retrouve l'accès -> réaffichée
      e.set("off", { panel_hidden_for: [] }); await tick();
      ok(!isHidden(e.w.__ssr.querySelector('[data-panel="maintenance"]')), "accès rendu : entrée réaffichée");
    }
    e.w.close();
  }
  e = env({ attrs: { panel_hidden_for: ["adm"] }, sidebar: buildSidebar("attr"), state: "off", user: { id: "own", is_owner: true } }); await tick();
  ok(!isHidden(e.w.__ssr.querySelector('[data-panel="maintenance"]')), "le propriétaire n'est jamais masqué");
  e.w.close();

  // ------------------------------------------------ PRÉFÉRENCE NATIVE (panneaux masqués)
  let calls = [];
  e = env({ attrs: { panel_hidden_for: ["adm"] }, state: "off", wsCalls: calls, userData: { panelOrder: ["map"], hiddenPanels: ["logbook"] } }); await tick();
  const set = calls.find((c) => c.type === "frontend/set_user_data");
  ok(set && set.key === "sidebar" && set.value.hiddenPanels.join() === "logbook,maintenance" && set.value.panelOrder.join() === "map", "préférence : « maintenance » ajouté aux panneaux masqués (autres réglages conservés)");
  ok(e.w.localStorage.getItem("maintenance_mode_hidden:adm") === "1", "marqueur local posé");
  const n1 = calls.filter((c) => c.type === "frontend/set_user_data").length;
  await tick(); await tick();
  ok(calls.filter((c) => c.type === "frontend/set_user_data").length === n1, "pas d'appels répétés à chaque seconde");
  e.w.close();

  calls = [];
  e = env({ attrs: { panel_hidden_for: [] }, state: "off", wsCalls: calls, userData: { hiddenPanels: ["maintenance", "logbook"] } }); await tick();
  ok(!calls.some((c) => c.type === "frontend/set_user_data"), "masqué par l'utilisateur lui-même (pas de marqueur) : on n'y touche pas");
  e.w.close();

  calls = [];
  e = env({ attrs: { panel_hidden_for: [] }, state: "off", wsCalls: calls, userData: { hiddenPanels: ["maintenance", "logbook"] } });
  e.w.localStorage.setItem("maintenance_mode_hidden:adm", "1"); await tick();
  const unset = calls.find((c) => c.type === "frontend/set_user_data");
  ok(unset && unset.value.hiddenPanels.join() === "logbook" && e.w.localStorage.getItem("maintenance_mode_hidden:adm") === null, "accès rendu : on retire seulement ce que nous avions masqué");
  e.w.close();

  console.log(fail ? `\n${fail} ÉCHEC(S)` : "\nTOUT PASSE"); process.exit(fail ? 1 : 0);
})();
