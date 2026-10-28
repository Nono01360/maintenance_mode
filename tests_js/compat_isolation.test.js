// Règle 1 de la feuille de route : aucune astuce sur le DOM interne de Home Assistant hors du module `compat`.
const path = require("path");
const fs = require("fs");
const SRC = fs.readFileSync(path.join(__dirname, "..", "custom_components", "maintenance_mode", "www", "overlay.js"), "utf8");
let fail = 0; const ok = (c, m, e) => { if (!c) { fail++; console.log("FAIL:", m, e ?? ""); } else console.log("ok  :", m); };

const begin = SRC.indexOf("// COMPAT — SEUL endroit");
const end = SRC.indexOf("FIN COMPAT");
ok(begin > 0 && end > begin && SRC.includes("const compat = (() => {"), "le module compat existe et est délimité");
const outside = SRC.slice(0, begin) + SRC.slice(end);
const inside = SRC.slice(begin, end);

const FORBIDDEN = ["shadowRoot", "attachShadow", "home-assistant-main", "ha-sidebar", "ha-drawer", "deepFind", "MutationObserver", "data-panel"];
for (const token of FORBIDDEN) {
  ok(!outside.includes(token), `« ${token} » n'apparaît pas hors du module compat`, outside.includes(token) ? "trouvé hors compat" : "");
}
ok(inside.includes("home-assistant-main") && inside.includes("ha-sidebar"), "…et se trouve bien dans le module compat");
ok(/^\s*return \{[^}]*sidebarWidth[^}]*setPanelHidden[^}]*pushPage/ms.test(inside.slice(inside.lastIndexOf("return {"))), "compat expose une interface réduite (sidebarWidth, setPanelHidden, pushPage…)");
// le reste du code n'utilise que cette interface
for (const call of ["compat.sidebarWidth(", "compat.setPanelHidden(", "compat.pushPage(", "compat.sidebarPending("]) {
  ok(outside.includes(call), `le reste du code appelle ${call})`);
}
console.log(fail ? `\n${fail} ÉCHEC(S)` : "\nTOUT PASSE"); process.exit(fail ? 1 : 0);
