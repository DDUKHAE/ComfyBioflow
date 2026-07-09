# ComfyBIO Slice 1: Server Bridge + Canvas Load — Design

Date: 2026-07-09
Status: Approved (design), pending implementation plan

## Context

The ComfyBIO panel (`web/js/comfybio_panel.js`) is currently a static mockup: all
step data is hardcoded, no backend calls are made, and the "Generate Graph" button
only dispatches an unhandled DOM event. A deterministic backend pipeline already
exists (`parse_prompt` → `WorkflowPlanner.plan` → `WorkflowBuilder.build` → ComfyUI
workflow JSON), driven only by the CLI (`cli.build_workflow`). There is no HTTP
surface connecting the panel to that pipeline.

The overall goal (agreed separately) is a four-slice program that connects the panel
to real workflow generation, canvas loading, path-parameterized execution, and LLM
brief extraction. This document specifies **Slice 1** only.

## Goal (Slice 1)

Wire the panel's three actions (Submit / Approve / Generate) to the existing
deterministic backend over HTTP, and auto-load the generated workflow JSON onto the
ComfyUI canvas via `app.loadGraphData`.

### In scope

- HTTP bridge exposing `compile` (prompt → spec) and `generate` (spec → workflow JSON),
  plus a `health` probe.
- Panel refactor from hardcoded `STEP_CATALOG` rendering to data-driven rendering fed
  by the server response.
- Auto-load of the returned workflow JSON onto the canvas.

### Out of scope (deferred)

- **Panel path injection / multi-sample handling** → Slice 2. Node widget values remain
  the existing fixture paths.
- **Real node execution** → Slice 3. The graph appears on the canvas; running it via
  Queue Prompt still does not execute most nodes.
- **Claude brief extraction** → Slice 4. Slice 1 uses the existing keyword
  `prompt_parser`.
- **Migrating `custom_nodes/` → top-level `nodes/`** → rides with Slice 3, which rewrites
  those node classes anyway.

### Known limitation (explicit)

`generate` does **not** honor arbitrary user reordering/replacement of steps in the
Tool Select tab. It rebuilds deterministically from `request_text`. If the approved
sequence matches what `compile` returned (the common path), the result is correct.
Edits that diverge from the deterministic route are ignored for Slice 1 and surfaced to
the user as a warning. Wiring custom sequences into the builder (with artifact-format
compatibility validation) is deferred to a later slice.

## Target project layout

```
ComfyBioflow/
  nodes/     # ComfyUI custom node classes executed in ComfyUI (populated in Slice 3)
  web/       # panel / frontend assets
  harness/   # natural-language / LLM / TSR: parser, planner, registry, builder, server bridge
  tests/     # all tests
```

Slice 1 adds to `harness/` (server bridge), `web/` (panel), and `tests/` only. It does
not touch `nodes/` or the existing `custom_nodes/` package.

## Architecture

### Components

New Python package `harness/src/bioflow_harness/server/`:

- `dto.py` — request/response dataclasses (see Data Contracts).
- `handlers.py` — pure functions `dict -> dict`, testable without aiohttp/PromptServer:
  - `compile_spec(payload)` — `parse_prompt` → `WorkflowPlanner.plan` → `CompileResponse`.
  - `generate_workflow(payload)` — reuse `build_workflow` deterministic path → workflow
    JSON dict.
  - `list_stage_candidates(registry, stage)` — alternative tools for a stage, drawn from
    registry `stage_tags`.
- `routes.py` — `register_routes(server)` attaching thin aiohttp handlers that parse the
  request body, call `handlers.py`, and return `web.json_response(...)`.

Top-level `__init__.py` calls `register_comfybio_routes()` inside a `try/except` so that
importing the package outside ComfyUI (tests, CLI) does not require `PromptServer.instance`.

Frontend `web/js/comfybio_panel.js`:

- Call the backend with `api.fetchApi("/comfybio/...")`.
- Generalize `createStep(key)` → `createStep(stepData)`; render the Tool Select tab from
  server-provided steps. The existing constant catalog remains only as the pre-Submit
  placeholder layout.
- Submit → `/comfybio/compile`; Approve → local gate; Generate → `/comfybio/generate`
  then `app.loadGraphData(workflow)`. Remove the old `dispatchEvent` / `console.info`.

### Endpoints

- `POST /comfybio/compile` — body `{provider, model, request_text, resources[]}` →
  `CompileResponse`. Unsupported domain returns the existing `planning_required` payload.
- `POST /comfybio/generate` — body `{provider, model, request_text, resources[], steps[]}`
  → `GenerateResponse` with the workflow JSON.
- `GET /comfybio/health` — liveness probe so the panel can show "backend offline" instead
  of silently staying in mock mode.

## Data contracts (DTOs)

Defined in `server/dto.py` as dataclasses; reuse/extend `ui/request_contract.py`
(`PromptSubmission`) where it fits.

```
CompileRequest   = {provider, model, request_text, resources:[{label, type, path}]}
StepDTO          = {stage_id, stage_label, tool_id, tool_label,
                    input_types, output_types, tier, rationale,
                    candidates:[{tool_id, label, tier, note}]}
CompileResponse  = {status, domain, route_id, steps:[StepDTO], message?, confidence_notes?}
GenerateRequest  = {provider, model, request_text, resources, steps}
GenerateResponse = {status, workflow, route_id, domain, message?}
```

### Data flow

```
Panel Submit  → POST /comfybio/compile  → parse_prompt → plan → StepDTO[] → render Tool Select
Panel Approve → local gate (enables Generate)
Panel Generate→ POST /comfybio/generate → build_workflow (deterministic) → workflow JSON
              → app.loadGraphData(workflow)  → graph appears on canvas
```

Stage candidates: tools whose registry `stage_tags` include the stage, surfaced as the
Replace options for that step.

## Error handling

- Unsupported domain → `compile` returns `planning_required`; panel shows guidance +
  `next_steps` and disables Generate.
- Backend offline / non-200 → panel catches, shows an error in the message area, keeps
  buttons enabled to retry. No silent fallback to mock data.
- Registry/plan exceptions → 400/500 JSON with an error message; panel surfaces it.
- `loadGraphData` failure (malformed JSON) → caught in JS, error shown.
- `PromptServer.instance` absent at import (tests/CLI) → route registration guarded;
  handler logic unit-tested directly.

## Testing

- Python unit tests in `tests/test_comfybio_server.py`:
  - `compile_spec` for bulk_rna_seq, scrna_seq, and unsupported inputs → expected StepDTO
    lists / `planning_required`.
  - `generate_workflow` → returned JSON passes `validate_workflow_export`.
  - `list_stage_candidates` → correct alternatives from the registry.
  - DTO dict round-trip serialization.
- Handlers are pure `dict -> dict` functions, tested without aiohttp.
- No JS test runner exists → a **manual load test** is documented: launch ComfyUI, open
  the panel, Submit → Approve → Generate, confirm the graph is drawn on the canvas.
- pytest rootdir / `pyproject.toml` adjusted so `tests/` at the repo top level is
  collected.

## File/module summary

```
harness/src/bioflow_harness/server/__init__.py
harness/src/bioflow_harness/server/dto.py
harness/src/bioflow_harness/server/handlers.py
harness/src/bioflow_harness/server/routes.py
__init__.py                       # register_comfybio_routes() (guarded)
web/js/comfybio_panel.js          # data-driven rendering + api calls
tests/test_comfybio_server.py     # handler / DTO unit tests
```
