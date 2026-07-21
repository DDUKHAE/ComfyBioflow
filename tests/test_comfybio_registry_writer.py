import json
import shutil

import pytest

from bioflow_harness.autogen.node_synthesizer import synthesize
from bioflow_harness.autogen.registry_writer import RegistryWriteError, append_route_and_tools
from bioflow_harness.autogen.route_proposal import route_proposal_from_payload
from bioflow_harness.comfy.node_catalog import combined_node_catalog
from bioflow_harness.planner.tool_selector import load_registry

REAL_REGISTRY = "harness/registry/tool_selection_registry.yaml"


def _sample_payload(domain_slug="chip_seq_writer_test", *, valid=True):
    return {
        "domain_slug": domain_slug,
        "domain_label": "ChIP-seq Writer Test",
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
                "input_types": ["fastq_pair"] if valid else [],
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


def _copy_registry(tmp_path):
    dest = tmp_path / "tool_selection_registry.yaml"
    shutil.copy(REAL_REGISTRY, dest)
    return dest


def test_append_route_and_tools_commits_valid_proposal(tmp_path):
    registry_path = _copy_registry(tmp_path)
    nodes_dir = tmp_path / "nodes" / "autogen"
    catalog_path = tmp_path / "autogen_node_catalog.json"

    proposal = route_proposal_from_payload(_sample_payload())
    synthesized = synthesize(proposal, nodes_dir=nodes_dir, catalog_path=catalog_path)

    route_id = append_route_and_tools(
        registry_path, proposal, synthesized, node_catalog=combined_node_catalog(autogen_path=catalog_path)
    )

    assert route_id == "chip_seq_writer_test_autogen_ref"
    updated = load_registry(registry_path)
    assert updated.domain_routes["chip_seq_writer_test"] == route_id
    assert "chip_seq_writer_test" in updated.supported_domains
    assert updated.tool_by_id("chip_seq_writer_test_fastp_qc").tier == "REF"
    assert updated.official_route(route_id)[0].stage_id == "read_qc"


def test_append_route_and_tools_rolls_back_invalid_proposal(tmp_path):
    registry_path = _copy_registry(tmp_path)
    original_text = registry_path.read_text()
    nodes_dir = tmp_path / "nodes" / "autogen"
    catalog_path = tmp_path / "autogen_node_catalog.json"

    proposal = route_proposal_from_payload(_sample_payload("chip_seq_invalid_test", valid=False))
    synthesized = synthesize(proposal, nodes_dir=nodes_dir, catalog_path=catalog_path)

    with pytest.raises(RegistryWriteError):
        append_route_and_tools(
            registry_path, proposal, synthesized, node_catalog=combined_node_catalog(autogen_path=catalog_path)
        )

    # Registry file must be byte-for-byte unchanged after a rejected proposal.
    assert registry_path.read_text() == original_text
    assert not any(registry_path.parent.glob(".*tmp*"))


def test_appended_tool_entry_is_labeled_as_unreviewed(tmp_path):
    registry_path = _copy_registry(tmp_path)
    nodes_dir = tmp_path / "nodes" / "autogen"
    catalog_path = tmp_path / "autogen_node_catalog.json"

    proposal = route_proposal_from_payload(_sample_payload("chip_seq_label_test"))
    synthesized = synthesize(proposal, nodes_dir=nodes_dir, catalog_path=catalog_path)
    append_route_and_tools(
        registry_path, proposal, synthesized, node_catalog=combined_node_catalog(autogen_path=catalog_path)
    )

    data = json.loads(registry_path.read_text())
    appended = next(t for t in data["tools"] if t["id"] == "chip_seq_label_test_fastp_qc")
    assert appended["tier_rationale"].startswith("[LLM-researched, unreviewed]")
