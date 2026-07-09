# ComfyBIO Slice 2: Path Injection + Folder-Based Node Contract — Design

Date: 2026-07-09
Status: Approved (design), pending implementation plan

## Context

Slice 1 wired the ComfyBIO panel to the deterministic backend and auto-loads the
generated workflow onto the canvas, but every node still carries the fixture widget
paths (`harness/examples/fixtures/quickstart/...`). The generated graph does not reflect
the user's data. The overall program (see the roadmap and the slice 1 spec) reaches real
execution on user data across slices 2–4.

This document specifies **Slice 2**. Two design decisions were settled during
brainstorming:

- **Multi-sample representation:** runtime iteration over a fixed-shape graph. Nodes
  receive a folder path plus metadata and process samples internally (in Slice 3); the
  graph does not expand per sample.
- **Sample discovery (Slice 3 concern, recorded here):** metadata CSV first
  (`sample_id, condition, fastq_1, fastq_2`), falling back to scanning the FASTQ folder by
  filename convention when no metadata is provided.

Because runtime iteration requires nodes to consume a folder + metadata rather than
per-sample FASTQ slots, "path injection" only makes sense once the node widget contract is
folder-based. Slice 2 therefore includes the node-contract redesign and the
`custom_nodes/ → nodes/` migration (previously tentatively placed in Slice 3), leaving
only `run()` shell execution for Slice 3.

## Goal (Slice 2)

Redesign the bulk RNA-seq node contract to be folder + metadata based, inject the panel's
resource paths into the generated node widgets, and migrate the executable nodes to a
top-level `nodes/` package while removing the reverse dependency from `harness/` onto the
executable node classes.

### In scope

- Bulk-path node widget contract: per-sample `fastq_1/fastq_2` slots → `fastq_dir` +
  `metadata_csv`.
- `ResourceBindings` normalization of panel resources into named roles, injected into node
  widgets by the builder; fixture-default fallback when a role is absent.
- `custom_nodes/ → nodes/` migration; `harness/` no longer imports executable node classes.
- Non-blocking validation warning when required resources fall back to fixture defaults.

### Out of scope (deferred)

- **Node `run()` shell execution, sample discovery, parallel per-sample processing** →
  Slice 3.
- **Claude brief extraction** → Slice 4.
- **scRNA-seq node widget redesign** → not needed for the bulk demo (YAGNI); scRNA nodes
  keep their current widgets this slice.
- **Build-time filesystem existence checks** — paths may resolve on a remote execution
  host; existence is a Slice 3 runtime concern.

### Completion signal

Clicking Generate loads a folder-based node graph whose widgets contain the user's real
paths (FASTQ folder, metadata CSV, output directory, transcriptome). Opening e.g. the
Salmon Quant node on the canvas shows the injected paths. The graph still does not execute.

## Architecture

### Node contract redesign (folder + metadata)

Bulk-path nodes drop per-sample FASTQ slots in favor of a folder and metadata. Key
changes (node `INPUT_TYPES` in `nodes/` and matching `node_catalog` widget arrays):

| Node | Before (key widgets) | After (key widgets) |
|------|----------------------|---------------------|
| SampleMetadataValidator | metadata file | `fastq_dir`, `metadata_csv` |
| FastpQC | fastq_1, fastq_2, out | `fastq_dir`, `metadata_csv`, `output_dir` |
| FastpTrim | fastq_1, fastq_2, out | `fastq_dir`, `metadata_csv`, `output_dir` |
| SalmonIndex | transcriptome, index_dir | unchanged (sample-independent) |
| SalmonQuant | index, fastq_1, fastq_2, sample | `index_dir`, `fastq_dir`, `metadata_csv`, `output_dir` |
| Tximport | salmon_quant_dir (parent) | `salmon_quant_dir`, `metadata_csv` |
| DESeq2 / Viz / Report | count/results/plot | aggregate-based; only output paths injected |

Per-sample iteration is a runtime concern (Slice 3): nodes read `fastq_dir` + `metadata_csv`
at execution. Node `INPUT_TYPES` and the `node_catalog` `widgets` arrays are rewritten to
the new schema and order together.

### Resource binding + injection

New module `harness/src/bioflow_harness/comfy/resource_binding.py` (pure logic):

- `ResourceBindings` dataclass normalizes the panel resource list into roles:
  - `input_fastq_dir` ← resource label `input_path`
  - `output_base_dir` ← resource label `output_path`
  - `metadata_csv` ← resource type `metadata` or label `metadata_csv`
  - `transcriptome_fasta` ← resource type `index`/`reference`
  - `gtf_annotation` ← resource type `annotation` (reserved; unused on the bulk salmon route)
- `ResourceBindings.from_resources(resources: list[dict]) -> ResourceBindings` — each role is
  optional; a missing role falls back to the existing fixture default so the fixture/demo
  graph still builds.
