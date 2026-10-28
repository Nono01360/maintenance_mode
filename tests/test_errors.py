"""0.7.13 — erreurs à code stable, texte fr / en."""
import re
from pathlib import Path

import pytest

from custom_components.maintenance_mode import errors
from custom_components.maintenance_mode.errors import CATALOG, MaintenanceError, message

from .test_maintenance import _setup
from .test_roles import _ws_call

PACKAGE = Path(__file__).parent.parent / "custom_components" / "maintenance_mode"


def test_catalogues_have_the_same_codes_and_placeholders():
    assert set(CATALOG["fr"]) == set(CATALOG["en"])
    for code in CATALOG["fr"]:
        assert re.findall(r"\{(\w+)\}", CATALOG["fr"][code]) == re.findall(r"\{(\w+)\}", CATALOG["en"][code]), code


def test_every_code_used_in_the_code_exists_in_the_catalogue():
    used = set()
    for path in PACKAGE.glob("*.py"):
        used |= set(re.findall(r'MaintenanceError\(\s*"(\w+)"', path.read_text(encoding="utf-8")))
        used |= set(re.findall(r'_send_error\([^\n]*,\s*"(\w+)"\)', path.read_text(encoding="utf-8")))
    assert used and used <= set(CATALOG["fr"]), used - set(CATALOG["fr"])


def test_no_hardcoded_french_message_left_in_server_code():
    for path in PACKAGE.glob("*.py"):
        if path.name == "errors.py":
            continue
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"ServiceValidationError\(\s*f?\"", text), path.name


def test_message_follows_server_language_with_english_fallback():
    try:
        errors.set_language("fr-FR")
        assert message("overlaps_current") == "Cette période chevauche la maintenance en cours."
        errors.set_language("de")
        assert message("max_windows", max=50) == "Maximum 50 scheduled maintenances."
        errors.set_language(None)
        assert message("inconnu") == "inconnu"
    finally:
        errors.set_language("en")


async def test_validation_error_carries_code_and_placeholders(hass):
    _, m = await _setup(hass)
    with pytest.raises(MaintenanceError) as exc:
        await m.async_start_now(end=None, reason="x" * 500, pages=[], pause=False)
    assert exc.value.code == "reason_too_long" and exc.value.placeholders == {"max": "200"}
    assert "200" in str(exc.value)


async def test_ws_error_exposes_translation_key_and_placeholders(hass, hass_ws_client, hass_access_token):
    _, m = await _setup(hass)
    client = await hass_ws_client(hass, hass_access_token)
    r = await _ws_call(client, 1, type="maintenance_mode/start", reason="y" * 500)
    err = r["error"]
    assert not r["success"] and err["code"] == "invalid"
    assert err["translation_key"] == "reason_too_long" and err["translation_domain"] == "maintenance_mode"
    assert err["translation_placeholders"] == {"max": "200"}


async def test_ws_access_denied_has_a_code(hass, hass_ws_client, hass_read_only_access_token):
    _, m = await _setup(hass)
    client = await hass_ws_client(hass, hass_read_only_access_token)
    r = await _ws_call(client, 1, type="maintenance_mode/stop")
    assert r["error"]["code"] == "unauthorized" and r["error"]["translation_key"] == "access_denied"


def test_panel_translates_every_server_error_code():
    panel = (PACKAGE / "www" / "panel.js").read_text(encoding="utf-8")
    for code in CATALOG["fr"]:
        assert len(re.findall(rf"\berr_{code}:", panel)) == 2, f"err_{code} absent du panneau (fr et en)"
