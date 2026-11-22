// Enregistrer une carte de Paramètres ne doit PAS ramener la page en haut.
const path = require("path");
const WWW = path.join(__dirname, "..", "custom_components", "maintenance_mode", "www");
const { JSDOM } = require("jsdom");
const fs = require("fs");
const SRC = fs.readFileSync(path.join(WWW, "panel.js"), "utf8");
let fail = 0; const ok = (c, m, e) => { if (!c) { fail++; console.log("FAIL:", m, e ?? ""); } else console.log("ok  :", m); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  const dom = new JSDOM("<!doctype html><body><div id=host></div></body>", { url: "http://ha.local/maintenance", runScripts: "outside-only", pretendToBeVisual: true });
  const w = dom.window; const scrolls = []; w.scrollTo = (x, y) => { scrolls.push(y); };
  const calls = []; let push;
  const state = { role: "admin", permissions: ["view", "settings"], active: false, current: null, message: "m", upcoming: [],
    config: { automations: [], allowed_users: [], warn_minutes: 15, end_soon_minutes: 10, message: "Bonjour", notify_services: [], notify_kinds: ["pre"], banner_mode: "bar", banner_scroll: true,
      compat_mode: false, max_duration_minutes: 0, confirm_threshold: 20, blackouts: [], excluded_automations: [], excluded_labels: [], selected_labels: [], selected_areas: [], templates: [], hooks: [] }, users: [] };
  const hass = { themes: {}, locale: { language: "fr" }, localize: () => "", panels: {}, services: { notify: { mobile_app_x: {} } },
    states: { "automation.a1": { entity_id: "automation.a1", state: "on", attributes: { friendly_name: "A1" } } },
    connection: { subscribeMessage: async (c) => { push = c; c(JSON.parse(JSON.stringify(state))); return () => {}; } },
    callWS: async (m) => {
      calls.push(m);
      if (m.type === "maintenance_mode/get_catalog") return { labels: [], areas: [] };
      if (m.type === "maintenance_mode/update_config") { const { type, ...c } = m; Object.assign(state.config, c); }
      return JSON.parse(JSON.stringify(state));
    } };
  w.eval(SRC);
  const parent = w.document.getElementById("host");
  const el = w.document.createElement("maintenance-mode-panel"); parent.appendChild(el); el.hass = hass; await sleep(40);
  const sr = el.shadowRoot; const q = (s) => sr.querySelector(s);
  q("[data-tab=settings]").click(); await sleep(40);

  // l'utilisateur a fait défiler la page jusqu'à la carte « bandeau »
  const sc = () => q(".scroll");
  sc().scrollTop = 640; [...sr.querySelectorAll(".list")].forEach((l, i) => { l.scrollTop = 20 + i; });
  parent.scrollTop = 55; el.scrollTop = 33;
  const lists = () => [...sr.querySelectorAll(".list")].map((l) => l.scrollTop).join();
  const before = lists();
  const sel = q("select[data-action=banner-mode]"); sel.value = "card"; sel.dispatchEvent(new w.Event("change", { bubbles: true })); await sleep(10);
  ok(sc().scrollTop === 640, "choisir une valeur (rendu sans enregistrement) : la page reste où elle est", sc().scrollTop);
  q("[data-action=save-block][data-block=banner]").click();
  for (const ms of [0, 5, 20, 60, 150]) {
    await sleep(ms);
    ok(sc().scrollTop === 640, `après enregistrement (+${ms} ms) : défilement de la page conservé`, sc().scrollTop);
  }
  ok(parent.scrollTop === 55 && el.scrollTop === 33, "défilement du conteneur parent et de l'élément conservé", [parent.scrollTop, el.scrollTop]);
  ok(lists() === before, "listes internes : défilement conservé", lists());
  ok(calls.some((c) => c.type === "maintenance_mode/update_config" && c.banner_mode === "card"), "l'enregistrement a bien été envoyé");

  // le serveur pousse l'état (autre onglet, évènement) juste après : même chose
  push(JSON.parse(JSON.stringify(state))); await sleep(30);
  ok(sc().scrollTop === 640, "mise à jour poussée par le serveur : défilement conservé", sc().scrollTop);
  // ---- le focus rendu après un rendu doit revenir au MÊME élément (focus() fait défiler jusqu'à lui)
  const focusCalls = []; const realFocus = w.HTMLElement.prototype.focus;
  w.HTMLElement.prototype.focus = function (opts) { focusCalls.push({ el: this, opts }); return realFocus.call(this, opts); };
  // deux cartes modifiées : « page » (en haut) et « bandeau » ; on enregistre « bandeau »
  const msg = q("[data-field='draft.message']"); msg.value = "Autre"; msg.dispatchEvent(new w.Event("input", { bubbles: true }));
  const sel2 = q("select[data-action=banner-mode]"); sel2.value = "bar"; sel2.dispatchEvent(new w.Event("change", { bubbles: true })); await sleep(10);
  ok(!q("[data-action=save-block][data-block=page]").disabled, "carte « page » modifiée (son bouton est actif)");
  focusCalls.length = 0;
  const saveBanner = q("[data-action=save-block][data-block=banner]"); saveBanner.focus(); focusCalls.length = 0; saveBanner.click(); await sleep(60);
  const active = sr.activeElement;
  ok(!(active && active.dataset.block === "page"), "après « Enregistrer » sur la carte bandeau, le focus ne saute pas au bouton de la carte « page »", active && active.outerHTML.slice(0, 80));
  ok(focusCalls.filter((c) => c.el.dataset?.block === "page").length === 0, "…et aucun focus() n'est donné au bouton de la carte « page » (ce serait un saut en haut de page)");

  // plusieurs hooks : changer le moment du 3e ne doit pas redonner le focus au 1er
  q("[data-action=save-block][data-block=page]").click(); await sleep(40);
  state.config.hooks = [1, 2, 3].map((i) => ({ id: "h" + i, name: "H" + i, when: "after_start", entity_id: "script.s" + i, timeout: 30, on_failure: "continue" }));
  push(JSON.parse(JSON.stringify(state))); await sleep(30);
  const whens = () => [...sr.querySelectorAll("select[data-action=hk-when]")];
  ok(whens().length === 3, "trois hooks affichés");
  const third = whens()[2]; third.focus(); focusCalls.length = 0; third.value = "before_end"; third.dispatchEvent(new w.Event("change", { bubbles: true })); await sleep(30);
  ok(sr.activeElement === whens()[2], "changer le moment du 3e hook : le focus reste sur le 3e (pas sur le 1er)", sr.activeElement && sr.activeElement.dataset.idx);
  ok(focusCalls.length > 0 && focusCalls.every((c) => c.opts && c.opts.preventScroll === true), "tout focus() rendu après un rendu se fait sans faire défiler (preventScroll)", focusCalls.map((c) => JSON.stringify(c.opts)).join());
  console.log(fail ? `\n${fail} ÉCHEC(S)` : "\nTOUT PASSE"); process.exit(fail ? 1 : 0);
})();
