"""Plages interdites : jours et heures où l'on ne planifie ni ne démarre de maintenance.

Une règle = (jours, début, fin) en heure locale de Home Assistant. Fin < début : la plage passe minuit (elle appartient au
jour où elle commence). Aucun jour choisi = tous les jours. Seul le propriétaire peut déroger (journalisé).
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timedelta
from typing import Any

from homeassistant.util import dt as dt_util

from .errors import MaintenanceError

_LOGGER = logging.getLogger(__name__)
MAX_BLACKOUTS = 20
_HHMM = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def clean_blackouts(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for r in (raw or [])[:MAX_BLACKOUTS]:
        start, end = str(r.get("start", "")), str(r.get("end", ""))
        if not (_HHMM.match(start) and _HHMM.match(end)) or start == end:
            continue
        days = sorted({int(d) for d in r.get("days", []) if str(d).isdigit() and 0 <= int(d) <= 6})
        out.append({
            "id": str(r.get("id") or uuid.uuid4().hex[:8])[:12],
            "name": str(r.get("name", "")).strip()[:40],
            "days": days or list(range(7)),
            "start": start,
            "end": end,
        })
    return out


def _minutes(hhmm: str) -> int:
    return int(hhmm[:2]) * 60 + int(hhmm[3:])


def matching_rule(rules: list[dict[str, Any]], instant: datetime) -> dict[str, Any] | None:
    """Première règle qui interdit cet instant (heure locale), sinon None."""
    local = dt_util.as_local(instant)
    now_min = local.hour * 60 + local.minute
    today = local.weekday()
    yesterday = (local - timedelta(days=1)).weekday()
    for rule in rules:
        start, end = _minutes(rule["start"]), _minutes(rule["end"])
        if start < end:
            hit = today in rule["days"] and start <= now_min < end
        else:   # passe minuit
            hit = (today in rule["days"] and now_min >= start) or (yesterday in rule["days"] and now_min < end)
        if hit:
            return rule
    return None


class BlackoutMixin:
    """Suppose `config` du gestionnaire."""

    def _check_blackout(self, start: datetime, *, override: bool, by: str = "") -> bool:
        """Refuse un début situé dans une plage interdite. Renvoie True si une dérogation a été utilisée."""
        rule = matching_rule(self.config["blackouts"], start)
        if rule is None:
            return False
        if override:
            _LOGGER.warning("Plage interdite « %s » ignorée par le propriétaire (%s)", rule["name"] or rule["id"], by or "?")
            return True
        raise MaintenanceError("blackout_period", name=rule["name"] or f"{rule['start']}–{rule['end']}")
