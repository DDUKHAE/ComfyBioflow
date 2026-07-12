# ComfyBIO Execution & Runtime

This is the one part of the pipeline no skill covers: how registered nodes actually run tools, and what they write. For everything upstream (brief, planning, tool selection, node design, workflow JSON) see `ARCHITECTURE.md` and the `harness/skills/` packages.

## Managed conda environment

Real node execution runs external tools inside a managed conda environment named `bulk_rna_seq` (`runtime/environment.py::CONDA_ENV_NAME`, `nodes/stage_commands.py::ENV_NAME`). Tools are invoked as `conda run -n bulk_rna_seq <tool> ...` (`runtime/command_runner.py`). The checked-in environment file is `harness/envs/bulk_rna_seq.yaml`.

REF-only tool set (the official route):

- Executables: `fastp`, `salmon`, `Rscript`
- Packages: `python>=3.11`, `fastp`, `salmon`, `bioconductor-deseq2`, `bioconductor-tximport`, `r-ggplot2`, `r-pheatmap`

The R stages call scripts under `harness/scripts/` (`tximport_import.R`, `deseq2_analysis.R`, `deseq2_visualization.R`).

ALT tools such as `STAR`, `featureCounts`, and `MultiQC` are **not** installed by the REF-only setup; selecting them requires an explicit context-routing decision.

## Execution gating

A node runs real tools only when the environment and inputs validate:

- Input/asset and environment validation happens once at the entry `SampleMetadataValidatorNode`.
- If the `bulk_rna_seq` environment or a required REF executable is missing, execution surfaces a node error rather than silently producing placeholder output.
- Sample discovery is CSV-first (`sample_metadata.csv`) with a folder-scan fallback.

> `python -m bioflow_harness.cli --check-env` / `--run-fixture` remain as a **legacy** developer aid for exercising the pipeline outside ComfyUI. They are not the product path.

## Artifact sidecar

ComfyUI passes bioinformatics outputs between nodes as plain `STRING` paths. ComfyBIO records richer artifact meaning in `artifacts.sidecar.json`, written beside each run output directory by `runtime/artifact_sidecar.py`.

Each sidecar contains:

- `route_id`
- `artifact_count`
- artifact entries, each with:
  - `artifact_id`
  - `artifact_type`
  - `path`
  - `producer_stage_id`
  - `exists_at_validation_time`

Validate a sidecar from Python:

```python
from pathlib import Path
from bioflow_harness.runtime.artifact_sidecar import validate_artifact_sidecar

validate_artifact_sidecar(Path("harness/examples/runs/quickstart/artifacts.sidecar.json"))
```
