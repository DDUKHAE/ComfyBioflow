# Workflow JSON Generation Examples

The official workflow export contains 10 nodes and 9 links for `bulk_rna_seq_salmon_ref` (9 registry stages plus one builtin `PreviewImage`).

Validation should reject:

- unregistered node types
- disconnected or dangling links
- non-sequential node ids
- custom artifact port types outside the MVP `STRING` and `IMAGE` policy

The DESeq2 visualization node includes both:

- `plot_dir` as `STRING`
- `preview_plot` as `IMAGE`
