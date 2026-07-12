# Workflow Generation

Use this skill to convert an analysis brief into the official ComfyBIO staged workflow plan.

## Inputs

- Analysis brief
- `harness/registry/tool_selection_registry.yaml`

## Output

Return a stage list for the selected implemented route:

- `bulk_rna_seq_salmon_ref`: fastp, salmon, tximport-compatible import, DESeq2, DESeq2 visualization, and report stages.
- `scrna_seq_scanpy_ref`: 10x count, Scanpy QC, normalization, clustering, marker genes, scRNA visualization, and report stages.

## Rules

- The official route must only contain `REF` tools.
- The official route must reject planned or stubbed nodes.
- Multi-step tools must remain decomposed by operation.
- If the analysis brief is for a domain without an implemented route, stop generation and require domain exploration, workflow design, registry updates, and node implementation before emitting workflow JSON.
