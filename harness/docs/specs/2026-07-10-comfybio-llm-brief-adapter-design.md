# ComfyBIO Phase A — Claude LLM Brief Adapter Design

**Date:** 2026-07-10
**Status:** Approved (brainstorming)
**Slice:** 4 of the ComfyBIO wiring roadmap (LLM brief extraction).

## Goal

Replace the deterministic keyword parser (`parse_prompt`) that turns a panel prompt into an `AnalysisBrief` with a Claude-backed extractor, so the panel's advertised LLM-driven workflow generation is real — while keeping the existing registry/TSR planner, workflow builder, and ComfyUI nodes untouched. When no Anthropic credential (or SDK) is available, the deterministic parser is the fallback so the feature degrades gracefully and never crashes a route.

## Guiding constraint: minimize changes to the existing structure

The user's explicit constraint is to apply this **while modifying the pre-built structure as little as possible.** Concretely:

- **New code is additive** — a new `bioflow_harness/llm/` package. Nothing existing is restructured.
- **Unchanged:** `parser/prompt_parser.py` (reused verbatim as the fallback), `planner/*`, `comfy/workflow_builder.py`, `models/prompt_contract.py` (`AnalysisBrief`), `models/registry_contract.py`, the registry YAML, all `nodes/*`, and `server/dto.py` — the DTOs **already** carry `provider` and `model` with defaults, and the panel already sends them, so no DTO change is needed.
- **Minimal edits:** two call-sites in `server/handlers.py` (swap `parse_prompt(...)` for the new orchestrator), and the Claude model-ID list in `web/js/comfybio_panel.js`.

## Architecture

LLM is the **understanding layer**; the registry/TSR is the **decision layer**. The LLM extracts a structured `AnalysisBrief` from free text; that brief flows unchanged into the existing `WorkflowPlanner.plan(brief)` → `WorkflowBuilder.build(plan, bindings)` path. The LLM never bypasses the registry — it feeds it.

```
panel prompt ──▶ extract_brief(text, provider, model)
                    │  provider=="claude" & SDK+creds ok
                    ├──▶ ClaudeBriefExtractor ──▶ AnalysisBrief
                    │  else / on any failure
                    └──▶ parse_prompt (deterministic) ──▶ AnalysisBrief
                                                              │
                          existing, unchanged ───────────────▼
                    WorkflowPlanner.plan ─▶ WorkflowBuilder.build ─▶ workflow JSON
```

### New package `bioflow_harness/llm/`

**`brief_extractor.py`** — provider routing + fallback orchestration.

- A `BriefExtractor` `Protocol` with one method: `extract(request_text: str) -> AnalysisBrief`. This is the extension seam for future providers.
- `@dataclass(frozen=True) ExtractionMeta` — `source: str` (`"claude"` | `"deterministic"`), `model: str`, `note: str` (human-readable provenance/fallback reason).
- `extract_brief(request_text: str, provider: str = "codex", model: str = "", *, client=None) -> tuple[AnalysisBrief, ExtractionMeta]`:
  - `provider == "claude"` → construct `ClaudeBriefExtractor(model or DEFAULT_MODEL, client=client)`, call `.extract()`. On **any** exception (SDK missing, no credential, API error, refusal, schema-invalid), catch it, fall back to `parse_prompt`, and return meta noting the reason.
  - `provider in {"codex", "gemini"}` → `parse_prompt`, meta note `"provider '<p>' not yet wired; used deterministic parser"`.
  - Success path returns meta `source="claude"`, `note="brief extracted via claude/<model>"`.
- `DEFAULT_MODEL = "claude-opus-4-8"`.
- The returned brief is annotated: `extract_brief` appends the meta `note` to a **copy** of the brief's `confidence_notes` (via `dataclasses.replace`) so provenance is visible downstream without mutating `parse_prompt`'s output contract.

**`claude_extractor.py`** — the Claude call.

