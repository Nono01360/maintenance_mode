"""9.8 — tests de temps : changements d'heure, horloge qui recule, fuseau modifié, redémarrage à la seconde de la fin."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed, async_capture_events

from custom_components.maintenance_mode.manager import Window

from .test_chaos import _restart
from .test_maintenance import _setup, _state

PARIS = ZoneInfo("Europe/Paris")


def _w(y, mo, d, h, mi=0, hours=2, repeat="daily"):
    start = datetime(y, mo, d, h, mi, tzinfo=PARIS)
    return Window("w", dt_util.as_utc(start), dt_util.as_utc(start) + timedelta(hours=hours), repeat=repeat, anchor_day=d)


def _chain(window, n):
    out, w = [], window
    for _ in range(n):
        w = w.next_occurrence(w.start)
        out.append(w)
    return out


# ------------------------------------------------------------------ changements d'heure
async def test_daily_keeps_wall_clock_across_both_transitions(hass):
    await hass.config.async_set_time_zone("Europe/Paris")
    for start in (_w(2027, 3, 26, 10), _w(2026, 10, 23, 10)):        # passage à l'heure d'été puis d'hiver
        wins = _chain(start, 5)
        assert all(w.start.astimezone(PARIS).hour == 10 and w.end.astimezone(PARIS).hour == 12 for w in wins)
        assert all(b.start - a.start in (timedelta(hours=23), timedelta(hours=24), timedelta(hours=25))
                   for a, b in zip([start] + wins, wins))


async def test_nonexistent_and_ambiguous_wall_times_never_go_backwards(hass):
    await hass.config.async_set_time_zone("Europe/Paris")
    for start in (_w(2027, 3, 27, 2, 30, hours=1), _w(2026, 10, 24, 2, 30, hours=1)):   # 02:30 : inexistante le 28/03, ambiguë le 25/10
        prev = start
        for w in _chain(start, 4):
            assert w.start > prev.start and w.end > w.start, "ni retour en arrière, ni durée négative"
            prev = w


async def test_window_starting_in_the_nonexistent_hour_keeps_a_real_duration(hass):
    """Régression : 02:30 n'existe pas le 28/03/2027 à Paris ; début et fin tombaient au même instant (durée nulle) et la
    maintenance de cette nuit-là aurait été ignorée comme « déjà passée »."""
    await hass.config.async_set_time_zone("Europe/Paris")
    start = _w(2027, 3, 27, 2, 30, hours=1)
    nxt = start.next_occurrence(start.start)
    assert nxt.start.astimezone(PARIS).date().day == 28 and nxt.end - nxt.start == timedelta(hours=1)


async def test_window_straddling_the_transition_keeps_its_wall_duration(hass):
    await hass.config.async_set_time_zone("Europe/Paris")
    w = _chain(_w(2027, 3, 27, 1, 0, hours=3), 1)[0]               # 01:00 → 04:00 le 28/03 (nuit de 2 h réelles)
    local_end = w.end.astimezone(PARIS)
    assert w.start.astimezone(PARIS).hour == 1 and (local_end.day, local_end.hour) == (28, 4)


# ------------------------------------------------------------------ horloge qui recule
async def test_clock_going_back_does_not_end_start_or_renotify(hass, freezer):
    _, m = await _setup(hass)
    now = dt_util.utcnow()
    started = async_capture_events(hass, "maintenance_mode_started")
    ended = async_capture_events(hass, "maintenance_mode_ended")
    await m.async_start_now(end=now + timedelta(hours=1), reason="x", pages=[], pause=True)
    await m.async_add_window(start=now + timedelta(hours=3), end=now + timedelta(hours=4), reason="y", pages=[], pause=True)
    freezer.move_to(now - timedelta(hours=2))                     # l'horloge recule de 2 h (NTP, VM restaurée…)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert m.current and m.current.reason == "x" and len(m.schedule) == 1
    assert _state(hass, "automation.a1") == "off" and len(started) == 1 and ended == []
    freezer.move_to(now + timedelta(hours=1, minutes=1))          # puis le temps repart : fin une seule fois
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert m.current is None and len(ended) == 1 and _state(hass, "automation.a1") == "on"
    freezer.move_to(now + timedelta(hours=3, minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert m.current and m.current.reason == "y" and len(started) == 2


async def test_clock_back_gives_a_non_negative_duration_in_the_report(hass, freezer):
    _, m = await _setup(hass)
    now = dt_util.utcnow()
    await m.async_start_now(end=None, reason="", pages=[], pause=False)
    freezer.move_to(now - timedelta(hours=1))
    await m.async_stop()
    assert m.history[-1]["report"]["duration"] == 0


# ------------------------------------------------------------------ fuseau modifié
async def test_time_zone_change_affects_only_future_occurrences(hass):
    await hass.config.async_set_time_zone("Europe/Paris")
    _, m = await _setup(hass)
    start = dt_util.utcnow() + timedelta(days=2)
    w = await m.async_add_window(start=start, end=start + timedelta(hours=2), reason="", pages=[], pause=False, repeat="daily")
    first = w.start
    await hass.config.async_set_time_zone("Asia/Kolkata")
    assert m.schedule[0].start == first, "une occurrence déjà planifiée est un instant : elle ne bouge pas"
    nxt = m.schedule[0].next_occurrence(first)
    assert nxt.start.astimezone(ZoneInfo("Asia/Kolkata")).hour == first.astimezone(ZoneInfo("Asia/Kolkata")).hour
    assert nxt.start > first and nxt.end > nxt.start


# ------------------------------------------------------------------ redémarrage à la seconde de la fin
@pytest.mark.parametrize("offset,still_active", [(-1, True), (0, False), (1, False)])
async def test_restart_at_the_second_of_the_end(hass, hass_storage, freezer, offset, still_active):
    entry, m = await _setup(hass)
    now = dt_util.utcnow().replace(microsecond=0)
    freezer.move_to(now)
    end = now + timedelta(hours=1)
    await m.async_start_now(end=end, reason="fin", pages=[], pause=True)
    freezer.move_to(end + timedelta(seconds=offset))
    m2 = await _restart(hass, entry, m)                           # redémarrage exactement à T-1 s, T ou T+1 s
    assert (m2.current is not None) is still_active
    assert _state(hass, "automation.a1") == ("off" if still_active else "on")
    if still_active:                                              # il reste 1 s : la minuterie termine la maintenance
        freezer.move_to(end + timedelta(seconds=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert m2.current is None and _state(hass, "automation.a1") == "on"
    assert [h["ended_by"] for h in m2.history] == ["auto"]


async def test_restart_at_the_second_of_a_scheduled_start(hass, hass_storage, freezer):
    entry, m = await _setup(hass)
    now = dt_util.utcnow().replace(microsecond=0)
    freezer.move_to(now)
    start = now + timedelta(hours=1)
    await m.async_add_window(start=start, end=start + timedelta(hours=1), reason="pile", pages=[], pause=True)
    freezer.tick(timedelta(seconds=5))                            # l'enregistrement d'une planification est différé de 2 s
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    freezer.move_to(start)
    m2 = await _restart(hass, entry, m)
    assert m2.current and m2.current.reason == "pile" and m2.schedule == []
    assert _state(hass, "automation.a1") == "off"
