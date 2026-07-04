# Workflow Generation

Use this skill to convert an analysis brief into the official ComfyBIO staged workflow plan.

## Inputs

- Analysis brief
- `harness/registry/tool_selection_registry.yaml`

## Output

Return a stage list for `bulk_rna_seq_salmon_ref`, including fastp, salmon, tximport-compatible import, DESeq2, DESeq2 visualization, report, and workflow export stages.

## Rules

- The official route must only contain `REF` tools.
- The official route must reject planned or stubbed nodes.
- Multi-step tools must remain decomposed by operation.

