from dataclasses import dataclass, field


@dataclass(frozen=True)
class PromptSubmission:
    request_text: str
    workflow_domain_hint: str | None = None
    input_asset_descriptions: list[str] = field(default_factory=list)
    expected_outputs: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    preferred_tools: list[str] = field(default_factory=list)
    submit_timestamp: str | None = None

