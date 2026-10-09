/* Mode maintenance — panneau de configuration (Web Component, sans build).
 * Les droits (aucun / vue utilisateur / vue administrateur) sont vérifiés côté
 * serveur ; ce fichier ne fait qu'afficher ce que le serveur autorise.
 * Langues : français et anglais (selon la langue de l'utilisateur). */

const esc = (v) =>
  String(v ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const T = {
  fr: {
    title: "Maintenance", tab_list: "Maintenances", tab_settings: "Paramètres", tab_access: "Accès",
    loading: "Chargement…", unreachable: "Impossible de joindre l'intégration.",
    no_access: "Tu n'as pas accès à ce panneau.", no_access_hint: "Demande à un administrateur de modifier tes droits.",
    running: "Maintenance en cours", since: "Depuis {start}", end_planned: "Fin prévue {end} ({rel})",
    no_end: "Pas d'heure de fin définie", paused_n: "{n} automatisation(s) suspendue(s)",
    edit: "Modifier", stop_now: "Terminer maintenant", confirm_stop: "Confirmer l'arrêt ?",
    none_running: "Aucune maintenance en cours", next: "Prochaine : {start} ({rel})", none_planned: "Aucune maintenance planifiée.",
    start_btn: "Démarrer une maintenance", planned_title: "Maintenances planifiées", plan_btn: "Planifier",
    nothing: "Rien de prévu pour le moment.", no_end_text: "fin non définie", autos_kept: "Automatisations non suspendues",
    duplicate: "Dupliquer", delete: "Supprimer", confirm_delete: "Confirmer ?",
    repeat_none: "Aucune", repeat_daily: "Tous les jours", repeat_weekly: "Toutes les semaines", repeat_monthly: "Tous les mois",
    all_ha: "Tout Home Assistant", main_dashboard: "Tableau de bord principal",
    form_add: "Planifier une maintenance", form_edit: "Modifier la maintenance",
    form_now: "Démarrer une maintenance maintenant", form_current: "Modifier la maintenance en cours",
    tpl_apply: "Appliquer un modèle", tpl_choose: "— choisir —", start: "Début", end_opt: "Fin prévue (facultatif)",
    reason_opt: "Motif (facultatif)", scope: "Portée", scope_pages: "Certaines pages seulement",
    custom_ph: "Autre chemin, ex. config/helpers", add: "Ajouter", remove: "Retirer",
    page_hint: "Un chemin bloque aussi ses sous-pages (ex. config/devices bloque config/devices/dashboard).",
    repeat: "Répétition", repeat_hint: "Une répétition demande une fin. Supprimer l'occurrence suivante arrête la série.",
    pause_autos: "Suspendre les automatisations pendant la maintenance", save: "Enregistrer", cancel: "Annuler",
    tpl_save: "Enregistrer comme modèle", tpl_name_ph: "Nom du modèle",
    err_pages: "Sélectionne au moins une page, ou choisis « Tout Home Assistant ».", err_start: "Indique la date de début.",
    err_tpl_name: "Donne un nom au modèle.",
    s_page: "Page de maintenance", s_message: "Message affiché aux utilisateurs bloqués",
    s_warn: "Préavis de la notification (minutes avant le début)", s_autos: "Automatisations suspendues",
    s_autos_n: "{n} sélectionnée(s) : seules celles-ci sont coupées.",
    s_autos_all: "Aucune sélectionnée : <b>toutes</b> les automatisations sont coupées pendant la maintenance.",
    search: "Rechercher…", no_autos: "Aucune automatisation trouvée.", deselect_all: "Tout désélectionner",
    s_users: "Utilisateurs non impactés", s_users_some: "Ces utilisateurs (et le propriétaire) ne sont jamais bloqués.",
    s_users_none: "Aucun sélectionné : seul le propriétaire n'est pas impacté.",
    owner_fixed: "propriétaire · toujours exempté", admin_badge: "administrateur",
    s_notify: "Notifications push", s_notify_hint: "Services de notification qui recevront les messages (application mobile…).",
    no_notify: "Aucun service de notification trouvé.", k_pre: "Avant le début", k_started: "Au début",
    k_end_soon: "Avant la fin", k_ended: "À la fin", end_soon_min: "Rappel avant la fin (minutes)",
    s_templates: "Modèles", no_templates: "Aucun modèle. Enregistre-en un depuis le formulaire d'une maintenance.",
    save_changes: "Enregistrer", reset_changes: "Annuler les modifications",
    a_title: "Qui voit quelle vue du panneau",
    a_hint: "« Par défaut » : les administrateurs ont la vue administrateur, les autres la vue utilisateur. Le propriétaire a toujours la vue administrateur. Une vue administrateur permet de tout configurer, y compris pour un utilisateur non administrateur de Home Assistant. « Aucun accès » masque aussi le panneau dans le menu.",
    role_none: "Aucun accès", role_viewer: "Vue utilisateur", role_admin: "Vue administrateur",
    default_for: "Par défaut ({role})", fixed_admin: "Vue administrateur (fixe)",
    u_owner: "propriétaire", u_admin: "administrateur", u_user: "utilisateur",
    h_title: "Historique", h_empty: "Aucune maintenance passée.", h_by: "par {who}",
    e_manual: "arrêtée à la main", e_auto: "terminée automatiquement", e_replaced: "remplacée par une autre",
  },
  en: {
    title: "Maintenance", tab_list: "Maintenance", tab_settings: "Settings", tab_access: "Access",
    loading: "Loading…", unreachable: "Cannot reach the integration.",
    no_access: "You do not have access to this panel.", no_access_hint: "Ask an administrator to change your rights.",
    running: "Maintenance in progress", since: "Since {start}", end_planned: "Expected end {end} ({rel})",
    no_end: "No end time set", paused_n: "{n} automation(s) paused",
    edit: "Edit", stop_now: "End now", confirm_stop: "Confirm stop?",
    none_running: "No maintenance in progress", next: "Next: {start} ({rel})", none_planned: "No maintenance scheduled.",
    start_btn: "Start a maintenance", planned_title: "Scheduled maintenance", plan_btn: "Schedule",
    nothing: "Nothing planned for now.", no_end_text: "no end set", autos_kept: "Automations not paused",
    duplicate: "Duplicate", delete: "Delete", confirm_delete: "Confirm?",
    repeat_none: "None", repeat_daily: "Every day", repeat_weekly: "Every week", repeat_monthly: "Every month",
    all_ha: "All of Home Assistant", main_dashboard: "Main dashboard",
    form_add: "Schedule a maintenance", form_edit: "Edit maintenance",
    form_now: "Start a maintenance now", form_current: "Edit current maintenance",
    tpl_apply: "Apply a template", tpl_choose: "— choose —", start: "Start", end_opt: "Expected end (optional)",
    reason_opt: "Reason (optional)", scope: "Scope", scope_pages: "Some pages only",
    custom_ph: "Other path, e.g. config/helpers", add: "Add", remove: "Remove",
    page_hint: "A path also blocks its sub-pages (e.g. config/devices blocks config/devices/dashboard).",
    repeat: "Repeat", repeat_hint: "A repeat requires an end. Deleting the next occurrence stops the series.",
    pause_autos: "Pause automations during maintenance", save: "Save", cancel: "Cancel",
    tpl_save: "Save as template", tpl_name_ph: "Template name",
    err_pages: "Select at least one page, or choose \"All of Home Assistant\".", err_start: "Enter the start date.",
    err_tpl_name: "Give the template a name.",
    s_page: "Maintenance page", s_message: "Message shown to blocked users",
    s_warn: "Notification lead time (minutes before start)", s_autos: "Paused automations",
    s_autos_n: "{n} selected: only these are turned off.",
    s_autos_all: "None selected: <b>all</b> automations are turned off during maintenance.",
    search: "Search…", no_autos: "No automation found.", deselect_all: "Deselect all",
    s_users: "Unaffected users", s_users_some: "These users (and the owner) are never blocked.",
    s_users_none: "None selected: only the owner is unaffected.",
    owner_fixed: "owner · always exempt", admin_badge: "administrator",
    s_notify: "Push notifications", s_notify_hint: "Notification services that will receive the messages (mobile app…).",
    no_notify: "No notification service found.", k_pre: "Before start", k_started: "At start",
    k_end_soon: "Before end", k_ended: "At end", end_soon_min: "Reminder before end (minutes)",
    s_templates: "Templates", no_templates: "No template. Save one from a maintenance form.",
    save_changes: "Save", reset_changes: "Discard changes",
    a_title: "Who sees which view of the panel",
    a_hint: "\"Default\": administrators get the administrator view, others the user view. The owner always has the administrator view. The administrator view can configure everything, even for a non-administrator Home Assistant user. \"No access\" also hides the panel from the menu.",
    role_none: "No access", role_viewer: "User view", role_admin: "Administrator view",
    default_for: "Default ({role})", fixed_admin: "Administrator view (fixed)",
    u_owner: "owner", u_admin: "administrator", u_user: "user",
    h_title: "History", h_empty: "No past maintenance.", h_by: "by {who}",
    e_manual: "stopped manually", e_auto: "ended automatically", e_replaced: "replaced by another",
  },
};

const EXTRA_PAGES = {
  fr: [
    ["config/devices", "Paramètres › Appareils"], ["config/integrations", "Paramètres › Intégrations"],
    ["config/entities", "Paramètres › Entités"], ["config/areas", "Paramètres › Zones"],
    ["config/automation", "Paramètres › Automatisations"], ["config/script", "Paramètres › Scripts"],
    ["config/scene", "Paramètres › Scènes"], ["config/helpers", "Paramètres › Entrées"],
    ["config/backup", "Paramètres › Sauvegardes"], ["config/person", "Paramètres › Personnes"],
    ["config/users", "Paramètres › Utilisateurs"], ["config/voice-assistants", "Paramètres › Assistants vocaux"],
    ["config/lovelace/dashboards", "Paramètres › Tableaux de bord"],
  ],
  en: [
    ["config/devices", "Settings › Devices"], ["config/integrations", "Settings › Integrations"],
    ["config/entities", "Settings › Entities"], ["config/areas", "Settings › Areas"],
    ["config/automation", "Settings › Automations"], ["config/script", "Settings › Scripts"],
    ["config/scene", "Settings › Scenes"], ["config/helpers", "Settings › Helpers"],
    ["config/backup", "Settings › Backups"], ["config/person", "Settings › People"],
    ["config/users", "Settings › Users"], ["config/voice-assistants", "Settings › Voice assistants"],
    ["config/lovelace/dashboards", "Settings › Dashboards"],
  ],
};

const NOTIFY_KINDS = ["pre", "started", "end_soon", "ended"];

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
  .btn:disabled { opacity: .5; cursor: default; }
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
  td.sel { width: 220px; }
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
  set narrow(v) {
    v = !!v;
    if (v === this._narrow) return;  // HA réaffecte la propriété à chaque mise à jour
    this._narrow = v;
    if (this._data || this._fatal) this._render(true);
  }
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

  // ---------- traduction ----------
  _lang() { return this._hass?.locale?.language || "fr"; }
  _code() { const c = this._lang().split("-")[0]; return T[c] ? c : "en"; }
  _t(key, vars = {}) {
    let s = T[this._code()][key] ?? T.en[key] ?? key;
    for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, esc(v));
    return s;
  }

  // ---------- données ----------
  _init() {
    this._hass.connection
      .subscribeMessage((d) => this._onData(d), { type: "maintenance_mode/subscribe" })
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
        end_soon_minutes: d.config.end_soon_minutes,
        message: d.config.message,
        notify_services: [...d.config.notify_services],
        notify_kinds: [...d.config.notify_kinds],
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
    return `${this._fmt(w.start)} → ${w.end ? this._fmt(w.end) : this._t("no_end_text")}`;
  }

  _pageOptions() {
    const out = new Map();
    const panels = this._hass?.panels || {};
    for (const p of Object.values(panels)) {
      if (!p?.url_path) continue;
      if (!p.title && p.url_path !== "lovelace") continue; // seulement ce qui est dans la barre latérale
      const label = p.title ? (this._hass.localize?.(`panel.${p.title}`) || p.title) : this._t("main_dashboard");
      out.set(p.url_path, label);
    }
    for (const [path, label] of EXTRA_PAGES[this._code()]) out.set(path, label);
    return [...out.entries()].map(([path, label]) => ({ path, label }))
      .sort((a, b) => a.label.localeCompare(b.label, this._lang()));
  }

  _pageLabel(path) {
    return this._pageOptions().find((o) => o.path === path)?.label || path;
  }

  _repeatLabel(r) { return this._t(`repeat_${r}`); }

  _chips(w) {
    const scope = w.pages && w.pages.length
      ? w.pages.map((p) => `<span class="chip">${esc(this._pageLabel(p))}</span>`).join("")
      : `<span class="chip">${this._t("all_ha")}</span>`;
    const rep = w.repeat && w.repeat !== "none" ? `<span class="chip">↻ ${this._repeatLabel(w.repeat)}</span>` : "";
    return `<div class="chips">${scope}${rep}</div>`;
  }

  _automations() {
    return Object.values(this._hass?.states || {})
      .filter((s) => s.entity_id.startsWith("automation."))
      .map((s) => ({ id: s.entity_id, name: s.attributes.friendly_name || s.entity_id }))
      .sort((a, b) => a.name.localeCompare(b.name, this._lang()));
  }

  _notifyServices() {
    return Object.keys(this._hass?.services?.notify || {})
      .filter((n) => n !== "send_message").sort();
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
    // Positions de défilement : page (.scroll) puis listes internes (.list), dans l'ordre du DOM
    const keep = this._resetScroll
      ? []
      : [...root.querySelectorAll(".scroll, .list")].map((e) => e.scrollTop);
    this._resetScroll = false;
    root.innerHTML = `<style>${STYLES}</style>
      <div class="shell">
        ${this._barHtml()}
        <div class="scroll"><div class="wrap">${this._bodyHtml()}</div></div>
      </div>`;
    const apply = () => {
      const els = [...root.querySelectorAll(".scroll, .list")];
      keep.forEach((v, i) => { if (els[i]) els[i].scrollTop = v; });
    };
    apply();
    requestAnimationFrame(apply);  // 2e passe : le contenu des ha-card est rendu en différé
  }

  _barHtml() {
    const admin = this._data?.role === "admin";
    const tab = (id, label) =>
      `<button class="tab ${this._tab === id ? "active" : ""}" data-action="tab" data-tab="${id}">${label}</button>`;
    return `<div class="bar">
      <div class="toolbar">
        <button class="icon-btn" data-action="menu" ${this._narrow ? "" : "hidden"} aria-label="Menu">
          <ha-icon icon="mdi:menu"></ha-icon></button>
        <h1>${this._t("title")}</h1>
      </div>
      ${admin ? `<div class="tabs">${tab("list", this._t("tab_list"))}${tab("settings", this._t("tab_settings"))}${tab("access", this._t("tab_access"))}</div>` : ""}
    </div>`;
  }

  _bodyHtml() {
    if (this._fatal) {
      return `<ha-card class="card"><div class="empty"><ha-icon icon="mdi:alert-circle-outline"></ha-icon>
        ${this._t("unreachable")}<br><span class="muted">${esc(this._fatal)}</span></div></ha-card>`;
    }
    if (!this._data) {
      return `<ha-card class="card"><div class="empty"><ha-icon icon="mdi:timer-sand"></ha-icon>${this._t("loading")}</div></ha-card>`;
    }
    if (this._data.role === "none") {
      return `<ha-card class="card"><div class="empty"><ha-icon icon="mdi:lock-outline"></ha-icon>
        ${this._t("no_access")}<br><span class="muted">${this._t("no_access_hint")}</span></div></ha-card>`;
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
      const end = cur.end
        ? this._t("end_planned", { end: this._fmt(cur.end), rel: this._rel(cur.end) })
        : esc(this._t("no_end"));
      html += `<ha-card class="card"><div class="row">
        <div class="badge warn"><ha-icon icon="mdi:wrench-clock"></ha-icon></div>
        <div class="grow"><h2>${this._t("running")}</h2>
          <div class="muted">${this._t("since", { start: this._fmt(cur.start) })} · ${end}</div>
          ${cur.reason ? `<div style="margin-top:6px">${esc(cur.reason)}</div>` : ""}
          ${this._chips(cur)}
          ${admin && d.disabled_count ? `<div class="muted" style="margin-top:6px">${this._t("paused_n", { n: d.disabled_count })}</div>` : ""}
        </div></div>
        ${admin ? `<div class="actions">
          <button class="btn" data-action="form-current">${this._t("edit")}</button>
          <button class="btn danger" data-action="stop">${this._confirm === "stop" ? this._t("confirm_stop") : this._t("stop_now")}</button>
        </div>` : ""}</ha-card>`;
    } else {
      const next = d.upcoming[0];
      html += `<ha-card class="card"><div class="row">
        <div class="badge"><ha-icon icon="mdi:check-circle-outline"></ha-icon></div>
        <div class="grow"><h2>${this._t("none_running")}</h2>
          <div class="muted">${next ? this._t("next", { start: this._fmt(next.start), rel: this._rel(next.start) }) : this._t("none_planned")}</div>
        </div></div>
        ${admin ? `<div class="actions"><button class="btn primary" data-action="form-now">${this._t("start_btn")}</button></div>` : ""}
      </ha-card>`;
    }

    if (this._form) html += this._formHtml();

    html += `<ha-card class="card"><div class="row"><div class="grow"><h2>${this._t("planned_title")}</h2></div>
      ${admin && !this._form ? `<button class="btn primary sm" data-action="form-add">${this._t("plan_btn")}</button>` : ""}</div>`;
    if (!d.upcoming.length) {
      html += `<div class="empty"><ha-icon icon="mdi:calendar-blank-outline"></ha-icon>${this._t("nothing")}</div>`;
    } else {
      html += d.upcoming.map((w) => `<div class="item">
        <div class="badge"><ha-icon icon="mdi:${w.repeat && w.repeat !== "none" ? "calendar-sync" : "calendar-clock"}"></ha-icon></div>
        <div class="grow"><h3>${this._fmt(w.start)} <span class="muted">(${this._rel(w.start)})</span></h3>
          <div class="muted">${esc(this._range(w))}</div>
          ${w.reason ? `<div style="margin-top:4px">${esc(w.reason)}</div>` : ""}
          ${this._chips(w)}
          ${admin && !w.pause_automations ? `<div class="muted" style="margin-top:4px">${this._t("autos_kept")}</div>` : ""}
        </div>
        ${admin ? `<div class="col" style="gap:6px">
          <button class="btn sm" data-action="form-edit" data-id="${esc(w.id)}">${this._t("edit")}</button>
          <button class="btn sm" data-action="form-dup" data-id="${esc(w.id)}">${this._t("duplicate")}</button>
          <button class="btn sm danger" data-action="delete" data-id="${esc(w.id)}">${this._confirm === w.id ? this._t("confirm_delete") : this._t("delete")}</button>
        </div>` : ""}
      </div>`).join("");
    }
    html += `</ha-card>`;

    if (admin) html += this._historyHtml();
    return html;
  }

  _historyHtml() {
    const hist = this._data.history || [];
    const ended = { manual: "e_manual", auto: "e_auto", replaced: "e_replaced" };
    return `<ha-card class="card"><h2>${this._t("h_title")}</h2>
      ${hist.length ? hist.map((h) => `<div class="item">
        <div class="badge"><ha-icon icon="mdi:history"></ha-icon></div>
        <div class="grow"><h3>${this._fmt(h.start)} → ${this._fmt(h.ended_at)}</h3>
          <div class="muted">${this._t(ended[h.ended_by] || "e_auto")}${h.started_by ? " · " + this._t("h_by", { who: h.started_by }) : ""}</div>
          ${h.reason ? `<div style="margin-top:4px">${esc(h.reason)}</div>` : ""}
          ${this._chips(h)}
        </div></div>`).join("")
        : `<div class="empty"><ha-icon icon="mdi:history"></ha-icon>${this._t("h_empty")}</div>`}
    </ha-card>`;
  }

  _formHtml() {
    const f = this._form;
    const titles = { add: "form_add", edit: "form_edit", now: "form_now", current: "form_current" };
    const showStart = f.mode === "add" || f.mode === "edit";
    const showPause = f.mode !== "current";
    const showRepeat = showStart;
    const showTpl = f.mode !== "current";
    const tpls = this._data.config?.templates || [];
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
        <input type="text" placeholder="${esc(this._t("custom_ph"))}" data-field="form.custom" value="${esc(f.custom)}">
        <button class="btn sm" data-action="add-custom-page">${this._t("add")}</button>
      </div>
      ${extra.length ? `<div class="chips">${extra.map((p) => `<span class="chip">${esc(p)}<button data-action="remove-page" data-page="${esc(p)}" aria-label="${esc(this._t("remove"))}">×</button></span>`).join("")}</div>` : ""}
      <div class="muted">${this._t("page_hint")}</div>` : "";

    return `<ha-card class="card"><div class="col">
      <h2>${this._t(titles[f.mode])}</h2>
      ${this._error ? `<div class="banner error">${esc(this._error)}</div>` : ""}
      ${showTpl && tpls.length ? `<label class="field">${this._t("tpl_apply")}
        <select data-action="apply-template"><option value="">${this._t("tpl_choose")}</option>
          ${tpls.map((t) => `<option value="${esc(t.id)}">${esc(t.name)}</option>`).join("")}</select></label>` : ""}
      <div class="grid2">
        ${showStart ? `<label class="field">${this._t("start")}<input type="datetime-local" data-field="form.start" value="${esc(f.start)}"></label>` : ""}
        <label class="field">${this._t("end_opt")}<input type="datetime-local" data-field="form.end" value="${esc(f.end)}"></label>
      </div>
      <label class="field">${this._t("reason_opt")}<input type="text" maxlength="200" data-field="form.reason" value="${esc(f.reason)}"></label>
      <div class="col" style="gap:8px"><span class="muted">${this._t("scope")}</span>
        <div class="radio">
          <label><input type="radio" name="scope" data-action="scope" value="all" ${f.scope === "all" ? "checked" : ""}> ${this._t("all_ha")}</label>
          <label><input type="radio" name="scope" data-action="scope" value="pages" ${f.scope === "pages" ? "checked" : ""}> ${this._t("scope_pages")}</label>
        </div>
        ${pagesBlock}
      </div>
      ${showRepeat ? `<label class="field">${this._t("repeat")}
        <select data-action="form-repeat">${["none", "daily", "weekly", "monthly"].map((r) =>
          `<option value="${r}" ${f.repeat === r ? "selected" : ""}>${this._repeatLabel(r)}</option>`).join("")}</select>
        <span class="muted">${this._t("repeat_hint")}</span></label>` : ""}
      ${showPause ? `<label class="check"><input type="checkbox" data-action="form-pause" ${f.pause ? "checked" : ""}>
        <span>${this._t("pause_autos")}</span></label>` : ""}
      <div class="actions" style="margin-top:0">
        <button class="btn primary" data-action="form-save">${this._t("save")}</button>
        <button class="btn" data-action="form-cancel">${this._t("cancel")}</button>
      </div>
      ${showTpl ? `<div class="row">
        <input type="text" maxlength="40" placeholder="${esc(this._t("tpl_name_ph"))}" data-field="form.tplName" value="${esc(f.tplName)}">
        <button class="btn sm" data-action="save-template">${this._t("tpl_save")}</button></div>` : ""}
    </div></ha-card>`;
  }

  // ----- onglet « Paramètres » -----
  _settingsHtml() {
    const dr = this._draft;
    const users = this._data.users || [];
    const autos = this._automations();
    const f = this._autoFilter.toLowerCase();
    const selected = new Set(dr.automations);
    const notifyServices = this._notifyServices();
    const tpls = this._data.config?.templates || [];
    return `
      <ha-card class="card"><div class="col">
        <h2>${this._t("s_page")}</h2>
        <label class="field">${this._t("s_message")}
          <textarea maxlength="255" data-field="draft.message">${esc(dr.message)}</textarea></label>
        <label class="field">${this._t("s_warn")}
          <input type="number" min="1" max="1440" data-field="draft.warn" value="${esc(dr.warn_minutes)}"></label>
      </div></ha-card>

      <ha-card class="card"><div class="col">
        <div><h2>${this._t("s_autos")}</h2>
          <div class="muted">${dr.automations.length ? this._t("s_autos_n", { n: dr.automations.length }) : this._t("s_autos_all")}</div></div>
        <input type="text" placeholder="${esc(this._t("search"))}" data-field="auto-search" value="${esc(this._autoFilter)}">
        <div class="list">
          ${autos.length ? autos.map((a) => `<label class="check" data-filter="${esc((a.name + " " + a.id).toLowerCase())}"
              ${f && !(a.name + " " + a.id).toLowerCase().includes(f) ? "hidden" : ""}>
            <input type="checkbox" data-action="toggle-auto" data-entity="${esc(a.id)}" ${selected.has(a.id) ? "checked" : ""}>
            <span class="grow">${esc(a.name)} <span class="muted">${esc(a.id)}</span></span></label>`).join("")
            : `<div class="empty">${this._t("no_autos")}</div>`}
        </div>
        ${dr.automations.length ? `<div><button class="btn sm" data-action="auto-none">${this._t("deselect_all")}</button></div>` : ""}
      </div></ha-card>

      <ha-card class="card"><div class="col">
        <div><h2>${this._t("s_users")}</h2>
          <div class="muted">${dr.allowed_users.length ? this._t("s_users_some") : this._t("s_users_none")}</div></div>
        <div class="list">
          ${users.map((u) => u.is_owner
            ? `<label class="check"><input type="checkbox" checked disabled>
                <span class="grow">${esc(u.name)} <span class="muted">${this._t("owner_fixed")}</span></span></label>`
            : `<label class="check"><input type="checkbox" data-action="toggle-user" data-user="${esc(u.id)}" ${dr.allowed_users.includes(u.id) ? "checked" : ""}>
                <span class="grow">${esc(u.name)} ${u.is_admin ? `<span class="muted">${this._t("admin_badge")}</span>` : ""}</span></label>`).join("")}
        </div>
      </div></ha-card>

      <ha-card class="card"><div class="col">
        <div><h2>${this._t("s_notify")}</h2><div class="muted">${this._t("s_notify_hint")}</div></div>
        <div class="list">
          ${notifyServices.length ? notifyServices.map((n) => `<label class="check">
            <input type="checkbox" data-action="toggle-notify" data-svc="${esc(n)}" ${dr.notify_services.includes(n) ? "checked" : ""}>
            <span class="grow">notify.${esc(n)}</span></label>`).join("")
            : `<div class="empty">${this._t("no_notify")}</div>`}
        </div>
        <div class="radio">
          ${NOTIFY_KINDS.map((k) => `<label><input type="checkbox" data-action="toggle-kind" data-kind="${k}" ${dr.notify_kinds.includes(k) ? "checked" : ""}> ${this._t("k_" + k)}</label>`).join("")}
        </div>
        <label class="field">${this._t("end_soon_min")}
          <input type="number" min="1" max="1440" data-field="draft.endsoon" value="${esc(dr.end_soon_minutes)}"></label>
      </div></ha-card>

      <div class="actions" style="margin-top:0">
        <button class="btn primary" data-action="save-settings" ${this._draftDirty ? "" : "disabled"}>${this._t("save_changes")}</button>
        <button class="btn" data-action="reset-settings" ${this._draftDirty ? "" : "disabled"}>${this._t("reset_changes")}</button>
      </div>

      <ha-card class="card"><div class="col">
        <h2>${this._t("s_templates")}</h2>
        ${tpls.length ? tpls.map((t) => `<div class="item">
          <div class="badge"><ha-icon icon="mdi:content-copy"></ha-icon></div>
          <div class="grow"><h3>${esc(t.name)}</h3>
            <div class="muted">${t.duration ? t.duration + " min" : ""}${t.reason ? (t.duration ? " · " : "") + esc(t.reason) : ""}</div>
            ${this._chips(t)}</div>
          <button class="btn sm danger" data-action="delete-template" data-id="${esc(t.id)}">${this._confirm === "tpl:" + t.id ? this._t("confirm_delete") : this._t("delete")}</button>
        </div>`).join("") : `<div class="muted">${this._t("no_templates")}</div>`}
      </div></ha-card>`;
  }

  // ----- onglet « Accès » -----
  _accessHtml() {
    const users = this._data.users || [];
    const roleLabel = (r) => this._t(`role_${r}`);
    return `<ha-card class="card"><div class="col">
      <div><h2>${this._t("a_title")}</h2><div class="muted">${this._t("a_hint")}</div></div>
      <table>${users.map((u) => `<tr>
        <td><div>${esc(u.name)}</div>
          <div class="muted">${u.is_owner ? this._t("u_owner") : u.is_admin ? this._t("u_admin") : this._t("u_user")}</div></td>
        <td class="sel">${u.is_owner
          ? `<span class="muted">${this._t("fixed_admin")}</span>`
          : `<select data-action="role" data-user="${esc(u.id)}">
              <option value="" ${u.explicit ? "" : "selected"}>${this._t("default_for", { role: roleLabel(u.is_admin ? "admin" : "viewer") })}</option>
              ${["admin", "viewer", "none"].map((r) =>
                `<option value="${r}" ${u.explicit && u.role === r ? "selected" : ""}>${roleLabel(r)}</option>`).join("")}
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
    else if (field === "form.tplName") this._form.tplName = t.value;
    else if (field === "draft.message") { this._draft.message = t.value; this._markDirty(); }
    else if (field === "draft.warn") { this._draft.warn_minutes = Number(t.value) || 15; this._markDirty(); }
    else if (field === "draft.endsoon") { this._draft.end_soon_minutes = Number(t.value) || 10; this._markDirty(); }
  }

  _markDirty() {
    if (this._draftDirty) return;
    this._draftDirty = true;
    
    // CORRECTION : On cible directement les boutons existants dans le DOM actuel
    // pour changer leur état instantanément SANS relancer de rendu destructif.
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

  // mode : add | edit | now | current ; w : fenêtre source ; dup : copie (nouvelles dates)
  _openForm(mode, w, dup = false) {
    const start = this._defaultStart();
    let startV = w && !dup ? this._local(w.start) : this._local(start);
    let endV = "";
    if (w && !dup) endV = this._local(w.end);
    else if (w && dup && w.end) endV = this._local(new Date(start.getTime() + (new Date(w.end) - new Date(w.start))));
    else if (mode === "add") endV = this._local(new Date(start.getTime() + 2 * 3600000));
    this._form = {
      mode, id: dup ? null : (w?.id || null),
      start: startV, end: endV,
      reason: w?.reason || "",
      scope: w?.pages?.length ? "pages" : "all",
      pages: [...(w?.pages || [])],
      custom: "", tplName: "",
      pause: w ? w.pause_automations !== false : true,
      repeat: w?.repeat || "none",
    };
    this._error = "";
    this._render(true);
  }

  _applyTemplate(id) {
    const t = (this._data.config?.templates || []).find((x) => x.id === id);
    if (!t) return;
    const f = this._form;
    f.reason = t.reason || "";
    f.pages = [...(t.pages || [])];
    f.scope = f.pages.length ? "pages" : "all";
    f.pause = t.pause_automations !== false;
    f.repeat = t.repeat || "none";
    if (t.duration) {
      const base = f.start ? new Date(f.start) : new Date();
      f.end = this._local(new Date(base.getTime() + t.duration * 60000));
    }
    this._render(true);
  }

  async _saveTemplate() {
    const f = this._form;
    const name = f.tplName.trim();
    if (!name) { this._error = this._t("err_tpl_name"); this._render(true); return; }
    let duration = null;
    if (f.start && f.end) {
      const mins = Math.round((new Date(f.end) - new Date(f.start)) / 60000);
      if (mins > 0) duration = mins;
    }
    const tpl = { name, reason: f.reason.trim(), pages: f.scope === "pages" ? f.pages : [],
      pause_automations: f.pause, duration, repeat: f.repeat };
    const templates = [...(this._data.config?.templates || []), tpl];
    if (await this._call("update_config", { templates })) { f.tplName = ""; this._render(true); }
  }

  async _saveForm() {
    const f = this._form;
    if (f.scope === "pages" && !f.pages.length) { this._error = this._t("err_pages"); this._render(true); return; }
    const iso = (v) => (v ? new Date(v).toISOString() : null);
    const base = { reason: f.reason.trim(), pages: f.scope === "pages" ? f.pages : [] };
    const end = iso(f.end);
    let ok;
    if (f.mode === "add" || f.mode === "edit") {
      if (!f.start) { this._error = this._t("err_start"); this._render(true); return; }
      const payload = { ...base, start: iso(f.start), end, pause_automations: f.pause, repeat: f.repeat };
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
    const keepConfirm = ["stop", "delete", "delete-template"];
    if (!keepConfirm.includes(action)) this._confirm = null;
    const f = this._form;
    switch (action) {
      case "menu":
        this.dispatchEvent(new CustomEvent("hass-toggle-menu", { bubbles: true, composed: true }));
        return;
      case "tab":
        this._tab = t.dataset.tab; this._error = ""; this._form = null;
        this._resetScroll = true; this._render(true); return;
      case "form-add": this._openForm("add"); return;
      case "form-now": this._openForm("now"); return;
      case "form-current": this._openForm("current", this._data.current); return;
      case "form-edit": this._openForm("edit", this._data.upcoming.find((w) => w.id === t.dataset.id)); return;
      case "form-dup": this._openForm("add", this._data.upcoming.find((w) => w.id === t.dataset.id), true); return;
      case "form-cancel": this._form = null; this._error = ""; this._render(true); return;
      case "form-save": await this._saveForm(); return;
      case "form-pause": f.pause = t.checked; return;
      case "form-repeat": f.repeat = t.value; return;
      case "apply-template": this._applyTemplate(t.value); return;
      case "save-template": await this._saveTemplate(); return;
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
      case "delete-template": {
        const key = "tpl:" + t.dataset.id;
        if (this._confirm !== key) { this._confirm = key; this._render(true); return; }
        this._confirm = null;
        const templates = (this._data.config?.templates || []).filter((x) => x.id !== t.dataset.id);
        await this._call("update_config", { templates });
        return;
      }
      case "toggle-auto":
        this._toggle(this._draft.automations, t.dataset.entity); 
        this._markDirty(); // CORRECTION : Active le bouton en direct sans toucher au DOM
        return;
        
      case "auto-none":
        this._draft.automations = []; 
        this._draftDirty = true; 
        this._render(true); // Ici on garde le render(true) car "Tout désélectionner" doit vider visuellement toutes les cases d'un coup
        return;
        
      case "toggle-user":
        this._toggle(this._draft.allowed_users, t.dataset.user); 
        this._markDirty(); // CORRECTION
        return;
        
      case "toggle-notify":
        this._toggle(this._draft.notify_services, t.dataset.svc); 
        this._markDirty(); // CORRECTION
        return;
        
      case "toggle-kind":
        this._toggle(this._draft.notify_kinds, t.dataset.kind); 
        this._markDirty(); // CORRECTION
        return;

      case "save-settings": {
        const ok = await this._call("update_config", {
          automations: this._draft.automations,
          allowed_users: this._draft.allowed_users,
          warn_minutes: Number(this._draft.warn_minutes) || 15,
          end_soon_minutes: Number(this._draft.end_soon_minutes) || 10,
          message: this._draft.message,
          notify_services: this._draft.notify_services,
          notify_kinds: this._draft.notify_kinds,
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
