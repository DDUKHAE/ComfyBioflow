import pytest

from bioflow_harness.autogen.node_synthesizer import NodeSynthesisError, synthesize
from bioflow_harness.autogen.route_proposal import route_proposal_from_payload


def _sample_payload(domain_slug="chip_seq_synth_test"):
    return {
        "domain_slug": domain_slug,
        "domain_label": "ChIP-seq Synth Test",
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
                "static_args": ["-w", "2"],
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


def test_synthesize_writes_valid_argv_and_node_modules(tmp_path):
    proposal = route_proposal_from_payload(_sample_payload())
    nodes_dir = tmp_path / "nodes" / "autogen"
    catalog_path = tmp_path / "autogen_node_catalog.json"

    result = synthesize(proposal, nodes_dir=nodes_dir, catalog_path=catalog_path)

    assert [node.class_name for node in result] == ["ChipSeqSynthTestFastpQcNode", "ChipSeqSynthTestVizNode"]
    nodes_module = nodes_dir / "chip_seq_synth_test_nodes.py"
    stage_commands_module = nodes_dir / "chip_seq_synth_test_stage_commands.py"
    assert nodes_module.exists()
    assert stage_commands_module.exists()
    assert "AUTOGEN_NODE_CLASSES" in nodes_module.read_text()


def test_synthesize_appends_to_existing_catalog_without_duplicating(tmp_path):
    nodes_dir = tmp_path / "nodes" / "autogen"
    catalog_path = tmp_path / "autogen_node_catalog.json"

    proposal = route_proposal_from_payload(_sample_payload("chip_seq_dup_test"))
    synthesize(proposal, nodes_dir=nodes_dir, catalog_path=catalog_path)
    first_size = len(__import__("json").loads(catalog_path.read_text()))

    # Re-synthesizing the same proposal must not duplicate catalog entries.
    synthesize(proposal, nodes_dir=nodes_dir, catalog_path=catalog_path)
    second_size = len(__import__("json").loads(catalog_path.read_text()))
    assert first_size == second_size == 2


def test_synthesize_rejects_proposal_without_visualization_stage():
    payload = _sample_payload("chip_seq_no_viz")
    payload["stages"][1]["produces_image"] = False
    with pytest.raises(ValueError):
        route_proposal_from_payload(payload)


def test_smoke_test_failure_leaves_no_files_behind(tmp_path, monkeypatch):
    import bioflow_harness.autogen.node_synthesizer as node_synthesizer

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated broken generated code")

    monkeypatch.setattr(node_synthesizer, "_smoke_test_module", _boom)

    proposal = route_proposal_from_payload(_sample_payload("chip_seq_broken"))
    nodes_dir = tmp_path / "nodes" / "autogen"
    catalog_path = tmp_path / "autogen_node_catalog.json"

    with pytest.raises(NodeSynthesisError):
        synthesize(proposal, nodes_dir=nodes_dir, catalog_path=catalog_path)

    assert not (nodes_dir / "chip_seq_broken_nodes.py").exists()
    assert not catalog_path.exists()
