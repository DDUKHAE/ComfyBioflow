# Workflow Discovery

Use this skill to convert a natural-language genomics request into a normalized ComfyBIO analysis brief.

## Inputs

- Natural-language request text
- Optional dataset or project notes

## Output

Return an analysis brief with:

- `analysis_type`
- `domain`
- `input_assets`
- `organism`
- `expected_outputs`
- `constraints`
- `preferred_tools`
- `confidence_notes`
- `submission_source`
- `data_characteristics`

## Rules

- Map bulk RNA-seq prompts to `bulk_rna_seq`.
- Map single-cell RNA-seq, scRNA-seq, 10x, UMAP, or marker-gene prompts to `scrna_seq`.
- Detect planned or unmodeled domains separately. Do not route them to `bulk_rna_seq` just because the prompt contains `RNA-seq`.
- For planned domains that do not have an implemented route, return a domain value and confidence note that workflow expansion is required.
- Treat DESeq2 result tables and visualization artifacts as required outputs when the prompt asks for the official REF path.
- Record uncertainty in `confidence_notes` rather than silently guessing.
