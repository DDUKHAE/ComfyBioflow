from llm_core.gold.schema import AlternativeGold, CanonicalGold, TieredGold, Verdict


def test_tiered_gold_creation():
    gold = TieredGold(
        query_id="TR_006",
        family="de_analysis",
        context={"n_samples_per_group": 4},
        canonical=CanonicalGold(
            tools=["edgeR"],
            expected_output_criteria={"top10_overlap_min": 1.0},
        ),
        alternatives=AlternativeGold(
            tools=["DESeq2"],
            functional_equivalence_criteria={"top10_overlap_with_canonical": ">= 0.80"},
        ),
        invalid_tools=["kallisto", "STAR"],
    )
    assert gold.query_id == "TR_006"
    assert "edgeR" in gold.canonical.tools
    assert "DESeq2" in gold.alternatives.tools
    assert "kallisto" in gold.invalid_tools


def test_verdict_values():
    assert Verdict.CORRECT_CANONICAL != Verdict.CORRECT_ALTERNATIVE
    assert Verdict.CRITICAL_ERROR != Verdict.INCORRECT
