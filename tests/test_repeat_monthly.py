"""6.2.2 — répétition mensuelle : le jour d'origine ne dérive plus."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from homeassistant.util import dt as dt_util

from custom_components.maintenance_mode.manager import Window

from .test_maintenance import _setup

PARIS = ZoneInfo("Europe/Paris")


def _w(year, month, day, hour=10, end_hour=12, anchor=None):
    start = datetime(year, month, day, hour, tzinfo=PARIS)
    end = datetime(year, month, day, end_hour, tzinfo=PARIS)
    return Window("w", dt_util.as_utc(start), dt_util.as_utc(end), repeat="monthly", anchor_day=anchor)


def _chain(window, count):
    """`count` occurrences successives, vues en heure de Paris."""
    out, w = [], window
    for _ in range(count):
        w = w.next_occurrence(w.start)
        out.append((w.start.astimezone(PARIS), w.end.astimezone(PARIS)))
    return out


async def test_31st_does_not_drift(hass):
    await hass.config.async_set_time_zone("Europe/Paris")
    days = [(s.month, s.day, s.hour, e.hour) for s, e in _chain(_w(2027, 1, 31, anchor=31), 5)]
    # fév (28) → mars (31 retrouvé) → avril (30) → mai (31) → juin (30)
    assert days == [(2, 28, 10, 12), (3, 31, 10, 12), (4, 30, 10, 12), (5, 31, 10, 12), (6, 30, 10, 12)]


async def test_leap_year(hass):
    await hass.config.async_set_time_zone("Europe/Paris")
    s, _ = _chain(_w(2028, 1, 31, anchor=31), 1)[0]
    assert (s.month, s.day) == (2, 29)


async def test_year_rollover_and_30th(hass):
    await hass.config.async_set_time_zone("Europe/Paris")
    seq = [(s.year, s.month, s.day) for s, _ in _chain(_w(2026, 11, 30, anchor=30), 4)]
    assert seq == [(2026, 12, 30), (2027, 1, 30), (2027, 2, 28), (2027, 3, 30)]


async def test_wall_clock_kept_across_dst(hass):
    await hass.config.async_set_time_zone("Europe/Paris")
    # 3 h locale le 15 mars (heure d'hiver) → 15 avril (heure d'été) : toujours 3 h locale
    s, e = _chain(_w(2027, 3, 15, hour=3, end_hour=5, anchor=15), 1)[0]
    assert (s.month, s.day, s.hour, e.hour) == (4, 15, 3, 5)


async def test_legacy_window_without_anchor_uses_start_day(hass):
    await hass.config.async_set_time_zone("Europe/Paris")
    w = _w(2027, 1, 31, anchor=None)
    data = w.as_dict()
    data.pop("anchor_day")                      # fenêtre enregistrée avant la 0.6.2
    legacy = Window.from_dict(data)
    assert legacy.anchor_day is None
    s, _ = _chain(legacy, 1)[0]
    assert (s.month, s.day) == (2, 28)
    # l'ancre survit à l'enregistrement
    assert Window.from_dict(w.as_dict()).anchor_day is None
    assert Window.from_dict(_w(2027, 1, 31, anchor=31).as_dict()).anchor_day == 31


async def test_daily_and_weekly_unchanged(hass):
    await hass.config.async_set_time_zone("Europe/Paris")
    start = dt_util.as_utc(datetime(2027, 3, 26, 10, tzinfo=PARIS))
    end = start + timedelta(hours=2)
    d = Window("d", start, end, repeat="daily").next_occurrence(start)
    assert d.start.astimezone(PARIS).hour == 10 and d.start.astimezone(PARIS).day == 27
    w = Window("w", start, end, repeat="weekly").next_occurrence(start)
    assert w.start.astimezone(PARIS).day == 2 and w.start.astimezone(PARIS).month == 4 and w.start.astimezone(PARIS).hour == 10   # heure d'été
    assert w.end.astimezone(PARIS).hour == 12


async def test_anchor_set_when_scheduling(hass):
    await hass.config.async_set_time_zone("Europe/Paris")
    _, m = await _setup(hass)
    start = dt_util.utcnow() + timedelta(days=2)
    w = await m.async_add_window(start=start, end=start + timedelta(hours=2), reason="", pages=[], pause=False, repeat="monthly")
    assert w.anchor_day == dt_util.as_local(start).day
