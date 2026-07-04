from dataclasses import dataclass, field


@dataclass(frozen=True)
class AnalysisBrief:
    analysis_type: str
    domain: str
    input_assets: list[str]
    organism: str | None
    expected_outputs: list[str]
    constraints: list[str] = field(default_factory=list)
    preferred_tools: list[str] = field(default_factory=list)
    confidence_notes: list[str] = field(default_factory=list)
    submission_source: str = "text_prompt"
    data_characteristics: dict[str, str] = field(default_factory=dict)

