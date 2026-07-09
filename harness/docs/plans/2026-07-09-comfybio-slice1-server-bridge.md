# ComfyBIO Slice 1: Server Bridge + Canvas Load — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the ComfyBIO panel's Submit/Approve/Generate actions to the existing deterministic backend over HTTP and auto-load the generated workflow JSON onto the ComfyUI canvas.

**Architecture:** A new `bioflow_harness.server` package exposes two pure `dict -> dict` handlers (`compile_spec`, `generate_workflow`) that reuse the existing `parse_prompt → WorkflowPlanner → WorkflowBuilder` pipeline. A thin `routes.py` attaches them to ComfyUI's `PromptServer` via aiohttp; the top-level `__init__.py` registers them behind a guard. The panel calls these endpoints with `api.fetchApi`, renders the Tool Select tab from the server response, and loads the returned workflow with `app.loadGraphData`.

**Tech Stack:** Python 3.11+, dataclasses, aiohttp (ComfyUI-provided), pytest; vanilla JS ComfyUI extension.

## Global Constraints

- Python `requires-python = ">=3.11"`; use built-in generics (`list[str]`, `str | None`).
- Handlers MUST be pure `dict -> dict` functions importable without aiohttp or `PromptServer` (import aiohttp lazily inside `register_routes`).
- Slice 1 does NOT touch node execution, `custom_nodes/`, or `nodes/`; node widget values stay as the existing fixture paths.
- `generate_workflow` rebuilds deterministically from `request_text`; user step reordering/replacement in the panel is NOT honored this slice (surface a warning, do not error).
- No silent fallback to mock data on backend failure — surface the error in the panel.
- Registry path: `harness/registry/tool_selection_registry.yaml` (JSON content, loaded with `load_registry`).
- Commit identity for this repo: `ddukhae <dongjoon69@gmail.com>` (already set locally).
- Work branch: `comfybio-slice1-server-bridge` (already checked out).

## File Structure

```
pyproject.toml                                    # NEW (repo root): pytest config for top-level tests/
harness/src/bioflow_harness/server/__init__.py    # NEW: package marker
harness/src/bioflow_harness/server/dto.py         # NEW: request/response dataclasses
harness/src/bioflow_harness/server/handlers.py    # NEW: compile_spec, generate_workflow, list_stage_candidates
harness/src/bioflow_harness/server/routes.py      # NEW: register_routes(server)
__init__.py                                        # MODIFY: register comfybio routes (guarded)
web/js/comfybio_panel.js                           # MODIFY: data-driven rendering + api calls
tests/test_comfybio_dto.py                         # NEW: DTO round-trip
tests/test_comfybio_handlers.py                    # NEW: compile/generate/candidates
tests/test_comfybio_routes.py                      # NEW: route registration
```

---

### Task 1: Top-level test harness

**Files:**
- Create: `pyproject.toml` (repo root: `ComfyBioflow/pyproject.toml`)
- Create: `tests/test_smoke.py`

**Interfaces:**
- Consumes: nothing.
- Produces: a repo-root pytest config that puts `harness/src` on `pythonpath` and collects `tests/`. All later tasks run `pytest` from the repo root.

- [ ] **Step 1: Write the failing test**

Create `tests/test_smoke.py`:

```python
def test_bioflow_harness_importable():
    import bioflow_harness  # noqa: F401
```

- [ ] **Step 2: Run it and confirm it fails (no config yet)**

Run from repo root: `cd /home/ydj/main/ComfyUI/custom_nodes/ComfyBioflow && python -m pytest tests/test_smoke.py -v`
Expected: collection error / `ModuleNotFoundError: No module named 'bioflow_harness'` (no `pythonpath` configured at root).

- [ ] **Step 3: Create the repo-root pytest config**

Create `pyproject.toml`:

```toml
[tool.pytest.ini_options]
pythonpath = ["harness/src"]
testpaths = ["tests"]
```

- [ ] **Step 4: Run it and confirm it passes**

