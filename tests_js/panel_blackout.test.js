const path = require("path");
const WWW = path.join(__dirname, "..", "custom_components", "maintenance_mode", "www");
const { JSDOM } = require("jsdom");
const fs = require("fs");
const SRC = fs.readFileSync(path.join(WWW, "panel.js"), "utf8");
let fail = 0; const ok = (c, m, e) => { if (!c) { fail++; console.log("FAIL:", m, e ?? ""); } else console.log("ok  :", m); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function run(owner, fn) {
  const dom = new JSDOM("<!doctype html><body></body>", { url: "http://ha.local/maintenance", runScripts: "outside-only", pretendToBeVisual: true });
  const w = dom.window; w.scrollTo = () => {}; const calls = [];
  const state = { role: "admin", permissions: ["view", "control", "schedule", "templates", "settings"], active: false, current: null, message: "m", upcoming: [],
    config: { automations: [], allowed_users: [], warn_minutes: 15, end_soon_minutes: 10, message: "m", notify_services: [], notify_kinds: ["pre"], banner_mode: "bar",
      banner_scroll: true, compat_mode: false, max_duration_minutes: 0, excluded_automations: [], excluded_labels: [], selected_labels: [], selected_areas: [], templates: [],
      blackouts: [{ id: "b1", name: "Nuit", days: [4], start: "22:00", end: "06:00" }] }, users: [] };
  const hass = { user: { is_owner: owner }, themes: {}, locale: { language: "fr" }, localize: () => "", panels: {}, services: { notify: {} }, states: {},
    connection: { subscribeMessage: async (c) => { c(state); return () => {}; } },
    callWS: async (m) => { calls.push(m); return m.type === "maintenance_mode/get_catalog" ? { labels: [], areas: [] } : state; } };
  w.eval(SRC);
  const el = w.document.createElement("maintenance-mode-panel"); w.document.body.appendChild(el); el.hass = hass; await sleep(40);
  await fn({ w, sr: el.shadowRoot, calls, last: (t) => calls.filter((c) => c.type === "maintenance_mode/" + t).pop() });
  el.remove(); w.close();
}

(async () => {
  await run(false, async ({ w, sr, last }) => {
    sr.querySelector("[data-tab=settings]").click(); await sleep(30);
    ok(sr.textContent.includes("Plages interdites") && sr.querySelector("[data-field='bo.name']").value === "Nuit", "paramètres : plage existante affichée");
    ok(sr.querySelector("input[data-action=toggle-bo-day][data-day='4']").checked && !sr.querySelector("input[data-action=toggle-bo-day][data-day='0']").checked, "jours cochés selon la règle (vendredi)");
    sr.querySelector("[data-action=add-blackout]").click(); await sleep(20);
    ok(sr.querySelectorAll("[data-field='bo.name']").length === 2, "ajout d'une plage");
    const nm = sr.querySelectorAll("[data-field='bo.name']")[1]; nm.value = "Matin"; nm.dispatchEvent(new w.Event("input", { bubbles: true }));
    const st = sr.querySelectorAll("[data-field='bo.start']")[1]; st.value = "07:00"; st.dispatchEvent(new w.Event("input", { bubbles: true }));
    const en = sr.querySelectorAll("[data-field='bo.end']")[1]; en.value = "08:30"; en.dispatchEvent(new w.Event("input", { bubbles: true }));
    sr.querySelector("input[data-action=toggle-bo-day][data-idx='1'][data-day='2']").click(); await sleep(10);
    sr.querySelector("[data-action=delete-blackout][data-idx='0']").click(); await sleep(20);
    sr.querySelector("[data-action=save-block][data-block=blackout]").click(); await sleep(30);
    const cfg = last("update_config");
    ok(cfg.blackouts.length === 1 && cfg.blackouts[0].name === "Matin" && cfg.blackouts[0].start === "07:00" && cfg.blackouts[0].end === "08:30" && cfg.blackouts[0].days.join() === "2" && !("id" in cfg.blackouts[0]), "enregistrement : plage créée (sans id), ancienne supprimée");
    sr.querySelector("[data-tab=list]").click(); await sleep(10);
    sr.querySelector("[data-action=start-now]").click(); await sleep(15);
    ok(!sr.querySelector("input[data-action=form-override]"), "non propriétaire : pas de case de dérogation");
    sr.querySelector("[data-action=save-form]").click(); await sleep(20);
    ok(!("override_blackout" in last("start")), "non propriétaire : aucune dérogation envoyée");
  });
  await run(true, async ({ sr, last }) => {
    sr.querySelector("[data-action=start-now]").click(); await sleep(15);
    const box = sr.querySelector("input[data-action=form-override]");
    ok(!!box && !box.checked, "propriétaire : case de dérogation visible, décochée");
    box.click(); await sleep(10);
    sr.querySelector("[data-action=save-form]").click(); await sleep(20);
    ok(last("start").override_blackout === true, "propriétaire : dérogation envoyée seulement si cochée");
    sr.querySelector("[data-action=open-add]").click(); await sleep(15);
    sr.querySelector("input[data-action=form-override]").click(); await sleep(10);
    sr.querySelector("[data-action=save-form]").click(); await sleep(20);
    ok(last("add_window").override_blackout === true, "propriétaire : la planification envoie aussi la dérogation");
  });
  console.log(fail ? `\n${fail} ÉCHEC(S)` : "\nTOUT PASSE"); process.exit(fail ? 1 : 0);
})();
