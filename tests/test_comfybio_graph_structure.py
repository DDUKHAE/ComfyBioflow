from bioflow_harness.server.handlers import generate_workflow


def _types(request_text: str) -> list[str]:
    # "mistral" has no CLI integration, so this always exercises the deterministic parser
    # instead of attempting a real codex/claude/gemini subprocess call.
    workflow = generate_workflow({"request_text": request_text, "provider": "mistral"})["workflow"]
    return [node["type"] for node in workflow["nodes"]]


def test_bulk_graph_starts_at_metadata_validator_no_orchestration():
    types = _types("bulk RNA-seq human treated vs control with DESeq2 plots and report")
    assert types[0] == "SampleMetadataValidatorNode"
    assert types[-1] == "PreviewImage"
    assert types[-2] == "ComfyBIOReportNode"
    assert "WorkflowRequestLoader" not in types
    assert "WorkflowJSONOutput" not in types


def test_scrna_graph_starts_at_tenx_count_no_orchestration():
    types = _types("single-cell RNA-seq with scanpy, clustering and umap and marker genes")
    assert types[0] == "TenxCountNode"
    assert "WorkflowRequestLoader" not in types
    assert "WorkflowJSONOutput" not in types


def test_metadata_validator_has_no_upstream_input():
    import nodes

    required = nodes.NODE_CLASS_MAPPINGS["SampleMetadataValidatorNode"].INPUT_TYPES()["required"]
    assert "workflow_request" not in required
    assert "fastq_dir" in required


def test_variant_graph_starts_at_input_validator_ends_at_preview():
    types = _types("germline variant calling with bwa-mem2 on paired-end WGS FASTQs, call and filter variants")
    assert types[0] == "VariantInputValidatorNode"
    assert types[-1] == "PreviewImage"
    assert types[-2] == "VariantReportNode"
    assert "BcftoolsCallNode" in types
    assert "BcftoolsFilterNode" in types


def test_variant_route_resolves_through_stage_mapper():
    from bioflow_harness.planner.stage_mapper import route_for_domain

    assert route_for_domain("variant_analysis") == "variant_analysis_bwa_ref"


def test_variant_prompt_parses_to_variant_analysis_domain():
    from bioflow_harness.parser.prompt_parser import parse_prompt

    brief = parse_prompt("call germline SNPs and indels from WGS FASTQs with bwa-mem2 and bcftools")
    assert brief.domain == "variant_analysis"


def test_atac_graph_starts_at_input_validator_ends_at_preview():
    types = _types("call ATAC-seq peaks from paired-end open chromatin FASTQs with bwa-mem2 and macs3")
    assert types[0] == "AtacInputValidatorNode"
    assert types[-1] == "PreviewImage"
    assert types[-2] == "AtacReportNode"
    assert "Macs3PeakCallingNode" in types
    assert "AtacQualityFilterNode" in types


def test_atac_route_resolves_through_stage_mapper():
    from bioflow_harness.planner.stage_mapper import route_for_domain

    assert route_for_domain("epigenomics") == "atac_seq_macs3_ref"


def test_atac_prompt_parses_to_epigenomics_domain():
    from bioflow_harness.parser.prompt_parser import parse_prompt

    brief = parse_prompt("call peaks from ATAC-seq chromatin accessibility FASTQs with macs3")
    assert brief.domain == "epigenomics"


def test_variant_and_scrna_and_bulk_prompts_still_route_correctly_after_atac_addition():
    from bioflow_harness.parser.prompt_parser import parse_prompt

    assert parse_prompt("bulk RNA-seq human treated vs control with DESeq2 plots and report").domain == "bulk_rna_seq"
    assert parse_prompt("single-cell RNA-seq with scanpy, clustering and umap and marker genes").domain == "scrna_seq"
    assert parse_prompt("call germline SNPs and indels from WGS FASTQs with bwa-mem2 and bcftools").domain == "variant_analysis"


