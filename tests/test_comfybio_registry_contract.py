import pytest

from bioflow_harness.models.registry_contract import Operation, ToolEntry
from bioflow_harness.planner.tool_selector import load_registry

REGISTRY = "harness/registry/tool_selection_registry.yaml"

_OPERATION = Operation(id="op", label="Op", input_types=[], output_types=[], node_type="Node")


def _tool(**overrides):
    defaults = dict(
        id="tool",
        label="Tool",
        domain_tags=[],
        stage_tags=[],
        input_types=[],
        output_types=[],
        language="external_cli",
        python_bindings=[],
        summary="summary",
        tier="REF",
        tier_rationale="rationale",
        context_routing_rules=[],
        applicability_constraints=[],
        selection_rules=[],
        operations=[_OPERATION],
        future_comfy_node="Node",
        runnable_node_status="runnable",
    )
    defaults.update(overrides)
    return ToolEntry(**defaults)


def test_evidence_tier_defaults_to_pending_citation_review():
    tool = _tool()
    tool.validate()
    assert tool.evidence_tier == "pending_citation_review"
    assert tool.evidence_citation == ""


def test_evidence_tier_accepts_secondary_literature_with_citation():
    tool = _tool(evidence_tier="secondary_literature", evidence_citation="Some Paper (2020), https://example.com")
    tool.validate()  # must not raise


def test_invalid_evidence_tier_raises():
    tool = _tool(evidence_tier="vibes_based")
    with pytest.raises(ValueError):
        tool.validate()


def test_real_registry_tags_every_tool_with_a_supported_evidence_tier():
    from bioflow_harness.models.registry_contract import SUPPORTED_EVIDENCE_TIERS

    registry = load_registry(REGISTRY)
    for tool in registry.tools:
        assert tool.evidence_tier in SUPPORTED_EVIDENCE_TIERS, tool.id


def test_real_registry_secondary_literature_tools_have_a_citation():
    registry = load_registry(REGISTRY)
    for tool in registry.tools:
        if tool.evidence_tier == "secondary_literature":
            assert tool.evidence_citation.strip(), f"{tool.id} is tagged secondary_literature but has no citation"


def test_not_applicable_internal_node_is_a_permanent_classification_not_a_todo():
    # not_applicable_internal_node means "no citation is owed" (a ComfyBIO-authored glue node
    # with no competing external tool) — distinct from pending_citation_review, which means
    # "a real REF-vs-ALT choice that still needs one." Neither should carry a citation string.
    tool = _tool(evidence_tier="not_applicable_internal_node")
    tool.validate()  # must not raise
    assert tool.evidence_citation == ""


def test_real_registry_has_more_cited_tools_than_pending_after_the_citation_pass():
    # Regression guard for the citation-completion pass: most of the registry should now be
    # resolved (secondary_literature or not_applicable_internal_node), not stuck pending.
    registry = load_registry(REGISTRY)
    tiers = [tool.evidence_tier for tool in registry.tools]
    resolved = sum(1 for t in tiers if t != "pending_citation_review")
    pending = sum(1 for t in tiers if t == "pending_citation_review")
    assert resolved > pending
