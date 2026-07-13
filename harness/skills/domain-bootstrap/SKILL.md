# Domain Bootstrap

Use this skill when adding a new ComfyBIO analysis domain that is not yet in `supported_domains`.

## Process

1. **Decompose into canonical stages.** One ComfyBIO node per functional operation, the way `bulk_rna_seq_salmon_ref` and `variant_analysis_bwa_ref` do — do not bundle multiple tool invocations behind one stage_id unless they are genuinely one operation (see `custom-node-spec`).
2. **Select the REF tool per stage** using the `tool-ranking` skill's criteria: community usage, downstream compatibility, reproducibility, and — new for this skill — conda-installable weight. Prefer the lightest dependency set that is still a credible default (e.g. bcftools over GATK for the variant-calling REF stage; GATK is recorded as `ALT`/`planned` instead of implemented).
3. **Give the domain its own conda environment.** Add a `bioflow_harness.runtime.environment.DomainEnvironmentRequirements` and a `harness/envs/<domain>.yaml`. Never reuse another domain's environment, even if the executable overlaps — each domain's env is independently installable and versioned.
4. **Author the nodes** following `node-implementation-design`: core UI params as widgets, advanced/route-specific flags in `extra_command`, `STRING` outputs for file/directory artifacts, `IMAGE` only for a visualization node's preview, and mark newly generated node types restart-required until ComfyUI reloads them.
5. **Add the registry route + tool entries** to `harness/registry/tool_selection_registry.yaml` under `routes`/`tools`. Every REF-tier tool in the route must have `runnable_node_status: "runnable"` and a `node_type` that resolves in `NODE_CLASS_MAPPINGS` with a real (non-inherited) `run()` method. Credible alternatives go in as separate `tier: "ALT"`, `runnable_node_status: "planned"` tool entries — record them, don't implement them, unless a user explicitly asks for that alternative.
6. **Wire domain routing**: add the domain to `planner/stage_mapper.py::ROUTES_BY_DOMAIN` and add keyword detection to `parser/prompt_parser.py::parse_prompt` (and, when available, the equivalent LLM-brief-extraction prompt/schema) so natural-language requests actually reach the new route.
7. **Run the promotion gate** (`harness/skills/domain-bootstrap/scripts/validate_domain_promotion.py --route-id <route_id>`). It must print `"ready": true` (exit code 0) before the domain moves from `planned_domains` to `supported_domains`.
8. **Never silently route an unimplemented domain to an existing one.** `stage_mapper.route_for_domain` already raises for unknown domains, and `server/handlers.py` already turns that into a `planning_required` response — do not add a fallback that maps a planned domain to a different domain's route.

## Rules

- A domain may only move from `planned_domains` to `supported_domains` after `scripts/validate_domain_promotion.py` reports `ready: true` for its route.
- Every REF-tier tool in a route must have a node with a real `run()` implementation, not a construction-only stub — the promotion gate checks this by introspecting `NODE_CLASS_MAPPINGS`.
- Tool selection for a new domain is a human (developer) decision made by following this skill, not a runtime LLM decision — this matches the TSR's expert-curated-registry design; an end user's natural-language request only ever *selects among* already-curated, already-promoted routes.
- Do not build a code-generation/scaffolding tool for this process unless repeated domain-bootstrap cycles show it's worth the engineering cost (YAGNI) — every skill in `harness/skills/` today is thin documentation plus a small validation script, and domain-bootstrap follows that same shape.
