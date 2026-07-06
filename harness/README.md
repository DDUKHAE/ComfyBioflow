# ComfyBIO Harness

ComfyBIO Harness converts a natural-language genomics request into a deterministic ComfyUI workflow export JSON. The first implemented path is `bulk_rna_seq_salmon_ref`, which models FASTQ QC, optional trimming, salmon indexing and quantification, tximport-compatible import, DESeq2 analysis, DESeq2 visualization, report generation, and workflow JSON export.

The code in this directory is intentionally small and registry-driven so future domains can reuse the same parser, planner, node catalog, and workflow builder. Future domains are not treated as runnable until they complete the domain expansion workflow.

See also:

- `docs/quickstart.md`
- `docs/environment.md`
- `docs/custom_nodes.md`
- `docs/domain_expansion.md`
- `docs/artifact_sidecar.md`
- `docs/workflow_validation.md`
- `docs/registry_validation.md`
- `docs/node_activation.md`
- `docs/real_fixture_run.md`
- `examples/case_studies/bulk_rna_seq_public_case_study.md`
