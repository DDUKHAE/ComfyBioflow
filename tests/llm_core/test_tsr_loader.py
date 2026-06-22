import pytest
from llm_core.tsr.loader import list_domains, load_domain_tsr
from llm_core.tsr.schema import ToolValidity


def test_list_domains_includes_bioinformatics():
    domains = list_domains()
    assert "bioinformatics" in domains


def test_list_domains_includes_transcriptomics():
    domains = list_domains()
    assert "transcriptomics" in domains


def test_load_bioinformatics_tsr():
    tsr = load_domain_tsr("bioinformatics")
    assert tsr.domain_id == "bioinformatics"
    assert len(tsr.steps) >= 1


def test_load_transcriptomics_tsr():
    tsr = load_domain_tsr("transcriptomics")
    assert tsr.domain_id == "transcriptomics"
    step_ids = [s.step_id for s in tsr.steps]
    # step_ids renamed in Task 5: alignment→genome_alignment, de_analysis→differential_expression
    assert "genome_alignment" in step_ids
    assert "differential_expression" in step_ids


def test_transcriptomics_alignment_has_canonical():
    from llm_core.tsr.engine import TSREngine
    tsr = load_domain_tsr("transcriptomics")
    engine = TSREngine(tsr)
    ctx = {"data_type": "short_read", "read_length": 150}
    assert engine.canonical("genome_alignment", ctx) == "STAR"


def test_load_unknown_domain_raises():
    with pytest.raises(FileNotFoundError):
        load_domain_tsr("nonexistent_domain_xyz")
