process.env.TZ = "America/New_York";
const path = require("path");
const WWW = path.join(__dirname, "..", "custom_components", "maintenance_mode", "www");
const { JSDOM } = require("jsdom");
const fs = require("fs");
const SRC = fs.readFileSync(path.join(WWW, "overlay.js"), "utf8");
let fail = 0; const ok = (c, m, e) => { if (!c) { fail++; console.log("FAIL:", m, e ?? ""); } else console.log("ok  :", m); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function run(mode) {
  const dom = new JSDOM("<!doctype html><body></body>", { url: "http://ha.local/lovelace/0", runScripts: "outside-only", pretendToBeVisual: true });
  const w = dom.window; w.scrollTo = () => {};
  const ha = w.document.createElement("home-assistant");
  // fin prévue dans 3 jours à 14:30 UTC => 16:30 à Paris (été) / 10:30 à New York
  const end = new Date(Date.UTC(2030, 6, 10, 14, 30)).toISOString();
  const cur = { id: "c", start: new Date(Date.now() - 6e4).toISOString(), end, reason: "", pages: [], pause_automations: true };
  ha.hass = { user: { id: "adm", is_owner: false }, locale: { language: "fr", time_zone: mode }, config: { time_zone: "Europe/Paris" }, callWS: async () => ({ exempt: true, panel_hidden: false }), panels: {}, localize: () => "",
    states: { "switch.m": { entity_id: "switch.m", state: "on", attributes: { maintenance_mode_entity: true, rights_rev: "r1", current: cur, next: null, banner_mode: "bar", banner_scroll: false, message: "" } } } };
  w.document.body.appendChild(ha);
  const hsr = ha.attachShadow({ mode: "open" }); hsr.appendChild(w.document.createElement("home-assistant-main"));
  w.eval(SRC); await sleep(1200);
  const t = w.document.getElementById("maintenance-bar")?.textContent || "";
  w.close(); return t;
}
(async () => {
  const server = await run("server"), local = await run("local");
  ok(server.includes("16:30") && !server.includes("10:30"), "bandeau, profil serveur : fin prévue affichée 16:30 (Paris)", server);
  ok(local.includes("10:30") && !local.includes("16:30"), "bandeau, profil local : fin prévue affichée 10:30 (New York)", local);
  console.log(fail ? `\n${fail} ÉCHEC(S)` : "\nTOUT PASSE"); process.exit(fail ? 1 : 0);
})();
