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
| Tool selection (REF/ALT decision, incl. context-override reasoning) | `harness/skills/tool-ranking/` | `planner/tool_selector.py`, registry YAML |
| Operation → custom node spec & implementation | `harness/skills/node-implementation-design/` | `nodes/*` |
| Workflow plan → ComfyUI workflow JSON | `harness/skills/workflow-json-generation/` | `comfy/workflow_builder.py`, `comfy/node_catalog.py` |

## LLM brief adapter

No skill covers this (it is the slice-4 adapter), so it is documented here.

`bioflow_harness/server/handlers.py` calls `extract_brief(request_text, provider, model)` (in `bioflow_harness/llm/brief_extractor.py`). `provider` is one of `"claude"`, `"codex"`, `"gemini"`, each shelling out to that CLI's already-logged-in session (no API key stored anywhere) — the shared BRIEF_SCHEMA/SYSTEM_PROMPT and post-processing (`brief_from_payload`, `extract_json_object`) live in `bioflow_harness/llm/brief_schema.py` so the three extractors differ only in how they invoke their CLI and where they find the final response text:

- **claude** (`claude_extractor.py`): `claude -p <request_text> --output-format json --model <model> --system-prompt <prompt> --disallowedTools "*"`. Parses the CLI's JSON envelope (`{type, subtype, is_error, result, ...}`) and extracts `result`.
- **codex** (`codex_extractor.py`): `codex exec "<system prompt>\n\nResearcher's request:\n<request_text>" --skip-git-repo-check --sandbox read-only --model <model> --output-schema <schema file> --json`. Codex has no separate system-prompt flag, so instructions and request text are combined into one prompt; `--output-schema` constrains the response to BRIEF_SCHEMA. `--json` prints one JSONL event per line to stdout — the last `item.completed`/`agent_message` event's `text` field is the response.
- **gemini** (`gemini_extractor.py`): `gemini -p "<system prompt>\n\nResearcher's request:\n<request_text>" -m <model>`, parsing stdout directly. **This one is unverified** — it was implemented against Gemini CLI's documented non-interactive usage without a `gemini` binary available to test against in the environment it was written in; treat it as less proven than the claude/codex paths until checked against a real login.

On any failure (missing binary, not logged in, non-zero exit, error/malformed response, schema-invalid payload) `extract_brief` falls back to the deterministic `parse_prompt`, so a route always returns a usable brief regardless of which provider is selected or whether its CLI is installed.

## Node catalog (authoritative)

These are the registered ComfyUI node classes (`nodes/registry.py::NODE_CLASS_MAPPINGS`, mirrored by `comfy/node_catalog.py`). This table is the source of truth for node names and socket contracts because no skill lists them. `plot_dir`/`preview_plot` visualization nodes emit an `IMAGE` output for a ComfyUI `PreviewImage`; all other data flows as `STRING` file/directory paths.

The **Title** column is the workflow-JSON node title from `comfy/node_catalog.py`; the name ComfyUI shows in its Add-Node menu is derived separately from the class name via `nodes/registry.py::NODE_DISPLAY_NAME_MAPPINGS` (e.g. `SalmonIndexNode` → `SalmonIndex`, no space). The **Execution** column reflects actual `run()` coverage in `nodes/ref_nodes.py`: the 9 bulk nodes, the 8 variant-analysis nodes, the 9 epigenomics (ATAC-seq) nodes, the 6 metagenome (Kraken2/Bracken) nodes, and the 6 genome assembly (SPAdes) nodes execute real tools via conda; the 7 scRNA nodes are **construction-only stubs** — they are registered and appear in generated workflow JSON, but have no `run()` method yet, so executing a scRNA graph in ComfyUI currently raises an error. Registry `runnable_node_status` does **not** capture this distinction (see the Selection-gate caveat below).