Run: `python -m pytest tests/test_smoke.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml tests/test_smoke.py
git commit -m "test: add repo-root pytest config and top-level tests dir"
```

---

### Task 2: Server DTOs

**Files:**
- Create: `harness/src/bioflow_harness/server/__init__.py`
- Create: `harness/src/bioflow_harness/server/dto.py`
- Test: `tests/test_comfybio_dto.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `ResourceDTO(label: str, type: str, path: str)`
  - `CandidateDTO(tool_id: str, label: str, tier: str, note: str)`
  - `StepDTO(stage_id, stage_label, tool_id, tool_label, input_types: list[str], output_types: list[str], tier, rationale, candidates: list[CandidateDTO])`
  - `CompileRequest.from_dict(data: dict) -> CompileRequest` with fields `request_text, provider, model, resources: list[ResourceDTO]`
  - `GenerateRequest.from_dict(data: dict) -> GenerateRequest` with fields `request_text, provider, model, resources: list[ResourceDTO], steps: list[str]`
  - `CompileResponse(status, domain, route_id: str | None, steps: list[StepDTO], message: str | None, confidence_notes: list[str]).to_dict() -> dict`

- [ ] **Step 1: Write the failing test**

Create `tests/test_comfybio_dto.py`:

```python
from bioflow_harness.server.dto import (
    CandidateDTO,
    CompileRequest,
    CompileResponse,
    GenerateRequest,
    StepDTO,
)


def test_compile_request_from_dict_defaults():
    req = CompileRequest.from_dict({"request_text": "bulk rna-seq"})
    assert req.request_text == "bulk rna-seq"
    assert req.provider == "codex"
    assert req.resources == []


def test_compile_request_parses_resources():
    req = CompileRequest.from_dict(
        {"request_text": "x", "resources": [{"label": "input_path", "type": "path", "path": "/data/fastq"}]}
    )
    assert req.resources[0].label == "input_path"
    assert req.resources[0].path == "/data/fastq"


def test_generate_request_parses_steps():
    req = GenerateRequest.from_dict({"request_text": "x", "steps": ["fastp", "salmon"]})
    assert req.steps == ["fastp", "salmon"]


def test_compile_response_to_dict_is_nested_plain_data():
    resp = CompileResponse(
        status="ok",
        domain="bulk_rna_seq",
        route_id="bulk_rna_seq_salmon_ref",
        steps=[
            StepDTO(
                stage_id="read_qc",
                stage_label="FASTQ QC",
                tool_id="fastp_qc",
                tool_label="fastp",
                input_types=["fastq"],
                output_types=["fastp_qc_json"],
                tier="REF",
                rationale="default",
                candidates=[CandidateDTO(tool_id="fastp_qc", label="fastp", tier="REF", note="qc")],
            )
        ],
        message=None,
        confidence_notes=[],
    )
    data = resp.to_dict()
    assert data["status"] == "ok"
    assert data["steps"][0]["tool_label"] == "fastp"
    assert data["steps"][0]["candidates"][0]["tier"] == "REF"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_comfybio_dto.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'bioflow_harness.server'`.

- [ ] **Step 3: Create the package marker and DTOs**

Create `harness/src/bioflow_harness/server/__init__.py`:

```python
"""HTTP bridge between the ComfyBIO panel and the deterministic harness pipeline."""
```

Create `harness/src/bioflow_harness/server/dto.py`:

```python
from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class ResourceDTO:
    label: str
    type: str
    path: str

    @classmethod
    def from_dict(cls, data: dict) -> "ResourceDTO":
        return cls(
            label=str(data.get("label", "")),
            type=str(data.get("type", "")),
            path=str(data.get("path", "")),
        )


@dataclass(frozen=True)
class CandidateDTO:
    tool_id: str
    label: str
    tier: str
    note: str


@dataclass(frozen=True)
class StepDTO:
    stage_id: str
    stage_label: str
    tool_id: str
    tool_label: str
    input_types: list[str]
    output_types: list[str]
    tier: str
    rationale: str
    candidates: list[CandidateDTO] = field(default_factory=list)


