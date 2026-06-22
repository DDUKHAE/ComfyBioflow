from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ToolValidity(str, Enum):
    CANONICAL = "canonical"
    ALTERNATIVE_VALID = "alternative_valid"
    INVALID = "invalid"


@dataclass
class ToolChoice:
    tool_id: str
    validity: ToolValidity
    reason: str = ""


@dataclass
class StepRule:
    step_id: str
    step_name: str
    condition: str
    tools: list[ToolChoice] = field(default_factory=list)


@dataclass
class DomainTSR:
    domain_id: str
    description: str
    steps: list[StepRule] = field(default_factory=list)
