# ComfyBIO Slice 3: Real Node Execution — Design

Date: 2026-07-10
Status: Approved (design), pending implementation plan

## Context

Slices 1–2 wired the ComfyBIO panel to the deterministic backend, auto-load the generated
graph onto the ComfyUI canvas, and inject the user's real resource paths into node widgets.
But the loaded graph still does not execute: the bulk RNA-seq ComfyUI node classes in
`nodes/ref_nodes.py` mostly lack a `run()` method, so clicking Queue/Run does nothing.

A complete per-stage execution layer already exists under `harness/src/bioflow_harness/runtime/`
(`ref_nodes.py` `*NodeRuntime` classes, `command_runner.py`, `environment.py`,
`ref_workflow.py`). That layer is CLI/fixture-shaped: it is driven by `run_ref_fixture()` as
one monolithic function and is coupled to `QuickstartFixture` (fixed filenames). It is **not**
reused wholesale here (see decisions below).

This document specifies **Slice 3**: give the bulk RNA-seq ComfyUI nodes working `run()`
methods that shell out to real tools in a conda environment, so that loading and running the
generated graph executes the pipeline on the quickstart fixture end to end.

### Settled decisions (from brainstorming)

- **Completion signal = real conda execution, environment-gated.** Nodes run real
  `fastp`/`salmon`/`Rscript` (DESeq2) via `conda run`. If the environment is not ready, the
  entry node raises with the approval-required install plan. No default dry-run completion.
- **conda env is per-domain, not per-tool.** One env, `bulk_rna_seq`, contains all bulk tools
  (`fastp`, `salmon`, `Rscript` + Bioconductor DESeq2/tximport). This matches the existing
  `runtime/environment.py`.
- **Environment + input validation happens once, at the entry data-input node.** The first
  node that consumes real data (`SampleMetadataValidatorNode`) validates the conda env and the
  input files. Downstream nodes assume readiness and do not re-check (avoids per-node probe
  cost and repeated activation).
- **Execution logic is written fresh in `nodes/`, not shared with `runtime/ref_nodes.py`.**
  The runtime layer stays as the CLI path. The ComfyUI nodes get their own execution code.
  Duplicated tool argv is accepted; it is confined to one module (`nodes/stage_commands.py`)
  to bound the maintenance cost. The generic, fixture-independent helpers
  (`runtime.command_runner`, `runtime.environment`) *are* reused.
- **Sample discovery: metadata CSV first, folder-scan fallback.** `load_samples(fastq_dir,
  metadata_csv)` reads the CSV when present; otherwise it scans `fastq_dir` by filename
  convention (`_R1/_R2`, `_1/_2`) and pairs reads with `condition="unknown"`.
- **Remove the two orchestration nodes from generated graphs.** `WorkflowRequestLoader` and
  `WorkflowJSONOutput` duplicate what the panel already does (the panel owns NL→plan and holds
  the workflow JSON it loads via `app.loadGraphData`). Every generated workflow now starts at
  `SampleMetadataValidatorNode` and ends at `ComfyBIOReportNode` (plus `PreviewImage`).

## Goal (Slice 3)

Loading the bulk RNA-seq graph and running it in ComfyUI executes fastp QC → fastp trim →
salmon index → salmon quant → tximport → DESeq2 → DESeq2 visualization → report on the
quickstart fixture, producing real artifacts on disk, with the conda environment validated
once at the entry node.

### In scope

- `run()` on the nine bulk stage nodes: `SampleMetadataValidatorNode`, `FastpQCNode`,
  `FastpTrimNode`, `SalmonIndexNode`, `SalmonQuantNode`, `TximportNode`,
  `DESeq2AnalysisNode`, `DESeq2VisualizationNode`, `ComfyBIOReportNode`.
- `nodes/sample_loading.py`: `load_samples` (CSV-first, folder-scan fallback).
- `nodes/stage_commands.py`: per-stage conda argv builders (single home for tool commands).
- Environment + input-file gate on `SampleMetadataValidatorNode`.
- `DESeq2VisualizationNode` additionally emits a ComfyUI `IMAGE` tensor for `PreviewImage`.
- Remove `WorkflowRequestLoader` / `WorkflowJSONOutput` from both routes (registry-driven),
  make the first stage node a root node, and clean up all references.