@dataclass(frozen=True)
class CompileRequest:
    request_text: str
    provider: str = "codex"
    model: str = ""
    resources: list[ResourceDTO] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "CompileRequest":
        return cls(
            request_text=str(data.get("request_text", "")),
            provider=str(data.get("provider", "codex")),
            model=str(data.get("model", "")),
            resources=[ResourceDTO.from_dict(item) for item in data.get("resources", [])],
        )


@dataclass(frozen=True)
class GenerateRequest:
    request_text: str
    provider: str = "codex"
    model: str = ""
    resources: list[ResourceDTO] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "GenerateRequest":
        return cls(
            request_text=str(data.get("request_text", "")),
            provider=str(data.get("provider", "codex")),
            model=str(data.get("model", "")),
            resources=[ResourceDTO.from_dict(item) for item in data.get("resources", [])],
            steps=[str(step) for step in data.get("steps", [])],
        )


@dataclass(frozen=True)
class CompileResponse:
    status: str
    domain: str
    route_id: str | None
    steps: list[StepDTO] = field(default_factory=list)
    message: str | None = None
    confidence_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_comfybio_dto.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add harness/src/bioflow_harness/server/__init__.py harness/src/bioflow_harness/server/dto.py tests/test_comfybio_dto.py
git commit -m "feat: add ComfyBIO server DTOs"
```

---

### Task 3: compile_spec and list_stage_candidates handlers

**Files:**
- Create: `harness/src/bioflow_harness/server/handlers.py`
- Test: `tests/test_comfybio_handlers.py`

**Interfaces:**
- Consumes: `CompileRequest`, `CompileResponse`, `StepDTO`, `CandidateDTO` from Task 2; `parse_prompt`, `route_for_domain`, `load_registry`, `WorkflowPlanner`, `ToolRegistry`.
- Produces:
  - `DEFAULT_REGISTRY_PATH: Path`
  - `list_stage_candidates(registry: ToolRegistry, stage_id: str) -> list[CandidateDTO]`
  - `compile_spec(payload: dict, registry_path: Path | None = None) -> dict`

- [ ] **Step 1: Write the failing test**

Create `tests/test_comfybio_handlers.py`:

```python
from bioflow_harness.server.handlers import compile_spec


def test_compile_spec_bulk_rna_seq_returns_salmon_route():
    result = compile_spec({"request_text": "Analyze this FASTQ folder as bulk RNA-seq, human, treated vs control with DESeq2."})
    assert result["status"] == "ok"
    assert result["domain"] == "bulk_rna_seq"
    assert result["route_id"] == "bulk_rna_seq_salmon_ref"
    tool_ids = [step["tool_id"] for step in result["steps"]]
    assert "fastp_qc" in tool_ids
    assert "salmon_quant" in tool_ids
    read_qc = next(step for step in result["steps"] if step["stage_id"] == "read_qc")
    assert any(c["tool_id"] == "fastp_qc" for c in read_qc["candidates"])


def test_compile_spec_scrna_returns_scanpy_route():
    result = compile_spec({"request_text": "single-cell RNA-seq with scanpy, clustering and umap and marker genes"})
    assert result["status"] == "ok"
    assert result["domain"] == "scrna_seq"
    assert result["route_id"] == "scrna_seq_scanpy_ref"


def test_compile_spec_unsupported_domain_is_planning_required():
    result = compile_spec({"request_text": "please assemble a bacterial genome"})
    assert result["status"] == "planning_required"
    assert result["route_id"] is None
    assert "planning is required" in result["message"].lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_comfybio_handlers.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'bioflow_harness.server.handlers'`.

- [ ] **Step 3: Write the handler**

Create `harness/src/bioflow_harness/server/handlers.py`:

```python
from __future__ import annotations

from pathlib import Path

from bioflow_harness.models.registry_contract import ToolRegistry
from bioflow_harness.parser.prompt_parser import parse_prompt
from bioflow_harness.planner.stage_mapper import route_for_domain
from bioflow_harness.planner.tool_selector import load_registry
from bioflow_harness.planner.workflow_planner import WorkflowPlanner
from bioflow_harness.server.dto import (
    CandidateDTO,
    CompileRequest,
    CompileResponse,
    StepDTO,
)

