# Bulk RNA-seq Public Case Study

This document records the paper-evidence run target for the official `bulk_rna_seq_salmon_ref` route. It is not the fast CI gate; the bundled quickstart fixture remains the routine acceptance fixture.

## Accession

Candidate accession: `GSE60450`, a small public bulk RNA-seq study commonly used in RNA-seq workflow examples.

## Source

NCBI Gene Expression Omnibus. Raw reads should be obtained from the linked SRA records for the selected subset.

## Usage Notes

Before publishing derived artifacts, confirm the GEO record and linked publication terms allow redistribution of any downloaded reads or processed subsets. Repository-shipped artifacts should prefer provenance, commands, metadata, and generated summaries over large raw data.

## Sample Subset

Use a small balanced subset with at least two samples per condition so the DESeq2 stage has replicated conditions. Record selected sample accessions in the run log before execution.

## Reference

Use a matching transcriptome FASTA for the study organism and record the reference source, release, checksum, and indexing command in the final run report.

## Tool Versions

Record versions for `fastp`, `salmon`, `R`, `tximport`, `DESeq2`, `ggplot2`, and `pheatmap` from the managed `bulk_rna_seq` environment.

## Expected Artifacts

- salmon quantification directories for every selected sample
- tximport-compatible count matrix
- DESeq2 results table
- PCA, MA, volcano, and heatmap plot outputs
- final ComfyBIO markdown report
- artifact sidecar JSON with sample set and reference identifiers