### Out of scope (deferred)

- **Parallel per-sample processing** — sequential per-sample loop is correct and sufficient;
  parallelism is a later optimization.
- **scRNA-seq node execution** — scRNA nodes keep their current non-executing behavior; only
  their graph is adjusted structurally (orchestration nodes removed, `TenxCountNode` becomes
  the root) so the graph still loads/validates.
- **Claude brief extraction** — Slice 4.
- **condition inference in the folder-scan fallback** — falls back to `condition="unknown"`;
  DESeq2 still requires real condition metadata (documented limitation).
- **Reconciling / removing `workflow_regenerator.py`** — it is a separate audit path using the
  abandoned per-sample graph-expansion model; this slice only keeps it consistent (drops the
  two removed node types) so its tests stay green. Its broader fate is tracked as tech-debt.

### Completion signal

With the `bulk_rna_seq` conda env present, the user opens the panel, clicks Generate (graph
loads starting at `SampleMetadataValidatorNode`), then Runs the graph in ComfyUI. The pipeline
executes on the quickstart fixture and writes artifacts (`qc/`, `trimmed/`, `salmon_index/`,
`salmon_quant/`, `deseq2/`, `plots/`, `report/`) under the output directory, and the
`PreviewImage` node shows a DESeq2 plot. With the env absent, running the graph fails at
`SampleMetadataValidatorNode` with the install-plan message.

## Architecture

### Graph structure change (registry is the source of truth)

Route stages are defined in `harness/registry/tool_selection_registry.yaml` and flow through
`WorkflowPlanner.plan` → `WorkflowBuilder.build`. Removing the two orchestration stages there
propagates automatically:

- Bulk route: drop `request_loading` (→ `WorkflowRequestLoader`) and `workflow_export`
  (→ `WorkflowJSONOutput`). New order: `metadata_validation` → `read_qc` → `trimming` →
  `salmon_index` → `salmon_quant` → `tximport_import` → `deseq2_analysis` →
  `deseq2_visualization` → `reporting`.
- scRNA route: drop the same two stages; `tenx_count` becomes the first stage.

Consequent changes:

- `node_catalog.py`: `SampleMetadataValidatorNode` (bulk) and `TenxCountNode` (scRNA) lose
  their `workflow_request` input (`inputs: []`), becoming root nodes. Remove the
  `WorkflowRequestLoader` and `WorkflowJSONOutput` catalog entries.
- `nodes/ref_nodes.py`: remove the `workflow_request` / upstream `forceInput` from the two new
  root nodes; delete the `WorkflowRequestLoader` and `WorkflowJSONOutput` classes.
- `nodes/registry.py`: drop the two classes from `NODE_CLASS_MAPPINGS`.
- `workflow_builder.py`: remove the `WorkflowRequestLoader` / `WorkflowJSONOutput` special
  cases in `_widgets_for_stage`.
- `workflow_regenerator.py`: drop the two node specs so `catalog[node_type]` lookups stay valid.
- Update slice 1/2 tests asserting node 1 == `WorkflowRequestLoader`, node counts, or the
  export node.

### Per-node execution model

ComfyUI's executor calls each node's `FUNCTION` (`run`) independently, in DAG order. Each bulk
stage node:

- Declares `RETURN_TYPES` (`("STRING",)`, except `DESeq2VisualizationNode` → `("STRING",
  "IMAGE")`) and returns its **primary output path** as the STRING output, which the next
  node receives on its `forceInput` upstream slot.
- Reads its **injected widget paths** for actual I/O (ResourceBindings injected consistent,
  derived paths in Slice 2, so widget paths and upstream-produced paths agree by construction).
  The upstream STRING enforces execution ordering.
