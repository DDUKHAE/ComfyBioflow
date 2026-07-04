# Workflow Generation Examples

The official route sequence is:

1. `workflow_request_loader`
2. `sample_metadata_validator`
3. `fastp_qc`
4. `fastp_trim`
5. `salmon_index`
6. `salmon_quant`
7. `tximport_import`
8. `deseq2_analysis`
9. `comfybio_deseq2_visualization`
10. `comfybio_report`
11. `workflow_json_output`

