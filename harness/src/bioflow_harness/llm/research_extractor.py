from __future__ import annotations

import json
import subprocess

from bioflow_harness.autogen.route_proposal import RouteProposal, route_proposal_from_payload
from bioflow_harness.llm.brief_schema import BriefExtractionError, extract_json_object
from bioflow_harness.models.prompt_contract import AnalysisBrief

DEFAULT_RESEARCH_MODEL = "claude-opus-4-8"
_TIMEOUT_SECONDS = 300

RESEARCH_SYSTEM_PROMPT = """You are researching which bioinformatics command-line tool(s) ComfyBIO should use
for an analysis domain/pipeline that is not yet in its Tool Selection Registry (TSR).

Use web search to find real evidence before answering. Evidence hierarchy, in priority order:
1. primary_openebench: an ELIXIR OpenEBench or bio.tools community benchmarking challenge, or a documented
   adoption-frequency statistic, that directly supports picking this tool over alternatives for this stage.
2. secondary_literature: no OpenEBench/bio.tools challenge exists for this exact comparison, but you found a
   specific benchmark paper (with title/venue/year you can cite) comparing this tool to its alternatives.
3. pending_citation_review: you believe this is the right tool but could not find a verifiable citation for
   tier 1 or 2. Use this honestly rather than inventing a citation — do not fabricate evidence.

Only choose evidence_tier "primary_openebench" or "secondary_literature" if you can put a real, checkable
source (challenge name/URL, or paper title+venue+year) in evidence_citation. If you are not confident the
citation is real, use "pending_citation_review" instead.

Design a complete pipeline (ordered list of stages) for the requested domain, each stage naming exactly one
REF-tier command-line tool. The final stage MUST be a visualization/plotting stage that produces an image
artifact (set "produces_image": true on it) — ComfyBIO's workflow builder requires this.

Respond with ONLY a single JSON object, no prose, no markdown fences, matching this shape:
{
  "domain_slug": "short_snake_case_domain_name",
  "domain_label": "Human Readable Domain Name",
  "conda_env_name": "short_snake_case_env_name",
  "stages": [
    {
      "stage_id": "short_snake_case_stage_id",
      "stage_label": "Human readable stage label",
      "tool_id": "short_snake_case_tool_id",
      "tool_label": "Tool Display Name",
      "summary": "One sentence describing what this tool does at this stage.",
      "language": "e.g. C++, Python, R",
      "executable": "the CLI executable name to invoke, e.g. fastp",
      "conda_packages": ["conda/bioconda package name(s) needed to install the executable"],
      "input_types": ["short input artifact name(s), snake_case"],
      "output_types": ["short output artifact name(s), snake_case"],
      "tier": "REF",
      "tier_rationale": "Why this tool was chosen as the default for this stage.",
      "evidence_tier": "primary_openebench | secondary_literature | pending_citation_review",
      "evidence_citation": "The specific challenge name/URL or paper title+venue+year, or empty string if pending_citation_review.",
      "static_args": ["literal", "CLI", "flags", "excluding", "input/output/thread", "paths"],
      "optional": false,
      "produces_image": false
    }
  ]
}
"""


def _default_runner(argv: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(argv, capture_output=True, text=True, timeout=_TIMEOUT_SECONDS)


class RouteResearchError(RuntimeError):
    """Raised when the research extractor fails to produce a usable route proposal."""


class ClaudeToolResearchExtractor:
    """Researches a missing domain/tool via the Claude Code CLI with web search enabled.

    Unlike ClaudeBriefExtractor (which disallows all tools for a fast, deterministic
    brief extraction), this extractor explicitly allows WebSearch/WebFetch so the model
    can find real evidence for TSR tier assignment instead of relying on unverifiable
    internal knowledge.
    """

    def __init__(self, model: str = "", *, runner=None):
        self._model = model or DEFAULT_RESEARCH_MODEL
        self._runner = runner or _default_runner

    def research(self, brief: AnalysisBrief) -> RouteProposal:
        request_text = (
            f"Design a ComfyBIO pipeline for domain '{brief.domain}'. "
            f"Analysis type: {brief.analysis_type}. "
            f"Input assets: {', '.join(brief.input_assets) or 'unspecified'}. "
            f"Organism: {brief.organism or 'unspecified'}. "
            f"Expected outputs: {', '.join(brief.expected_outputs) or 'unspecified'}. "
            f"Constraints: {', '.join(brief.constraints) or 'none'}. "
            f"Preferred tools mentioned by the user (consider but do not blindly trust): "
            f"{', '.join(brief.preferred_tools) or 'none'}."
        )
        argv = [
            "claude",
            "-p",
            request_text,
            "--output-format",
            "json",
            "--model",
            self._model,
            "--system-prompt",
            RESEARCH_SYSTEM_PROMPT,
            "--allowedTools",
            "WebSearch,WebFetch",
        ]
        completed = self._runner(argv)
        if getattr(completed, "returncode", 1) != 0:
            raise RouteResearchError(
                f"claude research CLI exited {completed.returncode}: {(completed.stderr or '').strip()}"
            )
        try:
            envelope = json.loads(completed.stdout)
        except (ValueError, TypeError) as exc:
            raise RouteResearchError(f"Unparseable CLI envelope: {exc}") from exc
        if envelope.get("is_error") or envelope.get("subtype") != "success":
            raise RouteResearchError(f"claude research CLI returned an error envelope: {envelope.get('subtype')}")
        result_text = envelope.get("result")
        if not isinstance(result_text, str):
            raise RouteResearchError("CLI envelope missing a string 'result'")
        try:
            data = extract_json_object(result_text, source="Claude research CLI")
        except BriefExtractionError as exc:
            raise RouteResearchError(str(exc)) from exc
        try:
            return route_proposal_from_payload(data)
        except ValueError as exc:
            raise RouteResearchError(f"Research proposal failed validation: {exc}") from exc