- Output paths nest under `output_base_dir`: `{output}/qc`, `{output}/trimmed`,
  `{output}/salmon_quant`, `{output}/deseq2/count_matrix.csv`, `{output}/plots`,
  `{output}/report/comfybio_report.md`.
- `validate_bindings(route_id: str, bindings: ResourceBindings) -> list[str]` — returns a
  warning message per required role that fell back to a fixture default (bulk requires
  `input_fastq_dir`, `metadata_csv`, `transcriptome_fasta`). Non-blocking.

Builder change: `WorkflowBuilder.build(plan, bindings)` gains a `bindings` parameter;
`_widgets_for_stage(definition, plan, bindings)` fills each node_type's injectable widget
slots from `bindings`, leaving non-injected slots at their catalog defaults. The
`generate_workflow` handler constructs `ResourceBindings` from `GenerateRequest.resources`
and passes them in, and appends any `validate_bindings` warnings to the response `message`.

### Migration + dependency decoupling

1. Replace `workflow_schema.py`'s `from bioflow_harness.custom_nodes.registry import
   NODE_CLASS_MAPPINGS` with validation against `default_node_catalog()` keys. The builder
   only emits catalog node types, so this is an equivalent check and removes the
   harness → executable-node import.
2. `git mv harness/src/bioflow_harness/custom_nodes/` → top-level `nodes/`
   (`ref_nodes.py`, `registry.py`, `biopython_sequence_info.py`, `__init__.py`).
3. Internal imports become relative: `registry.py` → `from .ref_nodes import ...`;
   `nodes/__init__.py` → `from .registry import ...`.
4. Root `__init__.py`: `from bioflow_harness.custom_nodes import ...` →
   `from .nodes import ...` (relative — avoids colliding with ComfyUI's top-level
   `nodes.py` on absolute import).
5. Dependency direction is now one-way: `nodes/ → bioflow_harness` (Slice 3 keeps this when
   nodes import `runtime.command_runner`).

## Data flow

```
Panel Generate → POST /comfybio/generate {request_text, resources[]}
  → GenerateRequest.from_dict
  → ResourceBindings.from_resources(resources)          # role normalization + fixture fallback
  → parse_prompt → WorkflowPlanner.plan
  → WorkflowBuilder(node_catalog).build(plan, bindings) # inject paths into widgets
  → workflow JSON (+ validate_bindings warnings in message) → app.loadGraphData
```

Panel already collects `input_path`, `output_path`, `metadata_csv`. Minimal panel change:
pre-populate one `transcriptome_fasta` resource (type `index`) in the initial resource list
so the bulk demo works without manual entry; the user can edit or remove it.

## Error handling

- Missing required resource → falls back to fixture default; `validate_bindings` warning is
  surfaced in the generate response `message` (non-blocking). The graph still builds.
- Malformed/unknown resources → ignored by `from_resources`; fixture defaults retained.
- No build-time filesystem existence check (Slice 3 runtime concern).
- Unexpected build errors continue to propagate as they do in Slice 1 (aiohttp 500);
  JSON-error hardening remains the deferred Slice-1 item.

## Testing

- `ResourceBindings.from_resources`: role mapping, fixture fallback when a role is missing,
  output-path nesting.
- Builder injection: binding values land in the correct widget slots for each bulk
  node_type, and the workflow still passes `validate_workflow_export`.
- `generate_workflow` with resources: e.g. the Salmon Quant `fastq_dir` widget equals the
  panel `input_path`.
- `validate_bindings`: returns warnings for missing required resources.
- **Schema-drift guard (important):** each bulk node's `INPUT_TYPES` widget count equals its
  `node_catalog` `widgets` length — catches node/catalog divergence since both change. Plus
  a migration smoke test: the `nodes` package imports and `NODE_CLASS_MAPPINGS` is non-empty.
- `workflow_schema` validates against `node_catalog` (no dependency on `nodes/`).
- Manual: restart ComfyUI, Generate, open the Salmon Quant node on the canvas, confirm the
  injected real paths.

## File/module summary

```
nodes/                                                  # MOVED from custom_nodes/; bulk INPUT_TYPES redesigned
harness/src/bioflow_harness/comfy/resource_binding.py   # NEW: ResourceBindings, from_resources, validate_bindings
harness/src/bioflow_harness/comfy/node_catalog.py       # MODIFY: bulk widgets → folder+metadata schema
harness/src/bioflow_harness/comfy/workflow_builder.py   # MODIFY: build(plan, bindings) + injection
harness/src/bioflow_harness/comfy/workflow_schema.py    # MODIFY: validate against node_catalog keys
harness/src/bioflow_harness/server/handlers.py          # MODIFY: resources → bindings, warnings in message
__init__.py                                             # MODIFY: from .nodes import ...
web/js/comfybio_panel.js                                # MODIFY (minor): pre-populate transcriptome resource
tests/test_comfybio_resource_binding.py                 # NEW
tests/test_comfybio_node_contract.py                    # NEW: schema-drift guard + migration smoke
tests/test_comfybio_handlers.py                         # MODIFY: injection assertions
```
