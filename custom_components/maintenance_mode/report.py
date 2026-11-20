"""Bilan de fin : ce qui s'est passé pendant la maintenance, écrit dans l'historique à sa fin.

- durée réelle ;
- entités devenues indisponibles depuis le début (celles qui l'étaient déjà au départ ne comptent pas) ;
- erreurs (niveau ERROR et plus) écrites dans le journal par d'autres composants, dédoublonnées et LIMITÉES
  (`MAX_REPORT_ERRORS` messages distincts de 200 caractères au plus, plus un total).
Le collecteur n'existe que pendant une maintenance ; il est retiré à la fin, au déchargement et recréé après un
rechargement ou un redémarrage (l'état du bilan est enregistré avec le reste).
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.util import dt as dt_util

MAX_REPORT_ENTITIES = 20
MAX_REPORT_ERRORS = 10
_OWN = "custom_components.maintenance_mode"


class ErrorCollector(logging.Handler):
    def __init__(self, sink) -> None:
        super().__init__(level=logging.ERROR)
        self._sink = sink

    def emit(self, record: logging.LogRecord) -> None:
        if record.name.startswith(_OWN):
            return
        try:
            text = record.getMessage()
        except Exception:  # noqa: BLE001
            text = str(record.msg)
        self._sink(record.name, text[:200])


class ReportMixin:
    """Suppose `hass`, `report`, `_log_handler`."""

    def _unavailable_now(self) -> list[str]:
        return sorted(s.entity_id for s in self.hass.states.async_all() if s.state == "unavailable")

    def _report_start(self) -> None:
        self.report = {"baseline": self._unavailable_now(), "errors": [], "errors_total": 0}
        self._report_attach()

    def _report_attach(self) -> None:
        if self._log_handler is None and self.report:
            self._log_handler = ErrorCollector(self._report_error)
            logging.getLogger().addHandler(self._log_handler)

    def _report_detach(self) -> None:
        if self._log_handler is not None:
            logging.getLogger().removeHandler(self._log_handler)
            self._log_handler = None

    def _report_error(self, logger: str, message: str) -> None:
        """Appelé depuis n'importe quel thread : seulement des opérations simples, jamais de journal ici."""
        report = self.report
        if not report:
            return
        report["errors_total"] = report.get("errors_total", 0) + 1
        for item in report["errors"]:
            if item["logger"] == logger and item["message"] == message:
                item["count"] += 1
                return
        if len(report["errors"]) < MAX_REPORT_ERRORS:
            report["errors"].append({"logger": logger, "message": message, "count": 1})

    def _report_finish(self, window: Any) -> dict[str, Any]:
        """Construit le bilan de `window`, retire le collecteur et remet le bilan à zéro."""
        gone = sorted(set(self._unavailable_now()) - set(self.report.get("baseline", [])))
        result = {
            "duration": max(0, int((dt_util.utcnow() - window.start).total_seconds())),
            "unavailable": gone[:MAX_REPORT_ENTITIES],
            "unavailable_total": len(gone),
            "errors": [dict(e) for e in self.report.get("errors", [])],
            "errors_total": self.report.get("errors_total", 0),
        }
        self._report_detach()
        self.report = {}
        return result
