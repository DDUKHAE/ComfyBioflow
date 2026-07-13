# Domain Bootstrap: variant_analysis worked example

This is the first domain built with the `domain-bootstrap` skill, and the reference for the next ones (epigenomics, genome_assembly).

## Stage decomposition

| stage_id | tool_id (tier) | node_type |
|---|---|---|
| `input_validation` | `variant_input_validator` (REF) | `VariantInputValidatorNode` |
| `reference_indexing` (optional) | `bwa_mem2_index` (REF) | `BwaMem2IndexNode` |
| `alignment` | `bwa_mem2_align` (REF) | `BwaMem2AlignNode` |
| `mark_duplicates` | `samtools_markdup` (REF) | `MarkDuplicatesNode` |
| `variant_calling` | `bcftools_call` (REF) / `gatk_haplotype_caller` (ALT, planned) | `BcftoolsCallNode` |
| `variant_filtering` | `bcftools_filter` (REF) | `BcftoolsFilterNode` |
| `variant_visualization` | `variant_visualization` (REF) | `VariantVisualizationNode` |
| `reporting` | `variant_report` (REF) | `VariantReportNode` |

## REF selection rationale

bwa-mem2 (not bwa or bowtie2) for alignment: fastest maintained short-read aligner with bwa-mem-compatible output, matching the "REF-only lightweight install scope" philosophy already used for fastp/salmon.

bcftools (not GATK HaplotypeCaller) for variant calling: a single lightweight conda dependency covering mpileup, calling, filtering, and stats — no Java runtime, no BQSR/known-sites reference data requirement. GATK is recorded as `tier: "ALT"`, `runnable_node_status: "planned"` so it stays visible as the community-standard alternative without forcing a heavier REF-only install.

## Environment isolation

`harness/envs/variant_analysis.yaml` is a separate conda environment (`bwa-mem2`, `samtools`, `bcftools`, `matplotlib`) from `bulk_rna_seq`, even though both could theoretically share a `python>=3.11` base — sharing would couple the two domains' dependency upgrade cycles together.

## No shell pipes

`runtime/command_runner.py::CommandRunner.run()` executes one argv list via `subprocess.run`, with no shell/pipe support. Every conceptually-piped step (`bwa-mem2 mem | samtools sort`, `bcftools mpileup | bcftools call`) uses either a tool's native `-o` flag through an intermediate file (`bcftools mpileup -o raw.bcf`, then `bcftools call raw.bcf`), or — for tools with no output flag (`bwa-mem2 mem`, `bcftools stats`) — captures `CommandRecord.stdout` and writes it to a file before the next call.

## Promotion gate output

```
python harness/skills/domain-bootstrap/scripts/validate_domain_promotion.py --route-id variant_analysis_bwa_ref
```

prints `"ready": true` once all 8 nodes have real `run()` methods and the route passes `validate_official_route` — confirmed against the deliberately-stubbed `scrna_seq_scanpy_ref` route, which correctly reports `"ready": false` with `TenxCountNode` (and its 6 siblings) listed in `stub_node_types`.
