from bioflow_harness.custom_nodes.ref_nodes import (
    ComfyBIOReportNode,
    DESeq2AnalysisNode,
    DESeq2VisualizationNode,
    FastpQCNode,
    FastpTrimNode,
    SalmonIndexNode,
    SalmonQuantNode,
    SampleMetadataValidatorNode,
    TximportNode,
    WorkflowJSONOutput,
    WorkflowRequestLoader,
)


NODE_CLASS_MAPPINGS = {
    "WorkflowRequestLoader": WorkflowRequestLoader,
    "SampleMetadataValidatorNode": SampleMetadataValidatorNode,
    "FastpQCNode": FastpQCNode,
    "FastpTrimNode": FastpTrimNode,
    "SalmonIndexNode": SalmonIndexNode,
    "SalmonQuantNode": SalmonQuantNode,
    "TximportNode": TximportNode,
    "DESeq2AnalysisNode": DESeq2AnalysisNode,
    "DESeq2VisualizationNode": DESeq2VisualizationNode,
    "ComfyBIOReportNode": ComfyBIOReportNode,
    "WorkflowJSONOutput": WorkflowJSONOutput,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    node_type: node_type.replace("Node", "").replace("Workflow", "Workflow ")
    for node_type in NODE_CLASS_MAPPINGS
}


def resolve_node_class(node_type: str):
    try:
        return NODE_CLASS_MAPPINGS[node_type]
    except KeyError as error:
        raise KeyError(f"No ComfyBIO custom node class registered for {node_type}") from error