- Accepts optional `runner` and `probe` parameters (dependency injection) defaulting to the
  real `CondaCommandRunner` / `CondaEnvironmentProbe`; tests pass a `DryRunCommandRunner` /
  fake probe so the suite needs no conda.

### Sample loading — `nodes/sample_loading.py`

```
@dataclass(frozen=True) Sample: sample_id, condition, fastq_1: Path, fastq_2: Path | None
load_samples(fastq_dir: Path, metadata_csv: Path | str | None) -> list[Sample]
```

- If `metadata_csv` exists: parse `sample_id, condition, fastq_1, fastq_2`; resolve FASTQ paths
  relative to their directory; reuse the column/shape rules already in
  `runtime/fixture_validation.py` where practical.
- Else: scan `fastq_dir` for FASTQ files, pair `_R1/_R2` or `_1/_2` by stem, set
  `condition="unknown"`, derive `sample_id` from the stem.
- Empty result raises a clear error.

### Stage commands — `nodes/stage_commands.py`

Pure argv builders returning `conda_command("bulk_rna_seq", tool, *args)` lists, grounded in
the existing `runtime/ref_nodes.py` invocations (single home for all bulk tool commands):
`fastp_qc_argv`, `fastp_trim_argv`, `salmon_index_argv`, `salmon_quant_argv`, `tximport_argv`,
`deseq2_argv`, `deseq2_viz_argv`. The report step is pure Python (no external tool).

### Environment gate — entry node

`SampleMetadataValidatorNode.run()`:

1. `validate_bulk_rna_seq_environment(probe)`; if `not report.ready`, raise
   `EnvironmentNotReadyError` (carries the approval-required install plan) — surfaced by
   ComfyUI as a node error.
2. Verify `fastq_dir` and (if provided) `metadata_csv` exist; run `load_samples` and validate
   samples (e.g. ≥2 samples per condition for DESeq2, mirroring the fixture rule).
3. Return the validated metadata path (STRING) to downstream nodes.

Because this node is upstream of all others, a failure aborts the whole prompt before any tool
runs. ComfyUI output caching may skip re-execution when inputs are unchanged; this is benign
because a passing env implies readiness and a failing env aborts the run (nothing cached).

### Per-node I/O contracts

| Node | Reads | Runs | Returns |
|------|-------|------|---------|
| SampleMetadataValidator | fastq_dir, metadata_csv | env + input validation, load_samples | metadata path (STRING) |
| FastpQC | fastq_dir, metadata_csv, qc_dir | fastp per sample → JSON/HTML in qc_dir | qc_dir |
| FastpTrim | fastq_dir, metadata_csv, trimmed_dir | fastp trim per sample → trimmed_dir | trimmed_dir |
| SalmonIndex | transcriptome_fasta, salmon_index_dir | salmon index | salmon_index_dir |
| SalmonQuant | salmon_index_dir, trimmed reads (per sample), salmon_quant_dir | salmon quant per sample | salmon_quant_dir |
| Tximport | salmon_quant_dir, metadata_csv, count_matrix | Rscript tximport → count matrix | count_matrix path |
| DESeq2Analysis | count_matrix, metadata_csv, results_csv | Rscript DESeq2 → results.csv | results_csv path |
| DESeq2Visualization | count_matrix, results_csv, plot_dir | Rscript plots → PNGs; load a representative PNG → IMAGE tensor | (plot_dir STRING, IMAGE) |
| ComfyBIOReport | results_csv, plot_dir, report_path | assemble Markdown (pure Python) | report_path |

`SalmonQuant` locates each sample's **trimmed** reads under the trimmed output dir by
`sample_id` (consistent with `FastpTrim`), not the raw input FASTQ.

### Preview image handling

`DESeq2VisualizationNode` returns a ComfyUI `IMAGE` tensor (loaded from a representative plot
PNG via ComfyUI's own Python: PIL/numpy/torch, which live in the ComfyUI process, not the
`bulk_rna_seq` conda env). The builder already links its IMAGE output slot to `PreviewImage`.

## Data flow

