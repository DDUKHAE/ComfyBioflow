from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Verdict(str, Enum):
    CORRECT_CANONICAL = "correct_canonical"
    CORRECT_ALTERNATIVE = "correct_alternative"
    INCORRECT = "incorrect"
    CRITICAL_ERROR = "critical_error"


@dataclass
class CanonicalGold:
    tools: list[str]
    expected_output_criteria: dict


@dataclass
class AlternativeGold:
    tools: list[str]
    functional_equivalence_criteria: dict


@dataclass
class AdversarialOverride:
    bad_hint_tool: str
    correct_behaviors: list[str]


@dataclass
class TieredGold:
    query_id: str
    family: str
    context: dict
    canonical: CanonicalGold
    alternatives: AlternativeGold
    invalid_tools: list[str] = field(default_factory=list)
    adversarial_override: AdversarialOverride | None = None
