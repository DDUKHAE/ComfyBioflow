from __future__ import annotations

from pathlib import Path

from bioflow_harness.models.registry_contract import ToolRegistry
from bioflow_harness.parser.prompt_parser import parse_prompt
from bioflow_harness.planner.stage_mapper import route_for_domain
from bioflow_harness.planner.tool_selector import load_registry
from bioflow_harness.planner.workflow_planner import WorkflowPlanner
from bioflow_harness.server.dto import (
    CandidateDTO,
    CompileRequest,
    CompileResponse,
    StepDTO,
)

DEFAULT_REGISTRY_PATH = (
    Path(__file__).resolve().parents[3] / "registry" / "tool_selection_registry.yaml"
)


def list_stage_candidates(registry: ToolRegistry, stage_id: str) -> list[CandidateDTO]:
    return [
        CandidateDTO(tool_id=tool.id, label=tool.label, tier=tool.tier, note=tool.summary)
        for tool in registry.tools
        if stage_id in tool.stage_tags
    ]


def compile_spec(payload: dict, registry_path: Path | None = None) -> dict:
    request = CompileRequest.from_dict(payload)
    registry = load_registry(registry_path or DEFAULT_REGISTRY_PATH)
    brief = parse_prompt(request.request_text)
    try:
        route_for_domain(brief.domain)
    except ValueError:
        return CompileResponse(
            status="planning_required",
            domain=brief.domain,
            route_id=None,
            steps=[],
            message=f"Workflow planning is required before generating domain: {brief.domain}",
            confidence_notes=list(brief.confidence_notes),
        ).to_dict()

    plan = WorkflowPlanner(registry).plan(brief)
    steps = [
        StepDTO(
            stage_id=stage.stage_id,
            stage_label=stage.stage_label,
            tool_id=stage.selected_tool_id,
            tool_label=registry.tool_by_id(stage.selected_tool_id).label,
            input_types=list(stage.required_inputs),
            output_types=list(stage.produced_outputs),
            tier=stage.selected_tier,
            rationale=stage.rationale,
            candidates=list_stage_candidates(registry, stage.stage_id),
        )
        for stage in plan.stages
    ]
    return CompileResponse(
        status="ok",
        domain=plan.domain,
        route_id=plan.route_id,
        steps=steps,
        message=None,
        confidence_notes=[],
    ).to_dict()
