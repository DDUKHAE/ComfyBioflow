import shutil

import pytest

import bioflow_harness.autogen.self_extend as self_extend_module
import bioflow_harness.server.handlers as handlers_module
from bioflow_harness.autogen.route_proposal import RouteProposal, route_proposal_from_payload
from bioflow_harness.autogen.self_extend import SelfExtensionError, ensure_domain_supported
from bioflow_harness.llm.brief_extractor import ExtractionMeta
from bioflow_harness.models.prompt_contract import AnalysisBrief
from bioflow_harness.planner.tool_selector import load_registry
from bioflow_harness.server.dto import GenerateRequest

REAL_REGISTRY = "harness/registry/tool_selection_registry.yaml"


def _sample_payload(domain_slug):
    return {
        "domain_slug": domain_slug,
        "domain_label": "ChIP-seq E2E Test",
        "conda_env_name": domain_slug,
        "stages": [
            {
                "stage_id": "read_qc",
                "stage_label": "QC",
                "tool_id": f"{domain_slug}_fastp_qc",
                "tool_label": "fastp",
                "summary": "Quality control.",
                "language": "C++",
                "executable": "fastp",
                "conda_packages": ["fastp"],
                "input_types": ["fastq_pair"],
                "output_types": ["qc_dir"],
                "tier": "REF",
                "tier_rationale": "Default QC tool.",
                "evidence_tier": "pending_citation_review",
                "evidence_citation": "",
                "static_args": [],
                "optional": False,
                "produces_image": False,
            },
            {
                "stage_id": "viz",
                "stage_label": "Visualization",
                "tool_id": f"{domain_slug}_viz",
                "tool_label": "Peak Viz",
                "summary": "Plots peaks.",
                "language": "Python",
                "executable": "peak_viz",
                "conda_packages": ["matplotlib"],
                "input_types": ["qc_dir"],
                "output_types": ["plot_dir"],
                "tier": "REF",
                "tier_rationale": "Default plotting tool.",
                "evidence_tier": "pending_citation_review",
                "evidence_citation": "",
                "static_args": [],
                "optional": False,
                "produces_image": True,
            },
        ],
    }


class _FakeResearchExtractor:
    def __init__(self, proposal: RouteProposal | None = None, error: Exception | None = None):
        self._proposal = proposal
        self._error = error

    def research(self, brief: AnalysisBrief) -> RouteProposal:
        if self._error is not None:
            raise self._error
        return self._proposal


def _brief(domain: str) -> AnalysisBrief:
    return AnalysisBrief(
        analysis_type="peak_calling",
        domain=domain,
        input_assets=["fastq"],
        organism="human",
        expected_outputs=["peaks"],
    )


def _copy_registry(tmp_path):
    dest = tmp_path / "tool_selection_registry.yaml"
    shutil.copy(REAL_REGISTRY, dest)
    return dest


def _use_isolated_nodes_dir(monkeypatch, tmp_path):
    import bioflow_harness.autogen.node_synthesizer as node_synthesizer
    import bioflow_harness.comfy.node_catalog as node_catalog_module

    nodes_dir = tmp_path / "nodes" / "autogen"
    catalog_path = tmp_path / "autogen_node_catalog.json"
    monkeypatch.setattr(node_synthesizer, "NODES_AUTOGEN_DIR", nodes_dir)
    monkeypatch.setattr(node_synthesizer, "AUTOGEN_NODE_CATALOG_PATH", catalog_path)
    # handlers.py calls combined_node_catalog() with no args, so its default must also
    # resolve to the same isolated catalog file used by synthesize() during this test.
    monkeypatch.setattr(node_catalog_module, "AUTOGEN_NODE_CATALOG_PATH", catalog_path)
    return nodes_dir, catalog_path


def test_ensure_domain_supported_extends_registry_for_new_domain(tmp_path, monkeypatch):
    _use_isolated_nodes_dir(monkeypatch, tmp_path)
    registry_path = _copy_registry(tmp_path)
    registry = load_registry(registry_path)
    proposal = route_proposal_from_payload(_sample_payload("chip_seq_ensure_test"))
    extractor = _FakeResearchExtractor(proposal=proposal)

    extended = ensure_domain_supported(registry, _brief("chip_seq_ensure_test"), registry_path, research_extractor=extractor)

    assert "chip_seq_ensure_test" in extended.domain_routes
    route_id = extended.domain_routes["chip_seq_ensure_test"]
    assert extended.official_route(route_id)[0].tool_id == "chip_seq_ensure_test_fastp_qc"


def test_ensure_domain_supported_is_noop_for_known_domain(tmp_path, monkeypatch):
    _use_isolated_nodes_dir(monkeypatch, tmp_path)
    registry_path = _copy_registry(tmp_path)
    registry = load_registry(registry_path)
    extractor = _FakeResearchExtractor(proposal=None)  # would raise if actually called

    result = ensure_domain_supported(registry, _brief("bulk_rna_seq"), registry_path, research_extractor=extractor)

    assert result is registry


def test_ensure_domain_supported_raises_self_extension_error_on_research_failure(tmp_path, monkeypatch):
    _use_isolated_nodes_dir(monkeypatch, tmp_path)
    registry_path = _copy_registry(tmp_path)
    registry = load_registry(registry_path)
    extractor = _FakeResearchExtractor(error=RuntimeError("no network in test"))

    with pytest.raises(SelfExtensionError):
        ensure_domain_supported(registry, _brief("chip_seq_fail_test"), registry_path, research_extractor=extractor)


def test_generate_workflow_end_to_end_self_extends_and_builds_workflow(tmp_path, monkeypatch):
    _use_isolated_nodes_dir(monkeypatch, tmp_path)
    registry_path = _copy_registry(tmp_path)
    proposal = route_proposal_from_payload(_sample_payload("chip_seq_handlers_test"))

    monkeypatch.setattr(
        handlers_module,
        "extract_brief",
        lambda request_text, provider, model: (_brief("chip_seq_handlers_test"), ExtractionMeta(source="fake", model="fake", note="")),
    )
    monkeypatch.setattr(
        self_extend_module,
        "ClaudeToolResearchExtractor",
        lambda *args, **kwargs: _FakeResearchExtractor(proposal=proposal),
    )

    response = handlers_module.generate_workflow(
        {"request_text": "chip-seq peak calling please"}, registry_path=registry_path
    )

    assert response["status"] == "ok"
    assert response["domain"] == "chip_seq_handlers_test"
    assert "restart ComfyUI" in (response["message"] or "")
    workflow = response["workflow"]
    node_types = [node["type"] for node in workflow["nodes"]]
    assert "ChipSeqHandlersTestFastpQcNode" in node_types
    assert "ChipSeqHandlersTestVizNode" in node_types


def test_generate_workflow_falls_back_to_planning_required_when_research_fails(tmp_path, monkeypatch):
    _use_isolated_nodes_dir(monkeypatch, tmp_path)
    registry_path = _copy_registry(tmp_path)

    monkeypatch.setattr(
        handlers_module,
        "extract_brief",
        lambda request_text, provider, model: (_brief("chip_seq_giveup_test"), ExtractionMeta(source="fake", model="fake", note="")),
    )
    monkeypatch.setattr(
        self_extend_module,
        "ClaudeToolResearchExtractor",
        lambda *args, **kwargs: _FakeResearchExtractor(error=RuntimeError("claude CLI not installed")),
    )

    response = handlers_module.generate_workflow(
        {"request_text": "something ComfyBIO cannot research"}, registry_path=registry_path
    )

    assert response["status"] == "planning_required"
    assert response["workflow"] is None
