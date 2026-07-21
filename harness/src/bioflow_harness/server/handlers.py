from __future__ import annotations

from pathlib import Path

from bioflow_harness.autogen.self_extend import SelfExtensionError, ensure_domain_supported
from bioflow_harness.comfy.node_catalog import combined_node_catalog
from bioflow_harness.comfy.resource_binding import ResourceBindings, validate_bindings
from bioflow_harness.comfy.workflow_builder import WorkflowBuilder
from bioflow_harness.models.registry_contract import ToolRegistry
from bioflow_harness.llm.brief_extractor import extract_brief
from bioflow_harness.planner.tool_selector import load_registry
from bioflow_harness.planner.workflow_planner import WorkflowPlanner
from bioflow_harness.server.dto import (
    CandidateDTO,
    CompileRequest,
    CompileResponse,
    GenerateRequest,
    StepDTO,
)

DEFAULT_REGISTRY_PATH = (
    Path(__file__).resolve().parents[3] / "registry" / "tool_selection_registry.yaml"
)

_RESTART_NOTE = (
    "New ComfyUI node types were generated for this domain; restart ComfyUI to see them "
    "in the node palette."
)


def list_stage_candidates(registry: ToolRegistry, stage_id: str) -> list[CandidateDTO]:
    return [
        CandidateDTO(tool_id=tool.id, label=tool.label, tier=tool.tier, note=tool.summary)
        for tool in registry.tools
        if stage_id in tool.stage_tags
    ]


def _resolve_registry_for_domain(registry, brief, registry_path: Path):
    """Returns (registry, note) if `brief.domain` is routable, self-extending the registry
    via research + node synthesis when it is not yet. Returns (None, message) if the
    domain still can't be routed after a self-extension attempt."""
    if brief.domain in registry.domain_routes:
        return registry, None
    try:
        extended = ensure_domain_supported(registry, brief, registry_path)
    except SelfExtensionError as exc:
        return None, f"Workflow planning is required before generating domain: {brief.domain} ({exc})"
    return extended, _RESTART_NOTE


def compile_spec(payload: dict, registry_path: Path | None = None) -> dict:
    request = CompileRequest.from_dict(payload)
    registry_path = registry_path or DEFAULT_REGISTRY_PATH
    registry = load_registry(registry_path)
    brief, _meta = extract_brief(request.request_text, request.provider, request.model)
    registry, note = _resolve_registry_for_domain(registry, brief, registry_path)
    if registry is None:
        return CompileResponse(
            status="planning_required",
            domain=brief.domain,
            route_id=None,
            steps=[],
            message=note,
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
        message=note,
        confidence_notes=[],
    ).to_dict()


def generate_workflow(payload: dict, registry_path: Path | None = None) -> dict:
    request = GenerateRequest.from_dict(payload)
    registry_path = registry_path or DEFAULT_REGISTRY_PATH
    registry = load_registry(registry_path)
    brief, _meta = extract_brief(request.request_text, request.provider, request.model)
    registry, note = _resolve_registry_for_domain(registry, brief, registry_path)
    if registry is None:
        return {
            "status": "planning_required",
            "domain": brief.domain,
            "route_id": None,
            "workflow": None,
            "message": note,
            "confidence_notes": list(brief.confidence_notes),
        }
    plan = WorkflowPlanner(registry).plan(brief)
    bindings = ResourceBindings.from_resources([r.__dict__ for r in request.resources])
    workflow = WorkflowBuilder(combined_node_catalog()).build(plan, bindings)
    warnings = validate_bindings(plan.route_id, bindings)
    deterministic_steps = [
        registry.tool_by_id(stage.selected_tool_id).label for stage in plan.stages
    ]
    if request.steps and list(request.steps) != deterministic_steps:
        warnings.append(
            "Your step edits (reordering/replacement) are not applied in Slice 1; "
            "the workflow was generated from the deterministic default route."
        )
    if note:
        warnings.append(note)
    return {
        "status": "ok",
        "domain": plan.domain,
        "route_id": plan.route_id,
        "workflow": workflow,
        "message": " ".join(warnings) if warnings else None,
    }
