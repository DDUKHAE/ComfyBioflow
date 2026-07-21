from __future__ import annotations

from pathlib import Path

from bioflow_harness.autogen import node_synthesizer
from bioflow_harness.autogen.registry_writer import append_route_and_tools
from bioflow_harness.comfy.node_catalog import combined_node_catalog
from bioflow_harness.llm.research_extractor import ClaudeToolResearchExtractor
from bioflow_harness.models.prompt_contract import AnalysisBrief
from bioflow_harness.models.registry_contract import ToolRegistry
from bioflow_harness.planner.tool_selector import load_registry


class SelfExtensionError(RuntimeError):
    """Raised when self-extension cannot complete for a domain. Callers should treat this
    the same as the pre-existing planning_required fallback — nothing is left half-written."""


def ensure_domain_supported(
    registry: ToolRegistry,
    brief: AnalysisBrief,
    registry_path: str | Path,
    *,
    research_extractor=None,
) -> ToolRegistry:
    """If `brief.domain` isn't already routable, research it via the Claude web-search
    extractor, synthesize ComfyUI nodes for any tools it names, and atomically merge the
    resulting route + tool entries into the TSR registry. Returns the (possibly updated,
    freshly reloaded) registry. Every step is automatic — there is no human approval gate —
    but each step has its own structural validation, and any failure raises
    SelfExtensionError rather than partially committing anything."""
    if brief.domain in registry.domain_routes:
        return registry

    extractor = research_extractor or ClaudeToolResearchExtractor()
    try:
        proposal = extractor.research(brief)
    except Exception as exc:  # noqa: BLE001 - any research failure must fail safe, not crash the request
        raise SelfExtensionError(f"Tool research failed for domain {brief.domain!r}: {exc}") from exc

    try:
        synthesized_nodes = node_synthesizer.synthesize(proposal)
    except Exception as exc:  # noqa: BLE001 - malformed proposals must fail safe, not crash the request
        raise SelfExtensionError(f"Node synthesis failed for domain {brief.domain!r}: {exc}") from exc

    # Validate against the same catalog file synthesize() just wrote to (its module-level
    # default may be monkeypatched in tests, so read it back rather than assuming the path).
    node_catalog = combined_node_catalog(autogen_path=node_synthesizer.AUTOGEN_NODE_CATALOG_PATH)
    try:
        append_route_and_tools(registry_path, proposal, synthesized_nodes, node_catalog=node_catalog)
    except Exception as exc:  # noqa: BLE001 - registry validation failures must fail safe, not crash the request
        raise SelfExtensionError(f"Registry write failed for domain {brief.domain!r}: {exc}") from exc

    return load_registry(registry_path)
