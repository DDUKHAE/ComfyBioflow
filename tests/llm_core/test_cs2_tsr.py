from llm_core.tsr.loader import load_domain_tsr
from llm_core.tsr.engine import TSREngine

_REQUIRED_STEPS = [
    "raw_qc", "adapter_trimming", "genome_alignment", "pseudo_alignment",
    "read_quantification", "differential_expression", "pathway_enrichment",
    "sc_preprocessing", "sc_clustering", "sc_annotation",
    "sc_trajectory", "visualization",
]


def test_transcriptomics_tsr_has_all_12_steps():
    tsr = load_domain_tsr("transcriptomics")
    step_ids = {s.step_id for s in tsr.steps}
    for required in _REQUIRED_STEPS:
        assert required in step_ids, f"Missing step: {required}"


def test_adapter_trimming_canonical_is_fastp():
    tsr = load_domain_tsr("transcriptomics")
    engine = TSREngine(tsr)
    assert engine.canonical("adapter_trimming", {}) == "fastp"


def test_genome_alignment_short_read_canonical_is_star():
    tsr = load_domain_tsr("transcriptomics")
    engine = TSREngine(tsr)
    ctx = {"data_type": "short_read", "read_length": 150}
    assert engine.canonical("genome_alignment", ctx) == "STAR"


def test_genome_alignment_long_read_star_is_invalid():
    from llm_core.tsr.schema import ToolValidity
    tsr = load_domain_tsr("transcriptomics")
    engine = TSREngine(tsr)
    ctx = {"data_type": "long_read"}
    assert engine.is_valid("genome_alignment", "STAR", ctx) == ToolValidity.INVALID


def test_de_small_sample_canonical_is_edger():
    tsr = load_domain_tsr("transcriptomics")
    engine = TSREngine(tsr)
    assert engine.canonical("differential_expression", {"n_samples_per_group": 3}) == "edgeR"


def test_de_large_sample_canonical_is_deseq2():
    tsr = load_domain_tsr("transcriptomics")
    engine = TSREngine(tsr)
    assert engine.canonical("differential_expression", {"n_samples_per_group": 8}) == "DESeq2"


def test_sc_clustering_leiden_canonical():
    tsr = load_domain_tsr("transcriptomics")
    engine = TSREngine(tsr)
    assert engine.canonical("sc_clustering", {"assay": "scrna_seq"}) == "leiden"


def test_sc_clustering_kmeans_invalid():
    from llm_core.tsr.schema import ToolValidity
    tsr = load_domain_tsr("transcriptomics")
    engine = TSREngine(tsr)
    assert engine.is_valid("sc_clustering", "kmeans", {"assay": "scrna_seq"}) == ToolValidity.INVALID
