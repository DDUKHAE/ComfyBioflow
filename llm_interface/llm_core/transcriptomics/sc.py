from __future__ import annotations

import tempfile
from pathlib import Path


def run_sc_preprocess(
    input_path: str,
    min_genes: int = 200,
    min_cells: int = 3,
    n_top_genes: int = 2000,
    output_path: str | None = None,
) -> str:
    import anndata as ad
    import scanpy as sc

    adata = ad.read_h5ad(input_path)
    sc.pp.filter_cells(adata, min_genes=min_genes)
    sc.pp.filter_genes(adata, min_cells=min_cells)
    sc.pp.normalize_total(adata, target_sum=1e4)
    sc.pp.log1p(adata)
    sc.pp.highly_variable_genes(adata, n_top_genes=min(n_top_genes, adata.n_vars))

    out = output_path or str(Path(tempfile.mkdtemp()) / "preprocessed.h5ad")
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    adata.write_h5ad(out)
    return out


def run_sc_cluster(
    input_path: str,
    resolution: float = 0.5,
    algorithm: str = "leiden",
    output_path: str | None = None,
) -> str:
    import anndata as ad
    import scanpy as sc

    adata = ad.read_h5ad(input_path)
    use_hvg = "highly_variable" in adata.var.columns
    sc.pp.pca(adata, use_highly_variable=use_hvg)
    sc.pp.neighbors(adata, n_neighbors=min(10, adata.n_obs - 1))

    if algorithm == "leiden":
        sc.tl.leiden(adata, resolution=resolution)
    elif algorithm == "louvain":
        sc.tl.louvain(adata, resolution=resolution)
    else:
        raise ValueError(f"Unknown clustering algorithm: {algorithm!r}. Use 'leiden' or 'louvain'.")

    out = output_path or str(Path(tempfile.mkdtemp()) / "clustered.h5ad")
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    adata.write_h5ad(out)
    return out


def run_sc_annotate(
    input_path: str,
    marker_genes: dict[str, list[str]],
    output_path: str | None = None,
) -> str:
    """Assign cell type labels to clusters based on marker gene expression."""
    import numpy as np
    import anndata as ad
    import scanpy as sc

    adata = ad.read_h5ad(input_path)
    cluster_col = "leiden" if "leiden" in adata.obs.columns else "louvain"

    cell_types: list[str] = []
    for cluster in adata.obs[cluster_col]:
        best_type = "Unknown"
        best_score = -1.0
        for cell_type, markers in marker_genes.items():
            present = [g for g in markers if g in adata.var_names]
            if not present:
                continue
            score = float(np.mean(adata[adata.obs[cluster_col] == cluster, present].X.mean(axis=0)))
            if score > best_score:
                best_score = score
                best_type = cell_type
        cell_types.append(best_type)

    adata.obs["cell_type"] = cell_types

    out = output_path or str(Path(tempfile.mkdtemp()) / "annotated.h5ad")
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    adata.write_h5ad(out)
    return out
