from bioflow_harness.server.handlers import generate_workflow


def _types(request_text: str) -> list[str]:
    workflow = generate_workflow({"request_text": request_text})["workflow"]
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
