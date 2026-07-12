from .ref_nodes import (
    ComfyBIOReportNode,
    DESeq2AnalysisNode,
    DESeq2VisualizationNode,
    FastpQCNode,
    FastpTrimNode,
    ScRNAReportNode,
    ScRNAVisualizationNode,
    SalmonIndexNode,
    SalmonQuantNode,
    SampleMetadataValidatorNode,
    ScanpyClusterNode,
    ScanpyMarkerGenesNode,
    ScanpyNormalizeNode,
    ScanpyQCNode,
    TenxCountNode,
    TximportNode,
)


NODE_CLASS_MAPPINGS = {
    "SampleMetadataValidatorNode": SampleMetadataValidatorNode,
    "FastpQCNode": FastpQCNode,
    "FastpTrimNode": FastpTrimNode,
    "TenxCountNode": TenxCountNode,
    "ScanpyQCNode": ScanpyQCNode,
    "ScanpyNormalizeNode": ScanpyNormalizeNode,
    "ScanpyClusterNode": ScanpyClusterNode,
    "ScanpyMarkerGenesNode": ScanpyMarkerGenesNode,
    "ScRNAVisualizationNode": ScRNAVisualizationNode,
    "ScRNAReportNode": ScRNAReportNode,
    "SalmonIndexNode": SalmonIndexNode,
    "SalmonQuantNode": SalmonQuantNode,
    "TximportNode": TximportNode,
    "DESeq2AnalysisNode": DESeq2AnalysisNode,
    "DESeq2VisualizationNode": DESeq2VisualizationNode,
    "ComfyBIOReportNode": ComfyBIOReportNode,
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
