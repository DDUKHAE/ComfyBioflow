from bioflow_harness.server.handlers import generate_workflow


def _types(request_text: str) -> list[str]:
    workflow = generate_workflow({"request_text": request_text})["workflow"]
    return [node["type"] for node in workflow["nodes"]]


def test_bulk_graph_starts_at_metadata_validator_no_orchestration():
    types = _types("bulk RNA-seq human treated vs control with DESeq2 plots and report")
    assert types[0] == "SampleMetadataValidatorNode"
    assert types[-1] == "PreviewImage"
    assert types[-2] == "ComfyBIOReportNode"
    assert "WorkflowRequestLoader" not in types
    assert "WorkflowJSONOutput" not in types


def test_scrna_graph_starts_at_tenx_count_no_orchestration():
    types = _types("single-cell RNA-seq with scanpy, clustering and umap and marker genes")
    assert types[0] == "TenxCountNode"
    assert "WorkflowRequestLoader" not in types
    assert "WorkflowJSONOutput" not in types


def test_metadata_validator_has_no_upstream_input():
    import nodes

    required = nodes.NODE_CLASS_MAPPINGS["SampleMetadataValidatorNode"].INPUT_TYPES()["required"]
    assert "workflow_request" not in required
    assert "fastq_dir" in required
