// Lance chaque fichier *.test.js dans son propre processus (certains fixent TZ) et résume.
const { spawnSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const dir = __dirname;
const only = process.argv[2];
const files = fs.readdirSync(dir).filter((f) => f.endsWith(".test.js") && (!only || f.includes(only))).sort();
let failed = 0;
const started = Date.now();

for (const file of files) {
  const t0 = Date.now();
  const r = spawnSync(process.execPath, [path.join(dir, file)], { encoding: "utf8" });
  const out = `${r.stdout}${r.stderr}`;
  const fails = out.split("\n").filter((l) => l.startsWith("FAIL:"));
  const ok = out.split("\n").filter((l) => l.startsWith("ok  :")).length;
  const passed = r.status === 0 && fails.length === 0;
  console.log(`${passed ? "✔" : "✘"} ${file}  (${ok} contrôles, ${((Date.now() - t0) / 1000).toFixed(1)} s)`);
  if (!passed) {
    failed++;
    fails.forEach((l) => console.log("    " + l));
    if (!fails.length) console.log(out.split("\n").slice(-15).map((l) => "    " + l).join("\n"));
  }
}
console.log(`\n${files.length - failed}/${files.length} fichiers OK en ${((Date.now() - started) / 1000).toFixed(0)} s`);
process.exit(failed ? 1 : 0);
