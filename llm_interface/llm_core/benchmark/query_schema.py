from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ToolSpecificity(str, Enum):
    TOOL_SPECIFIED = "tool_specified"
    GOAL_SPECIFIED = "goal_specified"
    CONTEXT_ONLY = "context_only"
    ADVERSARIAL = "adversarial"


class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    ADVERSARIAL = "adversarial"


@dataclass
class HeldOutQuery:
    query_id: str
    domain_id: str
    family: str
    nl_text: str
    difficulty: Difficulty
    tool_specificity: ToolSpecificity
    context: dict
    fixture_path: str
    adversarial_hint_tool: str | None = None
