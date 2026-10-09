"""Entité calendrier : maintenances en cours et planifiées (répétitions incluses)."""
from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .entity import MaintenanceEntity
from .manager import Window


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([MaintenanceCalendar(entry.runtime_data)])


def _event(w: Window, start: datetime, end: datetime | None) -> CalendarEvent:
    # Fin non définie : affichée sur 24 h (un évènement de calendrier a toujours une fin).
    end = end or start + timedelta(days=1)
    scope = ", ".join(w.pages) if w.pages else "Tout Home Assistant"
    return CalendarEvent(
        start=start,
        end=end,
        summary=f"Maintenance — {w.reason}" if w.reason else "Maintenance",
        description=f"Portée : {scope}",
        uid=f"{w.id}:{int(start.timestamp())}",
    )


class MaintenanceCalendar(MaintenanceEntity, CalendarEntity):
    _attr_name = "Planning"
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, manager) -> None:
        super().__init__(manager, "calendar")

    @property
    def event(self) -> CalendarEvent | None:
        """Maintenance en cours, sinon la prochaine."""
        m = self.manager
        if m.current:
            return _event(m.current, m.current.start, m.current.end)
        if m.next_window:
            w = m.next_window
            return _event(w, w.start, w.end)
        return None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        m = self.manager
        events: list[CalendarEvent] = []
        if m.current:
            c = m.current
            ev = _event(c, c.start, c.end)
            if ev.end > start_date and ev.start < end_date:
                events.append(ev)
        for w in m.schedule:
            for start, end in w.occurrences(end_date):
                ev = _event(w, start, end)
                if ev.end > start_date and ev.start < end_date:
                    events.append(ev)
        return sorted(events, key=lambda e: e.start)
