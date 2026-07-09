from bioflow_harness.server.handlers import compile_spec


def test_compile_spec_bulk_rna_seq_returns_salmon_route():
    result = compile_spec({"request_text": "Analyze this FASTQ folder as bulk RNA-seq, human, treated vs control with DESeq2."})
    assert result["status"] == "ok"
    assert result["domain"] == "bulk_rna_seq"
    assert result["route_id"] == "bulk_rna_seq_salmon_ref"
    tool_ids = [step["tool_id"] for step in result["steps"]]
    assert "fastp_qc" in tool_ids
    assert "salmon_quant" in tool_ids
    read_qc = next(step for step in result["steps"] if step["stage_id"] == "read_qc")
    assert any(c["tool_id"] == "fastp_qc" for c in read_qc["candidates"])


def test_compile_spec_scrna_returns_scanpy_route():
    result = compile_spec({"request_text": "single-cell RNA-seq with scanpy, clustering and umap and marker genes"})
    assert result["status"] == "ok"
    assert result["domain"] == "scrna_seq"
    assert result["route_id"] == "scrna_seq_scanpy_ref"


def test_compile_spec_unsupported_domain_is_planning_required():
    result = compile_spec({"request_text": "please assemble a bacterial genome"})
    assert result["status"] == "planning_required"
    assert result["route_id"] is None
    assert "planning is required" in result["message"].lower()
