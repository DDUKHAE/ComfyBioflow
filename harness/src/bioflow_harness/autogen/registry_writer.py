from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from bioflow_harness.autogen.node_synthesizer import SynthesizedNode
from bioflow_harness.autogen.route_proposal import RouteProposal
from bioflow_harness.comfy.node_catalog import combined_node_catalog
from bioflow_harness.planner.tool_selector import load_registry
from bioflow_harness.registry_validator import RegistryValidationError, validate_official_route

_UNREVIEWED_LABEL = "[LLM-researched, unreviewed] "


class RegistryWriteError(RuntimeError):
    """Raised when a researched proposal fails schema/route validation and is rolled back."""


def _tool_entry_dict(stage, node_type: str) -> dict:
    operation_id = f"{stage.tool_id}_operation"
    return {
        "id": stage.tool_id,
        "label": stage.tool_label,
        "domain_tags": [],
        "stage_tags": [stage.stage_id],
        "input_types": stage.input_types,
        "output_types": stage.output_types,
        "language": stage.language,
        "python_bindings": [],
        "summary": stage.summary,
        "tier": stage.tier,
        "tier_rationale": f"{_UNREVIEWED_LABEL}{stage.tier_rationale}",
        "context_routing_rules": [],
        "applicability_constraints": [],
        "selection_rules": [],
        "operations": [
            {
                "id": operation_id,
                "label": stage.stage_label,
                "input_types": stage.input_types,
                "output_types": stage.output_types,
                "node_type": node_type,
            }
        ],
        "future_comfy_node": node_type,
        "runnable_node_status": "runnable",
        "evidence_tier": stage.evidence_tier,
        "evidence_citation": stage.evidence_citation,
    }, operation_id


def append_route_and_tools(
    registry_path: str | Path,
    proposal: RouteProposal,
    synthesized_nodes: list[SynthesizedNode],
    *,
    route_id: str | None = None,
    node_catalog: dict | None = None,
) -> str:
    """Atomically append a researched route + its tool entries to the TSR registry file.
    Validates the new route with the same registry_validator used for hand-curated routes
    before committing; on any failure the registry file is left untouched and
    RegistryWriteError is raised (caller falls back to planning_required).

    `node_catalog` defaults to the real combined_node_catalog() (default + repo autogen
    sidecar) — pass it explicitly when synthesize() was called with a non-default
    catalog_path (e.g. in tests), so validation checks the same catalog the nodes were
    actually written into."""
    registry_path = Path(registry_path)
    node_catalog = node_catalog if node_catalog is not None else combined_node_catalog()
    route_id = route_id or f"{proposal.domain_slug}_autogen_ref"

    data = json.loads(registry_path.read_text(encoding="utf-8"))
    data.setdefault("tools", [])
    data.setdefault("routes", {})
    data.setdefault("domain_routes", {})
    data.setdefault("supported_domains", [])

    existing_tool_ids = {tool["id"] for tool in data["tools"]}
    route_stages = []
    for stage, node in zip(proposal.stages, synthesized_nodes):
        if stage.tool_id not in existing_tool_ids:
            entry, operation_id = _tool_entry_dict(stage, node.class_name)
            data["tools"].append(entry)
            existing_tool_ids.add(stage.tool_id)
        else:
            operation_id = f"{stage.tool_id}_operation"
        route_stages.append(
            {
                "stage_id": stage.stage_id,
                "stage_label": stage.stage_label,
                "tool_id": stage.tool_id,
                "operation_id": operation_id,
                **({"optional": True} if stage.optional else {}),
            }
        )

    data["routes"][route_id] = route_stages
    data["domain_routes"][proposal.domain_slug] = route_id
    if proposal.domain_slug not in data["supported_domains"]:
        data["supported_domains"].append(proposal.domain_slug)

    fd, tmp_name = tempfile.mkstemp(dir=str(registry_path.parent), prefix=f".{registry_path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
        try:
            registry = load_registry(tmp_name)
        except ValueError as exc:
            raise RegistryWriteError(f"Researched proposal produced an invalid TSR entry: {exc}") from exc
        try:
            validate_official_route(registry, route_id, node_catalog)
        except RegistryValidationError as exc:
            raise RegistryWriteError(f"Researched proposal failed route validation: {exc}") from exc
        os.replace(tmp_name, registry_path)
    except BaseException:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)
        raise
    return route_id
