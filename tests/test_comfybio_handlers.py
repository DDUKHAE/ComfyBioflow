from bioflow_harness.server.handlers import compile_spec
from bioflow_harness.comfy.workflow_schema import validate_workflow_export
from bioflow_harness.server.handlers import generate_workflow

# "mistral" has no CLI integration, so every call below exercises the deterministic
# parser instead of attempting a real codex/claude/gemini subprocess call.
_PROVIDER = "mistral"


def test_compile_spec_bulk_rna_seq_returns_salmon_route():
    result = compile_spec({"request_text": "Analyze this FASTQ folder as bulk RNA-seq, human, treated vs control with DESeq2.", "provider": _PROVIDER})
    assert result["status"] == "ok"
    assert result["domain"] == "bulk_rna_seq"
    assert result["route_id"] == "bulk_rna_seq_salmon_ref"
    tool_ids = [step["tool_id"] for step in result["steps"]]
    assert "fastp_qc" in tool_ids
    assert "salmon_quant" in tool_ids
    read_qc = next(step for step in result["steps"] if step["stage_id"] == "read_qc")
    assert any(c["tool_id"] == "fastp_qc" for c in read_qc["candidates"])


def test_compile_spec_scrna_returns_scanpy_route():
    result = compile_spec({"request_text": "single-cell RNA-seq with scanpy, clustering and umap and marker genes", "provider": _PROVIDER})
    assert result["status"] == "ok"
    assert result["domain"] == "scrna_seq"
    assert result["route_id"] == "scrna_seq_scanpy_ref"


def test_compile_spec_unsupported_domain_is_planning_required():
    result = compile_spec({"request_text": "please assemble a bacterial genome", "provider": _PROVIDER})
    assert result["status"] == "planning_required"
    assert result["route_id"] is None
    assert "planning is required" in result["message"].lower()


def test_generate_workflow_returns_valid_export():
    result = generate_workflow({"request_text": "bulk RNA-seq human treated vs control with DESeq2 plots and report", "provider": _PROVIDER})
    assert result["status"] == "ok"
    assert result["route_id"] == "bulk_rna_seq_salmon_ref"
    workflow = result["workflow"]
    assert workflow["metadata"]["format"] == "comfyui_workflow_export"
    validate_workflow_export(workflow)  # raises if malformed


def test_generate_workflow_unsupported_is_planning_required():
    result = generate_workflow({"request_text": "assemble a bacterial genome", "provider": _PROVIDER})
    assert result["status"] == "planning_required"
    assert result["workflow"] is None


def test_generate_workflow_matching_steps_has_no_message():
    request_text = "bulk RNA-seq human treated vs control with DESeq2 plots and report"
    compiled = compile_spec({"request_text": request_text, "provider": _PROVIDER})
    deterministic_steps = [step["tool_label"] for step in compiled["steps"]]
    result = generate_workflow(
        {
            "request_text": request_text,
            "provider": _PROVIDER,
            "steps": deterministic_steps,
            "resources": [
                {"label": "input_path", "path": "/data/fastq"},
                {"label": "output_path", "path": "/data/out"},
                {"label": "metadata_csv", "type": "metadata", "path": "/data/meta.csv"},
                {"label": "tx", "type": "index", "path": "/data/tx.fasta"},
            ],
        }
    )
    assert result["status"] == "ok"
    assert result["message"] is None


def test_generate_workflow_reordered_steps_surfaces_warning_not_error():
    result = generate_workflow(
        {
            "request_text": "bulk RNA-seq human treated vs control with DESeq2 plots and report",
            "provider": _PROVIDER,
            "steps": ["some_reordered_tool", "another_replacement_tool"],
        }
    )
    assert result["status"] == "ok"
    assert result["workflow"] is not None
    assert result["route_id"] == "bulk_rna_seq_salmon_ref"
    assert result["message"]
    assert "not applied" in result["message"].lower()


def test_generate_workflow_injects_resource_paths():
    payload = {
        "request_text": "bulk RNA-seq human treated vs control with DESeq2 plots and report",
        "provider": _PROVIDER,
        "resources": [
            {"label": "input_path", "path": "/data/fastq"},
            {"label": "output_path", "path": "/data/out"},
            {"label": "metadata_csv", "type": "metadata", "path": "/data/meta.csv"},
            {"label": "tx", "type": "index", "path": "/data/tx.fasta"},
        ],
    }
    result = generate_workflow(payload)
    assert result["status"] == "ok"
    salmon = next(n for n in result["workflow"]["nodes"] if n["type"] == "SalmonQuantNode")
    assert salmon["widgets_values"][1] == "/data/fastq"
    assert result["message"] is None


def test_generate_workflow_warns_on_missing_resources():
    payload = {"request_text": "bulk RNA-seq treated vs control with DESeq2 plots and report", "provider": _PROVIDER}
    result = generate_workflow(payload)
    assert result["status"] == "ok"
    assert "transcriptome_fasta" in (result["message"] or "")
