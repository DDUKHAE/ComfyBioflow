from __future__ import annotations

import re

from .schema import TieredGold, Verdict


class GoldEvaluator:
    def __init__(self, gold: TieredGold) -> None:
        self._gold = gold

    def evaluate(self, generated_tools: list[str], output: dict) -> Verdict:
        """Evaluate generated workflow tools against tiered gold criteria.

        Canonical match requires exact set equality with canonical.tools.
        Alternative match requires at least one generated tool in alternatives.tools
        (intentionally looser — alternatives are valid substitutions, not full replacements).
        INVALID tool check always takes priority over both.
        """
        # Invalid tool → immediate CRITICAL_ERROR
        if any(t in self._gold.invalid_tools for t in generated_tools):
            return Verdict.CRITICAL_ERROR

        # Canonical match
        if set(generated_tools) == set(self._gold.canonical.tools):
            if self._check_canonical(output):
                return Verdict.CORRECT_CANONICAL

        # Alternative match
        if any(t in self._gold.alternatives.tools for t in generated_tools):
            if self._check_functional_equivalence(output):
                return Verdict.CORRECT_ALTERNATIVE

        return Verdict.INCORRECT

    def _check_canonical(self, output: dict) -> bool:
        for key, threshold in self._gold.canonical.expected_output_criteria.items():
            if key not in output:
                return False
            if not self._eval_criterion(output[key], threshold):
                return False
        return True

    def _check_functional_equivalence(self, output: dict) -> bool:
        for key, threshold_expr in self._gold.alternatives.functional_equivalence_criteria.items():
            if key not in output:
                return False
            if not self._eval_criterion(output[key], threshold_expr):
                return False
        return True

    @staticmethod
    def _eval_criterion(value: float, threshold: float | str) -> bool:
        try:
            if isinstance(threshold, (int, float)):
                return value >= threshold
            # Parse ">= 0.80", "== 1.0", "> 0.5" etc.
            m = re.fullmatch(r"\s*(>=|<=|==|>|<)\s*([0-9.]+)\s*", str(threshold))
            if not m:
                return False
            op, rhs = m.group(1), float(m.group(2))
            return {
                ">=": value >= rhs,
                "<=": value <= rhs,
                "==": value == rhs,
                ">": value > rhs,
                "<": value < rhs,
            }[op]
        except (TypeError, ValueError):
            return False
