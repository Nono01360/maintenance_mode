// Banc de bout en bout — À LANCER CONTRE UN VRAI HOME ASSISTANT (voir .github/workflows/e2e.yml).
// Variables : HA_URL (défaut http://localhost:8123). Le conteneur doit être neuf (onboarding non fait).
// ATTENTION : ce banc n'a pas encore été exécuté par son auteur (0.7.16) ; premier passage = mise au point.
const { chromium } = require("playwright");
const HA = process.env.HA_URL || "http://localhost:8123";
const CLIENT = HA + "/";
let fail = 0;
const ok = (c, m, e) => { if (!c) { fail++; console.log("FAIL:", m, e ?? ""); } else console.log("ok  :", m); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const j = async (method, path, body, token) => {
  const r = await fetch(HA + path, { method, headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) }, body: body ? JSON.stringify(body) : undefined });
  const t = await r.text();
  if (!r.ok) throw new Error(`${method} ${path} -> ${r.status} ${t.slice(0, 200)}`);
  return t ? JSON.parse(t) : null;
};

async function waitForHa() {
  for (let i = 0; i < 120; i++) { try { const r = await fetch(HA + "/api/onboarding"); if (r.ok) return; } catch (_) { /* pas prêt */ } await sleep(2000); }
  throw new Error("Home Assistant ne répond pas");
}

async function onboard() {
  const { auth_code } = await j("POST", "/api/onboarding/users", { client_id: CLIENT, name: "Owner", username: "owner", password: "e2e-password-123", language: "fr" });
  const form = new URLSearchParams({ client_id: CLIENT, grant_type: "authorization_code", code: auth_code });
  const tok = await (await fetch(HA + "/auth/token", { method: "POST", body: form })).json();
  const t = tok.access_token;
  await j("POST", "/api/onboarding/core_config", {}, t);
  await j("POST", "/api/onboarding/analytics", {}, t);
  await j("POST", "/api/onboarding/integration", { client_id: CLIENT, redirect_uri: CLIENT }, t);
  return tok;
}

async function addIntegration(token) {
  const flow = await j("POST", "/api/config/config_entries/flow", { handler: "maintenance_mode", show_advanced_options: false }, token);
  await j("POST", `/api/config/config_entries/flow/${flow.flow_id}`, {}, token);
}

const service = (token, name, data) => j("POST", `/api/services/maintenance_mode/${name}`, data, token);

(async () => {
  await waitForHa();
  const tok = await onboard();
  await addIntegration(tok.access_token);
  await sleep(3000);

  const browser = await chromium.launch();
  const page = await (await browser.newContext({ viewport: { width: 1280, height: 800 } })).newPage();
  const errors = []; page.on("pageerror", (e) => errors.push(String(e)));
  await page.addInitScript((t) => {
    localStorage.setItem("hassTokens", JSON.stringify({ access_token: t.access_token, token_type: "Bearer", expires_in: t.expires_in, hassUrl: location.origin, clientId: location.origin + "/", expires: Date.now() + 1e9, refresh_token: t.refresh_token }));
  }, tok);

  // ---- 1. bandeau : position, décalage de la page, défilement
  await service(tok.access_token, "start", { reason: "E2E", duration: "01:00:00", pause_automations: false });
  await page.goto(HA + "/lovelace/0"); await sleep(6000);
  const bar = await page.evaluate(() => { const b = document.getElementById("maintenance-bar"); if (!b) return null; const r = b.getBoundingClientRect(); return { top: r.top, height: r.height }; });
  ok(!!bar && bar.top === 0 && bar.height > 0, "bandeau collé en haut de la fenêtre", JSON.stringify(bar));
  const pushed = await page.evaluate(() => { const ha = document.querySelector("home-assistant"); return ha ? ha.getBoundingClientRect().top : null; });
  ok(bar && pushed !== null && Math.abs(pushed - bar.height) <= 1, "interface Home Assistant décalée sous le bandeau", `bandeau ${bar?.height}, interface ${pushed}`);
  const scrollY = await page.evaluate(() => { window.scrollTo(0, 500); return window.scrollY; });
  ok(scrollY === 0, "le document lui-même ne défile pas (le défilement est dans le contenu)", scrollY);
  const status = await page.evaluate(() => window.__maintenanceModeCompat);
  ok(status && status.main === true && status.pushed === true, "diagnostic de compatibilité : structure reconnue, page décalée", JSON.stringify(status));

  // ---- 2. panneau accessible
  await page.goto(HA + "/maintenance"); await sleep(4000);
  const panel = await page.evaluate(() => !!document.querySelector("home-assistant")?.shadowRoot && !!document.querySelector("maintenance-mode-panel") || !!document.querySelector("home-assistant")?.shadowRoot?.querySelector("home-assistant-main")?.shadowRoot?.querySelector("maintenance-mode-panel"));
  ok(panel, "le panneau Maintenance s'affiche");

  // ---- 3. mode compatibilité : plus rien n'est touché
  await j("POST", "/api/services/maintenance_mode/stop", {}, tok.access_token);
  console.log("note : le mode compatibilité se règle depuis le panneau (websocket) ; à automatiser lors de la mise au point du banc");

  ok(errors.length === 0, "aucune erreur JavaScript dans la page", errors.join(" | "));
  await page.screenshot({ path: "e2e-last.png" });
  await browser.close();
  console.log(fail ? `\n${fail} ÉCHEC(S)` : "\nTOUT PASSE"); process.exit(fail ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(2); });
