---
name: tool-ranking
description: Use when inspecting, explaining, or validating REF versus ALT tool assignments in the tool selection registry — why tools like DESeq2, salmon, or MultiQC sit in a given tier, whether a request's context is worth recording as a reason to consider an ALT such as STAR or featureCounts, and whether the official route validates before it is implementation-ready.
---

# Tool Ranking

Use this skill to inspect or explain `REF` and `ALT` registry assignments, including whether a request's context is worth recording as a reason to look at an ALT tool.

## Rules

- `REF` means the recommended tool for the stage and eligible for the official MVP route. `planner/tool_selector.py::ToolSelector.select_official_route()` only ever selects `REF`-tier, `runnable_node_status: "runnable"` tools — this is the only tool-selection code path that actually runs today.
- `ALT` means a credible alternative recorded in the registry (`tier_rationale`, `context_routing_rules`) for a developer or reviewer to read — it requires a recorded reason before it is ever wired into a route, but there is no runtime code that automatically promotes a request to an ALT tool. Treat ALT selection as a documentation/registry-editing decision, not a live per-request branch.
- `DESeq2` is `REF` for differential expression in the official MVP route.
- `MultiQC` is `ALT` for enhanced QC aggregation, not the required DESeq2 visualization gate.
- The official route must validate with `bioflow_harness.cli --validate-registry --route-id <route_id>` before it is treated as implementation-ready.

## REF selection rubric

When choosing which tool becomes `REF` for a new stage (see `domain-bootstrap`), weigh these in order — drawn from the 4 domains bootstrapped so far (`references/examples.md` in `domain-bootstrap` has the full rationale for each):

1. **Community usage / de facto standard** — e.g. bwa-mem2 for short-read alignment, Kraken2 for taxonomic classification, SPAdes for bacterial isolate assembly.
2. **Downstream compatibility** — the tool's output must feed the next REF stage without a format-conversion detour (bwa-mem2's bwa-mem-compatible SAM output; Bracken sharing Kraken2's database).
3. **Reproducibility** — no Java runtime, no bundled reference-data requirement beyond what the user supplies (bcftools over GATK HaplotypeCaller for exactly this reason).
4. **Conda-installable weight** — prefer the lightest dependency set that is still credible; this is why a domain gets its own conda environment (rule 3 in `domain-bootstrap`) rather than trying to share one across domains.
5. **Single unambiguous output file, where tools differ on this** — Bracken's two similarly-shaped outputs (`-o` vs `-w`) caused a real bug (the visualization script read the wrong one); QUAST's one-file-per-run report structurally avoids that failure mode. All else equal, prefer the tool with less output-file ambiguity.

A credible tool that loses on these criteria is still worth recording as `tier: "ALT"`, `runnable_node_status: "planned"` rather than dropped — e.g. GATK, MEGAHIT, Centrifuge, MultiQC.

## Evidence tier: tagging *why* a rubric criterion applies, not just asserting it

Every tool entry carries `evidence_tier` and `evidence_citation`, so a REF/ALT rationale is never just an unattributed developer claim. This is the mechanism behind the "Evidence Hierarchy for Tier Assignment" described in the project paper (`paper.md` Section 3.2.1):

1. `primary_openebench` — backed by a concretely identified ELIXIR OpenEBench/bio.tools community benchmarking challenge or adoption-frequency statistic for this exact comparison. Do not use this tag unless you can name and check the actual challenge/community page — as of this registry's last citation pass, no such page had been independently confirmed for any tool here, so this tier is currently unused.
2. `secondary_literature` — OpenEBench/bio.tools has no dedicated challenge for the comparison; backed instead by a specific, checkable benchmark paper cited in `evidence_citation` (author/year/venue/URL), or explicitly reusing the citation already verified for the other side of the same head-to-head comparison (e.g. `gatk_haplotype_caller`'s citation just points back to `bcftools_call`'s). 55 of 93 tools carry this tag after two citation passes — see the registry for the exact text per tool. Where the literature is mixed (e.g. `deseq2_analysis`, `salmon_quant`, `samtools_markdup`), the citation says so rather than overclaiming a unanimous win, and flags itself as weaker evidence when the only source found is a community forum thread rather than a published benchmark (e.g. `samtools_markdup`/`atac_samtools_markdup`/`picard_markduplicates`).
3. `not_applicable_internal_node` — a permanent classification, not a to-do: this entry is a ComfyBIO-authored glue/validation/reporting node (input validators, most `*_visualization`/`*_report` nodes) with no competing external tool to benchmark against, so no citation is ever owed. 17 tools are tagged this way. Don't confuse this with tier 4 below — if a tool has a recorded `ALT` alternative (e.g. `comfybio_report` vs `multiqc`), it's a real REF-vs-ALT choice and belongs in tier 2, not here.
4. `pending_citation_review` — a real REF-vs-ALT choice between external tools that hasn't been backed by a verified citation yet. 21 tools remain here after two citation passes (mostly niche ALT entries — e.g. `snpeff_annotate`, `humann_functional`, `bwa_align`, `sambamba`) — do the research before upgrading one of these, don't guess.

