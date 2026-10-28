"""Erreurs de l'intégration : un code stable + des paramètres ; le texte vient d'un catalogue fr / en.

Le serveur écrit son message dans la langue de Home Assistant (services, journaux) ; le panneau reçoit le code et
les paramètres (`translation_key`, `translation_placeholders`) et traduit dans la langue de l'utilisateur.
"""
from __future__ import annotations

from typing import Any

from homeassistant.exceptions import ServiceValidationError

CATALOG: dict[str, dict[str, str]] = {
    "fr": {
        "no_current": "Aucune maintenance en cours.",
        "end_overlaps_scheduled": "La fin chevauche une maintenance planifiée.",
        "max_windows": "Maximum {max} maintenances planifiées.",
        "not_loaded": "L'intégration Mode maintenance n'est pas chargée.",
        "end_or_duration": "Indique soit `end`, soit `duration`, pas les deux.",
        "history_not_found": "Entrée d'historique introuvable.",
        "cannot_grant": "Tu ne peux pas accorder des droits que tu n'as pas toi-même.",
        "window_not_found": "Maintenance introuvable.",
        "reason_too_long": "Motif trop long ({max} caractères max).",
        "invalid_repeat": "Répétition invalide.",
        "repeat_needs_end": "Une maintenance répétée doit avoir une fin.",
        "duration_exceeds_period": "La durée dépasse la période de répétition.",
        "end_in_past": "La fin doit être dans le futur.",
        "start_in_past": "Le début doit être dans le futur.",
        "end_before_start": "La fin doit être postérieure au début.",
        "overlaps_scheduled": "Cette période chevauche une autre maintenance planifiée.",
        "overlaps_current": "Cette période chevauche la maintenance en cours.",
        "too_many_pages": "Maximum {max} pages par maintenance.",
        "access_denied": "Accès refusé.",
        "rate_limited": "Trop de modifications en peu de temps : réessaie dans quelques secondes.",
    },
    "en": {
        "no_current": "No maintenance in progress.",
        "end_overlaps_scheduled": "The end overlaps a scheduled maintenance.",
        "max_windows": "Maximum {max} scheduled maintenances.",
        "not_loaded": "The Maintenance mode integration is not loaded.",
        "end_or_duration": "Provide either `end` or `duration`, not both.",
        "history_not_found": "History entry not found.",
        "cannot_grant": "You cannot grant permissions you do not have yourself.",
        "window_not_found": "Maintenance not found.",
        "reason_too_long": "Reason too long ({max} characters max).",
        "invalid_repeat": "Invalid repeat.",
        "repeat_needs_end": "A repeating maintenance must have an end.",
        "duration_exceeds_period": "The duration exceeds the repeat period.",
        "end_in_past": "The end must be in the future.",
        "start_in_past": "The start must be in the future.",
        "end_before_start": "The end must be after the start.",
        "overlaps_scheduled": "This period overlaps another scheduled maintenance.",
        "overlaps_current": "This period overlaps the current maintenance.",
        "too_many_pages": "Maximum {max} pages per maintenance.",
        "access_denied": "Access denied.",
        "rate_limited": "Too many changes in a short time: try again in a few seconds.",
    },
}

_language = "en"


def set_language(language: str | None) -> None:
    """Langue des messages côté serveur (celle de Home Assistant ; anglais si inconnue)."""
    global _language
    code = (language or "en").split("-")[0].lower()
    _language = code if code in CATALOG else "en"


def message(code: str, **placeholders: Any) -> str:
    template = CATALOG[_language].get(code) or CATALOG["en"].get(code) or code
    try:
        return template.format(**placeholders)
    except (KeyError, IndexError):
        return template


class MaintenanceError(ServiceValidationError):
    """Erreur de validation : `code` stable (clé du catalogue) et `placeholders` (valeurs insérées dans le texte)."""

    def __init__(self, code: str, **placeholders: Any) -> None:
        self.code = code
        self.placeholders = {k: str(v) for k, v in placeholders.items()}
        super().__init__(message(code, **placeholders))
