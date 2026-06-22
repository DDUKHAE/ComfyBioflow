def test_transcriptomics_package_importable():
    from llm_core.transcriptomics import de, sc, qc, align
    assert de is not None
    assert sc is not None
    assert qc is not None
    assert align is not None


def test_fixtures_exist():
    from pathlib import Path
    base = Path(__file__).parent.parent / "fixtures" / "transcriptomics"
    assert (base / "counts_small.tsv").exists()
    assert (base / "metadata.tsv").exists()
    assert (base / "reads_R1.fastq").exists()


def test_run_deseq2_produces_result_tsv():
    import tempfile
    from pathlib import Path
    from llm_core.transcriptomics.de import run_deseq2

    fixtures = Path(__file__).parent.parent / "fixtures" / "transcriptomics"
    with tempfile.TemporaryDirectory() as tmp:
        out = run_deseq2(
            counts_path=str(fixtures / "counts_small.tsv"),
            metadata_path=str(fixtures / "metadata.tsv"),
            condition_col="condition",
            reference_level="control",
            output_path=str(Path(tmp) / "results.tsv"),
        )
        assert Path(out).exists()
        import pandas as pd
        df = pd.read_csv(out, sep="\t", index_col=0)
        assert "log2FoldChange" in df.columns
        assert "padj" in df.columns
        assert len(df) == 20  # 20 genes


def test_run_deseq2_detects_upregulated_genes():
    import tempfile
    from pathlib import Path
    from llm_core.transcriptomics.de import run_deseq2
    import pandas as pd

    fixtures = Path(__file__).parent.parent / "fixtures" / "transcriptomics"
    with tempfile.TemporaryDirectory() as tmp:
        out = run_deseq2(
            counts_path=str(fixtures / "counts_small.tsv"),
            metadata_path=str(fixtures / "metadata.tsv"),
            output_path=str(Path(tmp) / "results.tsv"),
        )
        df = pd.read_csv(out, sep="\t", index_col=0)
        # GENE_001~005 are 2x upregulated: log2FC ≈ 1
        sig = df[(df["padj"] < 0.05) & (df["log2FoldChange"] > 0.5)]
        assert len(sig) >= 3
