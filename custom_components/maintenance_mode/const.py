"""Constantes de l'intégration Mode maintenance."""
from __future__ import annotations

import json
from pathlib import Path

DOMAIN = "maintenance_mode"
VERSION = json.loads(
    Path(__file__).with_name("manifest.json").read_text(encoding="utf-8")
)["version"]

STATIC_BASE = "/maintenance_mode_static"
OVERLAY_JS = f"{STATIC_BASE}/overlay.js"
PANEL_JS = f"{STATIC_BASE}/panel.js"
PANEL_URL_PATH = "maintenance"
PANEL_ELEMENT = "maintenance-mode-panel"

PLATFORMS = ["switch", "sensor"]

# Droits sur le panneau
ROLE_NONE = "none"      # ne voit rien
ROLE_VIEWER = "viewer"  # voit les maintenances (vue utilisateur)
ROLE_ADMIN = "admin"    # configure tout (vue administrateur)
ROLES = (ROLE_NONE, ROLE_VIEWER, ROLE_ADMIN)

DEFAULT_WARN_MINUTES = 15
DEFAULT_MESSAGE = "Home Assistant est temporairement indisponible pour cause de maintenance."

MAX_WINDOWS = 50
MAX_REASON = 200
MAX_PAGES = 30

# Anciennes clés d'options (v0.2), conservées pour la migration
LEGACY_AUTOMATIONS = "automations"
LEGACY_ALLOWED_USERS = "allowed_users"
LEGACY_WARN_MINUTES = "warn_minutes"
