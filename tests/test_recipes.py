"""9.9 — les recettes du dossier docs/ sont lues par un test : syntaxe, services et champs de l'intégration, évènements."""
import re
from pathlib import Path

import yaml

from custom_components.maintenance_mode.const import MAX_HOOK_TIMEOUT

ROOT = Path(__file__).parent.parent
RECIPES = (ROOT / "docs" / "RECETTES.md").read_text(encoding="utf-8")
SERVICES = yaml.safe_load((ROOT / "custom_components" / "maintenance_mode" / "services.yaml").read_text(encoding="utf-8"))
EVENTS = {"maintenance_mode_started", "maintenance_mode_ended"}


def _blocks():
    return re.findall(r"```yaml\n(.*?)```", RECIPES, flags=re.S)


def _walk(node):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


def test_there_are_recipes_and_each_block_is_valid_yaml():
    blocks = _blocks()
    assert len(blocks) >= 5
    for b in blocks:
        assert yaml.safe_load(b)


def test_maintenance_services_exist_and_their_fields_are_declared():
    seen = set()
    for b in _blocks():
        for d in _walk(yaml.safe_load(b)):
            name = d.get("action") or d.get("service")
            if isinstance(name, str) and name.startswith("maintenance_mode."):
                svc = name.split(".", 1)[1]
                assert svc in SERVICES, f"service inconnu : {name}"
                fields = set((SERVICES[svc] or {}).get("fields", {}))
                assert set(d.get("data", {})) <= fields, f"{name} : champs non déclarés {set(d.get('data', {})) - fields}"
                for required, spec in ((SERVICES[svc] or {}).get("fields", {})).items():
                    if spec.get("required"):
                        assert required in d.get("data", {}), f"{name} : champ obligatoire « {required} » absent"
                seen.add(svc)
    assert {"start", "schedule"} <= seen


def test_event_types_are_the_ones_the_integration_fires():
    used = {d["event_type"] for b in _blocks() for d in _walk(yaml.safe_load(b)) if "event_type" in d}
    assert used and used <= EVENTS


def test_hook_recipe_respects_the_documented_limit():
    assert f"limite {MAX_HOOK_TIMEOUT} s par hook" in RECIPES        # le texte ne promet pas plus que la limite réelle
