from __future__ import annotations

from dataclasses import dataclass

from bioflow_harness.models.registry_contract import SUPPORTED_EVIDENCE_TIERS, SUPPORTED_TIERS


class RouteProposalError(ValueError):
    """Raised when a research proposal payload is missing fields or otherwise unusable."""


@dataclass(frozen=True)
class StageProposal:
    stage_id: str
    stage_label: str
    tool_id: str
    tool_label: str
    summary: str
    language: str
    executable: str
    conda_packages: list[str]
    input_types: list[str]
    output_types: list[str]
    tier: str
    tier_rationale: str
    evidence_tier: str
    evidence_citation: str
    static_args: list[str]
    optional: bool
    produces_image: bool


@dataclass(frozen=True)
class RouteProposal:
    domain_slug: str
    domain_label: str
    conda_env_name: str
    stages: list[StageProposal]

    @property
    def required_executables(self) -> list[str]:
        seen: list[str] = []
        for stage in self.stages:
            if stage.executable not in seen:
                seen.append(stage.executable)
        return seen

    @property
    def conda_packages(self) -> list[str]:
        seen: list[str] = []
        for stage in self.stages:
            for package in stage.conda_packages:
                if package not in seen:
                    seen.append(package)
        return seen


def _require(payload: dict, key: str, container: str = "stage") -> object:
    if key not in payload:
        raise RouteProposalError(f"Research proposal {container} is missing required field: {key}")
    return payload[key]


def _str_list(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise RouteProposalError(f"Expected a list, got {type(value).__name__}: {value!r}")
    return [str(item) for item in value]


def _stage_from_payload(payload: dict) -> StageProposal:
    tier = str(_require(payload, "tier"))
    if tier not in SUPPORTED_TIERS:
        raise RouteProposalError(f"Unsupported tier in research proposal: {tier}")
    evidence_tier = str(payload.get("evidence_tier", "pending_citation_review"))
    if evidence_tier not in SUPPORTED_EVIDENCE_TIERS:
        raise RouteProposalError(f"Unsupported evidence_tier in research proposal: {evidence_tier}")
    return StageProposal(
        stage_id=str(_require(payload, "stage_id")),
        stage_label=str(_require(payload, "stage_label")),
        tool_id=str(_require(payload, "tool_id")),
        tool_label=str(_require(payload, "tool_label")),
        summary=str(payload.get("summary", "")),
        language=str(payload.get("language", "unknown")),
        executable=str(_require(payload, "executable")),
        conda_packages=_str_list(payload.get("conda_packages")) or [str(payload.get("executable", ""))],
        input_types=_str_list(_require(payload, "input_types")),
        output_types=_str_list(_require(payload, "output_types")),
        tier=tier,
        tier_rationale=str(payload.get("tier_rationale", "")),
        evidence_tier=evidence_tier,
        evidence_citation=str(payload.get("evidence_citation", "")),
        static_args=_str_list(payload.get("static_args")),
        optional=bool(payload.get("optional", False)),
        produces_image=bool(payload.get("produces_image", False)),
    )


def route_proposal_from_payload(data: dict) -> RouteProposal:
    stages_payload = _require(data, "stages", container="proposal")
    if not isinstance(stages_payload, list) or not stages_payload:
        raise RouteProposalError("Research proposal must declare at least one stage.")
    stages = [_stage_from_payload(stage) for stage in stages_payload]
    if not any(stage.produces_image for stage in stages):
        raise RouteProposalError(
            "Research proposal must end with a visualization stage that produces_image=true "
            "(WorkflowBuilder requires an IMAGE-producing node)."
        )
    domain_slug = str(_require(data, "domain_slug", container="proposal"))
    return RouteProposal(
        domain_slug=domain_slug,
        domain_label=str(data.get("domain_label", domain_slug)),
        conda_env_name=str(data.get("conda_env_name", domain_slug)),
        stages=stages,
    )
