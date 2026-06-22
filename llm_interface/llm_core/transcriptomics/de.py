from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd


def run_deseq2(
    counts_path: str,
    metadata_path: str,
    condition_col: str = "condition",
    reference_level: str = "control",
    output_path: str | None = None,
) -> str:
    """Run DESeq2 differential expression analysis.

    Args:
        counts_path: Path to counts matrix TSV (genes × samples)
        metadata_path: Path to metadata TSV (samples × conditions)
        condition_col: Column name for the condition to test
        reference_level: Reference level for condition (e.g., 'control')
        output_path: Output path for results TSV. If None, uses temp directory.

    Returns:
        Path to results TSV file containing log2FoldChange and padj columns.
    """
    from pydeseq2.dds import DeseqDataSet
    from pydeseq2.default_inference import DefaultInference
    from pydeseq2.ds import DeseqStats

    # Load counts and metadata
    counts = pd.read_csv(counts_path, sep="\t", index_col=0).T
    metadata = pd.read_csv(metadata_path, sep="\t", index_col=0)

    # Align sample order
    common = counts.index.intersection(metadata.index)
    counts = counts.loc[common]
    metadata = metadata.loc[common]

    # Create DESeqDataSet and run DESeq2
    dds = DeseqDataSet(
        counts=counts,
        metadata=metadata,
        design_factors=condition_col,
        ref_level=[condition_col, reference_level],
        refit_cooks=True,
        inference=DefaultInference(n_cpus=1),
    )
    dds.deseq2()

    # Get statistics - contrast: [factor, condition, reference_level]
    # This creates a contrast between the condition and reference_level
    unique_conditions = metadata[condition_col].unique()
    test_condition = [c for c in unique_conditions if c != reference_level][0]

    contrast = [condition_col, test_condition, reference_level]
    stat_res = DeseqStats(dds, contrast=contrast, inference=DefaultInference(n_cpus=1))
    stat_res.summary()
    results = stat_res.results_df

    # Write results
    if output_path is None:
        tmp = tempfile.mkdtemp()
        output_path = str(Path(tmp) / "deseq2_results.tsv")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(output_path, sep="\t")
    return output_path