| Node class | Title | Category | Inputs | Outputs | Domain | Execution |
|---|---|---|---|---|---|---|
| `SampleMetadataValidatorNode` | Validate Sample Metadata | ComfyBIO/Input | — | `sample_metadata_csv`:STRING | bulk | runs (conda) |
| `FastpQCNode` | FASTQ QC | ComfyBIO/QC | `fastq_pair`:STRING | `fastp_qc_json`:STRING | bulk | runs (conda) |
| `FastpTrimNode` | Optional FASTQ Trimming | ComfyBIO/QC | `fastp_qc_json`:STRING | `trimmed_fastq_dir`:STRING | bulk | runs (conda) |
| `SalmonIndexNode` | Salmon Index | ComfyBIO/Quantification | `transcriptome_fasta_path`:STRING | `salmon_index_dir`:STRING | bulk | runs (conda) |
| `SalmonQuantNode` | Salmon Quant | ComfyBIO/Quantification | `salmon_index_dir`:STRING | `salmon_quant_dir`:STRING | bulk | runs (conda) |
| `TximportNode` | Import Counts For DESeq2 | ComfyBIO/Differential Expression | `salmon_quant_dir_path`:STRING | `deseq2_count_matrix`:STRING | bulk | runs (conda) |
| `DESeq2AnalysisNode` | DESeq2 Analysis | ComfyBIO/Differential Expression | `deseq2_count_matrix`:STRING | `deseq2_results_table`:STRING | bulk | runs (conda) |
| `DESeq2VisualizationNode` | DESeq2 Visualization | ComfyBIO/Visualization | `deseq2_results_table`:STRING | `plot_dir`:STRING, `preview_plot`:IMAGE | bulk | runs (conda) |
| `ComfyBIOReportNode` | ComfyBIO Report | ComfyBIO/Reporting | `plot_dir_path`:STRING | `report_markdown`:STRING | bulk | runs (conda) |
| `VariantInputValidatorNode` | Validate Variant Inputs | ComfyBIO/Input | — | `sample_metadata_csv`:STRING | variant_analysis | runs (conda) |
| `BwaMem2IndexNode` | bwa-mem2 Index | ComfyBIO/Alignment | `sample_metadata_csv`:STRING | `reference_fasta_indexed`:STRING | variant_analysis | runs (conda) |
| `BwaMem2AlignNode` | bwa-mem2 Align | ComfyBIO/Alignment | `reference_fasta_indexed`:STRING | `sorted_bam_dir`:STRING | variant_analysis | runs (conda) |
| `MarkDuplicatesNode` | Mark Duplicates | ComfyBIO/Alignment | `sorted_bam_dir`:STRING | `dedup_bam_dir`:STRING | variant_analysis | runs (conda) |
| `BcftoolsCallNode` | bcftools Call | ComfyBIO/Variant Calling | `dedup_bam_dir`:STRING | `raw_vcf_dir`:STRING | variant_analysis | runs (conda) |
| `BcftoolsFilterNode` | bcftools Filter | ComfyBIO/Variant Calling | `raw_vcf_dir`:STRING | `filtered_vcf_dir`:STRING | variant_analysis | runs (conda) |
| `VariantVisualizationNode` | Variant Visualization | ComfyBIO/Visualization | `filtered_vcf_dir`:STRING | `plot_dir`:STRING, `preview_plot`:IMAGE | variant_analysis | runs (conda) |
| `VariantReportNode` | Variant Report | ComfyBIO/Reporting | `plot_dir_path`:STRING | `report_markdown`:STRING | variant_analysis | runs (conda) |
| `AtacInputValidatorNode` | Validate ATAC-seq Inputs | ComfyBIO/Input | — | `sample_metadata_csv`:STRING | epigenomics | runs (conda) |
| `AtacFastpTrimNode` | fastp Trim (ATAC-seq) | ComfyBIO/QC | `sample_metadata_csv`:STRING | `trimmed_fastq_dir`:STRING | epigenomics | runs (conda) |
| `AtacBwaMem2IndexNode` | bwa-mem2 Index (ATAC-seq) | ComfyBIO/Alignment | `trimmed_fastq_dir`:STRING | `reference_fasta_indexed`:STRING | epigenomics | runs (conda) |
| `AtacBwaMem2AlignNode` | bwa-mem2 Align (ATAC-seq) | ComfyBIO/Alignment | `reference_fasta_indexed`:STRING | `sorted_bam_dir`:STRING | epigenomics | runs (conda) |
| `AtacMarkDuplicatesNode` | Mark Duplicates (ATAC-seq) | ComfyBIO/Alignment | `sorted_bam_dir`:STRING | `dedup_bam_dir`:STRING | epigenomics | runs (conda) |
| `AtacQualityFilterNode` | ATAC-seq Quality Filter | ComfyBIO/QC | `dedup_bam_dir`:STRING | `filtered_bam_dir`:STRING | epigenomics | runs (conda) |
| `Macs3PeakCallingNode` | MACS3 Peak Calling | ComfyBIO/Peak Calling | `filtered_bam_dir`:STRING | `peaks_dir`:STRING | epigenomics | runs (conda) |
| `AtacPeakVisualizationNode` | ATAC-seq Peak Visualization | ComfyBIO/Visualization | `peaks_dir`:STRING | `plot_dir`:STRING, `preview_plot`:IMAGE | epigenomics | runs (conda) |
| `AtacReportNode` | ATAC-seq Report | ComfyBIO/Reporting | `plot_dir_path`:STRING | `report_markdown`:STRING | epigenomics | runs (conda) |
| `MetagenomeInputValidatorNode` | Validate Metagenome Inputs | ComfyBIO/Input | — | `sample_metadata_csv`:STRING | metagenome | runs (conda) |
| `MetagenomeFastpTrimNode` | fastp Trim (Metagenome) | ComfyBIO/QC | `sample_metadata_csv`:STRING | `trimmed_fastq_dir`:STRING | metagenome | runs (conda) |
| `Kraken2ClassifyNode` | Kraken2 Classify | ComfyBIO/Taxonomic Classification | `trimmed_fastq_dir`:STRING | `kraken2_output_dir`:STRING | metagenome | runs (conda) |
| `BrackenAbundanceNode` | Bracken Abundance | ComfyBIO/Taxonomic Classification | `kraken2_output_dir`:STRING | `bracken_dir`:STRING | metagenome | runs (conda) |
| `MetagenomeVisualizationNode` | Metagenome Visualization | ComfyBIO/Visualization | `bracken_dir`:STRING | `plot_dir`:STRING, `preview_plot`:IMAGE | metagenome | runs (conda) |
| `MetagenomeReportNode` | Metagenome Report | ComfyBIO/Reporting | `plot_dir_path`:STRING | `report_markdown`:STRING | metagenome | runs (conda) |
| `AssemblyInputValidatorNode` | Validate Genome Assembly Inputs | ComfyBIO/Input | — | `sample_metadata_csv`:STRING | genome_assembly | runs (conda) |
| `AssemblyFastpTrimNode` | fastp Trim (Genome Assembly) | ComfyBIO/QC | `sample_metadata_csv`:STRING | `trimmed_fastq_dir`:STRING | genome_assembly | runs (conda) |
| `SpadesAssembleNode` | SPAdes Assemble | ComfyBIO/Assembly | `trimmed_fastq_dir`:STRING | `assembly_dir`:STRING | genome_assembly | runs (conda) |
| `QuastQcNode` | QUAST QC | ComfyBIO/Assembly | `assembly_dir`:STRING | `qc_dir`:STRING | genome_assembly | runs (conda) |
| `AssemblyVisualizationNode` | Genome Assembly Visualization | ComfyBIO/Visualization | `qc_dir`:STRING | `plot_dir`:STRING, `preview_plot`:IMAGE | genome_assembly | runs (conda) |
| `AssemblyReportNode` | Genome Assembly Report | ComfyBIO/Reporting | `plot_dir_path`:STRING | `report_markdown`:STRING | genome_assembly | runs (conda) |
| `TenxCountNode` | 10x Count Matrix Generation | ComfyBIO/scRNA-seq | — | `filtered_feature_bc_matrix`:STRING | scRNA | stub (no `run()` yet) |
| `ScanpyQCNode` | Scanpy Cell QC | ComfyBIO/scRNA-seq | `filtered_feature_bc_matrix`:STRING | `qc_h5ad`:STRING | scRNA | stub (no `run()` yet) |
| `ScanpyNormalizeNode` | Scanpy Normalize | ComfyBIO/scRNA-seq | `qc_h5ad`:STRING | `normalized_h5ad`:STRING | scRNA | stub (no `run()` yet) |
| `ScanpyClusterNode` | Scanpy Cluster | ComfyBIO/scRNA-seq | `normalized_h5ad`:STRING | `clustered_h5ad`:STRING | scRNA | stub (no `run()` yet) |
| `ScanpyMarkerGenesNode` | Scanpy Marker Genes | ComfyBIO/scRNA-seq | `clustered_h5ad`:STRING | `marker_genes_csv`:STRING | scRNA | stub (no `run()` yet) |
| `ScRNAVisualizationNode` | scRNA Visualization | ComfyBIO/scRNA-seq | `marker_genes_csv`:STRING | `plot_dir`:STRING, `preview_plot`:IMAGE | scRNA | stub (no `run()` yet) |
| `ScRNAReportNode` | scRNA Report | ComfyBIO/scRNA-seq | `plot_dir_path`:STRING | `report_markdown`:STRING | scRNA | stub (no `run()` yet) |

