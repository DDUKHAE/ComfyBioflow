# Tool Ranking Examples

- `salmon_index`: `REF`, because the official route is transcript-focused.
- `deseq2_analysis`: `REF`, because DESeq2 result tables are required for implementation success.
- `multiqc`: `ALT`, because enhanced QC aggregation is optional.

## Context override examples

- Transcript-focused quantification request: keep `salmon` (`REF`), no override needed.
- Genome-alignment-specific request: consider `STAR` or `featureCounts` as `ALT`, with an explicit override reason recorded in the registry.
- Request for enhanced QC aggregation: note `MultiQC` as `ALT`, without replacing the required DESeq2 visualization stage.

