process.env.TZ = "America/New_York";          // le « navigateur » est à New York ; Home Assistant est à Paris
const path = require("path");
const WWW = path.join(__dirname, "..", "custom_components", "maintenance_mode", "www");
const { JSDOM } = require("jsdom");
const fs = require("fs");
const W = WWW + "/";
let fail = 0; const ok = (c, m, extra) => { if (!c) { fail++; console.log("FAIL:", m, extra ?? ""); } else console.log("ok  :", m); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function panel(timeZoneMode, fn, serverTz = "Europe/Paris") {
  const dom = new JSDOM("<!doctype html><body></body>", { url: "http://ha.local/maintenance", runScripts: "outside-only", pretendToBeVisual: true });
  const w = dom.window; w.scrollTo = () => {}; const calls = [];
  const state = { role: "x", permissions: ["view", "history", "control", "schedule", "templates", "settings", "access"], active: false, current: null, message: "m",
    upcoming: [{ id: "w1", start: "2026-10-20T01:00:00+00:00", end: "2026-10-20T03:30:00+00:00", reason: "R", pages: [], pause_automations: true, repeat: "none" }],
    config: { automations: [], allowed_users: [], warn_minutes: 15, end_soon_minutes: 10, message: "m", notify_services: [], notify_kinds: [], banner_mode: "bar", banner_scroll: true,
      templates: [{ id: "t1", name: "T", reason: "", pages: [], pause_automations: true, duration: 90, repeat: "none" }], roles: [], panel_access: {} },
    users: [], history: [], disabled_count: 0 };
  const hass = { themes: {}, locale: { language: "fr", time_zone: timeZoneMode }, config: { time_zone: serverTz }, localize: () => "", panels: {}, services: { notify: {} }, states: {},
    connection: { subscribeMessage: async (c) => { c(state); return () => {}; } }, callWS: async (m) => { calls.push(m); return state; } };
  w.eval(fs.readFileSync(W + "panel.js", "utf8"));
  const el = w.document.createElement("maintenance-mode-panel"); w.document.body.appendChild(el); el.hass = hass; await sleep(40);
  await fn({ w, el, sr: el.shadowRoot, calls });
  el.remove(); w.close();
}

(async () => {
  console.log("TZ du processus :", Intl.DateTimeFormat().resolvedOptions().timeZone);

  // ---- profil « serveur » : le formulaire raisonne en heure de Paris
  await panel("server", async ({ w, sr, calls }) => {
    ok(sr.textContent.includes("03:00") && !sr.textContent.includes("21:00"), "affichage : 01:00Z est montré 03:00 (Paris) et non 21:00 (New York)");
    sr.querySelector("[data-action=open-add]").click(); await sleep(15);
    ok(sr.textContent.includes("Europe/Paris"), "le fuseau est indiqué à côté des champs");
    const start = sr.querySelector("[data-field='form.start']"); start.value = "2026-10-20T03:00"; start.dispatchEvent(new w.Event("input", { bubbles: true }));
    const end = sr.querySelector("[data-field='form.end']"); end.value = "2026-10-20T05:30"; end.dispatchEvent(new w.Event("input", { bubbles: true }));
    sr.querySelector("[data-action=save-form]").click(); await sleep(15);
    const c = calls.find((x) => x.type === "maintenance_mode/add_window");
    ok(c && c.start === "2026-10-20T01:00:00.000Z" && c.end === "2026-10-20T03:30:00.000Z", "03:00 saisi = 01:00Z envoyé (Paris UTC+2), pas 07:00Z (New York)", c && [c.start, c.end]);
  });
  // ---- profil « local » : comportement habituel du navigateur
  await panel("local", async ({ w, sr, calls }) => {
    ok(sr.textContent.includes("21:00"), "profil local : 01:00Z est montré 21:00 (New York)");
    sr.querySelector("[data-action=open-add]").click(); await sleep(15);
    ok(sr.textContent.includes("America/New_York"), "le fuseau du navigateur est indiqué");
    const start = sr.querySelector("[data-field='form.start']"); start.value = "2026-10-20T03:00"; start.dispatchEvent(new w.Event("input", { bubbles: true }));
    sr.querySelector("[data-action=save-form]").click(); await sleep(15);
    const c = calls.find((x) => x.type === "maintenance_mode/add_window");
    ok(c && c.start === "2026-10-20T07:00:00.000Z", "profil local : 03:00 saisi = 07:00Z (New York, UTC-4)", c && c.start);
  });

  // ---- modification d'une maintenance existante : aller-retour sans décalage
  await panel("server", async ({ w, sr, calls }) => {
    sr.querySelector("[data-action=edit-item]").click(); await sleep(15);
    ok(sr.querySelector("[data-field='form.start']").value === "2026-10-20T03:00" && sr.querySelector("[data-field='form.end']").value === "2026-10-20T05:30", "édition : le formulaire montre 03:00 → 05:30 (Paris)");
    sr.querySelector("[data-action=save-form]").click(); await sleep(15);
    const c = calls.find((x) => x.type === "maintenance_mode/update_window");
    ok(c && c.start === "2026-10-20T01:00:00.000Z" && c.end === "2026-10-20T03:30:00.000Z", "édition sans changement : les instants sont inchangés");
  });

  // ---- modèle appliqué (durée 90 min) à partir d'une heure saisie
  await panel("server", async ({ w, sr }) => {
    sr.querySelector("[data-action=open-add]").click(); await sleep(15);
    const start = sr.querySelector("[data-field='form.start']"); start.value = "2026-10-20T03:00"; start.dispatchEvent(new w.Event("input", { bubbles: true }));
    const sel = sr.querySelector("select[data-action=apply-template]"); sel.value = "t1"; sel.dispatchEvent(new w.Event("change", { bubbles: true })); await sleep(15);
    ok(sr.querySelector("[data-field='form.end']").value === "2026-10-20T04:30", "modèle 90 min : fin = 04:30 (heure de Paris)");
  });

  // ---- heure par défaut : ronde dans le fuseau affiché (Inde = +5:30)
  await panel("server", async ({ sr }) => {
    sr.querySelector("[data-action=open-add]").click(); await sleep(15);
    ok(/T\d{2}:00$/.test(sr.querySelector("[data-field='form.start']").value), "heure de début par défaut : minutes à 00 dans le fuseau affiché (Asie/Kolkata, +5:30)");
  }, "Asia/Kolkata");

  // ---- conversions aux changements d'heure (fonctions pures)
  const dom = new JSDOM("<!doctype html><body></body>", { runScripts: "outside-only" });
  // (les « const » d'un eval ne sont pas globales : on expose les deux fonctions dans le même eval)
  dom.window.eval(fs.readFileSync(W + "panel.js", "utf8") + "\n;globalThis.__tz = { zonedToDate, zonedLocal };");
  const z = (s, tz) => dom.window.__tz.zonedToDate(s, tz).toISOString();
  const back = (iso, tz) => dom.window.__tz.zonedLocal(new dom.window.Date(iso), tz);
  ok(z("2027-03-28T02:30", "Europe/Paris") === "2027-03-28T01:30:00.000Z", "heure inexistante (02:30 le 28/03/2027 à Paris) : décalée vers l'avant (03:30 CEST)");
  ok(z("2026-10-25T02:30", "Europe/Paris") === "2026-10-25T00:30:00.000Z", "heure ambiguë (02:30 le 25/10/2026) : première occurrence (CEST)");
  ok(z("2026-10-25T03:30", "Europe/Paris") === "2026-10-25T02:30:00.000Z", "après le retour à l'heure d'hiver : 03:30 CET");
  ok(z("2026-10-20T10:15", "Asia/Kolkata") === "2026-10-20T04:45:00.000Z", "fuseau à demi-heure (Inde)");
  ok(z("2026-07-01T00:00", "Pacific/Auckland") === "2026-06-30T12:00:00.000Z", "fuseau très en avance (Nouvelle-Zélande)");
  // aller-retour sur toute une année, hors heure ambiguë
  let bad = 0;
  for (let t = Date.UTC(2026, 0, 1); t < Date.UTC(2027, 0, 1); t += 37 * 60000) {
    const iso = new Date(t).toISOString();
    const local = back(iso, "Europe/Paris");
    if (z(local, "Europe/Paris") !== iso.replace(/:\d{2}\.\d{3}Z$/, ":00.000Z")) {
      const h = Date.UTC(2026, 9, 25, 0, 0) <= t && t < Date.UTC(2026, 9, 25, 2, 0);   // heure ambiguë : tolérée
      if (!h) bad++;
    }
  }
  ok(bad === 0, "aller-retour instant → heure locale → instant sur toute l'année 2026 (Paris)", bad);

  console.log(fail ? `\n${fail} ÉCHEC(S)` : "\nTOUT PASSE"); process.exit(fail ? 1 : 0);
})();
