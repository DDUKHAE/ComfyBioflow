# ComfyBIO Execution & Runtime

This is the one part of the pipeline no skill covers: how registered nodes actually run tools, and what they write. For everything upstream (brief, planning, tool selection, node design, workflow JSON) see `ARCHITECTURE.md` and the `harness/skills/` packages.

## Managed conda environment

Real node execution runs external tools inside a **managed conda environment per domain** — one per `bioflow_harness.runtime.environment.DomainEnvironmentRequirements` (e.g. `bulk_rna_seq`, `variant_analysis`). Tools are invoked as `conda run -n <env_name> <tool> ...` (`runtime/command_runner.py`). Each domain's checked-in environment file lives at `harness/envs/<domain>.yaml` (`harness/envs/bulk_rna_seq.yaml`, `harness/envs/variant_analysis.yaml`).

REF-only tool set (the official route):

- Executables: `fastp`, `salmon`, `Rscript`
- Packages: `python>=3.11`, `fastp`, `salmon`, `bioconductor-deseq2`, `bioconductor-tximport`, `r-ggplot2`, `r-pheatmap`

The R stages call scripts under `harness/scripts/` (`tximport_import.R`, `deseq2_analysis.R`, `deseq2_visualization.R`).

ALT tools such as `STAR`, `featureCounts`, and `MultiQC` are **not** installed by the REF-only setup; selecting them requires an explicit context-routing decision.

Variant analysis REF-only tool set (`variant_analysis_bwa_ref`):

- Executables: `bwa-mem2`, `samtools`, `bcftools`
- Packages: `python>=3.11`, `bwa-mem2`, `samtools`, `bcftools`, `matplotlib`

`gatk4` (GATK HaplotypeCaller) is **not** installed by the REF-only setup; selecting it requires an explicit context-routing decision, same as `STAR`/`featureCounts`/`MultiQC` for the bulk RNA-seq route.

Epigenomics (ATAC-seq) REF-only tool set (`atac_seq_macs3_ref`):

- Executables: `fastp`, `bwa-mem2`, `samtools`, `macs3`
- Packages: `python>=3.11`, `fastp`, `bwa-mem2`, `samtools`, `macs3`, `bedtools`, `matplotlib`

`macs2` and `genrich` are **not** installed by the REF-only setup; selecting either requires an explicit context-routing decision, same as `gatk4` for the variant_analysis route.

Metagenome REF-only tool set (`metagenome_kraken2_ref`):

- Executables: `fastp`, `kraken2`, `bracken`
- Packages: `python>=3.11`, `fastp`, `kraken2`, `bracken`, `matplotlib`

`centrifuge` is **not** installed by the REF-only setup; selecting it requires an explicit context-routing decision, same as `gatk4`/`macs2`/`genrich` for the prior two routes. A Kraken2 database is not bundled — the user points `kraken2_db_dir` at their own downloaded database.

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
