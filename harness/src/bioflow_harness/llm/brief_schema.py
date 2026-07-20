from __future__ import annotations

import json

from bioflow_harness.models.prompt_contract import AnalysisBrief


class BriefExtractionError(RuntimeError):
    """Raised when a provider CLI errors or returns an unusable payload."""


BRIEF_SCHEMA = {
    "type": "object",
    "properties": {
        "analysis_type": {"type": "string"},
        "domain": {
            "type": "string",
            "enum": [
                "bulk_rna_seq",
                "scrna_seq",
                "variant_analysis",
                "epigenomics",
                "metagenome",
                "genome_assembly",
                "unsupported",
            ],
        },
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
- "variant_analysis": germline variant calling (FASTQ reads, bwa-mem2 alignment, bcftools calling, VCF)
- "epigenomics": ATAC-seq chromatin accessibility (peak calling, MACS3). Not ChIP-seq — ChIP-seq needs
  control-sample pairing and has no route yet, so classify ChIP-seq requests as "unsupported".
- "metagenome": shotgun metagenomic taxonomic classification (Kraken2/Bracken, microbiome profiling)
- "genome_assembly": bacterial isolate de novo assembly (SPAdes, QUAST QC)
- "unsupported": anything that is none of the above

Fields:
- analysis_type: short slug for the intent (e.g. "differential_expression", "single_cell_analysis", "workflow_generation")
- domain: one of the values above
- input_assets: input data kinds mentioned (e.g. "fastq", "sample_metadata")
- organism: the species/genome if stated, else an empty string
- expected_outputs: artifacts wanted (e.g. "salmon_quantification", "deseq2_results", "visualization_artifacts", "report")
- constraints: any explicit constraints stated
- preferred_tools: tools named in the request
- data_characteristics: any stated properties, each as an object {"key": ..., "value": ...} (e.g. {"key": "layout", "value": "paired"})

Classify domain as "unsupported" when the request does not match any of the domains above.

Respond with ONLY a single JSON object with exactly these keys: analysis_type, domain, input_assets, organism, expected_outputs, constraints, preferred_tools, data_characteristics. Every key must be present (use "" or [] when unknown). Do not use any tools. Do not include prose, explanation, or markdown code fences — output the raw JSON object only."""


def brief_from_payload(data: dict) -> AnalysisBrief:
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


def extract_json_object(text: str, *, source: str = "CLI") -> dict:
    """Parse a JSON object from a model's result text, tolerating a ```json fence."""
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
        raise BriefExtractionError(f"No JSON object found in {source} result")
    candidate = stripped[start : end + 1]
    try:
        return json.loads(candidate)
    except (ValueError, TypeError) as exc:
        raise BriefExtractionError(f"Malformed JSON from {source}: {exc}") from exc
