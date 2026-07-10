import json
from dataclasses import dataclass, field

import pytest

from bioflow_harness.llm.claude_extractor import (
    BriefExtractionError,
    ClaudeBriefExtractor,
    DEFAULT_MODEL,
)
from bioflow_harness.models.prompt_contract import AnalysisBrief
from bioflow_harness.llm.brief_extractor import ExtractionMeta, extract_brief


@dataclass
class _Completed:
    """Stands in for subprocess.CompletedProcess."""

    returncode: int = 0
    stdout: str = ""
    stderr: str = ""


class _FakeRunner:
    """Callable stand-in for the injected subprocess runner: runner(argv) -> _Completed."""

    def __init__(self, completed=None, exc=None):
        self._completed = completed
        self._exc = exc
        self.calls = []  # list of argv lists

    def __call__(self, argv):
        self.calls.append(argv)
        if self._exc is not None:
            raise self._exc
        return self._completed


_VALID_PAYLOAD = {
    "analysis_type": "differential_expression",
    "domain": "bulk_rna_seq",
    "input_assets": ["fastq", "sample_metadata"],
    "organism": "Homo sapiens",
    "expected_outputs": ["salmon_quantification", "deseq2_results"],
    "constraints": [],
    "preferred_tools": ["salmon", "deseq2"],
    "data_characteristics": [{"key": "layout", "value": "paired"}],
}


def _envelope(result_text: str, *, is_error=False, subtype="success"):
    """Build a `claude --output-format json` envelope whose `result` is result_text."""
    return json.dumps(
        {
            "type": "result",
            "subtype": subtype,
            "is_error": is_error,
            "result": result_text,
        }
    )


def _ok_runner(payload=None, *, wrap_fence=False):
    body = json.dumps(payload or _VALID_PAYLOAD)
    if wrap_fence:
        body = f"```json\n{body}\n```"
    return _FakeRunner(completed=_Completed(returncode=0, stdout=_envelope(body)))


def test_extract_parses_envelope_result_into_brief():
    extractor = ClaudeBriefExtractor("claude-opus-4-8", runner=_ok_runner())
    brief = extractor.extract("Analyze this bulk RNA-seq FASTQ folder, human, treated vs control")
    assert isinstance(brief, AnalysisBrief)
    assert brief.domain == "bulk_rna_seq"
    assert brief.organism == "Homo sapiens"
    assert brief.input_assets == ["fastq", "sample_metadata"]
    assert brief.preferred_tools == ["salmon", "deseq2"]
    assert brief.data_characteristics == {"layout": "paired"}
    assert brief.submission_source == "text_prompt"


def test_extract_parses_fenced_result():
    extractor = ClaudeBriefExtractor("claude-opus-4-8", runner=_ok_runner(wrap_fence=True))
    brief = extractor.extract("x")
    assert brief.domain == "bulk_rna_seq"


def test_empty_organism_maps_to_none():
    payload = dict(_VALID_PAYLOAD, organism="")
    extractor = ClaudeBriefExtractor("claude-opus-4-8", runner=_ok_runner(payload))
    brief = extractor.extract("some request")
    assert brief.organism is None


def test_argv_carries_model_and_flags():
    runner = _ok_runner()
    ClaudeBriefExtractor("", runner=runner).extract("hello")
    argv = runner.calls[0]
    assert argv[0] == "claude"
    assert "-p" in argv
    assert "hello" in argv
    # default model substituted when blank
    mi = argv.index("--model")
    assert argv[mi + 1] == DEFAULT_MODEL
    assert "--output-format" in argv and argv[argv.index("--output-format") + 1] == "json"
    assert "--system-prompt" in argv


def test_nonzero_exit_raises_extraction_error():
    runner = _FakeRunner(completed=_Completed(returncode=1, stdout="", stderr="not logged in"))
    with pytest.raises(BriefExtractionError):
        ClaudeBriefExtractor("claude-opus-4-8", runner=runner).extract("x")


def test_error_envelope_raises_extraction_error():
    runner = _FakeRunner(
        completed=_Completed(returncode=0, stdout=_envelope("{}", is_error=True))
    )
    with pytest.raises(BriefExtractionError):
        ClaudeBriefExtractor("claude-opus-4-8", runner=runner).extract("x")


def test_malformed_result_raises_extraction_error():
    runner = _FakeRunner(
        completed=_Completed(returncode=0, stdout=_envelope("not json at all"))
    )
    with pytest.raises(BriefExtractionError):
        ClaudeBriefExtractor("claude-opus-4-8", runner=runner).extract("x")


def test_schema_invalid_payload_raises_extraction_error():
    runner = _FakeRunner(
        completed=_Completed(returncode=0, stdout=_envelope(json.dumps({"domain": "bulk_rna_seq"})))
    )
    with pytest.raises(BriefExtractionError):
        ClaudeBriefExtractor("claude-opus-4-8", runner=runner).extract("x")


def test_missing_binary_raises_and_is_catchable():
    runner = _FakeRunner(exc=FileNotFoundError("claude"))
    with pytest.raises(FileNotFoundError):
        ClaudeBriefExtractor("claude-opus-4-8", runner=runner).extract("x")


def test_extract_brief_claude_success_annotates_provenance():
    brief, meta = extract_brief("bulk RNA-seq, human", provider="claude", runner=_ok_runner())
    assert meta.source == "claude"
    assert brief.domain == "bulk_rna_seq"
    assert any("claude" in note for note in brief.confidence_notes)


def test_extract_brief_falls_back_when_claude_raises():
    failing = _FakeRunner(exc=FileNotFoundError("claude"))
    brief, meta = extract_brief(
        "Analyze this bulk RNA-seq data with DESeq2",
        provider="claude",
        runner=failing,
    )
    assert meta.source == "deterministic"
    assert brief.domain == "bulk_rna_seq"  # parse_prompt still classifies it
    assert any("deterministic" in note for note in brief.confidence_notes)


def test_extract_brief_falls_back_on_nonzero_exit():
    failing = _FakeRunner(completed=_Completed(returncode=1, stderr="not logged in"))
    brief, meta = extract_brief(
        "Analyze this bulk RNA-seq data with DESeq2",
        provider="claude",
        runner=failing,
    )
    assert meta.source == "deterministic"
    assert brief.domain == "bulk_rna_seq"


def test_extract_brief_non_claude_provider_uses_deterministic():
    brief, meta = extract_brief("Analyze bulk RNA-seq with DESeq2", provider="codex")
    assert meta.source == "deterministic"
    assert isinstance(meta, ExtractionMeta)
    assert any("not yet wired" in note for note in brief.confidence_notes)


from bioflow_harness.server.handlers import compile_spec, generate_workflow


def test_compile_spec_default_provider_still_produces_bulk_steps():
    payload = {
        "request_text": "Analyze this FASTQ folder as bulk RNA-seq, human, treated vs control with DESeq2",
        "provider": "codex",
        "model": "",
        "resources": [],
    }
    result = compile_spec(payload)
    assert result["status"] == "ok"
    assert result["domain"] == "bulk_rna_seq"
    assert len(result["steps"]) > 0


def test_generate_workflow_default_provider_returns_workflow():
    payload = {
        "request_text": "Analyze this FASTQ folder as bulk RNA-seq, human, treated vs control with DESeq2",
        "provider": "codex",
        "model": "",
        "resources": [],
        "steps": [],
    }
    result = generate_workflow(payload)
    assert result["status"] == "ok"
    assert result["workflow"] is not None
