/* Mode maintenance — panneau de configuration (Web Component, sans build).
 * Les droits (aucun / vue utilisateur / vue administrateur) sont vérifiés côté
 * serveur ; ce fichier ne fait qu'afficher ce que le serveur autorise. */

const esc = (v) =>
  String(v ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const EXTRA_PAGES = [
  ["config/devices", "Paramètres › Appareils"],
  ["config/integrations", "Paramètres › Intégrations"],
  ["config/entities", "Paramètres › Entités"],
  ["config/areas", "Paramètres › Zones"],
  ["config/automation", "Paramètres › Automatisations"],
];

const ROLE_LABELS = {
  none: "Aucun accès",
  viewer: "Vue utilisateur",
  admin: "Vue administrateur",
};

const STYLES = `
  :host { display: block; height: 100%; background: var(--primary-background-color);
    color: var(--primary-text-color);
    font-family: var(--paper-font-body1_-_font-family, Roboto, sans-serif); }
  * { box-sizing: border-box; }
  [hidden] { display: none !important; }
  .shell { display: flex; flex-direction: column; height: 100%; }
  .bar { flex: none; background: var(--app-header-background-color, var(--primary-color));
    color: var(--app-header-text-color, #fff); padding-top: env(safe-area-inset-top, 0px); }
  .toolbar { display: flex; align-items: center; gap: 8px; height: var(--header-height, 56px); padding: 0 12px; }
  .toolbar h1 { margin: 0; font-size: 20px; font-weight: 400; }
  .icon-btn { border: none; background: transparent; color: inherit; cursor: pointer;
    width: 40px; height: 40px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; }
  .icon-btn:hover { background: rgba(255,255,255,.15); }
  .tabs { display: flex; overflow-x: auto; padding: 0 8px; }
  .tab { border: none; background: transparent; color: inherit; opacity: .75; cursor: pointer;
    padding: 12px 16px; font: inherit; font-size: 14px; font-weight: 500; letter-spacing: .5px;
    text-transform: uppercase; border-bottom: 2px solid transparent; white-space: nowrap; }
  .tab.active { opacity: 1; border-bottom-color: currentColor; }
  .scroll { flex: 1; overflow: auto; }
  .wrap { max-width: 900px; margin: 0 auto; padding: 16px; display: flex; flex-direction: column; gap: 16px;
    padding-bottom: calc(16px + env(safe-area-inset-bottom, 0px)); }
  ha-card.card { display: block; padding: 16px; }
  .row { display: flex; align-items: center; gap: 12px; }
  .grow { flex: 1; min-width: 0; }
  .col { display: flex; flex-direction: column; gap: 12px; }
  h2 { margin: 0 0 4px; font-size: 18px; font-weight: 500; }
  h3 { margin: 0; font-size: 15px; font-weight: 500; }
  .muted { color: var(--secondary-text-color); font-size: 13px; }
  .badge { width: 48px; height: 48px; border-radius: 50%; flex: none; display: flex; align-items: center; justify-content: center;
    background: color-mix(in srgb, var(--primary-color) 15%, transparent); color: var(--primary-color); }
  .badge.warn { background: color-mix(in srgb, var(--warning-color, #ff9800) 20%, transparent); color: var(--warning-color, #ff9800); }
  .chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }
  .chip { display: inline-flex; align-items: center; gap: 4px; padding: 2px 10px; border-radius: 12px; font-size: 12px;
    background: var(--secondary-background-color); color: var(--primary-text-color); }
  .chip button { border: none; background: transparent; color: inherit; cursor: pointer; padding: 0 0 0 2px; font-size: 14px; line-height: 1; }
  .item { display: flex; gap: 12px; align-items: flex-start; padding: 12px 0; border-top: 1px solid var(--divider-color); }
  .item:first-of-type { border-top: none; }
  .actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 12px; }
  .btn { height: 36px; padding: 0 16px; border-radius: 18px; cursor: pointer; font: inherit; font-size: 14px; font-weight: 500;
    border: 1px solid var(--outline-color, var(--divider-color)); background: transparent; color: var(--primary-color); }
  .btn:hover { background: color-mix(in srgb, var(--primary-color) 8%, transparent); }
  .btn.primary { background: var(--primary-color); border-color: var(--primary-color); color: var(--text-primary-color, #fff); }
  .btn.primary:hover { filter: brightness(1.1); }
  .btn.danger { color: var(--error-color, #db4437); }
  .btn.sm { height: 30px; padding: 0 12px; font-size: 13px; }
  .banner { padding: 12px 16px; border-radius: 8px; font-size: 14px; }
  .banner.error { background: color-mix(in srgb, var(--error-color, #db4437) 15%, transparent); color: var(--error-color, #db4437); }
  label.field { display: flex; flex-direction: column; gap: 4px; font-size: 13px; color: var(--secondary-text-color); }
  input[type=text], input[type=number], input[type=datetime-local], textarea, select {
    width: 100%; padding: 10px 12px; border-radius: 8px; font: inherit; font-size: 15px;
    border: 1px solid var(--divider-color); background: var(--ha-card-background, var(--card-background-color));
    color: var(--primary-text-color); }
  textarea { min-height: 72px; resize: vertical; }
  input:focus, textarea:focus, select:focus { outline: 2px solid var(--primary-color); outline-offset: -1px; }
  .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  @media (max-width: 600px) { .grid2 { grid-template-columns: 1fr; } }
  .check { display: flex; align-items: center; gap: 10px; padding: 8px 4px; cursor: pointer; border-radius: 6px; }
  .check:hover { background: var(--secondary-background-color); }
  .check input { width: 18px; height: 18px; flex: none; accent-color: var(--primary-color); }
  .list { max-height: 320px; overflow: auto; border: 1px solid var(--divider-color); border-radius: 8px; padding: 4px 8px; }
  .radio { display: flex; gap: 16px; flex-wrap: wrap; }
  .radio label { display: flex; align-items: center; gap: 6px; cursor: pointer; font-size: 14px; color: var(--primary-text-color); }
  .empty { padding: 32px 16px; text-align: center; color: var(--secondary-text-color); }
  .empty ha-icon { --mdc-icon-size: 48px; display: block; margin: 0 auto 8px; opacity: .6; }
  table { width: 100%; border-collapse: collapse; }
  td { padding: 10px 4px; border-top: 1px solid var(--divider-color); vertical-align: middle; }
  tr:first-child td { border-top: none; }
  td.sel { width: 200px; }
  @media (max-width: 600px) { td.sel { width: 150px; } }
`;

class MaintenanceModePanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._data = null;
    this._tab = "list";
    this._form = null;
    this._draft = null;
    this._draftDirty = false;
    this._autoFilter = "";
    this._confirm = null;
    this._error = "";
    this._fatal = "";
    this._narrow = false;
    this._pending = false;
    this._unsub = null;
    this._timer = null;

    const root = this.shadowRoot;
    root.addEventListener("click", (e) => this._onClick(e));
    root.addEventListener("input", (e) => this._onInput(e));
    root.addEventListener("change", (e) => this._onChange(e));
    root.addEventListener("focusout", () =>
      setTimeout(() => { if (this._pending && !this._isEditing()) this._render(); }, 0));
  }

  // ---------- propriétés fournies par Home Assistant ----------
  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    this.style.colorScheme = hass.themes?.darkMode ? "dark" : "light";
    if (first) this._init();
  }
  get hass() { return this._hass; }
  set narrow(v) { this._narrow = !!v; if (this._data || this._fatal) this._render(true); }
  set panel(_v) {}
  set route(_v) {}

  connectedCallback() {
    if (this._hass && !this._unsub && !this._data) this._init();
    this._timer = setInterval(() => { if (this._data) this._render(); }, 30000);
    this._render(true);
  }

  disconnectedCallback() {
    clearInterval(this._timer);
    if (this._unsub) { this._unsub(); this._unsub = null; }
  }

  // ---------- données ----------
  _init() {
    const conn = this._hass.connection;
    conn.subscribeMessage((d) => this._onData(d), { type: "maintenance_mode/subscribe" })
      .then((unsub) => { this._unsub = unsub; })
      .catch((err) => { this._fatal = err?.message || String(err); this._render(true); });
  }

  _onData(d) {
    this._data = d;
    if (d.config && (!this._draft || !this._draftDirty)) {
      this._draft = {
        automations: [...d.config.automations],
        allowed_users: [...d.config.allowed_users],
        warn_minutes: d.config.warn_minutes,
        message: d.config.message,
      };
    }
    if (d.role !== "admin" && this._tab !== "list") this._tab = "list";
    this._render();
  }

  async _call(type, payload = {}) {
    this._error = "";
    try {
      const res = await this._hass.callWS({ type: `maintenance_mode/${type}`, ...payload });
      if (res && res.role) this._onData(res);
      return true;
    } catch (err) {
      this._error = err?.message || String(err);
      this._render(true);
      return false;
    }
  }

  // ---------- utilitaires d'affichage ----------
  _lang() { return this._hass?.locale?.language || "fr"; }

  _fmt(iso) {
    if (!iso) return "";
    return new Intl.DateTimeFormat(this._lang(), { dateStyle: "medium", timeStyle: "short" }).format(new Date(iso));
  }

  _rel(iso) {
    const ms = new Date(iso).getTime() - Date.now();
    const rtf = new Intl.RelativeTimeFormat(this._lang(), { numeric: "auto" });
    const abs = Math.abs(ms) / 1000;
    const sign = ms < 0 ? -1 : 1;
    if (abs < 60) return rtf.format(sign * Math.round(abs), "second");
    const m = Math.round(abs / 60);
    if (m < 90) return rtf.format(sign * m, "minute");
    const h = Math.round(m / 60);
    if (h < 36) return rtf.format(sign * h, "hour");
    return rtf.format(sign * Math.round(h / 24), "day");
  }

  _range(w) {
    const end = w.end ? this._fmt(w.end) : "fin non définie";
    return `${this._fmt(w.start)} → ${end}`;
  }

  _pageOptions() {
    const out = new Map();
    const panels = this._hass?.panels || {};
    for (const p of Object.values(panels)) {
      if (!p?.url_path) continue;
      if (!p.title && p.url_path !== "lovelace") continue; // seulement ce qui est dans la barre latérale
      let label = p.title ? (this._hass.localize?.(`panel.${p.title}`) || p.title) : "Tableau de bord principal";
      out.set(p.url_path, label);
    }
    for (const [path, label] of EXTRA_PAGES) out.set(path, label);
    return [...out.entries()].map(([path, label]) => ({ path, label }))
      .sort((a, b) => a.label.localeCompare(b.label, this._lang()));
  }

  _pageLabel(path) {
    return this._pageOptions().find((o) => o.path === path)?.label || path;
  }

  _scopeChips(pages) {
    if (!pages || !pages.length) return `<div class="chips"><span class="chip">Tout Home Assistant</span></div>`;
    return `<div class="chips">${pages.map((p) => `<span class="chip">${esc(this._pageLabel(p))}</span>`).join("")}</div>`;
  }

  _automations() {
    return Object.values(this._hass?.states || {})
      .filter((s) => s.entity_id.startsWith("automation."))
      .map((s) => ({ id: s.entity_id, name: s.attributes.friendly_name || s.entity_id }))
      .sort((a, b) => a.name.localeCompare(b.name, this._lang()));
  }

  // ---------- rendu ----------
  _isEditing() {
    const a = this.shadowRoot.activeElement;
    return !!a && /^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName);
  }

  _render(force = false) {
    if (!force && this._isEditing()) { this._pending = true; return; }
    this._pending = false;
    const root = this.shadowRoot;
    const top = root.querySelector(".scroll")?.scrollTop || 0;
    root.innerHTML = `<style>${STYLES}</style>
      <div class="shell">
        ${this._barHtml()}
        <div class="scroll"><div class="wrap">${this._bodyHtml()}</div></div>
      </div>`;
    const sc = root.querySelector(".scroll");
    if (sc) sc.scrollTop = top;
  }

  _barHtml() {
    const admin = this._data?.role === "admin";
    const tab = (id, label) =>
      `<button class="tab ${this._tab === id ? "active" : ""}" data-action="tab" data-tab="${id}">${label}</button>`;
    return `<div class="bar">
      <div class="toolbar">
        <button class="icon-btn" data-action="menu" ${this._narrow ? "" : "hidden"} aria-label="Menu">
          <ha-icon icon="mdi:menu"></ha-icon></button>
        <h1>Maintenance</h1>
      </div>
      ${admin ? `<div class="tabs">${tab("list", "Maintenances")}${tab("settings", "Paramètres")}${tab("access", "Accès")}</div>` : ""}
    </div>`;
  }

  _bodyHtml() {
    if (this._fatal) {
      return `<ha-card class="card"><div class="empty"><ha-icon icon="mdi:alert-circle-outline"></ha-icon>
        Impossible de joindre l'intégration.<br><span class="muted">${esc(this._fatal)}</span></div></ha-card>`;
    }
    if (!this._data) {
      return `<ha-card class="card"><div class="empty"><ha-icon icon="mdi:timer-sand"></ha-icon>Chargement…</div></ha-card>`;
    }
    if (this._data.role === "none") {
      return `<ha-card class="card"><div class="empty"><ha-icon icon="mdi:lock-outline"></ha-icon>
        Tu n'as pas accès à ce panneau.<br><span class="muted">Demande à un administrateur de modifier tes droits.</span></div></ha-card>`;
    }
    const err = this._error ? `<div class="banner error">${esc(this._error)}</div>` : "";
    if (this._data.role === "admin" && this._tab === "settings") return err + this._settingsHtml();
    if (this._data.role === "admin" && this._tab === "access") return err + this._accessHtml();
    return err + this._listHtml();
  }

  // ----- onglet « Maintenances » -----
  _listHtml() {
    const d = this._data;
    const admin = d.role === "admin";
    const cur = d.current;
    let html = "";

    if (cur) {
      const end = cur.end ? `Fin prévue ${this._fmt(cur.end)} (${this._rel(cur.end)})` : "Pas d'heure de fin définie";
      html += `<ha-card class="card"><div class="row">
        <div class="badge warn"><ha-icon icon="mdi:wrench-clock"></ha-icon></div>
        <div class="grow"><h2>Maintenance en cours</h2>
          <div class="muted">Depuis ${this._fmt(cur.start)} · ${esc(end)}</div>
          ${cur.reason ? `<div style="margin-top:6px">${esc(cur.reason)}</div>` : ""}
          ${this._scopeChips(cur.pages)}
          ${admin && d.disabled_count ? `<div class="muted" style="margin-top:6px">${d.disabled_count} automatisation(s) suspendue(s)</div>` : ""}
        </div></div>
        ${admin ? `<div class="actions">
          <button class="btn" data-action="form-current">Modifier</button>
          <button class="btn danger" data-action="stop">${this._confirm === "stop" ? "Confirmer l'arrêt ?" : "Terminer maintenant"}</button>
        </div>` : ""}</ha-card>`;
    } else {
      const next = d.upcoming[0];
      html += `<ha-card class="card"><div class="row">
        <div class="badge"><ha-icon icon="mdi:check-circle-outline"></ha-icon></div>
        <div class="grow"><h2>Aucune maintenance en cours</h2>
          <div class="muted">${next ? `Prochaine : ${this._fmt(next.start)} (${this._rel(next.start)})` : "Aucune maintenance planifiée."}</div>
        </div></div>
        ${admin ? `<div class="actions"><button class="btn primary" data-action="form-now">Démarrer une maintenance</button></div>` : ""}
      </ha-card>`;
    }

    if (this._form) html += this._formHtml();

    html += `<ha-card class="card"><div class="row"><div class="grow"><h2>Maintenances planifiées</h2></div>
      ${admin && !this._form ? `<button class="btn primary sm" data-action="form-add">Planifier</button>` : ""}</div>`;
    if (!d.upcoming.length) {
      html += `<div class="empty"><ha-icon icon="mdi:calendar-blank-outline"></ha-icon>Rien de prévu pour le moment.</div>`;
    } else {
      html += d.upcoming.map((w) => `<div class="item">
        <div class="badge"><ha-icon icon="mdi:calendar-clock"></ha-icon></div>
        <div class="grow"><h3>${this._fmt(w.start)} <span class="muted">(${this._rel(w.start)})</span></h3>
          <div class="muted">${esc(this._range(w))}</div>
          ${w.reason ? `<div style="margin-top:4px">${esc(w.reason)}</div>` : ""}
          ${this._scopeChips(w.pages)}
          ${admin && !w.pause_automations ? `<div class="muted" style="margin-top:4px">Automatisations non suspendues</div>` : ""}
        </div>
        ${admin ? `<div class="col" style="gap:6px">
          <button class="btn sm" data-action="form-edit" data-id="${esc(w.id)}">Modifier</button>
          <button class="btn sm danger" data-action="delete" data-id="${esc(w.id)}">${this._confirm === w.id ? "Confirmer ?" : "Supprimer"}</button>
        </div>` : ""}
      </div>`).join("");
    }
    html += `</ha-card>`;
    return html;
  }

  _formHtml() {
    const f = this._form;
    const titles = {
      add: "Planifier une maintenance",
      edit: "Modifier la maintenance",
      now: "Démarrer une maintenance maintenant",
      current: "Modifier la maintenance en cours",
    };
    const showStart = f.mode === "add" || f.mode === "edit";
    const showPause = f.mode !== "current";
    const pageOpts = this._pageOptions();
    const known = new Set(pageOpts.map((o) => o.path));
    const extra = f.pages.filter((p) => !known.has(p));
    const pagesBlock = f.scope === "pages" ? `
      <div class="list">
        ${pageOpts.map((o) => `<label class="check">
          <input type="checkbox" data-action="toggle-page" data-page="${esc(o.path)}" ${f.pages.includes(o.path) ? "checked" : ""}>
          <span class="grow">${esc(o.label)} <span class="muted">/${esc(o.path)}</span></span></label>`).join("")}
      </div>
      <div class="row">
        <input type="text" placeholder="Autre chemin, ex. config/helpers" data-field="form.custom" value="${esc(f.custom)}">
        <button class="btn sm" data-action="add-custom-page">Ajouter</button>
      </div>
      ${extra.length ? `<div class="chips">${extra.map((p) => `<span class="chip">${esc(p)}<button data-action="remove-page" data-page="${esc(p)}" aria-label="Retirer">×</button></span>`).join("")}</div>` : ""}
      <div class="muted">Un chemin bloque aussi toutes ses sous-pages (ex. config/devices bloque config/devices/dashboard).</div>` : "";

    return `<ha-card class="card"><div class="col">
      <h2>${titles[f.mode]}</h2>
      ${this._error ? `<div class="banner error">${esc(this._error)}</div>` : ""}
      ${showStart || f.mode === "now" || f.mode === "current" ? `<div class="grid2">
        ${showStart ? `<label class="field">Début<input type="datetime-local" data-field="form.start" value="${esc(f.start)}"></label>` : ""}
        <label class="field">Fin prévue (facultatif)<input type="datetime-local" data-field="form.end" value="${esc(f.end)}"></label>
      </div>` : ""}
      <label class="field">Motif (facultatif)<input type="text" maxlength="200" data-field="form.reason" value="${esc(f.reason)}"></label>
      <div class="col" style="gap:8px"><span class="muted">Portée</span>
        <div class="radio">
          <label><input type="radio" name="scope" data-action="scope" value="all" ${f.scope === "all" ? "checked" : ""}> Tout Home Assistant</label>
          <label><input type="radio" name="scope" data-action="scope" value="pages" ${f.scope === "pages" ? "checked" : ""}> Certaines pages seulement</label>
        </div>
        ${pagesBlock}
      </div>
      ${showPause ? `<label class="check"><input type="checkbox" data-action="form-pause" ${f.pause ? "checked" : ""}>
        <span>Suspendre les automatisations pendant la maintenance</span></label>` : ""}
      <div class="actions" style="margin-top:0">
        <button class="btn primary" data-action="form-save">Enregistrer</button>
        <button class="btn" data-action="form-cancel">Annuler</button>
      </div></div></ha-card>`;
  }

  // ----- onglet « Paramètres » -----
  _settingsHtml() {
    const dr = this._draft;
    const users = this._data.users || [];
    const autos = this._automations();
    const f = this._autoFilter.toLowerCase();
    const selected = new Set(dr.automations);
    return `
      <ha-card class="card"><div class="col">
        <h2>Page de maintenance</h2>
        <label class="field">Message affiché aux utilisateurs bloqués
          <textarea maxlength="255" data-field="draft.message">${esc(dr.message)}</textarea></label>
        <label class="field">Préavis de la notification (minutes avant le début)
          <input type="number" min="1" max="1440" data-field="draft.warn" value="${esc(dr.warn_minutes)}"></label>
      </div></ha-card>

      <ha-card class="card"><div class="col">
        <div><h2>Automatisations suspendues</h2>
          <div class="muted">${dr.automations.length
            ? `${dr.automations.length} sélectionnée(s) : seules celles-ci sont coupées.`
            : "Aucune sélectionnée : <b>toutes</b> les automatisations sont coupées pendant la maintenance."}</div></div>
        <input type="text" placeholder="Rechercher…" data-field="auto-search" value="${esc(this._autoFilter)}">
        <div class="list">
          ${autos.length ? autos.map((a) => `<label class="check" data-filter="${esc((a.name + " " + a.id).toLowerCase())}"
              ${f && !(a.name + " " + a.id).toLowerCase().includes(f) ? "hidden" : ""}>
            <input type="checkbox" data-action="toggle-auto" data-entity="${esc(a.id)}" ${selected.has(a.id) ? "checked" : ""}>
            <span class="grow">${esc(a.name)} <span class="muted">${esc(a.id)}</span></span></label>`).join("")
            : `<div class="empty">Aucune automatisation trouvée.</div>`}
        </div>
        ${dr.automations.length ? `<div><button class="btn sm" data-action="auto-none">Tout désélectionner</button></div>` : ""}
      </div></ha-card>

      <ha-card class="card"><div class="col">
        <div><h2>Utilisateurs non impactés</h2>
          <div class="muted">${dr.allowed_users.length
            ? "Ces utilisateurs (et le propriétaire) ne sont jamais bloqués."
            : "Aucun sélectionné : seul le propriétaire n'est pas impacté."}</div></div>
        <div class="list">
          ${users.map((u) => u.is_owner
            ? `<label class="check"><input type="checkbox" checked disabled>
                <span class="grow">${esc(u.name)} <span class="muted">propriétaire · toujours exempté</span></span></label>`
            : `<label class="check"><input type="checkbox" data-action="toggle-user" data-user="${esc(u.id)}" ${dr.allowed_users.includes(u.id) ? "checked" : ""}>
                <span class="grow">${esc(u.name)} ${u.is_admin ? `<span class="muted">administrateur</span>` : ""}</span></label>`).join("")}
        </div>
      </div></ha-card>

      <div class="actions" style="margin-top:0">
        <button class="btn primary" data-action="save-settings" ${this._draftDirty ? "" : "disabled"}>Enregistrer</button>
        <button class="btn" data-action="reset-settings" ${this._draftDirty ? "" : "disabled"}>Annuler les modifications</button>
      </div>`;
  }

  // ----- onglet « Accès » -----
  _accessHtml() {
    const users = this._data.users || [];
    const defaults = { true: "Vue administrateur", false: "Vue utilisateur" };
    return `<ha-card class="card"><div class="col">
      <div><h2>Qui voit quelle vue du panneau</h2>
        <div class="muted">« Par défaut » : les administrateurs ont la vue administrateur, les autres la vue utilisateur.
          Le propriétaire a toujours la vue administrateur. Une vue administrateur permet de tout configurer,
          y compris pour un utilisateur non administrateur de Home Assistant.</div></div>
      <table>${users.map((u) => `<tr>
        <td><div>${esc(u.name)}</div>
          <div class="muted">${u.is_owner ? "propriétaire" : u.is_admin ? "administrateur" : "utilisateur"}</div></td>
        <td class="sel">${u.is_owner
          ? `<span class="muted">Vue administrateur (fixe)</span>`
          : `<select data-action="role" data-user="${esc(u.id)}">
              <option value="" ${u.explicit ? "" : "selected"}>Par défaut (${defaults[u.is_admin]})</option>
              ${["admin", "viewer", "none"].map((r) =>
                `<option value="${r}" ${u.explicit && u.role === r ? "selected" : ""}>${ROLE_LABELS[r]}</option>`).join("")}
            </select>`}</td></tr>`).join("")}</table>
    </div></ha-card>`;
  }

  // ---------- évènements ----------
  _onClick(e) {
    const t = e.target.closest("[data-action]");
    if (!t || t.matches("input, select, textarea")) return;
    this._act(t.dataset.action, t);
  }

  _onChange(e) {
    const t = e.target;
    if (t.dataset?.action && t.matches("input, select")) this._act(t.dataset.action, t);
  }

  _onInput(e) {
    const t = e.target;
    const field = t.dataset?.field;
    if (!field) return;
    if (field === "auto-search") {
      this._autoFilter = t.value;
      const f = t.value.toLowerCase();
      this.shadowRoot.querySelectorAll("[data-filter]").forEach((row) => {
        row.hidden = !!f && !row.dataset.filter.includes(f);
      });
    } else if (field === "form.start") this._form.start = t.value;
    else if (field === "form.end") this._form.end = t.value;
    else if (field === "form.reason") this._form.reason = t.value;
    else if (field === "form.custom") this._form.custom = t.value;
    else if (field === "draft.message") { this._draft.message = t.value; this._markDirty(); }
    else if (field === "draft.warn") { this._draft.warn_minutes = Number(t.value) || 15; this._markDirty(); }
  }

  _markDirty() {
    if (this._draftDirty) return;
    this._draftDirty = true;
    this.shadowRoot.querySelectorAll('[data-action="save-settings"], [data-action="reset-settings"]')
      .forEach((b) => { b.disabled = false; });
  }

  _toggle(list, value) {
    const i = list.indexOf(value);
    if (i >= 0) list.splice(i, 1); else list.push(value);
  }

  _defaultStart() {
    const d = new Date(Date.now() + 60 * 60000);
    d.setMinutes(0, 0, 0);
    return d;
  }

  _local(d) {
    if (!d) return "";
    const x = d instanceof Date ? d : new Date(d);
    const p = (n) => String(n).padStart(2, "0");
    return `${x.getFullYear()}-${p(x.getMonth() + 1)}-${p(x.getDate())}T${p(x.getHours())}:${p(x.getMinutes())}`;
  }

  _openForm(mode, w) {
    const start = this._defaultStart();
    this._form = {
      mode,
      id: w?.id || null,
      start: w ? this._local(w.start) : this._local(start),
      end: w ? this._local(w.end) : mode === "add" ? this._local(new Date(start.getTime() + 2 * 3600000)) : "",
      reason: w?.reason || "",
      scope: w?.pages?.length ? "pages" : "all",
      pages: [...(w?.pages || [])],
      custom: "",
      pause: w ? w.pause_automations : true,
    };
    this._error = "";
    this._render(true);
  }

  async _saveForm() {
    const f = this._form;
    if (f.scope === "pages" && !f.pages.length) {
      this._error = "Sélectionne au moins une page, ou choisis « Tout Home Assistant ».";
      this._render(true);
      return;
    }
    const iso = (v) => (v ? new Date(v).toISOString() : null);
    const base = { reason: f.reason.trim(), pages: f.scope === "pages" ? f.pages : [] };
    const end = iso(f.end);
    let ok;
    if (f.mode === "add" || f.mode === "edit") {
      if (!f.start) { this._error = "Indique la date de début."; this._render(true); return; }
      const payload = { ...base, start: iso(f.start), end, pause_automations: f.pause };
      ok = f.mode === "add"
        ? await this._call("add_window", payload)
        : await this._call("update_window", { window_id: f.id, ...payload });
    } else if (f.mode === "now") {
      ok = await this._call("start", { ...base, end, pause_automations: f.pause });
    } else {
      ok = await this._call("update_current", { ...base, end });
    }
    if (ok) { this._form = null; this._render(true); }
  }

  async _act(action, t) {
    if (action !== "stop" && action !== "delete") this._confirm = null;
    const f = this._form;
    switch (action) {
      case "menu":
        this.dispatchEvent(new CustomEvent("hass-toggle-menu", { bubbles: true, composed: true }));
        return;
      case "tab":
        this._tab = t.dataset.tab; this._error = ""; this._form = null; this._render(true); return;
      case "form-add": this._openForm("add"); return;
      case "form-now": this._openForm("now"); return;
      case "form-current": this._openForm("current", this._data.current); return;
      case "form-edit": this._openForm("edit", this._data.upcoming.find((w) => w.id === t.dataset.id)); return;
      case "form-cancel": this._form = null; this._error = ""; this._render(true); return;
      case "form-save": await this._saveForm(); return;
      case "form-pause": f.pause = t.checked; return;
      case "scope": f.scope = t.value; this._render(true); return;
      case "toggle-page": this._toggle(f.pages, t.dataset.page); return;
      case "add-custom-page": {
        const p = f.custom.trim().replace(/^\/+|\/+$/g, "");
        if (p && !f.pages.includes(p)) f.pages.push(p);
        f.custom = ""; this._render(true); return;
      }
      case "remove-page": f.pages = f.pages.filter((p) => p !== t.dataset.page); this._render(true); return;
      case "stop":
        if (this._confirm !== "stop") { this._confirm = "stop"; this._render(true); return; }
        this._confirm = null; await this._call("stop"); return;
      case "delete":
        if (this._confirm !== t.dataset.id) { this._confirm = t.dataset.id; this._render(true); return; }
        this._confirm = null; await this._call("delete_window", { window_id: t.dataset.id }); return;
      case "toggle-auto":
        this._toggle(this._draft.automations, t.dataset.entity); this._draftDirty = true; this._render(true); return;
      case "auto-none":
        this._draft.automations = []; this._draftDirty = true; this._render(true); return;
      case "toggle-user":
        this._toggle(this._draft.allowed_users, t.dataset.user); this._draftDirty = true; this._render(true); return;
      case "save-settings": {
        const ok = await this._call("update_config", {
          automations: this._draft.automations,
          allowed_users: this._draft.allowed_users,
          warn_minutes: Number(this._draft.warn_minutes) || 15,
          message: this._draft.message,
        });
        if (ok) { this._draftDirty = false; if (this._data?.config) this._onData(this._data); }
        return;
      }
      case "reset-settings":
        this._draftDirty = false; this._onData(this._data); this._render(true); return;
      case "role": {
        const access = { ...(this._data.config?.panel_access || {}) };
        if (t.value) access[t.dataset.user] = t.value; else delete access[t.dataset.user];
        await this._call("update_config", { panel_access: access });
        return;
      }
      default:
    }
  }
}

customElements.define("maintenance-mode-panel", MaintenanceModePanel);
