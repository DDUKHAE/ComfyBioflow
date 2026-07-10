import json
from dataclasses import dataclass

import pytest

from bioflow_harness.llm.claude_extractor import (
    BriefExtractionError,
    ClaudeBriefExtractor,
    DEFAULT_MODEL,
)
from bioflow_harness.models.prompt_contract import AnalysisBrief


@dataclass
class _Block:
    text: str
    type: str = "text"


@dataclass
class _Response:
    content: list
    stop_reason: str = "end_turn"


class _FakeClient:
    """Stands in for anthropic.Anthropic(); client.messages.create(...)."""

    def __init__(self, response=None, exc=None):
        self._response = response
        self._exc = exc
        self.calls = []

    @property
    def messages(self):
        return self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self._exc is not None:
            raise self._exc
        return self._response


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


def _ok_client(payload=None):
    body = json.dumps(payload or _VALID_PAYLOAD)
    return _FakeClient(response=_Response(content=[_Block(text=body)]))


def test_extract_parses_structured_response_into_brief():
    extractor = ClaudeBriefExtractor("claude-opus-4-8", client=_ok_client())
    brief = extractor.extract("Analyze this bulk RNA-seq FASTQ folder, human, treated vs control")
    assert isinstance(brief, AnalysisBrief)
    assert brief.domain == "bulk_rna_seq"
    assert brief.organism == "Homo sapiens"
    assert brief.input_assets == ["fastq", "sample_metadata"]
    assert brief.preferred_tools == ["salmon", "deseq2"]
    assert brief.data_characteristics == {"layout": "paired"}
    assert brief.submission_source == "text_prompt"


def test_empty_organism_maps_to_none():
    payload = dict(_VALID_PAYLOAD, organism="")
    extractor = ClaudeBriefExtractor("claude-opus-4-8", client=_ok_client(payload))
    brief = extractor.extract("some request")
    assert brief.organism is None


def test_default_model_used_when_blank():
    client = _ok_client()
    ClaudeBriefExtractor("", client=client).extract("x")
    assert client.calls[0]["model"] == DEFAULT_MODEL


def test_refusal_raises_extraction_error():
    client = _FakeClient(response=_Response(content=[], stop_reason="refusal"))
    with pytest.raises(BriefExtractionError):
        ClaudeBriefExtractor("claude-opus-4-8", client=client).extract("x")


def test_malformed_json_raises_extraction_error():
    client = _FakeClient(response=_Response(content=[_Block(text="not json{")]))
    with pytest.raises(BriefExtractionError):
        ClaudeBriefExtractor("claude-opus-4-8", client=client).extract("x")


def test_schema_invalid_payload_raises_extraction_error():
    client = _FakeClient(response=_Response(content=[_Block(text=json.dumps({"domain": "bulk_rna_seq"}))]))
    with pytest.raises(BriefExtractionError):
        ClaudeBriefExtractor("claude-opus-4-8", client=client).extract("x")
