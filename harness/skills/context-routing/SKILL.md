# Context Routing

Use this skill to decide whether request context justifies moving away from the default `REF` tool.

## Rules

- Keep the official `bulk_rna_seq_salmon_ref` route on REF tools unless the user explicitly requests a different route.
- Record a context override reason whenever an `ALT` tool is selected.
- Genome-alignment-specific requests may select STAR or featureCounts ALT routes, but they are outside the MVP completion gate.

