from __future__ import annotations

import copy
from functools import lru_cache
from pathlib import Path

import yaml

from .schema import DomainTSR, StepRule, ToolChoice, ToolValidity

_DOMAINS_DIR = Path(__file__).resolve().parent / "domains"


def list_domains() -> list[str]:
    return sorted(p.stem for p in _DOMAINS_DIR.glob("*.yaml"))


@lru_cache(maxsize=None)
def _load_domain_tsr_cached(domain_id: str) -> DomainTSR:
    path = _DOMAINS_DIR / f"{domain_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"No TSR domain file for '{domain_id}': {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return _parse_domain(data)


def load_domain_tsr(domain_id: str) -> DomainTSR:
    return copy.deepcopy(_load_domain_tsr_cached(domain_id))


def _parse_domain(data: dict) -> DomainTSR:
    steps = [_parse_step(s) for s in data.get("steps", [])]
    return DomainTSR(
        domain_id=data["domain_id"],
        description=data.get("description", ""),
        steps=steps,
    )


def _parse_step(data: dict) -> StepRule:
    tools = [_parse_tool(t) for t in data.get("tools", [])]
    return StepRule(
        step_id=data["step_id"],
        step_name=data.get("step_name", data["step_id"]),
        condition=data.get("condition", "True"),
        tools=tools,
    )


def _parse_tool(data: dict) -> ToolChoice:
    return ToolChoice(
        tool_id=data["tool_id"],
        validity=ToolValidity(data["validity"]),
        reason=data.get("reason", ""),
    )
