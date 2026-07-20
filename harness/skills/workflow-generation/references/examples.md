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

Executing this graph in ComfyUI currently raises an error — the 7 nodes are construction-only stubs.

## Variant analysis (`variant_analysis_bwa_ref`)

An analysis brief classified as `variant_analysis` produces this 8-stage plan:

1. `variant_input_validator`
2. `bwa_mem2_index` (optional)
3. `bwa_mem2_align`
4. `samtools_markdup`
5. `bcftools_call`
6. `bcftools_filter`
7. `variant_visualization`
8. `variant_report`

## Epigenomics / ATAC-seq (`atac_seq_macs3_ref`)

An analysis brief classified as `epigenomics` produces this 9-stage plan:

1. `atac_input_validator`
2. `atac_fastp_trim`
3. `atac_bwa_mem2_index` (optional)
4. `atac_bwa_mem2_align`
5. `atac_samtools_markdup`
6. `atac_quality_filter`
7. `atac_macs3_callpeak`
8. `atac_peak_visualization`
9. `atac_report`

## Metagenome (`metagenome_kraken2_ref`)

An analysis brief classified as `metagenome` produces this 6-stage plan:

1. `metagenome_input_validator`
2. `metagenome_fastp_trim`
3. `kraken2_classify`
4. `bracken_reestimate`
5. `metagenome_visualization`
6. `metagenome_report`

## Genome assembly (`genome_assembly_spades_ref`)

An analysis brief classified as `genome_assembly` produces this 6-stage plan:

1. `assembly_input_validator`
2. `assembly_fastp_trim`
3. `spades_assemble`
4. `quast_qc`
5. `assembly_visualization`
6. `assembly_report`
