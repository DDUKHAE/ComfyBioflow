from bioflow_harness.models.prompt_contract import AnalysisBrief
from bioflow_harness.models.registry_contract import ToolRegistry
from bioflow_harness.models.workflow_plan import WorkflowPlan, WorkflowStage
from bioflow_harness.planner.tool_selector import ToolSelector


class WorkflowPlanner:
    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    def plan(self, brief: AnalysisBrief) -> WorkflowPlan:
        try:
            route_id = self.registry.route_id_for_domain(brief.domain)
        except KeyError as error:
            raise ValueError(str(error)) from error
        stages: list[WorkflowStage] = []
        selector = ToolSelector(self.registry)
        route = {stage.stage_id: stage for stage in self.registry.official_route(route_id)}
        for selection in selector.select_official_route(route_id):
            route_stage = route[selection.stage_id]
            tool = self.registry.tool_by_id(selection.tool_id)
            operation = next(operation for operation in tool.operations if operation.id == selection.operation_id)
            stages.append(
                WorkflowStage(
                    stage_id=selection.stage_id,
                    stage_label=selection.stage_label,
                    required_inputs=operation.input_types,
                    selected_tool_id=selection.tool_id,
                    produced_outputs=operation.output_types,
                    optionality=route_stage.optional,
                    rationale=selection.rationale,
                    implementation_status=tool.runnable_node_status,
                    selected_tier=selection.selected_tier,
                    context_override_reason=None,
                    source_operation=selection.operation_id,
                    node_activation_status="loaded",
                    restart_required=False,
                    node_type=operation.node_type,
                )
            )
        return WorkflowPlan(route_id=route_id, domain=brief.domain, brief=brief, stages=stages)

