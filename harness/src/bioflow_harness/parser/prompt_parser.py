from bioflow_harness.models.prompt_contract import AnalysisBrief


def parse_prompt(request_text: str) -> AnalysisBrief:
    text = request_text.lower()

    domain = "bulk_rna_seq" if any(token in text for token in ["bulk rna", "rna-seq", "rnaseq"]) else "unsupported"
    analysis_type = "differential_expression" if any(token in text for token in ["deseq2", "differential", "de "]) else "workflow_generation"

    input_assets: list[str] = []
    if "fastq" in text:
        input_assets.append("fastq")
    if "metadata" in text or "sample" in text:
        input_assets.append("sample_metadata")

    expected_outputs: list[str] = []
    if "salmon" in text or domain == "bulk_rna_seq":
        expected_outputs.append("salmon_quantification")
    if "deseq2" in text or analysis_type == "differential_expression":
        expected_outputs.append("deseq2_results")
    if any(token in text for token in ["plot", "pca", "volcano", "heatmap", "ma plot", "visual"]):
        expected_outputs.append("visualization_artifacts")
    if "report" in text:
        expected_outputs.append("report")

    preferred_tools = [tool for tool in ["fastp", "salmon", "tximport", "deseq2"] if tool in text]

    organism = None
    if "human" in text or "homo sapiens" in text:
        organism = "human"
    elif "mouse" in text or "mus musculus" in text:
        organism = "mouse"

    read_layout = "paired_end" if "paired-end" in text or "paired end" in text else "single_end" if "single-end" in text or "single end" in text else "unknown"

    confidence_notes = []
    if domain == "unsupported":
        confidence_notes.append("No supported domain keyword was found.")

    return AnalysisBrief(
        analysis_type=analysis_type,
        domain=domain,
        input_assets=input_assets,
        organism=organism,
        expected_outputs=expected_outputs,
        preferred_tools=preferred_tools,
        confidence_notes=confidence_notes,
        data_characteristics={"read_layout": read_layout},
    )

