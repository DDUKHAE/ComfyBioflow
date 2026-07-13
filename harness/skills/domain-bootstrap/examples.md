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

---

# Domain Bootstrap: epigenomics (ATAC-seq) worked example

The second domain built with the `domain-bootstrap` skill.

## Assay scope decision

"Epigenomics" spans ChIP-seq, ATAC-seq, WGBS/methylation, and Hi-C. ATAC-seq was chosen for this cycle because it needs no input/control sample pairing — a single-FASTQ-pair-per-sample pipeline, matching the shape every other route already uses. ChIP-seq (control-sample pairing) and WGBS (a bisulfite-aware aligner, a different dependency family) remain `planned_domains` follow-ons.

## Stage decomposition

| stage_id | tool_id (tier) | node_type |
|---|---|---|
| `input_validation` | `atac_input_validator` (REF) | `AtacInputValidatorNode` |
| `read_trimming` | `atac_fastp_trim` (REF) | `AtacFastpTrimNode` |
| `reference_indexing` (optional) | `atac_bwa_mem2_index` (REF) | `AtacBwaMem2IndexNode` |
| `alignment` | `atac_bwa_mem2_align` (REF) | `AtacBwaMem2AlignNode` |
| `mark_duplicates` | `atac_samtools_markdup` (REF) | `AtacMarkDuplicatesNode` |
| `quality_filtering` | `atac_quality_filter` (REF) | `AtacQualityFilterNode` |
| `peak_calling` | `atac_macs3_callpeak` (REF) / `atac_macs2_callpeak` (ALT, planned) / `atac_genrich_callpeak` (ALT, planned) | `Macs3PeakCallingNode` |
| `peak_visualization` | `atac_peak_visualization` (REF) | `AtacPeakVisualizationNode` |
| `reporting` | `atac_report` (REF) | `AtacReportNode` |

## REF selection rationale

fastp (not TrimGalore, nf-core's default) for trimming: already a proven-lightweight REF dependency in `bulk_rna_seq`; TrimGalore adds a Perl/Cutadapt dependency chain for no accuracy gain at this scope.

bwa-mem2 for alignment: same aligner family as nf-core/atacseq's BWA default, and already proven in the `variant_analysis` route — but installed into its own `epigenomics` conda environment, never shared across domains.

MACS3 (not MACS2, the current nf-core/atacseq default) for peak calling: the actively maintained successor with equivalent semantics. MACS2 and Genrich (an ATAC-seq-native alternative with built-in replicate handling) are both recorded as `tier: "ALT"`, `runnable_node_status: "planned"`.

## Environment isolation

`harness/envs/epigenomics.yaml` is a separate conda environment (`fastp`, `bwa-mem2`, `samtools`, `macs3`, `bedtools`, `matplotlib`) from both `bulk_rna_seq` and `variant_analysis`, even though `fastp`/`bwa-mem2`/`samtools` all overlap with one or the other — each domain's environment is independently installable and versioned, per the skill's rule 3.

## No shell pipes

Same discipline as `variant_analysis`: `bwa-mem2 mem` has no output flag, so `AtacBwaMem2AlignNode` captures `CommandRecord.stdout` and writes it to `aligned.sam` before handing off to `samtools sort`. Every other multi-tool step (`samtools collate/fixmate/sort/markdup`, `samtools view` quality filtering, `macs3 callpeak`) uses a native `-o`/positional output argument.

## Promotion gate output

```
PYTHONPATH="harness/src:." python harness/skills/domain-bootstrap/scripts/validate_domain_promotion.py --route-id atac_seq_macs3_ref
```

prints `"ready": true` once all 9 nodes have real `run()` methods and the route passes `validate_official_route` — the gate script itself needed zero changes from the `variant_analysis` cycle, confirming it generalizes across domains as intended.
