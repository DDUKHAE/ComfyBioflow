from bioflow_harness.models.prompt_contract import AnalysisBrief


def parse_prompt(request_text: str) -> AnalysisBrief:
    text = request_text.lower()

    scrna_tokens = ["single-cell", "single cell", "scrna", "10x", "cell ranger", "starsolo", "umap", "marker genes"]
    epigenomics_tokens = [
        "atac-seq", "atac seq", "chromatin accessibility", "open chromatin",
        "peak calling", "macs3", "macs2", "narrowpeak", "chip-seq", "chip seq",
    ]
    metagenome_tokens = [
        "metagenom", "kraken2", "kraken", "bracken", "taxonomic profil",
        "shotgun", "microbiome", "microbial communit",
    ]
    genome_assembly_tokens = [
        "de novo assembly", "genome assembly", "spades", "megahit", "contig",
        "assemble the genome", "isolate genome",
    ]
    variant_tokens = [
        "variant", "germline", "vcf", "bwa-mem2", "bwa mem2", "snp", "genotyp",
        "whole genome", "whole exome", " wgs", " wes", "bcftools",
    ]
    if any(token in text for token in scrna_tokens):
        domain = "scrna_seq"
        analysis_type = "single_cell_analysis"
    elif any(token in text for token in epigenomics_tokens):
        domain = "epigenomics"
        analysis_type = "peak_calling"
    elif any(token in text for token in genome_assembly_tokens):
        domain = "genome_assembly"
        analysis_type = "de_novo_assembly"
    elif any(token in text for token in metagenome_tokens):
        domain = "metagenome"
        analysis_type = "taxonomic_profiling"
    elif any(token in text for token in variant_tokens):
        domain = "variant_analysis"
        analysis_type = "variant_calling"
    else:
        domain = "bulk_rna_seq" if any(token in text for token in ["bulk rna", "rna-seq", "rnaseq"]) else "unsupported"
        analysis_type = "differential_expression" if any(token in text for token in ["deseq2", "differential", "de "]) else "workflow_generation"

    input_assets: list[str] = []
    if "fastq" in text:
        input_assets.append("fastq")
    if "metadata" in text or "sample" in text:
        input_assets.append("sample_metadata")
    if domain in ("variant_analysis", "epigenomics") and "reference" in text:
        input_assets.append("reference_fasta")

    expected_outputs: list[str] = []
    if "salmon" in text or domain == "bulk_rna_seq":
        expected_outputs.append("salmon_quantification")
    if "deseq2" in text or analysis_type == "differential_expression":
        expected_outputs.append("deseq2_results")
    if any(token in text for token in ["plot", "pca", "volcano", "heatmap", "ma plot", "visual"]):
        expected_outputs.append("visualization_artifacts")
    if "report" in text:
        expected_outputs.append("report")
    if domain == "scrna_seq":
        for output in ["cell_filtering", "normalization", "clustering", "umap", "marker_genes"]:
            if output not in expected_outputs:
                expected_outputs.append(output)
    if domain == "variant_analysis":
        for output in ["filtered_vcf", "variant_summary_plot"]:
            if output not in expected_outputs:
                expected_outputs.append(output)
    if domain == "epigenomics":
        for output in ["filtered_bam", "peaks", "peak_summary_plot"]:
            if output not in expected_outputs:
                expected_outputs.append(output)
    if domain == "metagenome":
        for output in ["taxonomic_profile", "abundance_estimates"]:
            if output not in expected_outputs:
                expected_outputs.append(output)
    if domain == "genome_assembly":
        for output in ["assembled_contigs", "assembly_qc_metrics"]:
            if output not in expected_outputs:
                expected_outputs.append(output)

    preferred_tools = [
        tool
        for tool in [
            "fastp", "salmon", "tximport", "deseq2", "cell ranger", "scanpy", "starsolo",
            "bwa-mem2", "samtools", "bcftools", "macs3", "macs2", "kraken2", "bracken",
            "spades", "megahit", "quast",
        ]
        if tool in text
    ]
    if domain == "scrna_seq" and "scanpy" not in preferred_tools:
        preferred_tools.append("scanpy")
    if domain == "variant_analysis" and "bwa-mem2" not in preferred_tools:
        preferred_tools.append("bwa-mem2")
    if domain == "epigenomics" and "macs3" not in preferred_tools:
        preferred_tools.append("macs3")
    if domain == "metagenome" and "kraken2" not in preferred_tools:
        preferred_tools.append("kraken2")
    if domain == "genome_assembly" and "spades" not in preferred_tools:
        preferred_tools.append("spades")

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
