"""0.7.8 — garde-fous d'architecture : aucun module Python de l'intégration ne dépasse 300 lignes."""
from pathlib import Path

MAX_LINES = 300
PACKAGE = Path(__file__).parent.parent / "custom_components" / "maintenance_mode"


def test_no_module_exceeds_300_lines():
    too_long = {p.name: n for p in PACKAGE.glob("*.py") if (n := len(p.read_text(encoding="utf-8").splitlines())) > MAX_LINES}
    assert not too_long, f"modules trop longs : {too_long}"


def test_manager_only_coordinates():
    """Le gestionnaire assemble des modules ; la logique vit dans les mixins."""
    from custom_components.maintenance_mode.manager import MaintenanceManager

    bases = {b.__name__ for b in MaintenanceManager.__mro__}
    assert {"AccessMixin", "NotificationsMixin", "SuspensionMixin", "ValidationMixin",
            "PlanningMixin", "StorageMixin", "SettingsMixin"} <= bases
