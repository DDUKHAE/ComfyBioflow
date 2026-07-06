from bioflow_harness.comfy.node_catalog import NodeDefinition
from bioflow_harness.comfy.workflow_schema import validate_workflow_export
from bioflow_harness.models.workflow_plan import WorkflowPlan


class WorkflowBuilder:
    def __init__(self, node_catalog: dict[str, NodeDefinition]) -> None:
        self.node_catalog = node_catalog

    def build(self, plan: WorkflowPlan) -> dict:
        nodes = []
        links = []
        visualization_node_id = None
        preview_link_id = len(plan.stages)
        next_x = 80
        for index, stage in enumerate(plan.stages, start=1):
            if stage.node_type not in self.node_catalog:
                raise ValueError(f"Node type {stage.node_type} is missing from the node catalog.")
            definition = self.node_catalog[stage.node_type]
            incoming_link_id = index - 1 if index > 1 else None
            output_links_by_slot = {0: [index] if index < len(plan.stages) else []}
            if stage.node_type == "DESeq2VisualizationNode":
                visualization_node_id = index
                output_links_by_slot[1] = [preview_link_id]
            size = self._node_size(definition.widgets)
            nodes.append(
                {
                    "id": index,
                    "type": definition.node_type,
                    "title": definition.title,
                    "pos": [next_x, 120],
                    "size": size,
                    "flags": {},
                    "order": index - 1,
                    "mode": 0,
                    "inputs": self._inputs_with_link(definition.inputs, incoming_link_id),
                    "outputs": self._outputs_with_links(definition.outputs, output_links_by_slot),
                    "properties": {"Node name for S&R": definition.node_type},
                    "widgets_values": definition.widgets,
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
            next_x += size[0] + 100
            if index > 1:
                links.append([index - 1, index - 1, 0, index, 0, "STRING"])
        if visualization_node_id is None:
            raise ValueError("Official workflow is missing DESeq2VisualizationNode.")
        preview_node_id = len(plan.stages) + 1
        nodes.append(
            {
                "id": preview_node_id,
                "type": "PreviewImage",
                "title": "Preview DESeq2 Plot",
                "pos": [nodes[visualization_node_id - 1]["pos"][0], 420],
                "size": [280, 120],
                "flags": {},
                "order": preview_node_id - 1,
                "mode": 0,
                "inputs": [{"name": "images", "type": "IMAGE", "link": preview_link_id}],
                "outputs": [],
                "properties": {"Node name for S&R": "PreviewImage"},
                "widgets_values": [],
                "metadata": {
                    "stage_id": "deseq2_preview",
                    "stage_label": "DESeq2 visualization preview",
                    "selected_tool_id": "comfyui_preview_image",
                    "selected_tier": "BUILTIN",
                    "source_operation": "preview_image",
                    "restart_required": False,
                },
            }
        )
        links.append([preview_link_id, visualization_node_id, 1, preview_node_id, 0, "IMAGE"])
        workflow = {
            "last_node_id": preview_node_id,
            "last_link_id": preview_link_id,
            "version": 0.4,
            "config": {},
            "extra": {},
            "groups": [],
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

    def _node_size(self, widgets: list[str | int | bool]) -> list[int]:
        string_values = [value for value in widgets if isinstance(value, str)]
        longest_value = max((len(value) for value in string_values), default=0)
        path_count = sum(1 for value in string_values if "/" in value)
        width = 280
        if path_count:
            width = max(520, min(760, 260 + longest_value * 6))
        height = max(140, 110 + len(widgets) * 24)
        return [width, height]

    def _inputs_with_link(self, inputs: list[dict[str, str]], link_id: int | None) -> list[dict]:
        copied_inputs = [dict(input_def) for input_def in inputs]
        if copied_inputs and link_id is not None:
            copied_inputs[0]["link"] = link_id
        return copied_inputs

    def _outputs_with_links(self, outputs: list[dict[str, str]], links_by_slot: dict[int, list[int]]) -> list[dict]:
        copied_outputs = []
        for slot_index, output in enumerate(outputs):
            copied_output = dict(output)
            copied_output["slot_index"] = slot_index
            copied_output["links"] = links_by_slot.get(slot_index) or []
            copied_outputs.append(copied_output)
        return copied_outputs
