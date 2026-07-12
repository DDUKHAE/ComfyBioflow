# ComfyBIO Architecture

ComfyBIO is a **ComfyUI custom-node extension** that turns a natural-language genomics request into a runnable ComfyUI workflow. This document is the map of the system: it describes the product wiring and the data contracts, and for each pipeline stage it points to the `harness/skills/` package that specifies how that stage works. Read a skill for *how to perform* a stage; read this file for *how the pieces fit and what the contracts are*.

> The standalone `bioflow_harness.cli` command still exists but is **legacy**. The product path is the ComfyUI extension described below (panel → server handlers → planner/builder → nodes).

## Product wiring

The repository is installed at `ComfyUI/custom_nodes/ComfyBIO`. ComfyUI imports the repository-root `__init__.py`, which:

- adds `harness/src` to `sys.path`,
- exports `NODE_CLASS_MAPPINGS`, `NODE_DISPLAY_NAME_MAPPINGS` (from `nodes/`), and `WEB_DIRECTORY = "./web/js"`,
- registers the ComfyBIO HTTP routes on ComfyUI's `PromptServer`.

The browser panel `web/js/comfybio_panel.js` renders the draggable launcher and the Prompt / Tool Select / Generate Graph UI, and calls the server routes registered by `bioflow_harness/server/routes.py`:

- `POST /comfybio/compile` → `handlers.compile_spec`
- `POST /comfybio/generate` → `handlers.generate_workflow`
- `GET /comfybio/health`

## End-to-end pipeline

```
panel prompt
  → LLM brief adapter (claude CLI)        # bioflow_harness/llm/
  → AnalysisBrief                         # models/prompt_contract.py
  → WorkflowPlanner (domain routing)      # planner/*
  → TSR tool selection (REF/ALT)          # planner/tool_selector.py + registry
  → WorkflowBuilder                       # comfy/workflow_builder.py + node_catalog.py
  → ComfyUI workflow JSON
  → nodes/ execution (conda)              # nodes/*  →  runtime/*
  → artifacts.sidecar.json                # runtime/artifact_sidecar.py
```

## Stage → skill map

Each stage is specified by a skill package; this table is the index. Do not duplicate a skill's content here — follow the link.

| Pipeline stage | Skill(s) | Owning code |
|---|---|---|
| Natural language → analysis brief | `harness/skills/workflow-discovery/` | `bioflow_harness/llm/`, `parser/prompt_parser.py` |
| Brief → staged workflow plan / route discovery | `harness/skills/workflow-generation/` | `planner/*` |
| Tool selection (REF/ALT decision) | `harness/skills/tool-ranking/`, `harness/skills/context-routing/` | `planner/tool_selector.py`, registry YAML |
| Operation → custom node spec & implementation | `harness/skills/custom-node-spec/`, `harness/skills/node-implementation-design/` | `nodes/*` |
| Workflow plan → ComfyUI workflow JSON | `harness/skills/workflow-json-generation/` | `comfy/workflow_builder.py`, `comfy/node_catalog.py` |

## LLM brief adapter

No skill covers this (it is the slice-4 adapter), so it is documented here.

`bioflow_harness/server/handlers.py` calls `extract_brief(request_text, provider, model)` (in `bioflow_harness/llm/brief_extractor.py`). When `provider == "claude"`, it uses `ClaudeBriefExtractor`, which shells out to the user's **logged-in Claude Code CLI**:

```
claude -p <request_text> --output-format json --model <model> --system-prompt <extraction prompt> --disallowedTools "*"
```

It parses the CLI's JSON envelope (`{type, subtype, is_error, result, ...}`), extracts the `result` text, and parses that into an `AnalysisBrief`. There is **no API key** — it reuses the Claude Code login. On any failure (missing binary, not logged in, non-zero exit, error envelope, unparseable output) it falls back to the deterministic `parse_prompt`, so a route always returns a usable brief. `provider` values `codex` and `gemini` fall back to the deterministic parser today.

## Node catalog (authoritative)

These are the registered ComfyUI node classes (`nodes/registry.py::NODE_CLASS_MAPPINGS`, mirrored by `comfy/node_catalog.py`). This table is the source of truth for node names and socket contracts because no skill lists them. `plot_dir`/`preview_plot` visualization nodes emit an `IMAGE` output for a ComfyUI `PreviewImage`; all other data flows as `STRING` file/directory paths.