When adding a new REF tool (during `domain-bootstrap`) or upgrading an existing rationale, search for a real citation before writing `secondary_literature` — an invented or unchecked citation is worse than leaving the tool `pending_citation_review`, since it looks evidence-backed without being verifiable. Check whether the other side of the same comparison already has a citation first (tier 2's reuse case) before starting new research. `models/registry_contract.py::SUPPORTED_EVIDENCE_TIERS` is the enforced enum; `ToolEntry.validate()` rejects any other value.

## Context override guidance

Some requests mention a need that a REF tool doesn't cover (e.g. explicit genome alignment, or a QC dashboard beyond fastp's report). Use this to decide whether that's worth recording, not to switch tools at runtime:

- Keep the official route (e.g. `bulk_rna_seq_salmon_ref`) on `REF` tools unless the user explicitly requests a different route.
- A genome-alignment-specific request may point at the `STAR`/`featureCounts` `ALT` entries; a request for enhanced QC aggregation may point at the `MultiQC` `ALT` entry. Neither replaces a required stage (e.g. MultiQC does not replace DESeq2 visualization).
- Recording the reason means adding or checking a `context_routing_rules` entry on the tool in the registry — it does not mean generating a workflow that runs the ALT tool, since no domain route currently implements ALT execution.

## REF is never live-avoided

There is no situation, at request-handling time, where an agent should cause a non-`REF` tool to be selected for the official route. `ToolSelector.select_official_route()` (`planner/tool_selector.py`) raises `ValueError` if any stage's tool isn't `tier: "REF"` and `runnable_node_status: "runnable"` — this is a hard invariant, not a default that can be reasoned around per-request. The only two legitimate ways a stage's `REF` tool doesn't end up running are:

1. **The stage is `optional` and its precondition isn't met** (e.g. skip `fastp_trim` if reads are already trimmed, skip `reference_indexing` if a pre-built index is supplied) — this *omits* the stage, it does not substitute a different tool into it.
2. **The domain has no implemented route at all** — this surfaces `planning_required`, which is a "no route exists" outcome, not a "we avoided REF" outcome.

Wanting a different tool for a stage that does have a route (e.g. "use STAR instead of salmon") is a `domain-bootstrap` registry-editing decision made by a human developer, never a runtime agent choice — see `domain-bootstrap`'s Rules on tool selection being a human decision. If a `REF` tool would plausibly fail for a specific request (e.g. an incompatible reference genome), there is currently no automatic ALT fallback — it will fail at execution time; this is a known gap, not a case to route around by picking ALT yourself.

## How to run scripts

`rank_tools.py` is the only script this skill owns; it lists REF/ALT tier and rationale for tools tagged to a stage. Run from the repository root:

    PYTHONPATH="harness/src:." python harness/skills/tool-ranking/scripts/rank_tools.py <stage> --registry harness/registry/tool_selection_registry.yaml

Registry validation reuses the project's own CLI instead of a duplicate script — `--validate-registry` now takes `--route-id` so it covers any of the 6 supported routes, not just the bulk route:

    PYTHONPATH="harness/src:." python -m bioflow_harness.cli --validate-registry --route-id <route_id> --registry harness/registry/tool_selection_registry.yaml

See [references/examples.md](references/examples.md) for worked REF/ALT and context-override examples.
