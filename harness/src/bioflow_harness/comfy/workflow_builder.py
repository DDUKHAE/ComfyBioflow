from bioflow_harness.comfy.node_catalog import NodeDefinition
from bioflow_harness.comfy.workflow_schema import validate_workflow_export
from bioflow_harness.models.workflow_plan import WorkflowPlan

# node_type -> {widget_index: attribute name on ResourceBindings}
_BULK_INJECTION = {
    "SampleMetadataValidatorNode": {0: "input_fastq_dir", 1: "metadata_csv"},
    "FastpQCNode": {0: "input_fastq_dir", 1: "metadata_csv", 2: "qc_dir"},
    "FastpTrimNode": {0: "input_fastq_dir", 1: "metadata_csv", 2: "trimmed_dir"},
    "SalmonIndexNode": {0: "transcriptome_fasta", 1: "salmon_index_dir"},
    "SalmonQuantNode": {0: "salmon_index_dir", 1: "input_fastq_dir", 2: "metadata_csv", 3: "salmon_quant_dir"},
    "TximportNode": {0: "salmon_quant_dir", 1: "metadata_csv", 2: "count_matrix"},
    "DESeq2AnalysisNode": {0: "count_matrix", 1: "metadata_csv", 2: "results_csv"},
    "DESeq2VisualizationNode": {0: "count_matrix", 1: "results_csv", 2: "plot_dir"},
    "ComfyBIOReportNode": {0: "results_csv", 1: "plot_dir", 2: "report_path"},
}


class WorkflowBuilder:
    def __init__(self, node_catalog: dict[str, NodeDefinition]) -> None:
        self.node_catalog = node_catalog

    def build(self, plan: WorkflowPlan, bindings=None) -> dict:
        nodes = []
        links = []
        preview_source_node_id = None
        preview_source_slot = None
        preview_link_id = len(plan.stages)
        next_x = 80
        for index, stage in enumerate(plan.stages, start=1):
            if stage.node_type not in self.node_catalog:
                raise ValueError(f"Node type {stage.node_type} is missing from the node catalog.")
            definition = self.node_catalog[stage.node_type]
            widgets = self._widgets_for_stage(definition, plan, bindings)
            incoming_link_id = index - 1 if index > 1 else None
            output_links_by_slot = {0: [index] if index < len(plan.stages) else []}
            image_output_slot = self._image_output_slot(definition)
            if image_output_slot is not None and preview_source_node_id is None:
                preview_source_node_id = index
                preview_source_slot = image_output_slot
                output_links_by_slot[image_output_slot] = [preview_link_id]
            size = self._node_size(widgets)
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
                    "widgets_values": widgets,
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
        if preview_source_node_id is None or preview_source_slot is None:
            raise ValueError("Official workflow is missing a visualization node with IMAGE output.")
        preview_node_id = len(plan.stages) + 1
        nodes.append(
            {
                "id": preview_node_id,
                "type": "PreviewImage",
                "title": self._preview_title(plan),
                "pos": [nodes[preview_source_node_id - 1]["pos"][0], 420],
                "size": [280, 120],
                "flags": {},
                "order": preview_node_id - 1,
                "mode": 0,
                "inputs": [{"name": "images", "type": "IMAGE", "link": preview_link_id}],
                "outputs": [],
                "properties": {"Node name for S&R": "PreviewImage"},
                "widgets_values": [],
                "metadata": {
                    "stage_id": f"{plan.domain}_preview",
                    "stage_label": f"{plan.domain} visualization preview",
                    "selected_tool_id": "comfyui_preview_image",
                    "selected_tier": "BUILTIN",
                    "source_operation": "preview_image",
                    "restart_required": False,
                },
            }
        )
        links.append([preview_link_id, preview_source_node_id, preview_source_slot, preview_node_id, 0, "IMAGE"])
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

    def _widgets_for_stage(self, definition: NodeDefinition, plan: WorkflowPlan, bindings=None) -> list[str | int | bool]:
        if definition.node_type == "WorkflowRequestLoader":
            return [self._request_text(plan)]
        if definition.node_type == "WorkflowJSONOutput":
            return [f"harness/examples/workflows/{plan.route_id}.json"]
        widgets = list(definition.widgets)
        if bindings is not None:
            for index, attribute in _BULK_INJECTION.get(definition.node_type, {}).items():
                if index < len(widgets):
                    widgets[index] = getattr(bindings, attribute)
        return widgets

    def _request_text(self, plan: WorkflowPlan) -> str:
        if plan.domain == "scrna_seq":
            return "Single-cell RNA-seq through 10x count, Scanpy QC, normalization, clustering, UMAP, marker genes, plots, and report."
        return "Bulk RNA-seq through salmon, DESeq2, plots, and report."

    def _preview_title(self, plan: WorkflowPlan) -> str:
        if plan.domain == "scrna_seq":
            return "Preview scRNA Plot"
        return "Preview DESeq2 Plot"

    def _node_size(self, widgets: list[str | int | bool]) -> list[int]:
        string_values = [value for value in widgets if isinstance(value, str)]
        longest_value = max((len(value) for value in string_values), default=0)
        path_count = sum(1 for value in string_values if "/" in value)
        width = 280
        if path_count:
            width = max(520, min(760, 260 + longest_value * 6))
        height = max(140, 110 + len(widgets) * 24)
        return [width, height]

    def _image_output_slot(self, definition: NodeDefinition) -> int | None:
        for slot_index, output in enumerate(definition.outputs):
            if output.get("type") == "IMAGE":
                return slot_index
        return None

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
