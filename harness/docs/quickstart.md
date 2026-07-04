# ComfyBIO Harness Quickstart

This quickstart exercises the official `bulk_rna_seq_salmon_ref` harness path from a natural-language prompt to a ComfyUI workflow export JSON.

## Inputs

- Prompt: `harness/examples/prompts/bulk_rna_seq_salmon_ref.txt`
- Registry: `harness/registry/tool_selection_registry.yaml`
- Fixture transcriptome: `harness/examples/fixtures/quickstart/toy_transcriptome.fasta`
- Fixture metadata: `harness/examples/fixtures/quickstart/sample_metadata.csv`
- Fixture FASTQ files:
  - `sample_a_R1.fastq`
  - `sample_a_R2.fastq`
  - `sample_b_R1.fastq`
  - `sample_b_R2.fastq`
  - `sample_c_R1.fastq`
  - `sample_c_R2.fastq`
  - `sample_d_R1.fastq`
  - `sample_d_R2.fastq`

The fixture has two `control` samples and two `treatment` samples so the DESeq2 stage has replicated conditions.

## Expected REF Path

1. Request payload loading
2. Sample metadata validation
3. FASTQ QC with `fastp`
4. Optional trimming with `fastp`
5. `salmon index`
6. `salmon quant`
7. `tximport`-compatible import
8. `DESeq2` differential expression
9. DESeq2 visualization artifacts
10. ComfyBIO report generation
11. ComfyUI workflow JSON export

`MultiQC` remains an optional ALT route for enhanced QC aggregation and is not part of the MVP completion gate.

## Generate Workflow JSON

From the repository root:

```bash
PYTHONPATH=harness/src python3 -m bioflow_harness.cli "$(cat harness/examples/prompts/bulk_rna_seq_salmon_ref.txt)" --registry harness/registry/tool_selection_registry.yaml --output harness/examples/workflows/bulk_rna_seq_salmon_ref.json
```

The default output path is `harness/examples/workflows/bulk_rna_seq_salmon_ref.json`.

## Check Managed Environment

The official route expects a managed Conda environment named `bulk_rna_seq`. Check the environment before attempting real execution:

```bash
PYTHONPATH=harness/src python3 -m bioflow_harness.cli --check-env
```

This reports a REF-only installation plan and marks it as approval-required. It does not install packages.

## Run REF Fixture Dry-Run

The dry-run runtime records the managed Conda commands that would be used for `fastp`, `salmon`, `tximport`, and `DESeq2`, then writes small placeholder artifacts that match the official REF contract.

```bash
PYTHONPATH=harness/src python3 -m bioflow_harness.cli --run-fixture-dry-run --fixture-dir harness/examples/fixtures/quickstart --run-output-dir harness/examples/runs/quickstart
```

Expected artifacts include:

- `artifacts.sidecar.json`
- `qc/fastp.json`
- `trimmed/`
- `salmon_index/`
- `salmon_quant/<sample_id>/quant.sf`
- `deseq2/count_matrix.csv`
- `deseq2/results.csv`
- `plots/pca.png`
- `plots/ma.png`
- `plots/volcano.png`
- `plots/heatmap.png`
- `report/comfybio_report.md`

## Run REF Fixture With Managed Conda

After `--check-env` reports `ready: true`, the same fixture can be run through the managed Conda execution path:

```bash
PYTHONPATH=harness/src python3 -m bioflow_harness.cli --run-fixture --fixture-dir harness/examples/fixtures/quickstart --run-output-dir harness/examples/runs/quickstart-real
```

If the `bulk_rna_seq` environment or required REF tools are missing, this command exits with code `2` and prints the approval-required REF-only install plan. It does not create the environment or install packages by itself.

The R stages call concrete scripts under `harness/scripts/`:

- `tximport_import.R`
- `deseq2_analysis.R`
- `deseq2_visualization.R`
