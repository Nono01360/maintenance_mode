const path = require("path");
const WWW = path.join(__dirname, "..", "custom_components", "maintenance_mode", "www");
const { JSDOM } = require("jsdom");
const fs = require("fs");
const SRC = fs.readFileSync(path.join(WWW, "panel.js"), "utf8");
let fail = 0; const ok = (c, m) => { if (!c) { fail++; console.log("FAIL:", m); } else console.log("ok  :", m); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
(async () => {
  const dom = new JSDOM("<!doctype html><body></body>", { url: "http://ha.local/maintenance", runScripts: "outside-only", pretendToBeVisual: true });
  const w = dom.window; w.scrollTo = () => {};
  const calls = []; const now = Date.now();
  const state = { role: "admin", permissions: ["view","history","control","schedule","templates","settings","access"], active: false, current: null, message: "m",
    upcoming: [{ id: "w1", start: new Date(now + 36e5).toISOString(), end: new Date(now + 72e5).toISOString(), reason: "R", pages: ["map"], pause_automations: true, repeat: "weekly", started_by: "" }],
    config: { automations: [], allowed_users: [], warn_minutes: 15, end_soon_minutes: 10, message: "m", notify_services: [], notify_kinds: [], banner_mode: "bar", banner_scroll: true,
      templates: [{ id: "t1", name: "MAJ", reason: "Mise à jour", pages: ["map"], pause_automations: false, duration: 90, repeat: "none" }], roles: [], panel_access: {} },
    users: [{ id: "u1", name: "N", is_owner: true, is_admin: true, role: "admin", explicit: false }], history: [], disabled_count: 0 };
  const hass = { themes: {}, locale: { language: "fr" }, localize: () => "", panels: { map: { url_path: "map", title: "map" } }, services: { notify: {} }, states: {},
    connection: { subscribeMessage: async (c) => { c(state); return () => {}; } }, callWS: async (m) => { calls.push(m); return state; } };
  w.eval(SRC);
  const el = w.document.createElement("maintenance-mode-panel"); w.document.body.appendChild(el); el.hass = hass; await sleep(40);
  const sr = el.shadowRoot; const click = async (sel) => { sr.querySelector(sel).click(); await sleep(15); };
  const last = (t) => calls.filter((c) => c.type === "maintenance_mode/" + t).pop();

  await click("[data-action=edit-item]");
  await click("[data-action=save-form]");
  let c = last("update_window");
  ok(c && c.window_id === "w1" && c.id === undefined && c.repeat === "weekly" && c.pages.join() === "map", "modifier : update_window avec window_id, répétition et pages");

  await click("[data-action=duplicate-item]");
  await click("[data-action=save-form]");
  c = last("add_window");
  ok(c && c.reason === "R" && c.repeat === "weekly" && c.start && c.end, "dupliquer : add_window");

  await click("[data-action=delete-item]");
  ok(sr.querySelector("[data-action=delete-item]").textContent.includes("Confirmer"), "supprimer : confirmation");
  await click("[data-action=delete-item]");
  c = last("delete_window");
  ok(c && c.window_id === "w1", "supprimer : delete_window avec window_id");

  await click("[data-action=start-now]");
  const sel = sr.querySelector("select[data-action=apply-template]"); sel.value = "t1"; sel.dispatchEvent(new w.Event("change", { bubbles: true })); await sleep(15);
  ok(sr.querySelector("[data-field='form.reason']").value === "Mise à jour" && !sr.querySelector("input[data-action=form-pause]").checked, "démarrer : modèle appliqué");
  await click("[data-action=save-form]");
  c = last("start");
  ok(c && c.reason === "Mise à jour" && c.pages.join() === "map" && c.pause_automations === false && c.end, "démarrer : start avec les valeurs du modèle");

  console.log(fail ? `\n${fail} ÉCHEC(S)` : "\nTOUT PASSE"); process.exit(fail ? 1 : 0);
})();
