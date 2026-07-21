import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bioflow_harness.models.registry_contract import Operation, RouteStage, ToolEntry, ToolRegistry


@dataclass(frozen=True)
class ToolSelection:
    stage_id: str
    stage_label: str
    tool_id: str
    operation_id: str
    selected_tier: str
    rationale: str


def _list(value: Any) -> list[str]:
    if value is None:
        return []
    return list(value)


def load_registry(path: str | Path) -> ToolRegistry:
    data = json.loads(Path(path).read_text(encoding="utf-8"))

    tools = [
        ToolEntry(
            id=item["id"],
            label=item["label"],
            domain_tags=_list(item.get("domain_tags")),
            stage_tags=_list(item.get("stage_tags")),
            input_types=_list(item.get("input_types")),
            output_types=_list(item.get("output_types")),
            language=item.get("language", "unknown"),
            python_bindings=_list(item.get("python_bindings")),
            summary=item["summary"],
            tier=item["tier"],
            tier_rationale=item["tier_rationale"],
            context_routing_rules=_list(item.get("context_routing_rules")),
            applicability_constraints=_list(item.get("applicability_constraints")),
            selection_rules=_list(item.get("selection_rules")),
            operations=[
                Operation(
                    id=operation["id"],
                    label=operation["label"],
                    input_types=_list(operation.get("input_types")),
                    output_types=_list(operation.get("output_types")),
                    node_type=operation["node_type"],
                )
                for operation in item.get("operations", [])
            ],
            future_comfy_node=item["future_comfy_node"],
            runnable_node_status=item["runnable_node_status"],
            evidence_tier=item.get("evidence_tier", "pending_citation_review"),
            evidence_citation=item.get("evidence_citation", ""),
        )
        for item in data["tools"]
    ]
    routes = {
        route_id: [
            RouteStage(
                stage_id=stage["stage_id"],
                stage_label=stage["stage_label"],
                tool_id=stage["tool_id"],
                operation_id=stage["operation_id"],
                optional=stage.get("optional", False),
            )
            for stage in stages
        ]
        for route_id, stages in data["routes"].items()
    }
    return ToolRegistry(
        metadata=data.get("metadata", {}),
        supported_domains=_list(data.get("supported_domains")),
        routes=routes,
        tools=tools,
        domain_routes=dict(data.get("domain_routes", {})),
    )


class ToolSelector:
    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    def select_official_route(self, route_id: str) -> list[ToolSelection]:
        selections: list[ToolSelection] = []
        for stage in self.registry.official_route(route_id):
            tool = self.registry.tool_by_id(stage.tool_id)
            if tool.tier != "REF":
                raise ValueError(f"Official route stage {stage.stage_id} selected non-REF tool {tool.id}.")
            if tool.runnable_node_status != "runnable":
                raise ValueError(f"Official route stage {stage.stage_id} selected non-runnable tool {tool.id}.")
            selections.append(
                ToolSelection(
                    stage_id=stage.stage_id,
                    stage_label=stage.stage_label,
                    tool_id=tool.id,
                    operation_id=stage.operation_id,
                    selected_tier=tool.tier,
                    rationale=tool.tier_rationale,
                )
            )
        return selections

