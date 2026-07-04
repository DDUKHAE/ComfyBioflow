from bioflow_harness.comfy.node_catalog import NodeDefinition
from bioflow_harness.comfy.workflow_schema import validate_workflow_export
from bioflow_harness.models.workflow_plan import WorkflowPlan


class WorkflowBuilder:
    def __init__(self, node_catalog: dict[str, NodeDefinition]) -> None:
        self.node_catalog = node_catalog

    def build(self, plan: WorkflowPlan) -> dict:
        nodes = []
        links = []
        for index, stage in enumerate(plan.stages, start=1):
            if stage.node_type not in self.node_catalog:
                raise ValueError(f"Node type {stage.node_type} is missing from the node catalog.")
            definition = self.node_catalog[stage.node_type]
            nodes.append(
                {
                    "id": index,
                    "type": definition.node_type,
                    "title": definition.title,
                    "pos": [80 + (index - 1) * 280, 120],
                    "size": [240, 120],
                    "widgets_values": definition.widgets,
                    "outputs": definition.outputs,
                    "metadata": {
                        "stage_id": stage.stage_id,
                        "stage_label": stage.stage_label,
                        "selected_tool_id": stage.selected_tool_id,
                        "selected_tier": stage.selected_tier,
                        "source_operation": stage.source_operation,
                        "restart_required": stage.restart_required,
                    },
                }
            )
            if index > 1:
                links.append(
                    {
                        "id": index - 1,
                        "origin_id": index - 1,
                        "origin_slot": 0,
                        "target_id": index,
                        "target_slot": 0,
                        "type": "STRING",
                    }
                )
        workflow = {
            "metadata": {
                "format": "comfyui_workflow_export",
                "route_id": plan.route_id,
                "domain": plan.domain,
                "manual_open_fallback": "Open this JSON file from ComfyUI if pending workflow loading is unavailable.",
            },
            "nodes": nodes,
            "links": links,
        }
        validate_workflow_export(workflow)
        return workflow

