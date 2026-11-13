// Paramètres : chaque carte s'enregistre séparément.
const path = require("path");
const WWW = path.join(__dirname, "..", "custom_components", "maintenance_mode", "www");
const { JSDOM } = require("jsdom");
const fs = require("fs");
const SRC = fs.readFileSync(path.join(WWW, "panel.js"), "utf8");
let fail = 0; const ok = (c, m, e) => { if (!c) { fail++; console.log("FAIL:", m, e ?? ""); } else console.log("ok  :", m); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  const dom = new JSDOM("<!doctype html><body></body>", { url: "http://ha.local/maintenance", runScripts: "outside-only", pretendToBeVisual: true });
  const w = dom.window; w.scrollTo = () => {}; const calls = []; let push;
  const state = { role: "admin", permissions: ["view", "settings"], active: false, current: null, message: "m", upcoming: [],
    config: { automations: [], allowed_users: [], warn_minutes: 15, end_soon_minutes: 10, message: "Bonjour", notify_services: [], notify_kinds: ["pre"], banner_mode: "bar", banner_scroll: true,
      compat_mode: false, max_duration_minutes: 0, confirm_threshold: 20, blackouts: [], excluded_automations: [], excluded_labels: [], selected_labels: [], selected_areas: [], templates: [] }, users: [] };
  const hass = { themes: {}, locale: { language: "fr" }, localize: () => "", panels: {}, services: { notify: { mobile_app_x: {} } },
    states: { "automation.a1": { entity_id: "automation.a1", state: "on", attributes: { friendly_name: "A1" } }, "automation.a2": { entity_id: "automation.a2", state: "on", attributes: { friendly_name: "A2" } } },
    connection: { subscribeMessage: async (c) => { push = c; c(JSON.parse(JSON.stringify(state))); return () => {}; } },
    callWS: async (m) => {
      calls.push(m);
      if (m.type === "maintenance_mode/get_catalog") return { labels: [], areas: [] };
      if (m.type === "maintenance_mode/update_config") {
        const { type, ...changes } = m;
        if ("message" in changes) changes.message = String(changes.message).trim();          // le serveur normalise
        Object.assign(state.config, changes);
      }
      return JSON.parse(JSON.stringify(state));
    } };
  w.eval(SRC);
  const el = w.document.createElement("maintenance-mode-panel"); w.document.body.appendChild(el); el.hass = hass; await sleep(40);
  const sr = el.shadowRoot; const q = (s) => sr.querySelector(s);
  const save = (b) => q(`[data-action=save-block][data-block=${b}]`), reset = (b) => q(`[data-action=reset-block][data-block=${b}]`), flag = (b) => q(`[data-block-flag=${b}]`);
  const upd = () => calls.filter((c) => c.type === "maintenance_mode/update_config");
  q("[data-tab=settings]").click(); await sleep(30);

  const blocks = ["page", "autos", "protect", "blackout", "select", "users", "notify", "banner", "compat"];
  ok(blocks.every((b) => save(b) && reset(b) && flag(b)), "chaque carte a son bouton Enregistrer, son bouton Annuler et son indicateur");
  ok(blocks.every((b) => save(b).disabled && reset(b).disabled && flag(b).hidden), "rien de modifié : tous les boutons sont désactivés");
  ok(!q("[data-action=save-settings]") && sr.querySelectorAll("[data-action=save-block]").length === 9, "plus de bouton global : neuf boutons, un par carte");

  // modification d'un champ : seule SA carte s'active, sans refaire le rendu (le focus est conservé)
  const msg = q("[data-field='draft.message']"); msg.focus(); msg.value = "  Nouveau message  "; msg.dispatchEvent(new w.Event("input", { bubbles: true }));
  ok(!save("page").disabled && !reset("page").disabled && !flag("page").hidden, "message modifié : carte « page » activée, indicateur « non enregistré » visible");
  ok(blocks.filter((b) => b !== "page").every((b) => save(b).disabled), "les autres cartes restent désactivées");
  ok(sr.activeElement === msg, "le champ en cours de saisie garde le focus");
  ok(flag("page").textContent.includes("non enregistrées"), "libellé de l'indicateur");

  // deux cartes modifiées ; enregistrer l'une ne touche pas à l'autre
  q("input[data-action=toggle-banner-scroll]").checked = false; q("input[data-action=toggle-banner-scroll]").dispatchEvent(new w.Event("change", { bubbles: true })); await sleep(10);
  ok(!save("banner").disabled && !save("page").disabled, "deux cartes modifiées en même temps");
  save("page").click(); await sleep(30);
  const c1 = upd().pop();
  ok(c1 && c1.message === "  Nouveau message  " && c1.warn_minutes === 15 && c1.max_duration_minutes === 0 && c1.confirm_threshold === 20, "enregistrement de « page » : ses quatre réglages");
  ok(!("banner_scroll" in c1) && !("automations" in c1) && !("compat_mode" in c1) && !("notify_services" in c1), "…et RIEN des autres cartes");
  ok(q("[data-field='draft.message']").value === "Nouveau message", "valeur normalisée par le serveur reprise dans le champ");
  ok(save("page").disabled && flag("page").hidden, "carte « page » de nouveau propre après enregistrement");
  ok(!save("banner").disabled && q("input[data-action=toggle-banner-scroll]").checked === false, "la carte « bandeau » garde sa modification non enregistrée");

  // le serveur pousse un changement pendant qu'une carte est modifiée : la carte modifiée garde ses valeurs, les autres suivent
  state.config.message = "Changé ailleurs"; state.config.warn_minutes = 40; push(JSON.parse(JSON.stringify(state))); await sleep(20);
  ok(el._draft.message === "Changé ailleurs" && el._draft.warn_minutes === 40, "carte propre : son brouillon suit le serveur");
  el._render(true);                                           // (pendant une saisie, l'affichage attend la fin de la saisie : comportement existant)
  ok(q("[data-field='draft.message']").value === "Changé ailleurs" && q("[data-field='draft.warn']").value === "40", "carte propre : l'affichage suit le serveur");
  ok(q("input[data-action=toggle-banner-scroll]").checked === false && !save("banner").disabled, "carte modifiée : ses modifications sont conservées");

  // annuler une carte
  reset("banner").click(); await sleep(20);
  ok(q("input[data-action=toggle-banner-scroll]").checked === true && save("banner").disabled, "« Annuler les modifications » : la carte retrouve les valeurs du serveur");

  // listes de cases à cocher : cocher puis décocher = aucune modification
  const a1 = q("input[data-action=toggle-auto][data-id='automation.a1']"), a2 = q("input[data-action=toggle-auto][data-id='automation.a2']");
  a1.click(); await sleep(5); a2.click(); await sleep(5);
  ok(!save("autos").disabled, "automatisations cochées : carte activée");
  a2.click(); await sleep(5); a1.click(); await sleep(5);
  ok(save("autos").disabled && flag("autos").hidden, "tout décoché (dans un autre ordre) : la carte redevient propre");
  a2.click(); await sleep(5); a1.click(); await sleep(5);
  save("autos").click(); await sleep(30);
  ok(upd().pop().automations.slice().sort().join() === "automation.a1,automation.a2" && Object.keys(upd().pop()).length === 2, "enregistrement de « automatisations » : seulement cette clé", Object.keys(upd().pop()));

  // échec serveur : la carte reste modifiée, rien n'est perdu
  hass.callWS = async (m) => { if (m.type === "maintenance_mode/update_config") { const e = new Error("refusé"); throw e; } return JSON.parse(JSON.stringify(state)); };
  const nt = q("input[data-action=toggle-notify][data-svc=mobile_app_x]"); nt.click(); await sleep(5);
  save("notify").click(); await sleep(30);
  ok(!save("notify").disabled && q("input[data-action=toggle-notify][data-svc=mobile_app_x]").checked, "échec de l'enregistrement : la carte reste modifiée avec sa saisie");
  ok(sr.textContent.includes("refusé"), "…et l'erreur est affichée");
  console.log(fail ? `\n${fail} ÉCHEC(S)` : "\nTOUT PASSE"); process.exit(fail ? 1 : 0);
})();