| Node class | Title | Category | Inputs | Outputs | Domain |
|---|---|---|---|---|---|
| `SampleMetadataValidatorNode` | Validate Sample Metadata | ComfyBIO/Input | — | `sample_metadata_csv`:STRING | bulk |
| `FastpQCNode` | FASTQ QC | ComfyBIO/QC | `fastq_pair`:STRING | `fastp_qc_json`:STRING | bulk |
| `FastpTrimNode` | Optional FASTQ Trimming | ComfyBIO/QC | `fastp_qc_json`:STRING | `trimmed_fastq_dir`:STRING | bulk |
| `SalmonIndexNode` | Salmon Index | ComfyBIO/Quantification | `transcriptome_fasta_path`:STRING | `salmon_index_dir`:STRING | bulk |
| `SalmonQuantNode` | Salmon Quant | ComfyBIO/Quantification | `salmon_index_dir`:STRING | `salmon_quant_dir`:STRING | bulk |
| `TximportNode` | Import Counts For DESeq2 | ComfyBIO/Differential Expression | `salmon_quant_dir_path`:STRING | `deseq2_count_matrix`:STRING | bulk |
| `DESeq2AnalysisNode` | DESeq2 Analysis | ComfyBIO/Differential Expression | `deseq2_count_matrix`:STRING | `deseq2_results_table`:STRING | bulk |
| `DESeq2VisualizationNode` | DESeq2 Visualization | ComfyBIO/Visualization | `deseq2_results_table`:STRING | `plot_dir`:STRING, `preview_plot`:IMAGE | bulk |
| `ComfyBIOReportNode` | ComfyBIO Report | ComfyBIO/Reporting | `plot_dir_path`:STRING | `report_markdown`:STRING | bulk |
| `TenxCountNode` | 10x Count Matrix Generation | ComfyBIO/scRNA-seq | — | `filtered_feature_bc_matrix`:STRING | scRNA |
| `ScanpyQCNode` | Scanpy Cell QC | ComfyBIO/scRNA-seq | `filtered_feature_bc_matrix`:STRING | `qc_h5ad`:STRING | scRNA |
| `ScanpyNormalizeNode` | Scanpy Normalize | ComfyBIO/scRNA-seq | `qc_h5ad`:STRING | `normalized_h5ad`:STRING | scRNA |
| `ScanpyClusterNode` | Scanpy Cluster | ComfyBIO/scRNA-seq | `normalized_h5ad`:STRING | `clustered_h5ad`:STRING | scRNA |
| `ScanpyMarkerGenesNode` | Scanpy Marker Genes | ComfyBIO/scRNA-seq | `clustered_h5ad`:STRING | `marker_genes_csv`:STRING | scRNA |
| `ScRNAVisualizationNode` | scRNA Visualization | ComfyBIO/scRNA-seq | `marker_genes_csv`:STRING | `plot_dir`:STRING, `preview_plot`:IMAGE | scRNA |
| `ScRNAReportNode` | scRNA Report | ComfyBIO/scRNA-seq | `plot_dir_path`:STRING | `report_markdown`:STRING | scRNA |

`nodes/biopython_sequence_info.py` (`BiopythonSequenceInfoNode`) is a standalone demo node and is not part of either route.

## Registry (TSR) schema

The tool-selection registry `harness/registry/tool_selection_registry.yaml` is JSON-in-YAML. Top level:

- `metadata` (`name`, `version`, `official_route_id`)
- `supported_domains` (`["bulk_rna_seq", "scrna_seq"]`), `planned_domains`
- `routes`: map of `route_id` → ordered list of **stages**, each `{stage_id, stage_label, tool_id, operation_id, optional?}`
- `tools`: list of **tool** entries.

The bulk route `bulk_rna_seq_salmon_ref` has 9 stages: `metadata_validation, read_qc, trimming (optional), salmon_index, salmon_quant, tximport_import, deseq2_analysis, deseq2_visualization, reporting`. The scRNA route `scrna_seq_scanpy_ref` has 7 stages: `tenx_count, scrna_qc, scrna_normalization, scrna_clustering, scrna_marker_genes, scrna_visualization, scrna_reporting`.

Each tool entry carries: `id`, `label`, `domain_tags`, `stage_tags`, `input_types`, `output_types`, `language`, `summary`, `tier` (`REF` or `ALT`), `tier_rationale`, `context_routing_rules`, `selection_rules`, `future_comfy_node`, `runnable_node_status` (`runnable` when a registered node backs it), and `operations`. Each operation is `{id, label, input_types, output_types, node_type}` where `node_type` must be a key in the node catalog above.

**Selection gate (implementation-ready route):** every stage's tool is `tier: REF`, `runnable_node_status: runnable`, and every `operation.node_type` resolves in `NODE_CLASS_MAPPINGS`. `ALT` tools (e.g. STAR, featureCounts, MultiQC) require a recorded context-routing reason and are outside the MVP gate. See the `tool-ranking` and `context-routing` skills for the decision rules.

## Node authoring policy

- Expose shared essential settings as core UI parameters; put route-specific or advanced CLI fragments in the node's `extra_command` input.
- `extra_command` is declared `multiline: True` and parsed with shell-style tokenization: one option per line or a single line of options; blank lines and lines starting with `#` are ignored.
- Every downstream node has one connected `STRING` input declared with `forceInput: True`, and its socket is named by artifact format (e.g. `salmon_quant_dir`, `qc_h5ad`, `marker_genes_csv`) rather than a generic `upstream`. File-path widgets stay editable.
- Emit `STRING` for bioinformatics file/directory paths and `IMAGE` only for visual previews.
- Newly generated node classes are restart-required until ComfyUI reloads (see the `node-implementation-design` skill).

## Adding a new domain

A domain that is not implemented must not be silently routed to an existing workflow; the harness returns a `planning_required` response until the domain has a runnable route and registered nodes. To add one: explore the analysis goal, inputs, and expected outputs; design canonical stages and the artifact contract between them; add a `routes` entry plus `tools`/`operations` with `domain_tags`, `tier`, and `node_type`; implement and register the ComfyBIO nodes; add fixtures and validation. Only then move the domain from `planned_domains` to `supported_domains`.

## Pointers

- Runtime, conda environment, and artifact sidecar: `harness/docs/execution.md`
- Tool/route registry: `harness/registry/tool_selection_registry.yaml`
- Stage skills: `harness/skills/`
- Worked example: `harness/examples/case_studies/bulk_rna_seq_public_case_study.md`