- `class ClaudeBriefExtractor` with `__init__(self, model: str, *, client=None)`.
- `extract(request_text) -> AnalysisBrief`:
  - If `client` is None, lazily `import anthropic` (inside the method, not at module top) and construct `anthropic.Anthropic()` (zero-arg → resolves `ANTHROPIC_API_KEY` or an `ant` profile). A missing SDK raises `ImportError`; missing credential surfaces as an `anthropic` error on the call — both are caught by `extract_brief`.
  - One `client.messages.create(model=self.model, max_tokens=1024, output_config={"format": {"type": "json_schema", "schema": BRIEF_SCHEMA}}, system=SYSTEM_PROMPT, messages=[{"role": "user", "content": request_text}])`. No thinking config (adaptive is off by default on opus-4-8; extraction doesn't need it); optional `output_config["effort"] = "low"`.
  - Guard `response.stop_reason == "refusal"` → raise a `BriefExtractionError`.
  - `output_config.format` guarantees the first text block is schema-valid JSON: take `next(b.text for b in response.content if b.type == "text")`, `json.loads`, and build `AnalysisBrief(**_coerce(data))`.
- `BRIEF_SCHEMA` — a JSON Schema mirroring `AnalysisBrief`'s LLM-relevant fields with `additionalProperties: false` and `required` on every property (structured-outputs requirement): `analysis_type` (string), `domain` (enum `["bulk_rna_seq", "scrna_seq", "unsupported"]`), `input_assets` (array of string), `organism` (string; empty string means unknown — the schema can't express nullable cleanly, so map `""` → `None` when building the brief), `expected_outputs` (array), `constraints` (array), `preferred_tools` (array), `data_characteristics` handled as an array of `{key, value}` pairs (structured outputs can't express open-ended object maps) then folded into a dict.
- `SYSTEM_PROMPT` — states the task (extract a structured bioinformatics analysis brief), enumerates the two supported domains and the meaning of each field, and instructs the model to classify as `"unsupported"` when the request is neither bulk RNA-seq nor single-cell RNA-seq. It mirrors the domain vocabulary `parse_prompt` and the registry already use, so the classifier stays inside what TSR can route.
- `BriefExtractionError(RuntimeError)` for refusal / malformed output — caught by `extract_brief`.

### `AnalysisBrief` mapping

`AnalysisBrief` (unchanged) has: `analysis_type`, `domain`, `input_assets`, `organism: str | None`, `expected_outputs`, `constraints`, `preferred_tools`, `confidence_notes`, `submission_source="text_prompt"`, `data_characteristics`. The extractor fills the first seven from the schema; `submission_source` stays `"text_prompt"`; `confidence_notes` is set by `extract_brief` from the meta note.

## Handler integration (the only server change)

`server/handlers.py`, two call-sites currently reading:
```python
brief = parse_prompt(request.request_text)
```
become:
```python
brief, _meta = extract_brief(request.request_text, request.provider, request.model)
```
Everything downstream (`route_for_domain`, `WorkflowPlanner`, `WorkflowBuilder`, response DTOs) is unchanged. `parse_prompt`'s import may stay (still used indirectly through the fallback) or be dropped from `handlers.py` since it's now reached via `extract_brief`; the design drops the now-unused direct import to keep the file honest.

## Panel change (cosmetic accuracy)

`web/js/comfybio_panel.js`, `PROVIDER_MODELS.claude` currently lists fictional IDs (`claude-opus-4.6`, `claude-sonnet-5.0`, `claude-haiku-4.5`). Replace with real IDs: `["claude-opus-4-8", "claude-sonnet-5", "claude-haiku-4-5"]` (opus-4-8 first = default selection). No other panel logic changes; provider/model are already sent in the compile/generate payloads.

## Credentials & dependency

- **Credential:** the zero-arg `anthropic.Anthropic()` resolves `ANTHROPIC_API_KEY` (or an `ant auth login` profile) itself. No key-management code, no key in the repo. Absent credential → caught → deterministic fallback.
- **Dependency:** `anthropic` is **optional**. It is imported lazily inside `ClaudeBriefExtractor.extract`, so importing `bioflow_harness`, loading the ComfyUI extension, and running the test suite never require it. Documented as an optional install (`pip install anthropic`) for users who want live LLM extraction.

## Error handling

`extract_brief` wraps the Claude path in a single `try/except Exception` that falls back to `parse_prompt`. Nothing in the LLM path can propagate to the route handler — a missing SDK, missing key, network error, rate limit, refusal, or malformed output all degrade to the deterministic parser with a provenance note. This matches the existing slice-1 behavior where a route must always return a usable brief.

## Testing (TDD, no network)

No test makes a real API call. `ClaudeBriefExtractor` takes an injectable `client`; tests pass a fake whose `messages.create` returns a canned response object (a small stand-in with `.stop_reason` and `.content` of text blocks carrying JSON). Cases:

1. `ClaudeBriefExtractor.extract` parses a well-formed structured response into the correct `AnalysisBrief` (domain enum, list fields, `""` organism → `None`, `data_characteristics` pairs → dict).
2. Refusal (`stop_reason == "refusal"`) raises `BriefExtractionError`.
3. Malformed / schema-violating JSON raises `BriefExtractionError`.
4. `extract_brief(provider="claude", client=fake_ok)` returns the Claude brief with `meta.source == "claude"` and a provenance note in `confidence_notes`.
5. `extract_brief(provider="claude", client=fake_raising)` falls back to `parse_prompt`, `meta.source == "deterministic"`, note records the reason.
6. `extract_brief(provider="codex")` uses the deterministic parser without touching Claude (note records "not yet wired").
7. Handler-level: `compile_spec` / `generate_workflow` still produce the same shape they do today when the extractor falls back (i.e. the swap is behavior-preserving in the no-credential default).

## Out of scope (YAGNI)

- Real `codex` / `gemini` adapters (interface is left for them; they fall back today).
- Streaming, tool use, prompt caching, retries beyond the SDK's built-in retry.
- scRNA execution, route-error hardening, stale example JSONs (separate roadmap items B/C/D, not part of "complete product = LLM adapter").
- Any change to `AnalysisBrief`, the planner, the builder, the registry, or the nodes.

## Risk / Rollback

- **Behavior-preserving default:** with no `ANTHROPIC_API_KEY`, every path falls back to today's `parse_prompt`, so the default deployment behaves exactly as it does now — the LLM is purely additive.
- **Structured-outputs model support:** `output_config.format` is supported on `claude-opus-4-8`, `claude-sonnet-5`, and `claude-haiku-4-5` (the panel's offered models). No other model is selectable.
- **Rollback:** revert the `llm/` package, the two handler lines, and the panel list.
