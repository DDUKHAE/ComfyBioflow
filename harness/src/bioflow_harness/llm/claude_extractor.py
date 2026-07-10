from __future__ import annotations

import json
import subprocess

from bioflow_harness.models.prompt_contract import AnalysisBrief

DEFAULT_MODEL = "claude-opus-4-8"
_TIMEOUT_SECONDS = 120


class BriefExtractionError(RuntimeError):
    """Raised when the Claude CLI errors or returns an unusable payload."""


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
- data_characteristics: any stated properties, each as an object {"key": ..., "value": ...} (e.g. {"key": "layout", "value": "paired"})

Classify domain as "unsupported" when the request is neither bulk nor single-cell RNA-seq.

Respond with ONLY a single JSON object with exactly these keys: analysis_type, domain, input_assets, organism, expected_outputs, constraints, preferred_tools, data_characteristics. Every key must be present (use "" or [] when unknown). Do not use any tools. Do not include prose, explanation, or markdown code fences — output the raw JSON object only."""


def _default_runner(argv: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(argv, capture_output=True, text=True, timeout=_TIMEOUT_SECONDS)


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


def _extract_json_object(text: str) -> dict:
    """Parse a JSON object from the model's result text, tolerating a ```json fence."""
    stripped = text.strip()
    if stripped.startswith("```"):
        # drop the opening fence line (``` or ```json) and any trailing fence
        stripped = stripped.split("\n", 1)[1] if "\n" in stripped else ""
        if stripped.rstrip().endswith("```"):
            stripped = stripped.rstrip()[: -3]
        stripped = stripped.strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise BriefExtractionError("No JSON object found in Claude CLI result")
    candidate = stripped[start : end + 1]
    try:
        return json.loads(candidate)
    except (ValueError, TypeError) as exc:
        raise BriefExtractionError(f"Malformed JSON from Claude CLI: {exc}") from exc


class ClaudeBriefExtractor:
    """Extracts an AnalysisBrief from free text via the logged-in Claude Code CLI."""

    def __init__(self, model: str, *, runner=None):
        self._model = model or DEFAULT_MODEL
        self._runner = runner or _default_runner

    def extract(self, request_text: str) -> AnalysisBrief:
        argv = [
            "claude",
            "-p",
            request_text,
            "--output-format",
            "json",
            "--model",
            self._model,
            "--system-prompt",
            SYSTEM_PROMPT,
            "--disallowedTools",
            "*",
        ]
        completed = self._runner(argv)
        if getattr(completed, "returncode", 1) != 0:
            raise BriefExtractionError(
                f"claude CLI exited {completed.returncode}: {(completed.stderr or '').strip()}"
            )
        try:
            envelope = json.loads(completed.stdout)
        except (ValueError, TypeError) as exc:
            raise BriefExtractionError(f"Unparseable CLI envelope: {exc}") from exc
        if envelope.get("is_error") or envelope.get("subtype") != "success":
            raise BriefExtractionError(f"claude CLI returned an error envelope: {envelope.get('subtype')}")
        result_text = envelope.get("result")
        if not isinstance(result_text, str):
            raise BriefExtractionError("CLI envelope missing a string 'result'")
        data = _extract_json_object(result_text)
        return _brief_from_payload(data)
