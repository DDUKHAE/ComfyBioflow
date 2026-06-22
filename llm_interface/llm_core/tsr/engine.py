from __future__ import annotations

import ast as _ast

from .schema import DomainTSR, ToolChoice, ToolValidity


class _SafeEvalVisitor(_ast.NodeVisitor):
    """Raises ValueError on any node type not in the safe whitelist."""
    _ALLOWED = (
        _ast.Expression, _ast.BoolOp, _ast.And, _ast.Or,
        _ast.Compare, _ast.Eq, _ast.NotEq, _ast.Lt, _ast.LtE, _ast.Gt, _ast.GtE,
        _ast.Name, _ast.Constant, _ast.Load,
    )

    def generic_visit(self, node: _ast.AST) -> None:
        if not isinstance(node, self._ALLOWED):
            raise ValueError(f"Disallowed AST node: {type(node).__name__}")
        super().generic_visit(node)


def _safe_eval(condition: str, context: dict) -> bool:
    try:
        tree = _ast.parse(condition, mode="eval")
        _SafeEvalVisitor().visit(tree)
        # Only Name lookups resolve against context; no builtins
        return bool(eval(compile(tree, "<condition>", "eval"), {"__builtins__": {}}, context))  # noqa: S307
    except Exception:
        return False


class TSREngine:
    def __init__(self, tsr: DomainTSR) -> None:
        self._tsr = tsr

    def resolve(self, step_id: str, context: dict) -> list[ToolChoice]:
        result: list[ToolChoice] = []
        for rule in self._tsr.steps:
            if rule.step_id == step_id and _safe_eval(rule.condition, context):
                result.extend(rule.tools)
        return result

    def canonical(self, step_id: str, context: dict) -> str | None:
        for tc in self.resolve(step_id, context):
            if tc.validity == ToolValidity.CANONICAL:
                return tc.tool_id
        return None

    def is_valid(self, step_id: str, tool_id: str, context: dict) -> ToolValidity:
        for tc in self.resolve(step_id, context):
            if tc.tool_id == tool_id:
                return tc.validity
        return ToolValidity.INVALID
