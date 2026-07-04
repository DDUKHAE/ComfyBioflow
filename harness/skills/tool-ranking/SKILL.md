# Tool Ranking

Use this skill to inspect or explain `REF` and `ALT` registry assignments.

## Rules

- `REF` means the recommended tool for the stage and eligible for the official MVP route.
- `ALT` means a credible alternative that requires a recorded reason before selection.
- `DESeq2` is `REF` for differential expression in the official MVP route.
- `MultiQC` is `ALT` for enhanced QC aggregation, not the required DESeq2 visualization gate.
- The official route must validate with `scripts/validate_registry.py` before it is treated as implementation-ready.