DEFAULT_REGISTRY_PATH = (
    Path(__file__).resolve().parents[3] / "registry" / "tool_selection_registry.yaml"
)


def list_stage_candidates(registry: ToolRegistry, stage_id: str) -> list[CandidateDTO]:
    return [
        CandidateDTO(tool_id=tool.id, label=tool.label, tier=tool.tier, note=tool.summary)
        for tool in registry.tools
        if stage_id in tool.stage_tags
    ]


def compile_spec(payload: dict, registry_path: Path | None = None) -> dict:
    request = CompileRequest.from_dict(payload)
    registry = load_registry(registry_path or DEFAULT_REGISTRY_PATH)
    brief = parse_prompt(request.request_text)
    try:
        route_for_domain(brief.domain)
    except ValueError:
        return CompileResponse(
            status="planning_required",
            domain=brief.domain,
            route_id=None,
            steps=[],
            message=f"Workflow planning is required before generating domain: {brief.domain}",
            confidence_notes=list(brief.confidence_notes),
        ).to_dict()

    plan = WorkflowPlanner(registry).plan(brief)
    steps = [
        StepDTO(
            stage_id=stage.stage_id,
            stage_label=stage.stage_label,
            tool_id=stage.selected_tool_id,
            tool_label=registry.tool_by_id(stage.selected_tool_id).label,
            input_types=list(stage.required_inputs),
            output_types=list(stage.produced_outputs),
            tier=stage.selected_tier,
            rationale=stage.rationale,
            candidates=list_stage_candidates(registry, stage.stage_id),
        )
        for stage in plan.stages
    ]
    return CompileResponse(
        status="ok",
        domain=plan.domain,
        route_id=plan.route_id,
        steps=steps,
        message=None,
        confidence_notes=[],
    ).to_dict()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_comfybio_handlers.py -v`
Expected: PASS (3 tests). If `test_compile_spec_bulk_rna_seq_returns_salmon_route` fails on a candidate assertion, print `result["steps"]` and confirm the registry stage_id/stage_tags alignment; adjust only the test's expected `stage_id` to match the registry, not the handler logic.

- [ ] **Step 5: Commit**

```bash
git add harness/src/bioflow_harness/server/handlers.py tests/test_comfybio_handlers.py
git commit -m "feat: add ComfyBIO compile_spec handler"
```

---

### Task 4: generate_workflow handler

**Files:**
- Modify: `harness/src/bioflow_harness/server/handlers.py`
- Test: `tests/test_comfybio_handlers.py` (add cases)

**Interfaces:**
- Consumes: `GenerateRequest` from Task 2; `default_node_catalog`, `WorkflowBuilder`, `validate_workflow_export` (existing); `parse_prompt`, `WorkflowPlanner` (already imported in Task 3).
- Produces: `generate_workflow(payload: dict, registry_path: Path | None = None) -> dict` returning `{"status": "ok", "workflow": <dict>, "route_id": str, "domain": str}` or a `planning_required` dict.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_comfybio_handlers.py`:

```python
from bioflow_harness.comfy.workflow_schema import validate_workflow_export
from bioflow_harness.server.handlers import generate_workflow


def test_generate_workflow_returns_valid_export():
    result = generate_workflow({"request_text": "bulk RNA-seq human treated vs control with DESeq2 plots and report"})
    assert result["status"] == "ok"
    assert result["route_id"] == "bulk_rna_seq_salmon_ref"
    workflow = result["workflow"]
    assert workflow["metadata"]["format"] == "comfyui_workflow_export"
    validate_workflow_export(workflow)  # raises if malformed


def test_generate_workflow_unsupported_is_planning_required():
    result = generate_workflow({"request_text": "assemble a bacterial genome"})
    assert result["status"] == "planning_required"
    assert result["workflow"] is None if "workflow" in result else True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_comfybio_handlers.py -k generate -v`
