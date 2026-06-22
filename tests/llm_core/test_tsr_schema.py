from llm_core.tsr.schema import DomainTSR, StepRule, ToolChoice, ToolValidity


def test_tool_choice_canonical():
    tc = ToolChoice(tool_id="STAR", validity=ToolValidity.CANONICAL, reason="splice-aware")
    assert tc.tool_id == "STAR"
    assert tc.validity == ToolValidity.CANONICAL


def test_step_rule_contains_tools():
    rule = StepRule(
        step_id="alignment",
        step_name="Genome Alignment",
        condition="data_type == 'short_read'",
        tools=[
            ToolChoice("STAR", ToolValidity.CANONICAL, "splice-aware"),
            ToolChoice("HISAT2", ToolValidity.ALTERNATIVE_VALID, "memory efficient"),
            ToolChoice("minimap2", ToolValidity.INVALID, "long-read only"),
        ],
    )
    assert len(rule.tools) == 3
    assert rule.tools[0].validity == ToolValidity.CANONICAL


def test_domain_tsr_step_count():
    tsr = DomainTSR(
        domain_id="transcriptomics",
        description="Bulk and single-cell RNA-seq analysis",
        steps=[
            StepRule("alignment", "Genome Alignment", "True", []),
            StepRule("de_analysis", "Differential Expression", "True", []),
        ],
    )
    assert len(tsr.steps) == 2
    assert tsr.domain_id == "transcriptomics"
