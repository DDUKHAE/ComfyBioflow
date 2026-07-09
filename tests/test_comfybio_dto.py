from bioflow_harness.server.dto import (
    CandidateDTO,
    CompileRequest,
    CompileResponse,
    GenerateRequest,
    StepDTO,
)


def test_compile_request_from_dict_defaults():
    req = CompileRequest.from_dict({"request_text": "bulk rna-seq"})
    assert req.request_text == "bulk rna-seq"
    assert req.provider == "codex"
    assert req.resources == []


def test_compile_request_parses_resources():
    req = CompileRequest.from_dict(
        {"request_text": "x", "resources": [{"label": "input_path", "type": "path", "path": "/data/fastq"}]}
    )
    assert req.resources[0].label == "input_path"
    assert req.resources[0].path == "/data/fastq"


def test_generate_request_parses_steps():
    req = GenerateRequest.from_dict({"request_text": "x", "steps": ["fastp", "salmon"]})
    assert req.steps == ["fastp", "salmon"]


def test_compile_response_to_dict_is_nested_plain_data():
    resp = CompileResponse(
        status="ok",
        domain="bulk_rna_seq",
        route_id="bulk_rna_seq_salmon_ref",
        steps=[
            StepDTO(
                stage_id="read_qc",
                stage_label="FASTQ QC",
                tool_id="fastp_qc",
                tool_label="fastp",
                input_types=["fastq"],
                output_types=["fastp_qc_json"],
                tier="REF",
                rationale="default",
                candidates=[CandidateDTO(tool_id="fastp_qc", label="fastp", tier="REF", note="qc")],
            )
        ],
        message=None,
        confidence_notes=[],
    )
    data = resp.to_dict()
    assert data["status"] == "ok"
    assert data["steps"][0]["tool_label"] == "fastp"
    assert data["steps"][0]["candidates"][0]["tier"] == "REF"
