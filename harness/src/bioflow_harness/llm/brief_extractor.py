from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Protocol

from bioflow_harness.llm.claude_extractor import DEFAULT_MODEL, ClaudeBriefExtractor
from bioflow_harness.models.prompt_contract import AnalysisBrief
from bioflow_harness.parser.prompt_parser import parse_prompt


class BriefExtractor(Protocol):
    def extract(self, request_text: str) -> AnalysisBrief: ...


@dataclass(frozen=True)
class ExtractionMeta:
    source: str
    model: str
    note: str


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
    if provider == "claude":
        chosen = model or DEFAULT_MODEL
        try:
            brief = ClaudeBriefExtractor(chosen, runner=runner).extract(request_text)
            meta = ExtractionMeta(
                source="claude",
                model=chosen,
                note=f"brief extracted via claude/{chosen}",
            )
            return _annotate(brief, meta), meta
        except Exception as exc:  # noqa: BLE001 - any failure degrades to deterministic
            meta = ExtractionMeta(
                source="deterministic",
                model=chosen,
                note=f"claude extraction unavailable ({exc}); used deterministic parser",
            )
            return _annotate(parse_prompt(request_text), meta), meta
    meta = ExtractionMeta(
        source="deterministic",
        model=model,
        note=f"provider '{provider}' not yet wired; used deterministic parser",
    )
    return _annotate(parse_prompt(request_text), meta), meta
