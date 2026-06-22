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


def _make_synthetic_adata(tmp_dir: str) -> str:
    """100 cells × 200 genes synthetic AnnData."""
    import tempfile
    import numpy as np
    import anndata as ad
    import pandas as pd
    from pathlib import Path

    rng = np.random.default_rng(42)
    X = rng.negative_binomial(5, 0.3, size=(100, 200)).astype(float)
    obs = pd.DataFrame({"cell_type": ["unknown"] * 100}, index=[f"cell_{i}" for i in range(100)])
    var = pd.DataFrame(index=[f"GENE_{i:04d}" for i in range(200)])
    adata = ad.AnnData(X=X, obs=obs, var=var)
    path = str(Path(tmp_dir) / "synthetic.h5ad")
    adata.write_h5ad(path)
    return path


def test_run_sc_preprocess_adds_normalized_layer():
    import tempfile
    from pathlib import Path
    from llm_core.transcriptomics.sc import run_sc_preprocess
    import anndata as ad

    with tempfile.TemporaryDirectory() as tmp:
        input_path = _make_synthetic_adata(tmp)
        out = run_sc_preprocess(
            input_path=input_path,
            min_genes=5,
            min_cells=3,
            n_top_genes=100,
            output_path=str(Path(tmp) / "preprocessed.h5ad"),
        )
        assert Path(out).exists()
        adata = ad.read_h5ad(out)
        assert "highly_variable" in adata.var.columns


def test_run_sc_cluster_adds_cluster_column():
    import tempfile
    from pathlib import Path
    from llm_core.transcriptomics.sc import run_sc_preprocess, run_sc_cluster
    import anndata as ad

    with tempfile.TemporaryDirectory() as tmp:
        input_path = _make_synthetic_adata(tmp)
        pre = run_sc_preprocess(
            input_path=input_path,
            min_genes=5,
            min_cells=3,
            n_top_genes=100,
            output_path=str(Path(tmp) / "pre.h5ad"),
        )
        out = run_sc_cluster(
            input_path=pre,
            resolution=0.3,
            algorithm="leiden",
            output_path=str(Path(tmp) / "clustered.h5ad"),
        )
        assert Path(out).exists()
        adata = ad.read_h5ad(out)
        assert "leiden" in adata.obs.columns
        assert adata.obs["leiden"].nunique() >= 1
