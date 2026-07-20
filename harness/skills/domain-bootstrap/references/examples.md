# Domain Bootstrap: variant_analysis worked example

This is the first domain built with the `domain-bootstrap` skill, and the reference for the next ones (epigenomics, metagenome, genome_assembly).

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

## A lesson from this cycle: deferring a domain isn't enough, its keywords must be actively excluded

When this cycle added `epigenomics_tokens` to `parser/prompt_parser.py::parse_prompt` for ATAC-seq, `"chip-seq"`/`"chip seq"` were included as if they were ATAC-seq synonyms — plausible, since both are "epigenomics" in the broad sense, but wrong: ChIP-seq needs control-sample pairing, a genuinely different pipeline shape from ATAC-seq's single-FASTQ-pair route, per the assay scope decision above. The result was a real bug that shipped for a while: a ChIP-seq request silently matched `epigenomics_tokens` and routed to `atac_seq_macs3_ref` instead of surfacing `planning_required`, directly violating this skill's rule 8 — without ever touching `stage_mapper.py` or `handlers.py`, since the domain classification itself was already wrong before either of those ran.

Deciding to defer a domain (as this cycle did for ChIP-seq and WGBS) only has teeth if its likely request vocabulary is also kept out of every *other* domain's token list — writing "ChIP-seq is deferred" in this file does nothing to stop a future edit from accidentally matching it against the closest implemented neighbor. Fixed by removing the two tokens and adding a negative-case regression test (`tests/test_comfybio_graph_structure.py::test_deferred_domains_with_overlapping_vocabulary_stay_unsupported`) asserting ChIP-seq/WGBS/Hi-C requests resolve to `"unsupported"`. Future cycles should add the same kind of test whenever a domain is deferred specifically because it resembles one being implemented.

**This was not a one-off.** A follow-up test pass across all 6 supported domains plus several unimplemented ones found the same failure mode a second time, in a different route: bare `"variant"` in `variant_tokens` (from the `variant_analysis` cycle) matched "structural variant" — long-read SV detection (minimap2/Sniffles), architecturally distinct from `variant_analysis_bwa_ref`'s short-read germline SNP/indel calling (bwa-mem2 + bcftools) — and silently misrouted it the same way ChIP-seq was. Fixed by removing the bare token (the more specific `"germline"`, `"vcf"`, `"snp"`, etc. tokens already cover the real route without it) and extending the same regression test. Two confirmed instances in two different domain cycles confirms this is a structural risk of keyword-substring classification itself, not a one-time mistake — treat the domain-bootstrap Rules section's collision-check step as load-bearing, not optional, every time a token list is touched.

## Environment isolation

`harness/envs/epigenomics.yaml` is a separate conda environment (`fastp`, `bwa-mem2`, `samtools`, `macs3`, `bedtools`, `matplotlib`) from both `bulk_rna_seq` and `variant_analysis`, even though `fastp`/`bwa-mem2`/`samtools` all overlap with one or the other — each domain's environment is independently installable and versioned, per the skill's rule 3.

## No shell pipes

Same discipline as `variant_analysis`: `bwa-mem2 mem` has no output flag, so `AtacBwaMem2AlignNode` captures `CommandRecord.stdout` and writes it to `aligned.sam` before handing off to `samtools sort`. Every other multi-tool step (`samtools collate/fixmate/sort/markdup`, `samtools view` quality filtering, `macs3 callpeak`) uses a native `-o`/positional output argument.

## Promotion gate output

```
PYTHONPATH="harness/src:." python harness/skills/domain-bootstrap/scripts/validate_domain_promotion.py --route-id atac_seq_macs3_ref
```

prints `"ready": true` once all 9 nodes have real `run()` methods and the route passes `validate_official_route` — the gate script itself needed zero changes from the `variant_analysis` cycle, confirming it generalizes across domains as intended.

---

# Domain Bootstrap: metagenome (Kraken2/Bracken) worked example

The third domain built with the `domain-bootstrap` skill.

## Assay scope decision

