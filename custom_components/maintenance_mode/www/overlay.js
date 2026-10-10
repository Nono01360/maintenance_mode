/* Mode maintenance — blocage visuel + notification de préavis.
 * Chargé pour tous les utilisateurs via frontend.add_extra_js_url.
 * ATTENTION : blocage côté navigateur uniquement (pas une barrière de sécurité). */
(() => {
  "use strict";

  const OVERLAY_ID = "maintenance-overlay";
  const TOAST_ID = "maintenance-toast";
  const BANNER_ID = "maintenance-banner";
  const BAR_ID = "maintenance-bar";
  const STYLE_ID = "maintenance-style";
  const DISMISS_KEY = "maintenance_mode_dismissed";

  const TEXT = {
    fr: {
      title: "Maintenance en cours",
      pageTitle: "Page en maintenance",
      defaultMessage: "Home Assistant est temporairement indisponible.",
      reason: "Motif :",
      expectedEnd: "Fin prévue :",
      overrun: "La maintenance dure plus longtemps que prévu. Merci de votre patience.",
      noEnd: "La reprise aura lieu dès que possible.",
      logout: "Se déconnecter",
      back: "Retour",
      soon: "Maintenance prévue",
      starts: "Début :",
      pages: "Pages concernées :",
      close: "Fermer",
      mainDashboard: "Tableau de bord principal",
      active: "Mode maintenance actif",
      open: "Ouvrir le panneau",
    },
    en: {
      title: "Maintenance in progress",
      pageTitle: "Page under maintenance",
      defaultMessage: "Home Assistant is temporarily unavailable.",
      reason: "Reason:",
      expectedEnd: "Expected end:",
      overrun: "Maintenance is taking longer than planned. Thank you for your patience.",
      noEnd: "Service will resume as soon as possible.",
      logout: "Log out",
      back: "Back",
      soon: "Scheduled maintenance",
      starts: "Starts:",
      pages: "Affected pages:",
      close: "Close",
      mainDashboard: "Main dashboard",
      active: "Maintenance mode active",
      open: "Open the panel",
    },
  };

  // Noms lisibles des sous-pages (le reste vient de hass.panels)
  const EXTRA_NAMES = {
    fr: {
      "config/devices": "Paramètres › Appareils",
      "config/integrations": "Paramètres › Intégrations",
      "config/entities": "Paramètres › Entités",
      "config/areas": "Paramètres › Zones",
      "config/automation": "Paramètres › Automatisations",
      "config/script": "Paramètres › Scripts",
      "config/scene": "Paramètres › Scènes",
      "config/helpers": "Paramètres › Entrées",
      "config/backup": "Paramètres › Sauvegardes",
      "config/person": "Paramètres › Personnes",
      "config/users": "Paramètres › Utilisateurs",
      "config/voice-assistants": "Paramètres › Assistants vocaux",
      "config/lovelace/dashboards": "Paramètres › Tableaux de bord",
    },
    en: {
      "config/devices": "Settings › Devices",
      "config/integrations": "Settings › Integrations",
      "config/entities": "Settings › Entities",
      "config/areas": "Settings › Areas",
      "config/automation": "Settings › Automations",
      "config/script": "Settings › Scripts",
      "config/scene": "Settings › Scenes",
      "config/helpers": "Settings › Helpers",
      "config/backup": "Settings › Backups",
      "config/person": "Settings › People",
      "config/users": "Settings › Users",
      "config/voice-assistants": "Settings › Voice assistants",
      "config/lovelace/dashboards": "Settings › Dashboards",
    },
  };
  const PANEL_PATH = "maintenance";
  const SIDEBAR_STYLE_ID = "maintenance-sidebar-style";

  const CSS = `
    #${OVERLAY_ID} {
      position: fixed; inset: 0; left: var(--maint-left, 0px); z-index: 99999;
      display: flex; align-items: center; justify-content: center;
      padding: 16px; box-sizing: border-box; overflow-y: auto;
      background: var(--primary-background-color);
      color: var(--primary-text-color);
      font-family: var(--paper-font-body1_-_font-family, Roboto, sans-serif);
    }
    #${OVERLAY_ID} ha-card {
      width: 100%; max-width: 440px; box-sizing: border-box; margin: auto;
      padding: 32px 24px; text-align: center;
    }
    #${OVERLAY_ID} .badge {
      width: 80px; height: 80px; margin: 0 auto 20px; border-radius: 50%;
      display: flex; align-items: center; justify-content: center;
      background: color-mix(in srgb, var(--primary-color) 15%, transparent);
      color: var(--primary-color);
    }
    #${OVERLAY_ID} .badge ha-icon {
      --mdc-icon-size: 44px;
      animation: maint-pulse 2.4s ease-in-out infinite;
    }
    #${OVERLAY_ID} h1 { margin: 0 0 12px; font-size: 24px; font-weight: 400; line-height: 1.3; }
    #${OVERLAY_ID} .message {
      margin: 0; font-size: 14px; line-height: 1.5;
      color: var(--secondary-text-color); white-space: pre-line; overflow-wrap: anywhere;
    }
    #${OVERLAY_ID} .reason {
      margin-top: 12px; font-size: 14px; white-space: pre-line; overflow-wrap: anywhere;
    }
    #${OVERLAY_ID} .end {
      margin-top: 20px; padding-top: 16px;
      border-top: 1px solid var(--divider-color);
      font-size: 13px; color: var(--secondary-text-color);
    }
    #${OVERLAY_ID} .actions {
      margin-top: 24px; display: flex; gap: 8px; justify-content: center; flex-wrap: wrap;
    }
    #${OVERLAY_ID} .btn {
      height: 40px; padding: 0 20px;
      display: inline-flex; align-items: center; gap: 8px;
      border-radius: 20px; cursor: pointer;
      border: 1px solid var(--outline-color, var(--divider-color));
      background: transparent; color: var(--primary-color);
      font: inherit; font-size: 14px; font-weight: 500;
    }
    #${OVERLAY_ID} .btn:hover {
      background: color-mix(in srgb, var(--primary-color) 8%, transparent);
    }
    #${OVERLAY_ID} .btn ha-icon { --mdc-icon-size: 18px; }

    #${TOAST_ID} {
      position: fixed; z-index: 9999; right: 16px;
      top: calc(var(--header-height, 56px) + 8px + env(safe-area-inset-top, 0px));
      width: min(360px, calc(100vw - 32px));
      font-family: var(--paper-font-body1_-_font-family, Roboto, sans-serif);
      color: var(--primary-text-color);
    }
    #${TOAST_ID} ha-card {
      display: flex; gap: 12px; align-items: flex-start; padding: 12px 8px 12px 16px;
      box-shadow: var(--ha-card-box-shadow, 0 4px 16px rgba(0,0,0,.25));
    }
    #${TOAST_ID} .icon { color: var(--warning-color, var(--primary-color)); padding-top: 2px; }
    #${TOAST_ID} .body { flex: 1; min-width: 0; }
    #${TOAST_ID} .title { font-size: 14px; font-weight: 500; }
    #${TOAST_ID} .line {
      margin-top: 2px; font-size: 13px; color: var(--secondary-text-color);
      overflow-wrap: anywhere; white-space: pre-line;
    }
    #${TOAST_ID} .reason { color: var(--primary-text-color); }
    #${TOAST_ID} .close {
      border: none; background: transparent; cursor: pointer; padding: 4px;
      color: var(--secondary-text-color); border-radius: 50%; display: flex;
    }
    #${TOAST_ID} .close:hover { background: var(--divider-color); }

    #${BANNER_ID} {
      position: fixed; z-index: 9999; right: 16px;
      top: calc(var(--header-height, 56px) + 8px + env(safe-area-inset-top, 0px));
      max-width: min(360px, calc(100vw - 32px));
      font-family: var(--paper-font-body1_-_font-family, Roboto, sans-serif);
      color: var(--primary-text-color);
    }
    #${BANNER_ID} ha-card {
      display: flex; gap: 10px; align-items: center; padding: 8px 14px; font-size: 13px;
      border: 1px solid color-mix(in srgb, var(--warning-color, #ff9800) 60%, transparent);
      box-shadow: var(--ha-card-box-shadow, 0 2px 8px rgba(0,0,0,.2));
    }
    #${BANNER_ID}.clickable ha-card { cursor: pointer; }
    #${BANNER_ID} .icon { color: var(--warning-color, #ff9800); display: flex; }
    #${BANNER_ID} .sub { color: var(--secondary-text-color); font-size: 12px; }

    #${BAR_ID} {
      position: fixed; top: 0; left: 0; right: 0; z-index: 100000;
      display: flex; align-items: center; gap: 10px; box-sizing: border-box;
      padding: 6px 12px; padding-top: calc(6px + env(safe-area-inset-top, 0px));
      font: 14px/1.4 var(--paper-font-body1_-_font-family, Roboto, sans-serif);
      box-shadow: 0 2px 6px rgba(0,0,0,.25);
    }
    #${BAR_ID}.active { background: var(--warning-color, #ff9800); color: #1b1b1b; }
    #${BAR_ID}.upcoming { background: var(--primary-color, #03a9f4); color: var(--text-primary-color, #fff); }
    #${BAR_ID} .icon { display: flex; flex: none; }
    #${BAR_ID} .viewport { flex: 1; min-width: 0; overflow: hidden; white-space: nowrap; }
    #${BAR_ID} .track { display: inline-block; }
    #${BAR_ID} .viewport.scroll .track {
      padding-left: 100%; animation: maint-marquee var(--dur, 20s) linear infinite;
    }
    #${BAR_ID} .viewport.scroll:hover .track { animation-play-state: paused; }
    #${BAR_ID} .viewport.wrap { white-space: normal; overflow-y: auto; max-height: 36vh; overflow-wrap: anywhere; }
    #${BAR_ID} .btn {
      flex: none; border: 1px solid currentColor; background: transparent; color: inherit;
      border-radius: 14px; padding: 2px 12px; font: inherit; font-size: 13px; cursor: pointer;
    }
    #${BAR_ID} .close {
      flex: none; border: none; background: transparent; color: inherit; cursor: pointer;
      display: flex; padding: 4px; border-radius: 50%;
    }
    #${BAR_ID} .close:hover, #${BAR_ID} .btn:hover { background: rgba(0,0,0,.12); }

    @keyframes maint-marquee { from { transform: translateX(0); } to { transform: translateX(-100%); } }
    @keyframes maint-pulse {
      0%, 100% { opacity: 1; transform: scale(1); }
      50% { opacity: .6; transform: scale(.92); }
    }
    @media (prefers-reduced-motion: reduce) {
      #${OVERLAY_ID} .badge ha-icon { animation: none; }
    }
  `;

  // ---------- utilitaires ----------
  const getHaEl = () => document.querySelector("home-assistant");
  const getHass = () => getHaEl()?.hass;

  const el = (tag, props = {}, ...children) => {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(props)) {
      if (k === "class") node.className = v;
      else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
      else node.setAttribute(k, v);
    }
    node.append(...children);
    return node;
  };
  const icon = (name) => el("ha-icon", { icon: name });

  const i18n = (hass) => {
    const lang = hass.locale?.language || hass.language || "en";
    return { lang, tx: TEXT[lang.split("-")[0]] || TEXT.en };
  };

  const parseDate = (value) => {
    if (!value) return null;
    const d = new Date(value);
    return Number.isNaN(d.getTime()) ? null : d;
  };
  const parseWin = (w) => (w ? { ...w, start: parseDate(w.start), end: parseDate(w.end) } : null);

  const fmt = (d, lang) => {
    const sameDay = d.toDateString() === new Date().toDateString();
    return new Intl.DateTimeFormat(
      lang,
      sameDay ? { timeStyle: "short" } : { dateStyle: "medium", timeStyle: "short" }
    ).format(d);
  };

  const rel = (ms, lang) => {
    const rtf = new Intl.RelativeTimeFormat(lang, { numeric: "auto" });
    const s = Math.max(0, Math.round(ms / 1000));
    if (s < 60) return rtf.format(s, "second");
    const m = Math.round(s / 60);
    if (m < 90) return rtf.format(m, "minute");
    const h = Math.round(m / 60);
    if (h < 36) return rtf.format(h, "hour");
    return rtf.format(Math.round(h / 24), "day");
  };

  const ensureStyle = () => {
    if (document.getElementById(STYLE_ID)) return;
    document.head.appendChild(el("style", { id: STYLE_ID }, CSS));
  };

  // Chemin courant sans slash de tête/queue : "config/devices/dashboard"
  const currentPath = () => location.pathname.replace(/^\/+|\/+$/g, "");

  // pages vide = tout Home Assistant ; sinon préfixe sur des segments entiers
  const pageBlocked = (pages) => {
    if (!pages || pages.length === 0) return true;
    const path = currentPath();
    return pages.some((p) => path === p || path.startsWith(p + "/"));
  };

  // Largeur de la barre latérale (pour la laisser accessible si blocage partiel).
  // Best-effort : dépend de la structure interne du frontend, repli sur 0.
  const sidebarWidth = () => {
    try {
      const main = getHaEl()?.shadowRoot?.querySelector("home-assistant-main");
      const sb =
        main?.shadowRoot?.querySelector("ha-drawer ha-sidebar") ||
        main?.shadowRoot?.querySelector("ha-sidebar");
      const r = sb?.getBoundingClientRect();
      if (r && r.left >= 0 && r.width > 0 && r.width < 500) return Math.round(r.right);
    } catch (_) { /* ignore */ }
    return 0;
  };

  // Nom lisible d'un chemin de page ("config/devices" -> "Paramètres › Appareils")
  const pageLabel = (path, hass, lang, tx) => {
    const code = lang.split("-")[0];
    const extra = (EXTRA_NAMES[code] || EXTRA_NAMES.en)[path];
    if (extra) return extra;
    const seg = path.split("/")[0];
    const panel = hass.panels?.[seg];
    let name = null;
    if (panel?.title) name = hass.localize?.(`panel.${panel.title}`) || panel.title;
    else if (seg === "lovelace") name = tx.mainDashboard;
    if (!name) return path;
    if (path === seg) return name;
    const rest = path.slice(seg.length + 1).replace(/[-_/]+/g, " ");
    return `${name} › ${rest.charAt(0).toUpperCase()}${rest.slice(1)}`;
  };

  // ---------- barre latérale : masquer l'entrée « Maintenance » ----------
  // Deux mécanismes complémentaires :
  //  1. masquage DOM de l'entrée (recherche récursive dans les shadow DOM, MutationObserver) ;
  //  2. préférence native de l'utilisateur (« panneaux masqués » de la barre latérale).
  const deepFind = (start, selector) => {
    const queue = [start];
    for (let i = 0; i < queue.length && i < 30000; i++) {
      const node = queue[i];
      if (node.matches && node.matches(selector)) return node;
      if (node.shadowRoot) queue.push(node.shadowRoot);
      for (const c of node.children || []) queue.push(c);
    }
    return null;
  };

  const isPanelItem = (node) => {
    if (!node.getAttribute) return false;
    if (node.getAttribute("data-panel") === PANEL_PATH) return true;
    const href = node.getAttribute("href") || (typeof node.href === "string" ? node.href : "");
    return !!href && new RegExp(`(^|/)${PANEL_PATH}/?$`).test(href.split(/[?#]/)[0]);
  };

  let sidebarEl = null;
  let sidebarObserver = null;
  let sidebarSearchAt = 0;
  let wantHidden = false;
  const hiddenEls = new Set();

  const applySidebar = () => {
    const root = sidebarEl?.shadowRoot;
    if (!root) return;
    if (!wantHidden) {
      hiddenEls.forEach((n) => n.style.removeProperty("display"));
      hiddenEls.clear();
      return;
    }
    const queue = [...root.children];
    for (let i = 0; i < queue.length && i < 5000; i++) {
      const n = queue[i];
      if (isPanelItem(n)) {            // l'élément le plus extérieur suffit
        if (!hiddenEls.has(n)) { n.style.setProperty("display", "none", "important"); hiddenEls.add(n); }
        continue;
      }
      if (n.shadowRoot) queue.push(...n.shadowRoot.children);
      queue.push(...n.children);
    }
  };

  const setPanelHidden = (hide) => {
    wantHidden = hide;
    if (!sidebarEl || !sidebarEl.isConnected) {
      sidebarObserver?.disconnect();
      sidebarObserver = null;
      sidebarEl = null;
      hiddenEls.clear();
      if (!hide) return;
      if (Date.now() - sidebarSearchAt < 3000) return;   // on ne fouille pas le DOM chaque seconde
      sidebarSearchAt = Date.now();
      sidebarEl = deepFind(getHaEl(), "ha-sidebar");
      if (sidebarEl?.shadowRoot) {
        sidebarObserver = new MutationObserver(() => applySidebar());
        sidebarObserver.observe(sidebarEl.shadowRoot, { childList: true, subtree: true });
      }
    }
    applySidebar();
  };

  let prefSynced = null;
  const syncSidebarPref = async (hass, hide) => {
    if (prefSynced === hide) return;
    prefSynced = hide;
    const marker = `maintenance_mode_hidden:${hass.user.id}`;
    try {
      const res = await hass.callWS({ type: "frontend/get_user_data", key: "sidebar" });
      const value = res?.value && typeof res.value === "object" ? res.value : {};
      const hidden = Array.isArray(value.hiddenPanels) ? value.hiddenPanels : [];
      const has = hidden.includes(PANEL_PATH);
      if (hide && !has) {
        await hass.callWS({ type: "frontend/set_user_data", key: "sidebar",
          value: { ...value, panelOrder: value.panelOrder || [], hiddenPanels: [...hidden, PANEL_PATH] } });
        localStorage.setItem(marker, "1");
      } else if (!hide && has && localStorage.getItem(marker)) {
        // on ne retire que ce que NOUS avons masqué (le choix de l'utilisateur est respecté)
        await hass.callWS({ type: "frontend/set_user_data", key: "sidebar",
          value: { ...value, hiddenPanels: hidden.filter((p) => p !== PANEL_PATH) } });
        localStorage.removeItem(marker);
      }
    } catch (err) {
      console.debug("maintenance_mode: préférence de barre latérale non modifiée", err);
    }
  };

  // ---------- recherche de l'entité (même renommée) ----------
  let entityId = null;
  const findState = (hass) => {
    if (entityId && hass.states[entityId]?.attributes?.maintenance_mode_entity) {
      return hass.states[entityId];
    }
    entityId = null;
    for (const id in hass.states) {
      if (id.startsWith("switch.") && hass.states[id].attributes?.maintenance_mode_entity) {
        entityId = id;
        return hass.states[id];
      }
    }
    return null;
  };

  // ---------- déconnexion ----------
  const logout = async () => {
    const hass = getHass();
    try {
      await hass.auth.revoke();
      location.href = "/";
    } catch (err) {
      console.warn("maintenance_mode: revoke() a échoué, repli sur l'évènement du frontend", err);
      getHaEl()?.dispatchEvent(new CustomEvent("hass-logout", { bubbles: true, composed: true }));
    }
  };

  // ---------- page de maintenance ----------
  let overlay = null;

  const buildOverlay = (partial) => {
    ensureStyle();
    const r = {};
    r.title = el("h1");
    r.message = el("p", { class: "message" });
    r.reason = el("div", { class: "reason" });
    r.end = el("div", { class: "end" });
    r.logoutLabel = el("span");
    const actions = el("div", { class: "actions" });
    if (partial) {
      r.backLabel = el("span");
      actions.append(
        el("button", { class: "btn", type: "button", onclick: () => history.back() },
          icon("mdi:arrow-left"), r.backLabel)
      );
    }
    actions.append(
      el("button", { class: "btn", type: "button", onclick: logout },
        icon("mdi:logout"), r.logoutLabel)
    );
    const root = el("div", { id: OVERLAY_ID },
      el("ha-card", {},
        el("div", { class: "badge" }, icon("mdi:wrench-clock")),
        r.title, r.message, r.reason, r.end, actions));
    document.body.appendChild(root);
    return { root, r, partial };
  };

  const renderOverlay = (st, cur, hass, now) => {
    const { lang, tx } = i18n(hass);
    const partial = !!(cur.pages && cur.pages.length);
    if (overlay && overlay.partial !== partial) removeOverlay();
    if (!overlay) overlay = buildOverlay(partial);
    const { r, root } = overlay;
    root.style.setProperty("--maint-left", partial ? `${sidebarWidth()}px` : "0px");
    r.title.textContent = partial ? tx.pageTitle : tx.title;
    r.message.textContent = st.attributes.message || tx.defaultMessage;
    r.reason.textContent = cur.reason ? `${tx.reason} ${cur.reason}` : "";
    r.reason.style.display = cur.reason ? "" : "none";
    r.logoutLabel.textContent = tx.logout;
    if (r.backLabel) r.backLabel.textContent = tx.back;
    if (!cur.end) r.end.textContent = tx.noEnd;
    else if (cur.end > now) r.end.textContent = `${tx.expectedEnd} ${fmt(cur.end, lang)} · ${rel(cur.end - now, lang)}`;
    else r.end.textContent = tx.overrun;
  };

  const removeOverlay = () => {
    overlay?.root.remove();
    overlay = null;
  };

  // ---------- notification de maintenance à venir ----------
  let toast = null;

  const dismissKey = (w) => `${w.id}@${w.start.toISOString()}`;
  const isDismissed = (w) => {
    try { return sessionStorage.getItem(DISMISS_KEY) === dismissKey(w); }
    catch { return false; }
  };
  const dismiss = (w) => {
    try { sessionStorage.setItem(DISMISS_KEY, dismissKey(w)); } catch { /* ignore */ }
    removeToast();
  };

  const buildToast = (w) => {
    ensureStyle();
    const r = {};
    r.title = el("div", { class: "title" });
    r.when = el("div", { class: "line" });
    r.end = el("div", { class: "line" });
    r.reason = el("div", { class: "line reason" });
    r.pages = el("div", { class: "line" });
    r.close = el("button", { class: "close", type: "button", onclick: () => dismiss(w) },
      icon("mdi:close"));
    const root = el("div", { id: TOAST_ID },
      el("ha-card", {},
        el("div", { class: "icon" }, icon("mdi:wrench-clock")),
        el("div", { class: "body" }, r.title, r.when, r.end, r.reason, r.pages),
        r.close));
    document.body.appendChild(root);
    return { root, r, key: dismissKey(w) };
  };

  const setLine = (node, text) => {
    node.textContent = text || "";
    node.style.display = text ? "" : "none";
  };

  const renderToast = (st, hass, now) => {
    const w = parseWin(st.attributes.next);
    const warnMs = (Number(st.attributes.warn_minutes) || 15) * 60000;
    const show = w && w.start && w.start > now && w.start - now <= warnMs && !isDismissed(w);
    if (!show) { removeToast(); return; }

    if (toast && toast.key !== dismissKey(w)) removeToast();
    const { lang, tx } = i18n(hass);
    if (!toast) toast = buildToast(w);
    const { r } = toast;
    r.title.textContent = tx.soon;
    r.close.setAttribute("aria-label", tx.close);
    r.when.textContent = `${tx.starts} ${rel(w.start - now, lang)} (${fmt(w.start, lang)})`;
    setLine(r.end, w.end ? `${tx.expectedEnd} ${fmt(w.end, lang)}` : "");
    setLine(r.reason, w.reason ? `${tx.reason} ${w.reason}` : "");
    setLine(r.pages, w.pages?.length
      ? `${tx.pages} ${w.pages.map((p) => pageLabel(p, hass, lang, tx)).join(", ")}` : "");
  };

  const removeToast = () => {
    toast?.root.remove();
    toast = null;
  };

  // ---------- bandeau « maintenance active » pour les utilisateurs NON bloqués ----------
  let banner = null;

  const buildBanner = () => {
    ensureStyle();
    const r = {};
    r.title = el("div", { class: "title" });
    r.sub = el("div", { class: "sub" });
    const root = el("div", { id: BANNER_ID },
      el("ha-card", {},
        el("div", { class: "icon" }, icon("mdi:wrench-clock")),
        el("div", {}, r.title, r.sub)));
    document.body.appendChild(root);
    return { root, r };
  };

  const renderBanner = (cur, hass, now, canOpen) => {
    const { lang, tx } = i18n(hass);
    if (!banner) {
      banner = buildBanner();
      banner.root.addEventListener("click", () => {
        if (!banner?.root.classList.contains("clickable")) return;
        history.pushState(null, "", `/${PANEL_PATH}`);
        window.dispatchEvent(new CustomEvent("location-changed"));
      });
    }
    banner.root.classList.toggle("clickable", canOpen);
    banner.r.title.textContent = tx.active;
    const bits = [];
    if (cur.end) bits.push(`${tx.expectedEnd} ${fmt(cur.end, lang)} · ${rel(Math.max(0, cur.end - now), lang)}`);
    if (canOpen) bits.push(tx.open);
    banner.r.sub.textContent = bits.join(" — ");
    banner.r.sub.style.display = bits.length ? "" : "none";
  };

  const removeBanner = () => {
    banner?.root.remove();
    banner = null;
  };

  // ---------- bandeau en haut de TOUTE la page (mode « bar ») ----------
  const BAR_DISMISS_KEY = "maintenance_mode_bar_dismissed";
  let bar = null;

  const reducedMotion = () => !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

  // Repousse toute l'interface Home Assistant sous le bandeau. Un `transform` fait de
  // l'élément le repère des éléments « fixed » (en-tête, barre latérale, boîtes de dialogue).
  const pushPage = (px) => {
    const ha = getHaEl();
    if (!ha) return;
    ha.style.transform = px > 0 ? `translateY(${px}px)` : "";
    ha.style.height = px > 0 ? `calc(100% - ${px}px)` : "";
  };

  const barDismissed = (key) => {
    try { return sessionStorage.getItem(BAR_DISMISS_KEY) === key; } catch { return false; }
  };

  const buildBar = (kind) => {
    ensureStyle();
    const r = {};
    r.track = el("span", { class: "track" });
    r.viewport = el("div", { class: "viewport" }, r.track);
    r.open = el("button", { class: "btn", type: "button" });
    r.close = el("button", { class: "close", type: "button" }, icon("mdi:close"));
    const root = el("div", { id: BAR_ID, class: kind },
      el("span", { class: "icon" }, icon("mdi:wrench-clock")), r.viewport, r.open, r.close);
    document.body.appendChild(root);
    return { root, r, kind, key: "", text: "", mode: null, width: 0, scrollOpt: null, pushed: -1 };
  };

  // Texte trop long ? défilement (option) ou retour à la ligne avec ascenseur vertical
  const fitBar = (scrollOpt) => {
    const { r } = bar;
    r.viewport.classList.remove("scroll", "wrap");
    bar.mode = "none";
    if (r.track.offsetWidth <= r.viewport.clientWidth) return;
    if (scrollOpt && !reducedMotion()) {
      r.viewport.style.setProperty("--dur", `${Math.max(12, Math.round(r.track.offsetWidth / 60))}s`);
      r.viewport.classList.add("scroll");
      bar.mode = "scroll";
    } else {
      r.viewport.classList.add("wrap");
      bar.mode = "wrap";
    }
  };

  const removeBar = () => {
    if (!bar) return;
    bar.root.remove();
    bar = null;
    pushPage(0);
  };

  const renderBar = (kind, key, text, o) => {
    if (barDismissed(key)) { removeBar(); return; }
    if (bar && bar.kind !== kind) removeBar();
    if (!bar) {
      bar = buildBar(kind);
      bar.r.close.addEventListener("click", () => {
        try { sessionStorage.setItem(BAR_DISMISS_KEY, bar.key); } catch { /* ignore */ }
        removeBar();
      });
      bar.r.open.addEventListener("click", () => {
        history.pushState(null, "", `/${PANEL_PATH}`);
        window.dispatchEvent(new CustomEvent("location-changed"));
      });
    }
    bar.key = key;
    const { r } = bar;
    const changed = text !== bar.text;
    if (changed) { r.track.textContent = text; bar.text = text; }
    r.open.textContent = o.openLabel;
    r.open.style.display = o.canOpen ? "" : "none";
    r.close.setAttribute("aria-label", o.closeLabel);
    if (bar.mode === null || r.viewport.clientWidth !== bar.width || bar.scrollOpt !== o.scroll
        || (changed && bar.mode === "none")) {
      fitBar(o.scroll);
      bar.width = r.viewport.clientWidth;
      bar.scrollOpt = o.scroll;
    }
    const h = Math.ceil(bar.root.getBoundingClientRect().height);
    if (h !== bar.pushed) { pushPage(h); bar.pushed = h; }
  };

  const pagesText = (pages, hass, lang, tx) =>
    `${tx.pages} ${pages.map((p) => pageLabel(p, hass, lang, tx)).join(", ")}`;

  const renderActiveBar = (st, cur, hass, now, canOpen) => {
    const { lang, tx } = i18n(hass);
    const parts = [tx.active];
    if (cur.reason) parts.push(`${tx.reason} ${cur.reason}`);
    if (cur.end) parts.push(`${tx.expectedEnd} ${fmt(cur.end, lang)} · ${rel(Math.max(0, cur.end - now), lang)}`);
    if (cur.pages?.length) parts.push(pagesText(cur.pages, hass, lang, tx));
    renderBar("active", `active:${cur.id}`, parts.join("  ·  "),
      { scroll: st.attributes.banner_scroll !== false, canOpen, openLabel: tx.open, closeLabel: tx.close });
  };

  const renderUpcomingBar = (st, hass, now) => {
    const w = parseWin(st.attributes.next);
    const warnMs = (Number(st.attributes.warn_minutes) || 15) * 60000;
    if (!(w && w.start && w.start > now && w.start - now <= warnMs)) { removeBar(); return; }
    const { lang, tx } = i18n(hass);
    const parts = [tx.soon, `${tx.starts} ${rel(w.start - now, lang)} (${fmt(w.start, lang)})`];
    if (w.end) parts.push(`${tx.expectedEnd} ${fmt(w.end, lang)}`);
    if (w.reason) parts.push(`${tx.reason} ${w.reason}`);
    if (w.pages?.length) parts.push(pagesText(w.pages, hass, lang, tx));
    renderBar("upcoming", dismissKey(w), parts.join("  ·  "),
      { scroll: st.attributes.banner_scroll !== false, canOpen: false, openLabel: tx.open, closeLabel: tx.close });
  };

  // ---------- boucle principale ----------
  const check = () => {
    const hass = getHass();
    if (!hass?.user) return;
    const st = findState(hass);
    if (!st) {
      setPanelHidden(false); syncSidebarPref(hass, false);
      removeOverlay(); removeToast(); removeBanner(); removeBar();
      return;
    }

    // Utilisateur sans accès au panneau : on retire son entrée du menu latéral.
    const panelHidden = !hass.user.is_owner && (st.attributes.panel_hidden_for || []).includes(hass.user.id);
    setPanelHidden(panelHidden);
    syncSidebarPref(hass, panelHidden);

    const now = new Date();
    const cur = parseWin(st.attributes.current);
    const exempt = hass.user.is_owner || (st.attributes.exempt_users || []).includes(hass.user.id);
    const barMode = st.attributes.banner_mode !== "card";   // « bar » par défaut

    if (st.state === "on" && cur && !exempt && pageBlocked(cur.pages)) {
      removeToast(); removeBanner(); removeBar();
      renderOverlay(st, cur, hass, now);
      return;
    }
    removeOverlay();
    if (st.state === "on") {
      removeToast();
      // Non bloqué alors que la maintenance les concernerait : on le rappelle
      if (cur && exempt && pageBlocked(cur.pages)) {
        if (barMode) { removeBanner(); renderActiveBar(st, cur, hass, now, !panelHidden); }
        else { removeBar(); renderBanner(cur, hass, now, !panelHidden); }
      } else {
        removeBanner(); removeBar();
      }
    } else {
      removeBanner();
      if (barMode) { removeToast(); renderUpcomingBar(st, hass, now); }
      else { removeBar(); renderToast(st, hass, now); }
    }
  };

  setInterval(check, 1000);
})();
