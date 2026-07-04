from dataclasses import dataclass, field

from bioflow_harness.models.prompt_contract import AnalysisBrief


@dataclass(frozen=True)
class WorkflowStage:
    stage_id: str
    stage_label: str
    required_inputs: list[str]
    selected_tool_id: str
    produced_outputs: list[str]
    optionality: bool
    rationale: str
    implementation_status: str
    selected_tier: str
    context_override_reason: str | None
    source_operation: str
    node_activation_status: str
    restart_required: bool
    node_type: str


@dataclass(frozen=True)
class WorkflowPlan:
    route_id: str
    domain: str
    brief: AnalysisBrief
    stages: list[WorkflowStage] = field(default_factory=list)