```
Panel Generate → workflow JSON (root = SampleMetadataValidatorNode) → app.loadGraphData
User Runs graph in ComfyUI:
  SampleMetadataValidator.run(fastq_dir, metadata_csv)
    → validate_bulk_rna_seq_environment(probe)   # gate, once
    → load_samples(fastq_dir, metadata_csv)       # CSV-first, scan fallback
    → return metadata_path
  FastpQC → FastpTrim → SalmonIndex → SalmonQuant → Tximport
    → DESeq2 → DESeq2Viz ─┬→ Report
                          └→ PreviewImage (IMAGE)
  each node: runner.run(<stage>_argv(...)) per sample/aggregate → returns output path
```

## Error handling

- **Env not ready** → `EnvironmentNotReadyError` at the entry node with the install plan.
- **Missing input files** → clear error at the entry node before any tool runs.
- **Tool failure** → `CondaCommandRunner` raises `RuntimeError` with the failing argv + stderr,
  surfaced on the node that ran it.
- **Folder-scan fallback + DESeq2** → `condition="unknown"` cannot satisfy DESeq2's contrast;
  DESeq2 fails with a clear "condition metadata required" message. QC/quant/tximport succeed.
- Unexpected exceptions propagate as ComfyUI node errors (route-handler JSON hardening remains
  the deferred Slice-1 item and is unrelated to graph execution).

## Testing

- `load_samples`: CSV parsing; folder-scan `_R1/_R2` pairing; empty/missing errors.
- Stage argv builders: exact `conda run -n bulk_rna_seq ...` argv per stage (no execution).
- Node `run()` with an injected `DryRunCommandRunner` + fake probe: asserts the expected
  commands are recorded, output subdirectories are created, and the returned path is correct —
  no conda required in CI.
- Entry-node gate: fake probe reporting `not ready` → `run()` raises `EnvironmentNotReadyError`;
  missing input files → validation error.
- Graph structure: generated bulk workflow starts at `SampleMetadataValidatorNode`, ends at
  `ComfyBIOReportNode`, contains no `WorkflowRequestLoader` / `WorkflowJSONOutput`, and still
  passes `validate_workflow_export`; the schema-drift guard (node `INPUT_TYPES` vs catalog
  widgets) still holds after the root-node input change.
- Manual/integration: real `bulk_rna_seq` env + quickstart fixture → run the graph in ComfyUI,
  confirm artifacts and the DESeq2 preview.

## File/module summary

```
harness/registry/tool_selection_registry.yaml     # MODIFY: drop request_loading + workflow_export stages (both routes)
nodes/sample_loading.py                            # NEW: Sample, load_samples (CSV-first + folder-scan)
nodes/stage_commands.py                            # NEW: per-stage conda argv builders
nodes/ref_nodes.py                                 # MODIFY: run() on 9 bulk nodes; root-node input change; delete 2 orchestration classes
nodes/registry.py                                  # MODIFY: drop 2 classes from NODE_CLASS_MAPPINGS
harness/src/bioflow_harness/comfy/node_catalog.py  # MODIFY: root-node inputs=[]; remove 2 catalog entries
harness/src/bioflow_harness/comfy/workflow_builder.py       # MODIFY: remove 2 special cases
harness/src/bioflow_harness/comfy/workflow_regenerator.py   # MODIFY: drop 2 node specs (consistency)
tests/test_comfybio_sample_loading.py              # NEW
tests/test_comfybio_stage_commands.py              # NEW
tests/test_comfybio_node_execution.py              # NEW: run() with dry-run runner + gate
tests/test_comfybio_graph_structure.py             # NEW: orchestration nodes absent, root = validator
tests/ (slice 1/2)                                 # MODIFY: update node-order / count / export-node assertions
```

Reused unchanged: `runtime/command_runner.py` (`conda_command`, `CondaCommandRunner`,
`DryRunCommandRunner`), `runtime/environment.py` (`validate_bulk_rna_seq_environment`,
`EnvironmentReport`, install plan). Dependency direction stays one-way: `nodes/ →
bioflow_harness`.