def test_deferred_domains_with_overlapping_vocabulary_stay_unsupported():
    """Regression test for two real bugs caused by the same failure mode: an overly
    generic token in one domain's list silently absorbing a different, unimplemented
    domain's request.

    1. "chip-seq"/"chip seq" were once listed in epigenomics_tokens, so a ChIP-seq
       request silently misrouted to the ATAC-seq route instead of surfacing
       planning_required.
    2. Bare "variant" was once listed in variant_tokens, so a long-read structural-variant
       (Nanopore/PacBio SV calling, e.g. minimap2 + Sniffles) request silently misrouted to
       variant_analysis_bwa_ref, which only implements short-read germline SNP/indel
       calling (bwa-mem2 + bcftools) — a different pipeline shape entirely.

    ChIP-seq, WGBS, Hi-C, and long-read structural-variant calling are all
    architecturally distinct from every implemented route (see domain-bootstrap
    references/examples.md) and must never resolve to an existing domain just because
    they share assay-family vocabulary with one.
    """
    from bioflow_harness.parser.prompt_parser import parse_prompt
    from bioflow_harness.planner.stage_mapper import route_for_domain

    for request_text in [
        "ChIP-seq data to find genome-wide transcription factor binding sites, with an input control sample",
        "WGBS bisulfite sequencing to profile DNA methylation",
        "Hi-C data to analyze chromatin interactions",
        "Long-read Nanopore sequencing to detect structural variants",
    ]:
        domain = parse_prompt(request_text).domain
        assert domain == "unsupported", f"{request_text!r} incorrectly classified as {domain!r}"
        try:
            route_for_domain(domain)
        except ValueError:
            pass
        else:
            raise AssertionError(f"route_for_domain should have raised for domain {domain!r}")


def test_metagenome_graph_starts_at_input_validator_ends_at_preview():
    types = _types("profile the microbial community in this shotgun metagenomic sample with kraken2 and bracken")
    assert types[0] == "MetagenomeInputValidatorNode"
    assert types[-1] == "PreviewImage"
    assert types[-2] == "MetagenomeReportNode"
    assert "Kraken2ClassifyNode" in types
    assert "BrackenAbundanceNode" in types


def test_metagenome_route_resolves_through_stage_mapper():
    from bioflow_harness.planner.stage_mapper import route_for_domain

    assert route_for_domain("metagenome") == "metagenome_kraken2_ref"


def test_metagenome_prompt_parses_to_metagenome_domain():
    from bioflow_harness.parser.prompt_parser import parse_prompt

    brief = parse_prompt("run taxonomic profiling on this shotgun microbiome sample using kraken2")
    assert brief.domain == "metagenome"


def test_all_five_domains_still_route_correctly_after_metagenome_addition():
    from bioflow_harness.parser.prompt_parser import parse_prompt

    assert parse_prompt("bulk RNA-seq human treated vs control with DESeq2 plots and report").domain == "bulk_rna_seq"
    assert parse_prompt("single-cell RNA-seq with scanpy, clustering and umap and marker genes").domain == "scrna_seq"
    assert parse_prompt("call germline SNPs and indels from WGS FASTQs with bwa-mem2 and bcftools").domain == "variant_analysis"
    assert parse_prompt("call ATAC-seq peaks from paired-end open chromatin FASTQs with bwa-mem2 and macs3").domain == "epigenomics"


def test_assembly_graph_starts_at_input_validator_ends_at_preview():
    types = _types("assemble this bacterial isolate genome de novo from paired-end Illumina reads with SPAdes")
    assert types[0] == "AssemblyInputValidatorNode"
    assert types[-1] == "PreviewImage"
    assert types[-2] == "AssemblyReportNode"
    assert "SpadesAssembleNode" in types
    assert "QuastQcNode" in types


def test_assembly_route_resolves_through_stage_mapper():
    from bioflow_harness.planner.stage_mapper import route_for_domain

    assert route_for_domain("genome_assembly") == "genome_assembly_spades_ref"


def test_assembly_prompt_parses_to_genome_assembly_domain():
    from bioflow_harness.parser.prompt_parser import parse_prompt

    brief = parse_prompt("run de novo genome assembly on this bacterial isolate with spades, produce contigs")
    assert brief.domain == "genome_assembly"


def test_all_six_domains_still_route_correctly_after_assembly_addition():
    from bioflow_harness.parser.prompt_parser import parse_prompt

    assert parse_prompt("bulk RNA-seq human treated vs control with DESeq2 plots and report").domain == "bulk_rna_seq"
    assert parse_prompt("single-cell RNA-seq with scanpy, clustering and umap and marker genes").domain == "scrna_seq"
    assert parse_prompt("call germline SNPs and indels from WGS FASTQs with bwa-mem2 and bcftools").domain == "variant_analysis"
    assert parse_prompt("call ATAC-seq peaks from paired-end open chromatin FASTQs with bwa-mem2 and macs3").domain == "epigenomics"
    assert parse_prompt("profile the microbial community in this shotgun metagenomic sample with kraken2 and bracken").domain == "metagenome"
