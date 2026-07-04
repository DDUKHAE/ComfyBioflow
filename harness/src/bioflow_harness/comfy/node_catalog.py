from dataclasses import dataclass


@dataclass(frozen=True)
class NodeDefinition:
    node_type: str
    title: str
    category: str
    inputs: list[dict[str, str]]
    outputs: list[dict[str, str]]
    widgets: list[str | int | bool]


def default_node_catalog() -> dict[str, NodeDefinition]:
    return {
        "WorkflowRequestLoader": NodeDefinition("WorkflowRequestLoader", "Workflow Request", "ComfyBIO/Orchestration", [], [{"name": "request_payload", "type": "STRING"}], ["Bulk RNA-seq through salmon, DESeq2, plots, and report."]),
        "SampleMetadataValidatorNode": NodeDefinition("SampleMetadataValidatorNode", "Validate Sample Metadata", "ComfyBIO/Input", [{"name": "sample_metadata", "type": "STRING"}], [{"name": "validated_metadata", "type": "STRING"}], ["harness/examples/fixtures/quickstart/sample_metadata.csv", ""]),
        "FastpQCNode": NodeDefinition("FastpQCNode", "FASTQ QC", "ComfyBIO/QC", [{"name": "fastq_1", "type": "STRING"}], [{"name": "qc_dir", "type": "STRING"}], ["harness/examples/fixtures/quickstart/sample_a_R1.fastq", "harness/examples/fixtures/quickstart/sample_a_R2.fastq", "harness/examples/runs/quickstart/qc/sample_a.fastp.json", 2, ""]),
        "FastpTrimNode": NodeDefinition("FastpTrimNode", "Optional FASTQ Trimming", "ComfyBIO/QC", [{"name": "fastq_1", "type": "STRING"}], [{"name": "trimmed_fastq_dir", "type": "STRING"}], ["harness/examples/fixtures/quickstart/sample_a_R1.fastq", "harness/examples/fixtures/quickstart/sample_a_R2.fastq", "harness/examples/runs/quickstart/trimmed/sample_a", 2, "--length_required 1"]),
        "SalmonIndexNode": NodeDefinition("SalmonIndexNode", "Salmon Index", "ComfyBIO/Quantification", [{"name": "transcriptome_fasta", "type": "STRING"}], [{"name": "salmon_index_dir", "type": "STRING"}], ["harness/examples/fixtures/quickstart/toy_transcriptome.fasta", "harness/examples/runs/quickstart/salmon_index", 2, "-k 7"]),
        "SalmonQuantNode": NodeDefinition("SalmonQuantNode", "Salmon Quant", "ComfyBIO/Quantification", [{"name": "index_dir", "type": "STRING"}], [{"name": "salmon_quant_dir", "type": "STRING"}], ["harness/examples/runs/quickstart/salmon_index", "harness/examples/runs/quickstart/trimmed/sample_a/R1.fastq", "harness/examples/runs/quickstart/trimmed/sample_a/R2.fastq", "harness/examples/runs/quickstart/salmon_quant/sample_a", "A", 2, ""]),
        "TximportNode": NodeDefinition("TximportNode", "Import Counts For DESeq2", "ComfyBIO/Differential Expression", [{"name": "salmon_quant_dir", "type": "STRING"}], [{"name": "deseq2_count_matrix", "type": "STRING"}], ["harness/examples/runs/quickstart/salmon_quant", "harness/examples/runs/quickstart/deseq2/count_matrix.csv", ""]),
        "DESeq2AnalysisNode": NodeDefinition("DESeq2AnalysisNode", "DESeq2 Analysis", "ComfyBIO/Differential Expression", [{"name": "count_matrix", "type": "STRING"}], [{"name": "deseq2_results_table", "type": "STRING"}], ["harness/examples/runs/quickstart/deseq2/count_matrix.csv", "harness/examples/fixtures/quickstart/sample_metadata.csv", "harness/examples/runs/quickstart/deseq2/results.csv", "~ condition", ""]),
        "DESeq2VisualizationNode": NodeDefinition("DESeq2VisualizationNode", "DESeq2 Visualization", "ComfyBIO/Visualization", [{"name": "count_matrix", "type": "STRING"}], [{"name": "plot_dir", "type": "STRING"}, {"name": "preview_plot", "type": "IMAGE"}], ["harness/examples/runs/quickstart/deseq2/count_matrix.csv", "harness/examples/runs/quickstart/deseq2/results.csv", "harness/examples/runs/quickstart/plots", "pca,ma,volcano,heatmap"]),
        "ComfyBIOReportNode": NodeDefinition("ComfyBIOReportNode", "ComfyBIO Report", "ComfyBIO/Reporting", [{"name": "results_csv", "type": "STRING"}], [{"name": "report_path", "type": "STRING"}], ["harness/examples/runs/quickstart/deseq2/results.csv", "harness/examples/runs/quickstart/plots", "harness/examples/runs/quickstart/report/comfybio_report.md", ""]),
        "WorkflowJSONOutput": NodeDefinition("WorkflowJSONOutput", "Workflow JSON Export", "ComfyBIO/Orchestration", [{"name": "workflow_json_path", "type": "STRING"}], [{"name": "workflow_json_path", "type": "STRING"}], ["harness/examples/workflows/bulk_rna_seq_salmon_ref.json"]),
    }