`nodes/biopython_sequence_info.py` (`BiopythonSequenceInfoNode`) is a standalone demo node and is not part of either route.

## Registry (TSR) schema

The tool-selection registry `harness/registry/tool_selection_registry.yaml` is JSON-in-YAML. Top level:

- `metadata` (`name`, `version`, `official_route_id`)
- `supported_domains` (`["bulk_rna_seq", "scrna_seq"]`), `planned_domains`
- `routes`: map of `route_id` → ordered list of **stages**, each `{stage_id, stage_label, tool_id, operation_id, optional?}`
- `tools`: list of **tool** entries.

The bulk route `bulk_rna_seq_salmon_ref` has 9 stages: `metadata_validation, read_qc, trimming (optional), salmon_index, salmon_quant, tximport_import, deseq2_analysis, deseq2_visualization, reporting`. The scRNA route `scrna_seq_scanpy_ref` has 7 stages: `tenx_count, scrna_qc, scrna_normalization, scrna_clustering, scrna_marker_genes, scrna_visualization, scrna_reporting`. The variant analysis route `variant_analysis_bwa_ref` has 8 stages: `input_validation, reference_indexing (optional), alignment, mark_duplicates, variant_calling, variant_filtering, variant_visualization, reporting`. The epigenomics route `atac_seq_macs3_ref` has 9 stages: `input_validation, read_trimming, reference_indexing (optional), alignment, mark_duplicates, quality_filtering, peak_calling, peak_visualization, reporting`. The metagenome route `metagenome_kraken2_ref` has 6 stages: `input_validation, read_trimming, taxonomic_classification, abundance_estimation, profile_visualization, reporting`. The genome assembly route `genome_assembly_spades_ref` has 6 stages: `input_validation, read_trimming, assembly, assembly_qc, assembly_visualization, reporting`.

