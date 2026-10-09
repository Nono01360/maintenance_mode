"""Cœur de l'intégration : maintenances planifiées, état courant, droits, notifications."""
from __future__ import annotations

import asyncio
import logging
import re
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from typing import Any, Iterator

from dateutil.relativedelta import relativedelta

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import STATE_ON
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    DEFAULT_END_SOON_MINUTES,
    DEFAULT_MESSAGE,
    DEFAULT_WARN_MINUTES,
    DOMAIN,
    EVENT_ENDED,
    EVENT_STARTED,
    LEGACY_ALLOWED_USERS,
    LEGACY_AUTOMATIONS,
    LEGACY_WARN_MINUTES,
    MAX_HISTORY,
    MAX_OCCURRENCES,
    MAX_PAGES,
    MAX_REASON,
    MAX_TEMPLATES,
    MAX_WINDOWS,
    NOTIFY_KINDS,
    REPEATS,
    ROLE_ADMIN,
    ROLE_NONE,
    ROLE_VIEWER,
    ROLES,
)

_LOGGER = logging.getLogger(__name__)
STORAGE_VERSION = 1
_FAR = datetime(9999, 12, 31, tzinfo=dt_util.UTC)
_NOTIFY_NAME = re.compile(r"^[a-z0-9_]+$")
_STEPS = {
    "daily": relativedelta(days=1),
    "weekly": relativedelta(weeks=1),
    "monthly": relativedelta(months=1),
}


# --------------------------------------------------------------------- utilitaires
def get_manager(hass: HomeAssistant) -> MaintenanceManager | None:
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is ConfigEntryState.LOADED:
            return entry.runtime_data
    return None


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = dt_util.parse_datetime(value)
    return dt_util.as_utc(parsed) if parsed else None


def iso(value: datetime | None) -> str | None:
    return dt_util.as_utc(value).isoformat() if value else None


def _clean_pages(pages: list[str] | None) -> list[str]:
    out: list[str] = []
    for page in pages or []:
        page = str(page).strip().strip("/")
        if page and page not in out:
            out.append(page)
    if len(out) > MAX_PAGES:
        raise ServiceValidationError(f"Maximum {MAX_PAGES} pages par maintenance.")
    return out


def _overlap(a_start, a_end, b_start, b_end) -> bool:
    return a_start < (b_end or _FAR) and b_start < (a_end or _FAR)


def _shift(start: datetime, end: datetime | None, repeat: str):
    """Décale d'une période en heure locale (l'heure « murale » est conservée malgré le DST)."""
    step = _STEPS[repeat]
    new_start = dt_util.as_utc(dt_util.as_local(start) + step)
    new_end = dt_util.as_utc(dt_util.as_local(end) + step) if end else None
    return new_start, new_end


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

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "start": iso(self.start),
            "end": iso(self.end),
            "reason": self.reason,
            "pages": list(self.pages),
            "pause_automations": self.pause_automations,
            "repeat": self.repeat,
            "started_by": self.started_by,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Window | None:
        start = _parse(data.get("start"))
        if start is None:
            return None
        repeat = data.get("repeat", "none")
        return cls(
            id=data.get("id") or uuid.uuid4().hex[:8],
            start=start,
            end=_parse(data.get("end")),
            reason=str(data.get("reason", "")),
            pages=list(data.get("pages", [])),
            pause_automations=bool(data.get("pause_automations", True)),
            repeat=repeat if repeat in REPEATS else "none",
            started_by=str(data.get("started_by", "")),
        )

    def next_occurrence(self, now: datetime) -> Window:
        start, end = self.start, self.end
        for _ in range(10000):
            start, end = _shift(start, end, self.repeat)
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
            start, end = _shift(start, end, self.repeat)


def _default_config() -> dict[str, Any]:
    return {
        "automations": [],       # vide = toutes les automatisations
        "allowed_users": [],     # exemptés ; vide = seul le propriétaire
        "warn_minutes": DEFAULT_WARN_MINUTES,
        "message": DEFAULT_MESSAGE,
        "panel_access": {},      # {user_id: rôle}
        "notify_services": [],   # noms de services notify.* (ex. mobile_app_pixel)
        "notify_kinds": list(NOTIFY_KINDS),
        "end_soon_minutes": DEFAULT_END_SOON_MINUTES,
        "templates": [],
    }