Expected: FAIL with `ImportError: cannot import name 'generate_workflow'`.

- [ ] **Step 3: Add the handler**

Add these imports at the top of `harness/src/bioflow_harness/server/handlers.py` (with the existing imports):

```python
from bioflow_harness.comfy.node_catalog import default_node_catalog
from bioflow_harness.comfy.workflow_builder import WorkflowBuilder
from bioflow_harness.server.dto import GenerateRequest
```

Append this function to the same file:

```python
def generate_workflow(payload: dict, registry_path: Path | None = None) -> dict:
    request = GenerateRequest.from_dict(payload)
    registry = load_registry(registry_path or DEFAULT_REGISTRY_PATH)
    brief = parse_prompt(request.request_text)
    try:
        plan = WorkflowPlanner(registry).plan(brief)
    except ValueError:
        return {
            "status": "planning_required",
            "domain": brief.domain,
            "route_id": None,
            "workflow": None,
            "message": f"Workflow planning is required before generating domain: {brief.domain}",
            "confidence_notes": list(brief.confidence_notes),
        }
    workflow = WorkflowBuilder(default_node_catalog()).build(plan)
    return {
        "status": "ok",
        "domain": plan.domain,
        "route_id": plan.route_id,
        "workflow": workflow,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_comfybio_handlers.py -v`
Expected: PASS (5 tests total).

- [ ] **Step 5: Commit**

```bash
git add harness/src/bioflow_harness/server/handlers.py tests/test_comfybio_handlers.py
git commit -m "feat: add ComfyBIO generate_workflow handler"
```

---

### Task 5: Route registration

**Files:**
- Create: `harness/src/bioflow_harness/server/routes.py`
- Modify: `__init__.py` (repo root)
- Test: `tests/test_comfybio_routes.py`

**Interfaces:**
- Consumes: `compile_spec`, `generate_workflow` from Tasks 3–4.
- Produces: `register_routes(server) -> None` that registers `POST /comfybio/compile`, `POST /comfybio/generate`, `GET /comfybio/health` on `server.routes`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_comfybio_routes.py`:

```python
from bioflow_harness.server.routes import register_routes


class _FakeRoutes:
    def __init__(self):
        self.registered = []

    def post(self, path):
        def deco(fn):
            self.registered.append(("POST", path))
            return fn

        return deco

    def get(self, path):
        def deco(fn):
            self.registered.append(("GET", path))
            return fn

        return deco


class _FakeServer:
    def __init__(self):
        self.routes = _FakeRoutes()


def test_register_routes_attaches_three_endpoints():
    server = _FakeServer()
    register_routes(server)
    assert ("POST", "/comfybio/compile") in server.routes.registered
    assert ("POST", "/comfybio/generate") in server.routes.registered
    assert ("GET", "/comfybio/health") in server.routes.registered
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_comfybio_routes.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'bioflow_harness.server.routes'`.

- [ ] **Step 3: Write routes.py**

Create `harness/src/bioflow_harness/server/routes.py`:

```python
from __future__ import annotations

from bioflow_harness.server.handlers import compile_spec, generate_workflow


def register_routes(server) -> None:
    from aiohttp import web

    routes = server.routes

    @routes.post("/comfybio/compile")
    async def _compile(request):
        payload = await request.json()
        return web.json_response(compile_spec(payload))

    @routes.post("/comfybio/generate")
    async def _generate(request):
        payload = await request.json()
        return web.json_response(generate_workflow(payload))

    @routes.get("/comfybio/health")
    async def _health(request):
        return web.json_response({"status": "ok"})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_comfybio_routes.py -v`
Expected: PASS. (`register_routes` imports `aiohttp.web`, which is provided by ComfyUI's environment; the fake routes capture registration without invoking handlers.)

- [ ] **Step 5: Register routes at ComfyUI load**

Modify `__init__.py` (repo root). Add, after the existing `from bioflow_harness.custom_nodes import ...` line:

```python
def _register_comfybio_routes() -> None:
    try:
        from server import PromptServer  # ComfyUI's top-level server module
    except Exception:
        return
    instance = getattr(PromptServer, "instance", None)
    if instance is None:
        return
    from bioflow_harness.server.routes import register_routes

    register_routes(instance)


