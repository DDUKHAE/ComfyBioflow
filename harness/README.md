# ComfyBIO Harness

ComfyBIO Harness converts a natural-language genomics request into a runnable ComfyUI workflow JSON. Implemented routes include `bulk_rna_seq_salmon_ref`, which models FASTQ QC, optional trimming, salmon indexing and quantification, tximport-compatible import, DESeq2 analysis, DESeq2 visualization, and report generation, and `scrna_seq_scanpy_ref`, which models a 10x/Scanpy single-cell workflow through QC, normalization, clustering, UMAP/marker visualization, and reporting.

The code in this directory is intentionally small and registry-driven so future domains can reuse the same parser, planner, node catalog, and workflow builder. Future domains are not treated as runnable until they complete the domain expansion workflow.

See also:

- `docs/ARCHITECTURE.md` — system map: product wiring, pipeline, node catalog, registry schema, and stage → skill index
- `docs/execution.md` — conda runtime and artifact sidecar
- `skills/` — per-stage skill packages (workflow discovery, tool ranking, node implementation, workflow JSON generation)
- `examples/case_studies/bulk_rna_seq_public_case_study.md`
