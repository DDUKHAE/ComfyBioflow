from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class ResourceDTO:
    label: str
    type: str
    path: str

    @classmethod
    def from_dict(cls, data: dict) -> "ResourceDTO":
        return cls(
            label=str(data.get("label", "")),
            type=str(data.get("type", "")),
            path=str(data.get("path", "")),
        )


@dataclass(frozen=True)
class CandidateDTO:
    tool_id: str
    label: str
    tier: str
    note: str


@dataclass(frozen=True)
class StepDTO:
    stage_id: str
    stage_label: str
    tool_id: str
    tool_label: str
    input_types: list[str]
    output_types: list[str]
    tier: str
    rationale: str
    candidates: list[CandidateDTO] = field(default_factory=list)


@dataclass(frozen=True)
class CompileRequest:
    request_text: str
    provider: str = "codex"
    model: str = ""
    resources: list[ResourceDTO] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "CompileRequest":
        return cls(
            request_text=str(data.get("request_text", "")),
            provider=str(data.get("provider", "codex")),
            model=str(data.get("model", "")),
            resources=[ResourceDTO.from_dict(item) for item in data.get("resources", [])],
        )


@dataclass(frozen=True)
class GenerateRequest:
    request_text: str
    provider: str = "codex"
    model: str = ""
    resources: list[ResourceDTO] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "GenerateRequest":
        return cls(
            request_text=str(data.get("request_text", "")),
            provider=str(data.get("provider", "codex")),
            model=str(data.get("model", "")),
            resources=[ResourceDTO.from_dict(item) for item in data.get("resources", [])],
            steps=[str(step) for step in data.get("steps", [])],
        )


@dataclass(frozen=True)
class CompileResponse:
    status: str
    domain: str
    route_id: str | None
    steps: list[StepDTO] = field(default_factory=list)
    message: str | None = None
    confidence_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)
