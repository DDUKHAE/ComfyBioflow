from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Protocol

from bioflow_harness.llm.claude_extractor import DEFAULT_MODEL as CLAUDE_DEFAULT_MODEL
from bioflow_harness.llm.claude_extractor import ClaudeBriefExtractor
from bioflow_harness.llm.codex_extractor import DEFAULT_MODEL as CODEX_DEFAULT_MODEL
from bioflow_harness.llm.codex_extractor import CodexBriefExtractor
from bioflow_harness.llm.gemini_extractor import DEFAULT_MODEL as GEMINI_DEFAULT_MODEL
from bioflow_harness.llm.gemini_extractor import GeminiBriefExtractor
from bioflow_harness.models.prompt_contract import AnalysisBrief
from bioflow_harness.parser.prompt_parser import parse_prompt


class BriefExtractor(Protocol):
    def extract(self, request_text: str) -> AnalysisBrief: ...


@dataclass(frozen=True)
class ExtractionMeta:
    source: str
    model: str
    note: str


_PROVIDERS = {
    "claude": (ClaudeBriefExtractor, CLAUDE_DEFAULT_MODEL),
    "codex": (CodexBriefExtractor, CODEX_DEFAULT_MODEL),
    "gemini": (GeminiBriefExtractor, GEMINI_DEFAULT_MODEL),
}


def _annotate(brief: AnalysisBrief, meta: "ExtractionMeta") -> AnalysisBrief:
    return dataclasses.replace(
        brief, confidence_notes=[*brief.confidence_notes, meta.note]
    )


def extract_brief(
    request_text: str,
    provider: str = "codex",
    model: str = "",
    *,
    runner=None,
) -> tuple[AnalysisBrief, ExtractionMeta]:
    entry = _PROVIDERS.get(provider)
    if entry is None:
        meta = ExtractionMeta(
            source="deterministic",
            model=model,
            note=f"provider '{provider}' not yet wired; used deterministic parser",
        )
        return _annotate(parse_prompt(request_text), meta), meta

    extractor_cls, default_model = entry
    chosen = model or default_model
    try:
        brief = extractor_cls(chosen, runner=runner).extract(request_text)
        meta = ExtractionMeta(
            source=provider,
            model=chosen,
            note=f"brief extracted via {provider}/{chosen}",
        )
        return _annotate(brief, meta), meta
    except Exception as exc:  # noqa: BLE001 - any failure degrades to deterministic
        meta = ExtractionMeta(
            source="deterministic",
            model=chosen,
            note=f"{provider} extraction unavailable ({exc}); used deterministic parser",
        )
        return _annotate(parse_prompt(request_text), meta), meta
