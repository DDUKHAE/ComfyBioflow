# Workflow JSON Generation Examples

The official workflow export contains 11 nodes and 10 links for `bulk_rna_seq_salmon_ref`.

Validation should reject:

- unregistered node types
- disconnected or dangling links
- non-sequential node ids
- custom artifact port types outside the MVP `STRING` and `IMAGE` policy

The DESeq2 visualization node includes both:

- `plot_dir` as `STRING`
- `preview_plot` as `IMAGE`