Taxonomic profiling only — "what organisms are in this sample and in what abundance," not assembly-based MAG binning (nf-core/mag's heavier MEGAHIT+MetaBAT2+CheckM+GTDB-TK chain, deliberately excluded as too heavy for the REF-only philosophy).

## Stage decomposition

| stage_id | tool_id (tier) | node_type |
|---|---|---|
| `input_validation` | `metagenome_input_validator` (REF) | `MetagenomeInputValidatorNode` |
| `read_trimming` | `metagenome_fastp_trim` (REF) | `MetagenomeFastpTrimNode` |
| `taxonomic_classification` | `kraken2_classify` (REF) / `centrifuge_classify` (ALT, planned) | `Kraken2ClassifyNode` |
| `abundance_estimation` | `bracken_reestimate` (REF) | `BrackenAbundanceNode` |
| `profile_visualization` | `metagenome_visualization` (REF) | `MetagenomeVisualizationNode` |
| `reporting` | `metagenome_report` (REF) | `MetagenomeReportNode` |

## REF selection rationale

Kraken2 (not Centrifuge) for classification: the fast, single-database-dependency community standard for shotgun metagenomic taxonomic classification. Centrifuge is a credible lower-memory alternative, recorded as `tier: "ALT"`, `runnable_node_status: "planned"`.

Bracken for abundance re-estimation: Kraken2's standard companion tool, shares the same database, no extra dependency.

## Environment isolation

`harness/envs/metagenome.yaml` is a separate conda environment (`fastp`, `kraken2`, `bracken`, `matplotlib`) from `bulk_rna_seq`/`variant_analysis`/`epigenomics`, even though `fastp` overlaps with all three.

## No shell pipes — and no stdout-capture workaround either

Unlike `variant_analysis` (bwa-mem2 mem) and `epigenomics` (also bwa-mem2 mem), **every** tool in this route has a native output-file flag — Kraken2's `--report`/`--output`, Bracken's `-o`/`-w` — so this is the first domain-bootstrap cycle where no `CommandRecord.stdout`-capture workaround was needed anywhere in the route.

## Promotion gate output

```
PYTHONPATH="harness/src:." python harness/skills/domain-bootstrap/scripts/validate_domain_promotion.py --route-id metagenome_kraken2_ref
```

prints `"ready": true` once all 6 nodes have real `run()` methods — the gate script itself needed zero changes for the third consecutive cycle.

---

# Domain Bootstrap: genome_assembly (SPAdes) worked example

The fourth and final domain built for the `planned_domains` entries that existed when `domain-bootstrap` began.

## Assay scope decision

Single bacterial isolate, short-read de novo assembly only — no hybrid (long+short) assembly, no MAG binning, no genome annotation. This route has no reference genome input at all, unlike `variant_analysis`/`epigenomics`.

## Stage decomposition

| stage_id | tool_id (tier) | node_type |
|---|---|---|
| `input_validation` | `assembly_input_validator` (REF) | `AssemblyInputValidatorNode` |
| `read_trimming` | `assembly_fastp_trim` (REF) | `AssemblyFastpTrimNode` |
| `assembly` | `spades_assemble` (REF) / `megahit_assemble` (ALT, planned) | `SpadesAssembleNode` |
| `assembly_qc` | `quast_qc` (REF) | `QuastQcNode` |
| `assembly_visualization` | `assembly_visualization` (REF) | `AssemblyVisualizationNode` |
| `reporting` | `assembly_report` (REF) | `AssemblyReportNode` |

## REF selection rationale

SPAdes (not MEGAHIT) for assembly: the de facto standard Illumina bacterial-isolate assembler, run in `--isolate` mode (SPAdes' own recommended flag for single-isolate short-read data). MEGAHIT trades assembly quality for speed/memory on large or complex genomes — recorded as `tier: "ALT"`, `runnable_node_status: "planned"`.

QUAST for assembly QC: the standard reference-free assembly-quality-metrics tool (N50, total length, contig count) used across essentially every genome assembly pipeline.

## Environment isolation

`harness/envs/genome_assembly.yaml` is a separate conda environment (`fastp`, `spades`, `quast`, `matplotlib`).

## Executable naming gotcha

`spades.py` and `quast.py` are invoked with a `.py` suffix (the real name the bioconda packages install), unlike every other tool in every prior cycle (`bwa-mem2`, `samtools`, `kraken2`, `bracken`, all suffix-less) — `required_executables` in `DomainEnvironmentRequirements` must use the exact invoked name or `CondaEnvironmentProbe.executable_exists`'s `which` check silently fails to find them.

## No shell pipes — and no stdout-capture workaround

Both `spades.py -o` and `quast.py -o` write their own output directly to the given output directory — no `CommandRecord.stdout`-capture workaround needed, the second consecutive cycle (after `metagenome`) where this holds for every stage.

## A lesson from the `metagenome` cycle: single-output-file tools avoid a whole bug class

The `metagenome` cycle's final review caught one Important bug: Bracken writes *two* similarly-shaped output files (`-o` and `-w`), and the visualization script initially read the wrong one — invisible to tests because the test fixture was misnamed. QUAST writes exactly **one** report file (`report.tsv`) per run, so that specific failure mode structurally cannot recur here — worth calling out in this skill's examples as a concrete "prefer tools with one unambiguous output file where possible" data point for future domain-bootstrap cycles.

## Promotion gate output

```
PYTHONPATH="harness/src:." python harness/skills/domain-bootstrap/scripts/validate_domain_promotion.py --route-id genome_assembly_spades_ref
```

prints `"ready": true` once all 6 nodes have real `run()` methods — the gate script itself needed zero changes for the fourth consecutive cycle.
