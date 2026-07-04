# Real Fixture Run

This record captures the first successful non-dry-run execution of the official `bulk_rna_seq_salmon_ref` route on the bundled quickstart fixture.

## Environment

Managed Conda environment: `bulk_rna_seq`

Detected REF tool versions:

- `fastp 1.3.6`
- `salmon 2.3.1`
- `Rscript (R) version 4.5.3`

## Command

```bash
PYTHONPATH=harness/src python3 -m bioflow_harness.cli \
  --run-fixture \
  --fixture-dir harness/examples/fixtures/quickstart \
  --run-output-dir harness/examples/runs/quickstart-real-4
```

## Success Evidence

The run completed with `route_id: bulk_rna_seq_salmon_ref` and produced:

- `harness/examples/runs/quickstart-real-4/salmon_quant`
- `harness/examples/runs/quickstart-real-4/deseq2/count_matrix.csv`
- `harness/examples/runs/quickstart-real-4/deseq2/results.csv`
- `harness/examples/runs/quickstart-real-4/plots/pca.png`
- `harness/examples/runs/quickstart-real-4/plots/ma.png`
- `harness/examples/runs/quickstart-real-4/plots/volcano.png`
- `harness/examples/runs/quickstart-real-4/plots/heatmap.png`
- `harness/examples/runs/quickstart-real-4/report/comfybio_report.md`
- `harness/examples/runs/quickstart-real-4/artifacts.sidecar.json`

`file` identifies all four plot outputs as real PNG images, not dry-run placeholders.

## Notes

The tiny fixture uses short synthetic reads, so the runtime sets `fastp --length_required 1` and builds the salmon toy index with `-k 7`. The DESeq2 script first attempts the standard DESeq2 path with `sfType = "poscounts"` and falls back to gene-wise dispersion estimates for tiny fixture data when the default dispersion curve fit is not applicable.
