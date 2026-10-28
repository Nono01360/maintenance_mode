"""Fenêtres de maintenance : structure `Window`, répétition et utilitaires purs (sans Home Assistant vivant)."""
from __future__ import annotations

import calendar
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any, Iterator

from dateutil.relativedelta import relativedelta

from homeassistant.util import dt as dt_util

from .errors import MaintenanceError
from .const import MAX_OCCURRENCES, MAX_PAGES, REPEATS

FAR = datetime(9999, 12, 31, tzinfo=dt_util.UTC)
_STEPS = {
    "daily": relativedelta(days=1),
    "weekly": relativedelta(weeks=1),
    "monthly": relativedelta(months=1),
}


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = dt_util.parse_datetime(value)
    return dt_util.as_utc(parsed) if parsed else None


def iso(value: datetime | None) -> str | None:
    return dt_util.as_utc(value).isoformat() if value else None


def clean_pages(pages: list[str] | None) -> list[str]:
    out: list[str] = []
    for page in pages or []:
        page = str(page).strip().strip("/")
        if page and page not in out:
            out.append(page)
    if len(out) > MAX_PAGES:
        raise MaintenanceError("too_many_pages", max=MAX_PAGES)
    return out


def overlap(a_start, a_end, b_start, b_end) -> bool:
    return a_start < (b_end or FAR) and b_start < (a_end or FAR)


def add_month(local: datetime, anchor_day: int) -> datetime:
    """Mois suivant, au jour d'origine (`anchor_day`) ou au dernier jour du mois s'il est plus court."""
    year = local.year + local.month // 12
    month = local.month % 12 + 1
    last = calendar.monthrange(year, month)[1]
    return local.replace(year=year, month=month, day=min(anchor_day, last))


def shift(start: datetime, end: datetime | None, repeat: str, anchor_day: int | None = None):
    """Décale d'une période en heure locale (l'heure « murale » est conservée malgré le DST).

    Mensuel : le jour d'origine est mémorisé (`anchor_day`), sinon 31 janvier → 28 février →
    28 mars… dériverait vers le bas à chaque mois court.
    """
    local_start = dt_util.as_local(start)
    if repeat == "monthly":
        new_start = add_month(local_start, anchor_day or local_start.day)
    else:
        new_start = local_start + _STEPS[repeat]
    new_end = None
    if end:
        # la durée « murale » est conservée : même heure de fin locale, quel que soit le DST
        wall = dt_util.as_local(end).replace(tzinfo=None) - local_start.replace(tzinfo=None)
        new_end = (new_start.replace(tzinfo=None) + wall).replace(tzinfo=new_start.tzinfo)
    return dt_util.as_utc(new_start), (dt_util.as_utc(new_end) if new_end else None)


@dataclass
class Window:
    """Une période de maintenance (en cours ou planifiée)."""

    id: str
    start: datetime
    end: datetime | None = None
    reason: str = ""
    pages: list[str] = field(default_factory=list)  # vide = tout Home Assistant
    pause_automations: bool = True
    repeat: str = "none"
    started_by: str = ""
    anchor_day: int | None = None  # jour du mois d'origine (répétition mensuelle)

    def as_dict(self, *, public: bool = False) -> dict[str, Any]:
        """`public=True` : version sans l'initiateur, pour tout ce qui est lisible par les
        utilisateurs (attributs d'entités, panneau sans l'autorisation `history`)."""
        data = {
            "id": self.id,
            "start": iso(self.start),
            "end": iso(self.end),
            "reason": self.reason,
            "pages": list(self.pages),
            "pause_automations": self.pause_automations,
            "repeat": self.repeat,
            "anchor_day": self.anchor_day,
        }
        if not public:
            data["started_by"] = self.started_by
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Window | None:
        start = parse_iso(data.get("start"))
        if start is None:
            return None
        repeat = data.get("repeat", "none")
        return cls(
            id=data.get("id") or uuid.uuid4().hex[:8],
            start=start,
            end=parse_iso(data.get("end")),
            reason=str(data.get("reason", "")),
            pages=list(data.get("pages", [])),
            pause_automations=bool(data.get("pause_automations", True)),
            repeat=repeat if repeat in REPEATS else "none",
            started_by=str(data.get("started_by", "")),
            anchor_day=data.get("anchor_day"),
        )

    def next_occurrence(self, now: datetime) -> Window:
        start, end = self.start, self.end
        for _ in range(10000):
            start, end = shift(start, end, self.repeat, self.anchor_day)
            if start > now:
                break
        return replace(self, id=uuid.uuid4().hex[:8], start=start, end=end, started_by="")

    def occurrences(self, until: datetime) -> Iterator[tuple[datetime, datetime | None]]:
        """Occurrences (la 1re est la fenêtre elle-même) jusqu'à `until`."""
        start, end = self.start, self.end
        for _ in range(MAX_OCCURRENCES):
            if start >= until:
                return
            yield start, end
            if self.repeat == "none":
                return
            start, end = shift(start, end, self.repeat, self.anchor_day)
