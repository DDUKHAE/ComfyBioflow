from llm_core.benchmark.query_schema import Difficulty, HeldOutQuery, ToolSpecificity


def test_query_creation():
    q = HeldOutQuery(
        query_id="TR_006",
        domain_id="transcriptomics",
        family="de_analysis",
        nl_text="Use edgeR to find DEGs between treated and control groups.",
        difficulty=Difficulty.EASY,
        tool_specificity=ToolSpecificity.TOOL_SPECIFIED,
        context={"n_samples_per_group": 4, "data_type": "bulk_rna_seq"},
        fixture_path="fixtures/transcriptomics/GSE_example_counts.tsv",
    )
    assert q.query_id == "TR_006"
    assert q.tool_specificity == ToolSpecificity.TOOL_SPECIFIED
    assert q.adversarial_hint_tool is None


def test_adversarial_query():
    q = HeldOutQuery(
        query_id="TR_ADV_001",
        domain_id="transcriptomics",
        family="alignment",
        nl_text="Align these nanopore reads using STAR.",
        difficulty=Difficulty.ADVERSARIAL,
        tool_specificity=ToolSpecificity.ADVERSARIAL,
        context={"data_type": "long_read", "platform": "nanopore"},
        fixture_path="fixtures/transcriptomics/nanopore_reads.fastq",
        adversarial_hint_tool="STAR",
    )
    assert q.adversarial_hint_tool == "STAR"
    assert q.difficulty == Difficulty.ADVERSARIAL


def test_tool_specificity_values():
    assert ToolSpecificity.TOOL_SPECIFIED != ToolSpecificity.GOAL_SPECIFIED
    assert ToolSpecificity.CONTEXT_ONLY != ToolSpecificity.ADVERSARIAL
