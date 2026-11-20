const path = require("path");
const WWW = path.join(__dirname, "..", "custom_components", "maintenance_mode", "www");
const { JSDOM } = require("jsdom");
const fs = require("fs");
const SRC = fs.readFileSync(path.join(WWW, "panel.js"), "utf8");
let fail = 0; const ok = (c, m, e) => { if (!c) { fail++; console.log("FAIL:", m, e ?? ""); } else console.log("ok  :", m); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function run(withHooks, fn) {
  const dom = new JSDOM("<!doctype html><body></body>", { url: "http://ha.local/maintenance", runScripts: "outside-only", pretendToBeVisual: true });
  const w = dom.window; w.scrollTo = () => {}; const calls = [];
  const cfg = { automations: [], allowed_users: [], warn_minutes: 15, end_soon_minutes: 10, message: "m", notify_services: [], notify_kinds: [], banner_mode: "bar", banner_scroll: true,
    compat_mode: false, max_duration_minutes: 0, blackouts: [], confirm_threshold: 20, selected_labels: [], selected_areas: [], excluded_automations: [], excluded_labels: [], templates: [], roles: [], panel_access: {} };
  if (withHooks) cfg.hooks = [{ id: "h1", name: "Sauvegarde", when: "before_start", entity_id: "script.backup", timeout: 60, on_failure: "abort" }];
  const hist = [{ hid: "x1", start: new Date(Date.now() - 9e6).toISOString(), ended_at: new Date(Date.now() - 8e6).toISOString(), ended_by: "manual", reason: "R", pages: [], repeat: "none",
    hooks: [{ name: "a", status: "ok" }, { name: "b", status: "timeout" }, { name: "c", status: "ok" }] }];
  const state = { role: "admin", permissions: ["view", "history", "settings"], active: false, current: null, message: "m", upcoming: [], config: cfg, users: [], history: hist, disabled_count: 0 };
  const hass = { themes: {}, locale: { language: "fr" }, localize: () => "", panels: {}, services: { notify: {} },
    states: { "script.backup": { entity_id: "script.backup", state: "off", attributes: {} }, "scene.nuit": { entity_id: "scene.nuit", state: "unknown", attributes: {} }, "light.x": { entity_id: "light.x", state: "on", attributes: {} } },
    connection: { subscribeMessage: async (c) => { c(state); return () => {}; } }, callWS: async (m) => { calls.push(m); return m.type === "maintenance_mode/update_config" ? { ...state, config: { ...cfg, ...m } } : state; } };
  w.eval(SRC);
  const el = w.document.createElement("maintenance-mode-panel"); w.document.body.appendChild(el); el.hass = hass; await sleep(40);
  await fn({ w, sr: el.shadowRoot, calls });
  el.remove(); w.close();
}
const input = (w, el, v) => { el.value = v; el.dispatchEvent(new w.Event("input", { bubbles: true })); };

(async () => {
  await run(false, async ({ sr }) => {
    sr.querySelector("[data-tab=settings]").click(); await sleep(15);
    ok(!sr.querySelector("[data-role=hooks]"), "sans droit administrateur : pas de carte Hooks (le serveur n'envoie pas les hooks)");
  });
  await run(true, async ({ w, sr, calls }) => {
    ok(sr.textContent.includes("Hooks : 2 réussi(s), 1 en échec ou ignoré(s)") && !!sr.querySelector("[data-role=hook-results]"), "historique : résumé des résultats de hooks");
    sr.querySelector("[data-tab=settings]").click(); await sleep(15);
    const card = sr.querySelector("[data-role=hooks]");
    ok(card && card.querySelector("[data-field='hk.name']").value === "Sauvegarde", "carte Hooks : hook existant affiché");
    const opts = [...sr.querySelectorAll("#hook-entities option")].map((o) => o.value);
    ok(opts.join() === "scene.nuit,script.backup", "suggestions : scripts et scènes seulement", opts.join());
    ok(card.querySelector("button[data-action=save-block]").disabled, "aucune modification : enregistrement grisé");
    card.querySelector("[data-action=add-hook]").click(); await sleep(15);
    const names = sr.querySelectorAll("[data-field='hk.name']"); ok(names.length === 2, "ajout d'un hook");
    input(w, names[1], "Nuit"); input(w, sr.querySelectorAll("[data-field='hk.entity']")[1], "scene.nuit"); input(w, sr.querySelectorAll("[data-field='hk.timeout']")[1], "15");
    const failSel = sr.querySelectorAll("select[data-action=hk-fail]")[1];
    ok(failSel.disabled, "« annuler le démarrage » indisponible hors « avant le début »");
    const when = sr.querySelectorAll("select[data-action=hk-when]")[1]; when.value = "after_end"; when.dispatchEvent(new w.Event("change", { bubbles: true })); await sleep(15);
    sr.querySelector("[data-role=hooks] button[data-action=save-block]").click(); await sleep(30);
    const c = calls.filter((x) => x.type === "maintenance_mode/update_config").pop();
    ok(c && Object.keys(c).filter((k) => !["type"].includes(k)).join() === "hooks", "enregistrement : seul « hooks » est envoyé", c && Object.keys(c).join());
    ok(c.hooks.length === 2 && c.hooks[0].id === "h1" && c.hooks[0].on_failure === "abort" && !("id" in c.hooks[1]), "ancien hook avec id, nouveau sans id");
    ok(c.hooks[1].when === "after_end" && c.hooks[1].entity_id === "scene.nuit" && c.hooks[1].timeout === 15 && c.hooks[1].on_failure === "continue", "nouveau hook : valeurs saisies");
    sr.querySelector("[data-action=delete-hook][data-idx='0']").click(); await sleep(15);
    ok(sr.querySelectorAll("[data-field='hk.name']").length === 1, "suppression d'un hook (brouillon)");
  });
  console.log(fail ? `\n${fail} ÉCHEC(S)` : "\nTOUT PASSE"); process.exit(fail ? 1 : 0);
})();