Each tool entry carries: `id`, `label`, `domain_tags`, `stage_tags`, `input_types`, `output_types`, `language`, `summary`, `tier` (`REF` or `ALT`), `tier_rationale`, `context_routing_rules`, `selection_rules`, `future_comfy_node`, `runnable_node_status` (`runnable` when a registered node backs it), and `operations`. Each operation is `{id, label, input_types, output_types, node_type}` where `node_type` must be a key in the node catalog above.

**Selection gate (route generation):** a route is selected and generated into workflow JSON when every stage's tool is `tier: REF`, `runnable_node_status: runnable`, and every `operation.node_type` resolves in `NODE_CLASS_MAPPINGS`. **Caveat:** `runnable_node_status: runnable` marks only that a *registered* node backs the operation; it does **not** guarantee the node *executes*. Today the bulk route (`bulk_rna_seq_salmon_ref`), the variant analysis route (`variant_analysis_bwa_ref`), the epigenomics route (`atac_seq_macs3_ref`), the metagenome route (`metagenome_kraken2_ref`), and the genome assembly route (`genome_assembly_spades_ref`) have nodes that implement `run()`; the scRNA route (`scrna_seq_scanpy_ref`) generates valid workflow JSON but its 7 nodes are construction-only stubs (see the Execution column above), so it is not yet an execution-ready route. `ALT` tools (e.g. STAR, featureCounts, MultiQC) require a recorded context-routing reason and are outside the MVP gate. See the `tool-ranking` skill for the decision rules.

## Node authoring policy

- Expose shared essential settings as core UI parameters; put route-specific or advanced CLI fragments in the node's `extra_command` input.
- `extra_command` is declared `multiline: True` and parsed with shell-style tokenization: one option per line or a single line of options; blank lines and lines starting with `#` are ignored.
- Every downstream node has one connected `STRING` input declared with `forceInput: True`, and its socket is named by artifact format (e.g. `salmon_quant_dir`, `qc_h5ad`, `marker_genes_csv`) rather than a generic `upstream`. File-path widgets stay editable.
- Emit `STRING` for bioinformatics file/directory paths and `IMAGE` only for visual previews.
- Newly generated node classes are restart-required until ComfyUI reloads (see the `node-implementation-design` skill).

## Adding a new domain

A domain that is not implemented must not be silently routed to an existing workflow; the harness returns a `planning_required` response until the domain has a runnable route and registered nodes. To add one: explore the analysis goal, inputs, and expected outputs; design canonical stages and the artifact contract between them; add a `routes` entry plus `tools`/`operations` with `domain_tags`, `tier`, and `node_type`; implement and register the ComfyBIO nodes; add fixtures and validation. Only then move the domain from `planned_domains` to `supported_domains`. Follow `harness/skills/domain-bootstrap/` for the concrete process and promotion gate (`scripts/validate_domain_promotion.py`); `variant_analysis` (see `harness/skills/domain-bootstrap/examples.md`) is the worked example. All four initial domain-bootstrap cycles are now complete and `planned_domains` is empty; any future domain starts fresh via the `domain-bootstrap` skill.

## Pointers

- Runtime, conda environment, and artifact sidecar: `harness/docs/execution.md`
- Tool/route registry: `harness/registry/tool_selection_registry.yaml`
- Stage skills: `harness/skills/`
- Worked example: `harness/examples/case_studies/bulk_rna_seq_public_case_study.md`
