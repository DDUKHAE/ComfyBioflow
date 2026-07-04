# Managed Environment

The official MVP route uses the managed Conda environment named `bulk_rna_seq`.

The checked-in environment file is `harness/envs/bulk_rna_seq.yaml`. It mirrors the REF-only install plan reported by `--check-env`.

## REF-Only Tool Set

Required REF executables:

- `fastp`
- `salmon`
- `Rscript`

Required REF packages:

- `python>=3.11`
- `fastp`
- `salmon`
- `bioconductor-deseq2`
- `bioconductor-tximport`
- `r-ggplot2`
- `r-pheatmap`

Optional ALT tools such as `STAR`, `featureCounts`, and `MultiQC` are not installed by the REF-only setup plan. They require a separate explicit approval when an ALT route or add-on is selected.

## Check Environment

From the repository root:

```bash
PYTHONPATH=harness/src python3 -m bioflow_harness.cli --check-env
```

The command reports:

- whether `bulk_rna_seq` exists
- which REF executables are missing
- detected tool versions when available
- a REF-only install plan
- `approval_required: true`

The checker does not create environments or install packages.

## Real Fixture Execution Gate

Actual fixture execution uses:

```bash
PYTHONPATH=harness/src python3 -m bioflow_harness.cli --run-fixture --fixture-dir harness/examples/fixtures/quickstart --run-output-dir harness/examples/runs/quickstart-real
```

This path is blocked until `--check-env` reports `ready: true`. When blocked, the command exits with code `2` and prints the same REF-only install plan so the user can approve setup explicitly.
