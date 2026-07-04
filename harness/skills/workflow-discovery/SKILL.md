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
- Treat DESeq2 result tables and visualization artifacts as required outputs when the prompt asks for the official REF path.
- Record uncertainty in `confidence_notes` rather than silently guessing.

