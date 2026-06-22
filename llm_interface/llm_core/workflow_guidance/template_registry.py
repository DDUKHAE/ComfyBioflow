from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
_REQUIRED_KEYS = {"template_id", "intent", "description", "required_nodes", "required_edges", "optional_nodes", "forbidden_nodes"}


def _validate_template(template: dict) -> dict:
    missing = sorted(_REQUIRED_KEYS - set(template))
    if missing:
        raise ValueError(f"Template missing required keys: {', '.join(missing)}")
    return template


@lru_cache(maxsize=None)
def load_template(template_id: str) -> dict:
    path = _TEMPLATE_DIR / f"{template_id}.json"
    return _validate_template(json.loads(path.read_text(encoding="utf-8")))


@lru_cache(maxsize=1)
def list_templates() -> list[dict]:
    return [load_template(path.stem) for path in sorted(_TEMPLATE_DIR.glob("*.json"))]


def get_template_for_intent(intent: str) -> dict | None:
    for template in list_templates():
        if template.get("intent") == intent:
            return template
    return None