def _fmt_local(value: datetime) -> str:
    local = dt_util.as_local(value)
    if local.date() == dt_util.as_local(dt_util.utcnow()).date():
        return local.strftime("%H:%M")
    return local.strftime("%d/%m %H:%M")


def _notification_text(hass: HomeAssistant, kind: str, w: Window) -> tuple[str, str]:
    en = (hass.config.language or "fr").startswith("en")
    reason = f" {w.reason}" if w.reason else ""
    if kind == "pre":
        mins = max(0, int((w.start - dt_util.utcnow()).total_seconds() // 60))
        if en:
            return "Scheduled maintenance", f"Starts in {mins} min ({_fmt_local(w.start)}).{reason}"
        return "Maintenance prévue", f"Début dans {mins} min ({_fmt_local(w.start)}).{reason}"
    if kind == "started":
        end = _fmt_local(w.end) if w.end else None
        if en:
            return "Maintenance started", (f"Expected end: {end}." if end else "No end time set.") + reason
        return "Maintenance en cours", (f"Fin prévue à {end}." if end else "Pas d'heure de fin définie.") + reason
    if kind == "end_soon":
        end = _fmt_local(w.end) if w.end else "?"
        if en:
            return "Maintenance ending soon", f"Expected end: {end}."
        return "La maintenance se termine bientôt", f"Fin prévue à {end}."
    if en:
        return "Maintenance finished", "Home Assistant is available again."
    return "Maintenance terminée", "Home Assistant est de nouveau disponible."


class MaintenanceManager:
    """Source de vérité unique ; entités, panneau, services et calendrier la reflètent."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.current: Window | None = None
        self.disabled: list[str] = []
        self.schedule: list[Window] = []
        self.history: list[dict[str, Any]] = []
        self.notified: list[str] = []
        self.config: dict[str, Any] = _default_config()
        self.users: list[dict[str, Any]] = []
        self.owner_ids: list[str] = []
        self._store: Store = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}")
        self._listeners: list[CALLBACK_TYPE] = []
        self._timer: CALLBACK_TYPE | None = None
        self._lock = asyncio.Lock()
        self._unloaded = False

    # ------------------------------------------------------------------ chargement
    async def async_load(self) -> None:
        data: dict[str, Any] = await self._store.async_load() or {}
        cfg = data.get("config")
        if cfg is None:  # migration depuis la v0.2
            cfg = {}
            opts = self.entry.options
            if opts.get(LEGACY_AUTOMATIONS):
                cfg["automations"] = list(opts[LEGACY_AUTOMATIONS])
            if opts.get(LEGACY_ALLOWED_USERS):
                cfg["allowed_users"] = list(opts[LEGACY_ALLOWED_USERS])
            if opts.get(LEGACY_WARN_MINUTES):
                cfg["warn_minutes"] = int(opts[LEGACY_WARN_MINUTES])
            if data.get("message"):
                cfg["message"] = data["message"]
        self.config = {**_default_config(), **cfg}
        self.disabled = list(data.get("disabled", []))
        self.history = list(data.get("history", []))[-MAX_HISTORY:]
        self.notified = list(data.get("notified", []))[-200:]

        if data.get("current"):
            self.current = Window.from_dict(data["current"])
        elif data.get("active"):  # ancien format
            self.current = Window(uuid.uuid4().hex[:8], dt_util.utcnow(), _parse(data.get("end")))
        self.schedule = [w for d in data.get("schedule", []) if (w := Window.from_dict(d))]
        legacy_start = _parse(data.get("start"))
        if (
            "schedule" not in data
            and data.get("start_armed")
            and legacy_start
            and legacy_start > dt_util.utcnow()
        ):
            self.schedule = [Window(uuid.uuid4().hex[:8], legacy_start, _parse(data.get("end")))]
        self.schedule.sort(key=lambda w: w.start)

        await self._refresh_users()
        async_at_started(self.hass, self._async_resume)

    @callback
    def async_unload(self) -> None:
        self._unloaded = True
        self._cancel_timer()
        self._listeners.clear()
        ir.async_delete_issue(self.hass, DOMAIN, "missing_automations")

    @callback
    def async_add_listener(self, update: CALLBACK_TYPE) -> CALLBACK_TYPE:
        self._listeners.append(update)

        @callback
        def remove() -> None:
            if update in self._listeners:
                self._listeners.remove(update)

        return remove

    # ------------------------------------------------------------------ lecture
    @property
    def exempt_users(self) -> list[str]:
        """Utilisateurs jamais bloqués : exemptés choisis + propriétaire(s)."""
        return sorted({*self.config["allowed_users"], *self.owner_ids})

    @property
    def hidden_panel_users(self) -> list[str]:
        """Utilisateurs sans accès au panneau (son entrée de menu est masquée)."""
        return [
            u["id"]
            for u in self.users
            if self.effective_role(u["id"], u["is_owner"], u["is_admin"]) == ROLE_NONE
        ]

    @property
    def next_window(self) -> Window | None:
        return self.schedule[0] if self.schedule else None

    def effective_role(self, user_id: str, is_owner: bool, is_admin: bool) -> str:
        if is_owner:
            return ROLE_ADMIN
        role = self.config["panel_access"].get(user_id)
        if role in ROLES:
            return role
        return ROLE_ADMIN if is_admin else ROLE_VIEWER

    def role_for(self, user: Any) -> str:
        return self.effective_role(user.id, user.is_owner, user.is_admin)

    def state_for(self, user: Any) -> dict[str, Any]:
        """Données envoyées au panneau, filtrées selon le rôle."""
        role = self.role_for(user)
        if role == ROLE_NONE:
            return {"role": role}
        data: dict[str, Any] = {
            "role": role,
            "now": iso(dt_util.utcnow()),
            "active": self.current is not None,
            "current": self.current.as_dict() if self.current else None,
            "upcoming": [w.as_dict() for w in self.schedule],
            "message": self.config["message"],
        }
        if role == ROLE_ADMIN:
            access = self.config["panel_access"]
            data["config"] = {k: (dict(v) if isinstance(v, dict) else list(v) if isinstance(v, list) else v)
                              for k, v in self.config.items()}
            data["users"] = [
                {
                    **u,
                    "role": self.effective_role(u["id"], u["is_owner"], u["is_admin"]),
                    "explicit": u["id"] in access,
                }
                for u in self.users
            ]
            data["disabled_count"] = len(self.disabled)
            data["history"] = list(reversed(self.history))[:20]
        return data

    # ------------------------------------------------------------------ actions
    async def async_start_now(
        self, *, end: datetime | None, reason: str, pages: list[str], pause: bool, by: str = ""
    ) -> None:
        async with self._lock:
            end = self._check_end(end)
            window = Window(
                id=uuid.uuid4().hex[:8],
                start=dt_util.utcnow(),
                end=end,
                reason=self._check_reason(reason),
                pages=_clean_pages(pages),
                pause_automations=pause,
                started_by=by,
            )
            if self.current:
                await self._deactivate("replaced")
            await self._activate(window)
            await self._commit()

    async def async_stop(self) -> None:
        async with self._lock:
            if self.current:
                await self._deactivate("manual")
                await self._commit()

    async def async_update_current(
        self, *, end: datetime | None, reason: str, pages: list[str]
    ) -> None:
        async with self._lock:
            if not self.current:
                raise ServiceValidationError("Aucune maintenance en cours.")
            end = self._check_end(end)
            if end:
                for w in self.schedule:
                    if _overlap(self.current.start, end, w.start, w.end):
                        raise ServiceValidationError("La fin chevauche une maintenance planifiée.")
            self.current.end = end
            self.current.reason = self._check_reason(reason)
            self.current.pages = _clean_pages(pages)
            await self._commit()

    async def async_add_window(
        self,
        *,
        start: datetime,
        end: datetime | None,
        reason: str,
        pages: list[str],
        pause: bool,
        repeat: str = "none",
    ) -> Window:
        async with self._lock:
            if len(self.schedule) >= MAX_WINDOWS:
                raise ServiceValidationError(f"Maximum {MAX_WINDOWS} maintenances planifiées.")
            start, end = self._check_window(start, end, ignore_id=None)
            window = Window(
                id=uuid.uuid4().hex[:8],
                start=start,
                end=end,
                reason=self._check_reason(reason),
                pages=_clean_pages(pages),
                pause_automations=pause,
                repeat=self._check_repeat(repeat, start, end),
            )
            self.schedule.append(window)
            self.schedule.sort(key=lambda w: w.start)
            await self._commit()
            return window

    async def async_update_window(
        self,
        window_id: str,
        *,
        start: datetime,
        end: datetime | None,
        reason: str,
        pages: list[str],
        pause: bool,
        repeat: str = "none",
    ) -> None:
        async with self._lock:
            window = self._find(window_id)
            start, end = self._check_window(start, end, ignore_id=window_id)
            window.start, window.end = start, end
            window.reason = self._check_reason(reason)
            window.pages = _clean_pages(pages)
            window.pause_automations = pause
            window.repeat = self._check_repeat(repeat, start, end)
            self.schedule.sort(key=lambda w: w.start)
            await self._commit()

    async def async_delete_window(self, window_id: str) -> None:
        async with self._lock:
            self.schedule.remove(self._find(window_id))
            await self._commit()

    async def async_update_config(self, changes: dict[str, Any]) -> None:
        async with self._lock:
            await self._refresh_users()
            valid = {u["id"] for u in self.users}
            cfg = self.config
            if "automations" in changes:
                cfg["automations"] = sorted(
                    {e for e in changes["automations"] if isinstance(e, str) and e.startswith("automation.")}
                )
            if "allowed_users" in changes:
                cfg["allowed_users"] = [u for u in dict.fromkeys(changes["allowed_users"]) if u in valid]
            if "warn_minutes" in changes:
                cfg["warn_minutes"] = max(1, min(1440, int(changes["warn_minutes"])))
            if "end_soon_minutes" in changes:
                cfg["end_soon_minutes"] = max(1, min(1440, int(changes["end_soon_minutes"])))
            if "message" in changes:
                cfg["message"] = str(changes["message"]).strip()[:255] or DEFAULT_MESSAGE
            if "panel_access" in changes:
                cfg["panel_access"] = {
                    uid: role
                    for uid, role in changes["panel_access"].items()
                    if uid in valid and role in ROLES
                }
            if "notify_services" in changes:
                cfg["notify_services"] = [
                    n
                    for n in dict.fromkeys(changes["notify_services"])
                    if _NOTIFY_NAME.match(n) and n != "send_message"
                ][:20]
            if "notify_kinds" in changes:
                cfg["notify_kinds"] = [k for k in NOTIFY_KINDS if k in changes["notify_kinds"]]
            if "templates" in changes:
                cfg["templates"] = self._clean_templates(changes["templates"])
            await self._commit()

    # ------------------------------------------------------------------ validation
    def _find(self, window_id: str) -> Window:
        for window in self.schedule:
            if window.id == window_id:
                return window
        raise ServiceValidationError("Maintenance introuvable.")

    @staticmethod
    def _check_reason(reason: str) -> str:
        reason = (reason or "").strip()
        if len(reason) > MAX_REASON:
            raise ServiceValidationError(f"Motif trop long ({MAX_REASON} caractères max).")
        return reason

    @staticmethod
    def _check_repeat(repeat: str, start: datetime, end: datetime | None) -> str:
        if repeat not in REPEATS:
            raise ServiceValidationError("Répétition invalide.")
        if repeat != "none" and end is None:
            raise ServiceValidationError("Une maintenance répétée doit avoir une fin.")
        if repeat != "none" and end is not None:
            next_start, _ = _shift(start, end, repeat)
            if end > next_start:
                raise ServiceValidationError("La durée dépasse la période de répétition.")
        return repeat

    @staticmethod
    def _check_end(end: datetime | None) -> datetime | None:
        if end is None:
            return None
        end = dt_util.as_utc(end)
        if end <= dt_util.utcnow():
            raise ServiceValidationError("La fin doit être dans le futur.")
        return end

    def _check_window(self, start, end, *, ignore_id):
        start = dt_util.as_utc(start)
        end = dt_util.as_utc(end) if end else None
        if start <= dt_util.utcnow():
            raise ServiceValidationError("Le début doit être dans le futur.")
        if end is not None and end <= start:
            raise ServiceValidationError("La fin doit être postérieure au début.")
        for other in self.schedule:
            if other.id != ignore_id and _overlap(start, end, other.start, other.end):
                raise ServiceValidationError("Cette période chevauche une autre maintenance planifiée.")
        if self.current and self.current.end and _overlap(start, end, self.current.start, self.current.end):
            raise ServiceValidationError("Cette période chevauche la maintenance en cours.")
        return start, end

    @staticmethod
    def _clean_templates(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for t in raw[:MAX_TEMPLATES]:
            name = str(t.get("name", "")).strip()[:40]
            if not name:
                continue
            duration = t.get("duration")
            repeat = t.get("repeat", "none")
            out.append(
                {
                    "id": str(t.get("id") or uuid.uuid4().hex[:8])[:12],
                    "name": name,
                    "reason": str(t.get("reason", "")).strip()[:MAX_REASON],
                    "pages": _clean_pages(t.get("pages", [])),
                    "pause_automations": bool(t.get("pause_automations", True)),
                    "duration": int(duration) if duration else None,
                    "repeat": repeat if repeat in REPEATS else "none",
                }
            )
        return out

    # ------------------------------------------------------------------ interne
    def _targets(self) -> list[str]:
        """Automatisations à couper : celles choisies, ou toutes si aucune choisie."""
        selected = self.config["automations"]
        candidates = selected or self.hass.states.async_entity_ids("automation")
        return [
            e for e in candidates
            if (state := self.hass.states.get(e)) and state.state == STATE_ON
        ]

    async def _activate(self, window: Window) -> None:
        targets = self._targets() if window.pause_automations else []
        if targets:
            try:
                await self.hass.services.async_call(
                    "automation", "turn_off",
                    {"entity_id": targets, "stop_actions": True}, blocking=True,
                )
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Impossible de désactiver les automatisations")
        self.disabled = targets
        self.current = window
        self.hass.bus.async_fire(EVENT_STARTED, window.as_dict())
        await self._notify("started", window)

    async def _deactivate(self, ended_by: str = "manual") -> None:
        window = self.current
        if self.disabled:
            try:
                await self.hass.services.async_call(
                    "automation", "turn_on", {"entity_id": self.disabled}, blocking=True
                )
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Impossible de réactiver les automatisations")
        self.disabled = []
        self.current = None
        if window:
            now = dt_util.utcnow()
            self.history.append({**window.as_dict(), "ended_at": iso(now), "ended_by": ended_by})
            self.history = self.history[-MAX_HISTORY:]
            self.hass.bus.async_fire(EVENT_ENDED, {**window.as_dict(), "ended_by": ended_by})
            if ended_by != "replaced":
                await self._notify("ended", window)

    async def _notify(self, kind: str, window: Window) -> None:
        key = f"{window.id}:{kind}"
        if key in self.notified:
            return
        self.notified = [*self.notified, key][-200:]
        services = self.config["notify_services"]
        if not services or kind not in self.config["notify_kinds"]:
            return
        title, message = _notification_text(self.hass, kind, window)
        for name in services:
            if not self.hass.services.has_service("notify", name):
                continue
            try:
                await self.hass.services.async_call(
                    "notify", name, {"title": title, "message": message}, blocking=False
                )
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Échec de la notification via notify.%s", name)

    async def _send_due_notifications(self, now: datetime) -> None:
        kinds = self.config["notify_kinds"]
        if not self.config["notify_services"]:
            return
        if "pre" in kinds:
            warn = timedelta(minutes=self.config["warn_minutes"])
            for w in list(self.schedule):
                if w.start - warn <= now < w.start:
                    await self._notify("pre", w)
        if "end_soon" in kinds and self.current and self.current.end:
            soon = timedelta(minutes=self.config["end_soon_minutes"])
            if self.current.end - soon <= now < self.current.end:
                await self._notify("end_soon", self.current)

    async def _refresh_users(self) -> None:
        users = await self.hass.auth.async_get_users()
        self.users = [
            {"id": u.id, "name": u.name or u.id, "is_owner": u.is_owner, "is_admin": u.is_admin}
            for u in users
            if u.is_active and not u.system_generated
        ]
        self.owner_ids = [u["id"] for u in self.users if u["is_owner"]]

    async def _process_due(self) -> None:
        """Termine / démarre ce qui est arrivé à échéance (idempotent)."""
        now = dt_util.utcnow()
        if self.current and self.current.end and self.current.end <= now:
            await self._deactivate("auto")
        while self.schedule and self.schedule[0].start <= now:
            window = self.schedule.pop(0)
            if window.repeat != "none":  # la série continue : prochaine occurrence
                self.schedule.append(window.next_occurrence(now))
                self.schedule.sort(key=lambda w: w.start)
            if window.end and window.end <= now:
                continue  # entièrement passée (ex. HA éteint)
            if self.current:
                await self._deactivate("replaced")
            window.started_by = window.started_by or "planification"
            await self._activate(window)

    async def _async_resume(self, _hass: HomeAssistant | None = None) -> None:
        if self._unloaded:
            return
        async with self._lock:
            await self._process_due()
            await self._commit()

    async def _async_timer_cb(self, _now: datetime) -> None:
        if self._unloaded:
            return
        async with self._lock:
            await self._process_due()
            await self._commit()

    def _cancel_timer(self) -> None:
        if self._timer:
            self._timer()
            self._timer = None

    @callback
    def _reschedule(self) -> None:
        self._cancel_timer()
        if self._unloaded:
            return
        now = dt_util.utcnow()
        due: list[datetime] = []
        if self.current and self.current.end:
            due.append(self.current.end)
        if self.schedule:
            due.append(self.schedule[0].start)
        if self.config["notify_services"]:
            kinds = self.config["notify_kinds"]
            if "pre" in kinds:
                warn = timedelta(minutes=self.config["warn_minutes"])
                due += [
                    w.start - warn for w in self.schedule
                    if w.start - warn > now and f"{w.id}:pre" not in self.notified
                ]
            if "end_soon" in kinds and self.current and self.current.end:
                t = self.current.end - timedelta(minutes=self.config["end_soon_minutes"])
                if t > now and f"{self.current.id}:end_soon" not in self.notified:
                    due.append(t)
        if due:
            self._timer = async_track_point_in_utc_time(self.hass, self._async_timer_cb, min(due))

    @callback
    def _update_issues(self) -> None:
        """Alertes dans Paramètres → Réparations."""
        if not self.hass.is_running:
            return
        missing = [e for e in self.config["automations"] if self.hass.states.get(e) is None]
        if missing:
            ir.async_create_issue(
                self.hass, DOMAIN, "missing_automations",
                is_fixable=False, severity=ir.IssueSeverity.WARNING,
                translation_key="missing_automations",
                translation_placeholders={"entities": ", ".join(missing)},
            )
        else:
            ir.async_delete_issue(self.hass, DOMAIN, "missing_automations")

    async def _commit(self) -> None:
        await self._refresh_users()
        await self._send_due_notifications(dt_util.utcnow())
        self._reschedule()
        self._update_issues()
        await self._store.async_save(
            {
                "config": self.config,
                "disabled": self.disabled,
                "current": self.current.as_dict() if self.current else None,
                "schedule": [w.as_dict() for w in self.schedule],
                "history": self.history,
                "notified": self.notified,
            }
        )
        for update in list(self._listeners):
            update()
