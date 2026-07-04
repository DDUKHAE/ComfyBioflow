from dataclasses import dataclass


@dataclass(frozen=True)
class NodeDefinition:
    node_type: str
    title: str
    category: str
    outputs: list[dict[str, str]]
    widgets: dict[str, str | int | bool]


def default_node_catalog() -> dict[str, NodeDefinition]:
    return {
        "WorkflowRequestLoader": NodeDefinition("WorkflowRequestLoader", "Workflow Request", "ComfyBIO/Orchestration", [{"name": "request_payload", "type": "STRING"}], {}),
        "SampleMetadataValidatorNode": NodeDefinition("SampleMetadataValidatorNode", "Validate Sample Metadata", "ComfyBIO/Input", [{"name": "validated_metadata", "type": "STRING"}], {}),
        "FastpQCNode": NodeDefinition("FastpQCNode", "FASTQ QC", "ComfyBIO/QC", [{"name": "qc_dir", "type": "STRING"}], {"threads": 2}),
        "FastpTrimNode": NodeDefinition("FastpTrimNode", "Optional FASTQ Trimming", "ComfyBIO/QC", [{"name": "trimmed_fastq_dir", "type": "STRING"}], {"threads": 2}),
        "SalmonIndexNode": NodeDefinition("SalmonIndexNode", "Salmon Index", "ComfyBIO/Quantification", [{"name": "salmon_index_dir", "type": "STRING"}], {"threads": 2}),
        "SalmonQuantNode": NodeDefinition("SalmonQuantNode", "Salmon Quant", "ComfyBIO/Quantification", [{"name": "salmon_quant_dir", "type": "STRING"}], {"threads": 2}),
        "TximportNode": NodeDefinition("TximportNode", "Import Counts For DESeq2", "ComfyBIO/Differential Expression", [{"name": "deseq2_count_matrix", "type": "STRING"}], {}),
        "DESeq2AnalysisNode": NodeDefinition("DESeq2AnalysisNode", "DESeq2 Analysis", "ComfyBIO/Differential Expression", [{"name": "deseq2_results_table", "type": "STRING"}], {"design_formula": "~ condition"}),
        "DESeq2VisualizationNode": NodeDefinition("DESeq2VisualizationNode", "DESeq2 Visualization", "ComfyBIO/Visualization", [{"name": "plot_dir", "type": "STRING"}, {"name": "preview_plot", "type": "IMAGE"}], {"plots": "pca,ma,volcano,heatmap"}),
        "ComfyBIOReportNode": NodeDefinition("ComfyBIOReportNode", "ComfyBIO Report", "ComfyBIO/Reporting", [{"name": "report_path", "type": "STRING"}], {}),
        "WorkflowJSONOutput": NodeDefinition("WorkflowJSONOutput", "Workflow JSON Export", "ComfyBIO/Orchestration", [{"name": "workflow_json_path", "type": "STRING"}], {}),
    }

