# Workflow Generation Examples

## Bulk RNA-seq (`bulk_rna_seq_salmon_ref`)

An analysis brief classified as `bulk_rna_seq` produces this 9-stage plan:

1. `sample_metadata_validator`
2. `fastp_qc`
3. `fastp_trim` (optional)
4. `salmon_index`
5. `salmon_quant`
6. `tximport_import`
7. `deseq2_analysis`
8. `comfybio_deseq2_visualization`
9. `comfybio_report`

The visualization stage additionally connects to a builtin `PreviewImage` node in the exported graph.

## scRNA-seq (`scrna_seq_scanpy_ref`)

An analysis brief classified as `scrna_seq` produces this 7-stage plan:

1. `tenx_count`
2. `scanpy_qc`
3. `scanpy_normalize`
4. `scanpy_cluster`
5. `scanpy_marker_genes`
6. `comfybio_scrna_visualization`
7. `comfybio_scrna_report`
