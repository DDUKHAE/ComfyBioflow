from __future__ import annotations

import json

from bioflow_harness.models.prompt_contract import AnalysisBrief

DEFAULT_MODEL = "claude-opus-4-8"


class BriefExtractionError(RuntimeError):
    """Raised when Claude returns a refusal or an unusable payload."""


BRIEF_SCHEMA = {
    "type": "object",
    "properties": {
        "analysis_type": {"type": "string"},
        "domain": {"type": "string", "enum": ["bulk_rna_seq", "scrna_seq", "unsupported"]},
        "input_assets": {"type": "array", "items": {"type": "string"}},
        "organism": {"type": "string"},
        "expected_outputs": {"type": "array", "items": {"type": "string"}},
        "constraints": {"type": "array", "items": {"type": "string"}},
        "preferred_tools": {"type": "array", "items": {"type": "string"}},
        "data_characteristics": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "key": {"type": "string"},
                    "value": {"type": "string"},
                },
                "required": ["key", "value"],
                "additionalProperties": False,
            },
        },
    },
    "required": [
        "analysis_type",
        "domain",
        "input_assets",
        "organism",
        "expected_outputs",
        "constraints",
        "preferred_tools",
        "data_characteristics",
    ],
    "additionalProperties": False,
}


SYSTEM_PROMPT = """You extract a structured bioinformatics analysis brief from a researcher's free-text request.

Supported domains:
- "bulk_rna_seq": bulk RNA sequencing (FASTQ reads, differential expression, salmon/DESeq2, etc.)
- "scrna_seq": single-cell RNA sequencing (10x, Cell Ranger, scanpy, clustering, UMAP, marker genes)
- "unsupported": anything that is neither of the above

Fields:
- analysis_type: short slug for the intent (e.g. "differential_expression", "single_cell_analysis", "workflow_generation")
- domain: one of the three values above
- input_assets: input data kinds mentioned (e.g. "fastq", "sample_metadata")
- organism: the species/genome if stated, else an empty string
- expected_outputs: artifacts wanted (e.g. "salmon_quantification", "deseq2_results", "visualization_artifacts", "report")
- constraints: any explicit constraints stated
- preferred_tools: tools named in the request
- data_characteristics: any stated properties as key/value pairs (e.g. key "layout", value "paired")

Classify domain as "unsupported" when the request is neither bulk nor single-cell RNA-seq."""


def _brief_from_payload(data: dict) -> AnalysisBrief:
    try:
        pairs = data["data_characteristics"]
        characteristics = {str(p["key"]): str(p["value"]) for p in pairs}
        return AnalysisBrief(
            analysis_type=str(data["analysis_type"]),
            domain=str(data["domain"]),
            input_assets=[str(x) for x in data["input_assets"]],
            organism=(str(data["organism"]) or None),
            expected_outputs=[str(x) for x in data["expected_outputs"]],
            constraints=[str(x) for x in data["constraints"]],
            preferred_tools=[str(x) for x in data["preferred_tools"]],
            data_characteristics=characteristics,
        )
    except (KeyError, TypeError) as exc:
        raise BriefExtractionError(f"Schema-invalid brief payload: {exc}") from exc


class ClaudeBriefExtractor:
    """Extracts an AnalysisBrief from free text via the Claude Messages API."""

    def __init__(self, model: str, *, client=None):
        self._model = model or DEFAULT_MODEL
        self._client = client

    def _resolve_client(self):
        if self._client is not None:
            return self._client
        import anthropic  # lazy; optional dependency

        return anthropic.Anthropic()

    def extract(self, request_text: str) -> AnalysisBrief:
        client = self._resolve_client()
        response = client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            output_config={"format": {"type": "json_schema", "schema": BRIEF_SCHEMA}},
            messages=[{"role": "user", "content": request_text}],
        )
        if getattr(response, "stop_reason", None) == "refusal":
            raise BriefExtractionError("Claude refused the extraction request")
        text = next(
            (b.text for b in response.content if getattr(b, "type", None) == "text"),
            None,
        )
        if text is None:
            raise BriefExtractionError("No text block in Claude response")
        try:
            data = json.loads(text)
        except (ValueError, TypeError) as exc:
            raise BriefExtractionError(f"Malformed JSON from Claude: {exc}") from exc
        return _brief_from_payload(data)