_register_comfybio_routes()
```

- [ ] **Step 6: Verify the whole suite still passes**

Run: `python -m pytest -v`
Expected: all tests PASS.

- [ ] **Step 7: Commit**

```bash
git add harness/src/bioflow_harness/server/routes.py __init__.py tests/test_comfybio_routes.py
git commit -m "feat: register ComfyBIO HTTP routes on PromptServer"
```

---

### Task 6: Panel — data-driven rendering and API wiring

**Files:**
- Modify: `web/js/comfybio_panel.js`

**Interfaces:**
- Consumes: `POST /comfybio/compile`, `POST /comfybio/generate` (Tasks 3–5); ComfyUI `api.fetchApi`, `app.loadGraphData`.
- Produces: no Python interface; delivers the working end-to-end panel.

**Note:** There is no JS test runner; this task ends with a documented manual verification instead of an automated test.

- [ ] **Step 1: Import the api module**

At the top of `web/js/comfybio_panel.js`, below the existing `app` import, add:

```javascript
import { api } from "../../scripts/api.js";
```

- [ ] **Step 2: Generalize `createStep` to take a step-data object**

Replace the `function createStep(key) {` signature and its first line. Change:

```javascript
function createStep(key) {
  const step = STEP_CATALOG[key];
  const item = el("div", { class: "cb-step", datakey: key });
```

to:

```javascript
function createStep(step) {
  const item = el("div", { class: "cb-step" });
```

(The rest of `createStep` already reads from `step.stage`, `step.tool`, `step.input`, `step.output`, `step.title`, `step.subtitle`, `step.candidates` and needs no further change.)

- [ ] **Step 3: Update the three `createStep` call sites**

In `initializePanel`, replace the initial render loop:

```javascript
  for (const key of INITIAL_STEPS) {
    stepList.append(createStep(key));
  }
  stepList.querySelector('[data-key="star"]').classList.add("expanded", "replace-open");
  stepList.querySelector('[data-key="star"] .cb-step-summary').setAttribute("aria-expanded", "true");
```

with:

```javascript
  for (const key of INITIAL_STEPS) {
    stepList.append(createStep(STEP_CATALOG[key]));
  }
```

In the add-step handler, replace `const item = createStep(option.dataset.step);` with:

```javascript
    const item = createStep(STEP_CATALOG[option.dataset.step]);
```

- [ ] **Step 4: Add a `stepFromDTO` helper and a server-step renderer**

Add these functions inside `initializePanel` (near `renumberSteps`):

```javascript
  function stepFromDTO(dto) {
    const io = `${(dto.input_types || []).join(", ") || "-"} / ${(dto.output_types || []).join(", ") || "-"}`;
    return {
      stage: dto.stage_label,
      tool: dto.tool_label,
      input: (dto.input_types || []).join(", ") || "-",
      output: (dto.output_types || []).join(", ") || "-",
      title: `TSR candidates for ${dto.stage_label}`,
      subtitle: io,
      candidates: (dto.candidates || []).map((candidate) => [
        candidate.label,
        candidate.tier,
        candidate.tier === "REF" ? "" : " amber",
        candidate.note || "",
      ]),
    };
  }

  function renderServerSteps(steps) {
    stepList.replaceChildren(...steps.map((dto) => createStep(stepFromDTO(dto))));
    renumberSteps();
    refreshSummary();
  }

  function showToolMessage(text) {
    const message = panel.querySelector('[data-panel="tool"] .cb-message');
    if (message) {
      message.innerHTML = `<span class="severity">status</span>${text}`;
    }
  }
```

- [ ] **Step 5: Rewrite the Submit handler to call `/comfybio/compile`**

Replace the entire `panel.querySelector(".cb-submit").addEventListener("click", () => { ... });` block with:

```javascript
  panel.querySelector(".cb-submit").addEventListener("click", async () => {
    const payload = {
      provider: provider.value,
      model: model.value,
      request_text: panel.querySelector(".cb-analysis-request").value.trim(),
      resources: getResources(),
    };
    state.lastPayload = payload;
    try {
      const response = await api.fetchApi("/comfybio/compile", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (data.status === "planning_required") {
        status.textContent = "Planning required";
        showToolMessage(data.message || "Domain requires planning.");
        return;
      }
      state.spec = data;
      renderServerSteps(data.steps || []);
      status.textContent = "Spec ready";
    } catch (error) {
      status.textContent = "Backend offline";
      showToolMessage(`Compile failed: ${error.message}`);
    }
  });
```

- [ ] **Step 6: Rewrite the Generate handler to call `/comfybio/generate` and load the graph**

Replace the entire `panel.querySelector(".cb-generate").addEventListener("click", () => { ... });` block with:

```javascript
  panel.querySelector(".cb-generate").addEventListener("click", async () => {
    refreshSummary();
    const payload = {
      provider: provider.value,
      model: model.value,
      request_text: panel.querySelector(".cb-analysis-request").value.trim(),
      resources: getResources(),
      steps: getToolSequence(),
    };
    try {
      const response = await api.fetchApi("/comfybio/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (data.status !== "ok" || !data.workflow) {
        status.textContent = "Generate failed";
        showToolMessage(data.message || "Workflow generation failed.");
        return;
      }
      app.loadGraphData(data.workflow);
      status.textContent = "Graph loaded";
    } catch (error) {
      status.textContent = "Backend offline";
      showToolMessage(`Generate failed: ${error.message}`);
    }
  });
```

- [ ] **Step 7: Confirm `state.spec` exists**

In the `state` object at the top of `initializePanel`, add `spec: null,` next to `lastPayload: null,`.

- [ ] **Step 8: Manual verification (no JS test runner)**

1. Restart ComfyUI so `__init__.py` re-registers routes and the web extension reloads.
2. Confirm the backend is up: `curl -s http://127.0.0.1:8188/comfybio/health` → `{"status": "ok"}` (adjust host/port to your ComfyUI).
3. Open ComfyUI in the browser, click the ComfyBIO launcher, go to the Prompt tab, keep the default request, click **Submit**. Expected: status badge → "Spec ready"; the Tool Select tab now shows salmon-route steps (WorkflowRequestLoader, SampleMetadataValidator, fastp, salmon…), each with real Replace candidates.
4. Go to Generate Graph, click **Generate Graph**. Expected: status → "Graph loaded" and the workflow graph appears on the ComfyUI canvas.
5. Negative check: stop ComfyUI's backend reachability (or edit the request to something unsupported like "assemble a bacterial genome" and Submit). Expected: a visible error/"Planning required" message in the Tool Select message area — never a silent mock.

- [ ] **Step 9: Commit**

```bash
git add web/js/comfybio_panel.js
git commit -m "feat: wire ComfyBIO panel to compile/generate endpoints and canvas load"
```

---

## Self-Review

- **Spec coverage:** compile/generate/health endpoints (Task 5), pure handlers (Tasks 3–4), DTOs (Task 2), panel data-driven rendering + auto-load (Task 6), planning_required + offline error handling (Tasks 3, 6), top-level `tests/` + pytest config (Task 1). Deferred items (path injection, execution, `nodes/` migration, Claude) are explicitly out of scope per the spec. All spec sections map to a task.
- **Placeholder scan:** No TBD/TODO; every code step shows complete code; the one non-automated deliverable (JS) has explicit manual steps.
- **Type consistency:** `StepDTO`/`CandidateDTO` field names used in `handlers.py` (Task 3) match Task 2 definitions; `stepFromDTO` (Task 6) reads the same `snake_case` fields the handler emits (`stage_label`, `tool_label`, `input_types`, `output_types`, `candidates[].label/tier/note`). `generate_workflow` returns `workflow`/`route_id`/`domain`/`status`, matching the panel's Generate handler and Task 4 test.
