---
name: workflow-generation
description: Use when converting an analysis brief into the official ComfyBIO staged workflow plan for any of the 6 implemented routes (bulk_rna_seq_salmon_ref, scrna_seq_scanpy_ref, variant_analysis_bwa_ref, atac_seq_macs3_ref, metagenome_kraken2_ref, genome_assembly_spades_ref), or when deciding a brief's domain has no implemented route and workflow generation must stop pending domain exploration.
---

# Workflow Generation

Use this skill to convert an analysis brief into the official ComfyBIO staged workflow plan.

## Inputs

- Analysis brief
- `harness/registry/tool_selection_registry.yaml`

## Output

Return a stage list for the selected implemented route. `supported_domains` currently has 6 routes; check the registry directly if this list is ever out of date:

- `bulk_rna_seq_salmon_ref` (9 stages): metadata validation, fastp QC, optional trimming, salmon index, salmon quant, tximport-compatible import, DESeq2 analysis, DESeq2 visualization, report. Runs (conda).
- `scrna_seq_scanpy_ref` (7 stages): 10x count, Scanpy QC, normalization, clustering, marker genes, scRNA visualization, report. Generates valid workflow JSON, but all 7 nodes are construction-only stubs — not execution-ready yet (see `ARCHITECTURE.md`).
- `variant_analysis_bwa_ref` (8 stages): input validation, optional reference indexing, bwa-mem2 alignment, mark duplicates, bcftools call, bcftools filter, variant visualization, report. Runs (conda).
- `atac_seq_macs3_ref` (9 stages): input validation, fastp trimming, optional reference indexing, bwa-mem2 alignment, mark duplicates, quality filtering, MACS3 peak calling, peak visualization, report. Runs (conda).
- `metagenome_kraken2_ref` (6 stages): input validation, fastp trimming, Kraken2 classification, Bracken abundance estimation, profile visualization, report. Runs (conda).
- `genome_assembly_spades_ref` (6 stages): input validation, fastp trimming, SPAdes assembly, QUAST QC, assembly visualization, report. Runs (conda).

## Rules

- The official route must only contain `REF` tools.
- The official route must reject planned nodes (`runnable_node_status` other than `"runnable"`). Note the registry's known gap: `runnable_node_status: "runnable"` only means a node is registered, not that its `run()` executes — `scrna_seq_scanpy_ref` passes this gate today but its 7 nodes are construction-only stubs (see `ARCHITECTURE.md`'s Selection-gate caveat), so it generates valid JSON without being execution-ready.
- Multi-step tools must remain decomposed by operation.
- If the analysis brief is for a domain without an implemented route, stop generation and require domain exploration, workflow design, registry updates, and node implementation before emitting workflow JSON — see the `domain-bootstrap` skill.

## How to run scripts

Run from the repository root:

    PYTHONPATH="harness/src:." python harness/skills/workflow-generation/scripts/generate_workflow_plan.py "<request text>" --registry harness/registry/tool_selection_registry.yaml

See [references/examples.md](references/examples.md) for a worked stage list per route.
