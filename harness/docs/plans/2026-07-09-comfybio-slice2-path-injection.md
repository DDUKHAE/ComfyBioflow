# ComfyBIO Slice 2: Path Injection + Folder-Based Node Contract — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the bulk RNA-seq node contract to folder + metadata based, inject the panel's resource paths into the generated node widgets, and migrate the executable nodes to a top-level `nodes/` package with a one-way `nodes/ → bioflow_harness` dependency.

**Architecture:** A new `ResourceBindings` value object normalizes panel resources into named roles (with fixture-default fallback) and derives nested output paths. `WorkflowBuilder.build(plan, bindings)` injects those values into per-node widget slots via an explicit node_type → index map. The executable node package moves from `harness/src/bioflow_harness/custom_nodes/` to top-level `nodes/`; `workflow_schema` validates against `node_catalog` keys instead of importing the node registry, removing the reverse dependency.

**Tech Stack:** Python 3.11+, dataclasses, pytest; vanilla JS ComfyUI extension.

## Global Constraints

- Python `requires-python = ">=3.11"`; built-in generics.
- Only the **bulk RNA-seq** path is redesigned this slice; scRNA node widgets are untouched.
- No node `run()` execution, sample discovery, or filesystem existence checks this slice (Slice 3).
- `WorkflowBuilder.build(plan, bindings=None)` with `bindings=None` MUST reproduce current behavior (catalog defaults) so `cli.build_workflow` and existing tests are unaffected.
- Dependency direction is one-way: `nodes/ → bioflow_harness`. `harness/` must not import executable node classes.
- The top-level package MUST be imported relatively (`from .nodes import ...`) — absolute `import nodes` collides with ComfyUI's `nodes.py`.
- Invariant (schema-drift guard): for every node in `NODE_CLASS_MAPPINGS`, the count of non-`forceInput` required inputs equals the length of its `node_catalog` widgets array.
- Commit identity: `ddukhae <dongjoon69@gmail.com>` (set locally). Run `pytest` from the repo root.

## File Structure

```
harness/src/bioflow_harness/comfy/workflow_schema.py     # MODIFY: validate against node_catalog keys
nodes/  (git mv from harness/src/bioflow_harness/custom_nodes/)  # MOVE + bulk INPUT_TYPES redesign
__init__.py                                              # MODIFY: from .nodes import ...
pyproject.toml                                           # MODIFY: add "." to pythonpath so tests import `nodes`
harness/src/bioflow_harness/comfy/node_catalog.py        # MODIFY: bulk widgets → folder+metadata schema
harness/src/bioflow_harness/comfy/resource_binding.py    # NEW: ResourceBindings, validate_bindings
harness/src/bioflow_harness/comfy/workflow_builder.py    # MODIFY: build(plan, bindings) + injection map
harness/src/bioflow_harness/server/handlers.py           # MODIFY: resources → bindings, warnings
web/js/comfybio_panel.js                                 # MODIFY (minor): pre-populate transcriptome resource
tests/test_comfybio_resource_binding.py                  # NEW
tests/test_comfybio_node_contract.py                     # NEW: schema-drift guard + migration smoke
tests/test_comfybio_builder_injection.py                 # NEW
tests/test_comfybio_handlers.py                          # MODIFY: injection assertions
```

---

### Task 1: Decouple workflow_schema from the executable node registry

**Files:**
- Modify: `harness/src/bioflow_harness/comfy/workflow_schema.py:22-30`
- Test: `tests/test_comfybio_node_contract.py`

**Interfaces:**
- Consumes: `default_node_catalog()` from `bioflow_harness.comfy.node_catalog`.
- Produces: `validate_workflow_export` no longer imports `bioflow_harness.custom_nodes`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_comfybio_node_contract.py`:

```python
import bioflow_harness.comfy.workflow_schema as schema_module


def test_workflow_schema_does_not_import_executable_nodes():
    source = __import__("inspect").getsource(schema_module)
    assert "custom_nodes" not in source
    assert "NODE_CLASS_MAPPINGS" not in source or "node_catalog" in source
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_comfybio_node_contract.py -v`
Expected: FAIL (source still references `custom_nodes`).

- [ ] **Step 3: Replace the import-based check with a catalog check**

In `harness/src/bioflow_harness/comfy/workflow_schema.py`, replace lines 22-30:

```python
    try:
        from bioflow_harness.custom_nodes.registry import NODE_CLASS_MAPPINGS
    except ImportError as error:
        raise WorkflowValidationError("Could not import ComfyBIO custom node registry.") from error

    node_id_set = set(node_ids)
    for node in workflow["nodes"]:
        node_type = node.get("type")
        if node_type not in NODE_CLASS_MAPPINGS and node_type not in BUILTIN_NODE_TYPES:
            raise WorkflowValidationError(f"Workflow references unregistered node type: {node_type}")
```

with:

```python
    from bioflow_harness.comfy.node_catalog import default_node_catalog

    known_node_types = set(default_node_catalog().keys())
    node_id_set = set(node_ids)
    for node in workflow["nodes"]:
        node_type = node.get("type")
        if node_type not in known_node_types and node_type not in BUILTIN_NODE_TYPES:
            raise WorkflowValidationError(f"Workflow references unregistered node type: {node_type}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_comfybio_node_contract.py -v && python -m pytest -q`
Expected: PASS; full suite still green.

- [ ] **Step 5: Commit**

```bash
git add harness/src/bioflow_harness/comfy/workflow_schema.py tests/test_comfybio_node_contract.py
git commit -m "refactor: validate workflow node types against node_catalog"
```

---

### Task 2: Migrate custom_nodes/ → top-level nodes/

**Files:**
- Move: `harness/src/bioflow_harness/custom_nodes/` → `nodes/`
- Modify: `nodes/registry.py`, `nodes/__init__.py` (relative imports)
- Modify: `__init__.py` (root)
- Modify: `pyproject.toml`
- Test: `tests/test_comfybio_node_contract.py` (add smoke)

**Interfaces:**
- Consumes: nothing new.
- Produces: `nodes` package importable in tests with `NODE_CLASS_MAPPINGS`, `NODE_DISPLAY_NAME_MAPPINGS`, `resolve_node_class`.

- [ ] **Step 1: Add "." to the test pythonpath**

Modify `pyproject.toml` (repo root):

```toml
[tool.pytest.ini_options]
pythonpath = ["harness/src", "."]
testpaths = ["tests"]
```

- [ ] **Step 2: Write the failing smoke test**

Append to `tests/test_comfybio_node_contract.py`:

```python
def test_nodes_package_registers_classes():
    import nodes

    assert nodes.NODE_CLASS_MAPPINGS
    assert "SalmonQuantNode" in nodes.NODE_CLASS_MAPPINGS
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_comfybio_node_contract.py::test_nodes_package_registers_classes -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'nodes'` (package still at old path).

- [ ] **Step 4: Move the package and fix imports**

```bash
git mv harness/src/bioflow_harness/custom_nodes nodes
```

In `nodes/registry.py`, change line 1:

```python
from bioflow_harness.custom_nodes.ref_nodes import (
```

to:

```python
from nodes.ref_nodes import (
```

In `nodes/__init__.py`, change:

```python
from bioflow_harness.custom_nodes.registry import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
```

to:

```python
from nodes.registry import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
```

(Absolute `nodes.*` imports resolve to this package in both the test path and the ComfyUI package context; do not use `bioflow_harness.custom_nodes` anymore.)

- [ ] **Step 5: Update the root entrypoint**

In `__init__.py` (repo root), change line 16:

```python
from bioflow_harness.custom_nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS  # noqa: E402
```

to:

```python
from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS  # noqa: E402
```

- [ ] **Step 6: Run the full suite**

Run: `python -m pytest -q`
Expected: all PASS (the new smoke test included). If any test still imports `bioflow_harness.custom_nodes`, update it to `nodes`.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor: move custom_nodes to top-level nodes package"
```

---

### Task 3: Redesign bulk node INPUT_TYPES + node_catalog widgets

**Files:**
- Modify: `nodes/ref_nodes.py` (SampleMetadataValidatorNode, FastpQCNode, FastpTrimNode, SalmonQuantNode, TximportNode)
- Modify: `harness/src/bioflow_harness/comfy/node_catalog.py` (matching widgets)
- Test: `tests/test_comfybio_node_contract.py` (schema-drift guard)

**Interfaces:**
- Consumes: `nodes.NODE_CLASS_MAPPINGS`, `default_node_catalog()`.
- Produces: bulk nodes accept `fastq_dir` + `metadata_csv`; catalog widget arrays match the new `INPUT_TYPES`.

- [ ] **Step 1: Write the failing schema-drift guard**

Append to `tests/test_comfybio_node_contract.py`:

```python
def _widget_input_count(input_types: dict) -> int:
    required = input_types.get("required", {})
    count = 0
    for _name, spec in required.items():
        options = spec[1] if isinstance(spec, tuple) and len(spec) > 1 else {}
        if not (isinstance(options, dict) and options.get("forceInput")):
            count += 1
    return count


def test_catalog_widgets_match_node_input_arity():
    import nodes
    from bioflow_harness.comfy.node_catalog import default_node_catalog

    catalog = default_node_catalog()
    for node_type, node_class in nodes.NODE_CLASS_MAPPINGS.items():
        if node_type not in catalog:
            continue
        widget_count = _widget_input_count(node_class.INPUT_TYPES())
        assert widget_count == len(catalog[node_type].widgets), (
            f"{node_type}: INPUT_TYPES widgets={widget_count} vs catalog widgets={len(catalog[node_type].widgets)}"
        )


def test_salmon_quant_uses_fastq_dir_and_metadata():
    import nodes

    required = nodes.NODE_CLASS_MAPPINGS["SalmonQuantNode"].INPUT_TYPES()["required"]
    assert "fastq_dir" in required
    assert "metadata_csv" in required
    assert "fastq_1" not in required
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_comfybio_node_contract.py -k "arity or fastq_dir" -v`
Expected: FAIL (`fastq_1` still present; arity may already pass for unchanged nodes).

- [ ] **Step 3: Redesign the five bulk node INPUT_TYPES**

In `nodes/ref_nodes.py`, replace each node's `INPUT_TYPES` body:

`SampleMetadataValidatorNode`:

```python
        return {
            "required": {
                "workflow_request": cls._upstream_input(),
                "fastq_dir": cls._string_input("fastq"),
                "metadata_csv": cls._string_input("sample_metadata.csv"),
                "extra_command": cls._extra_command_input(),
            }
        }
```

`FastpQCNode`:

```python
        return {
            "required": {
                "fastq_pair": cls._upstream_input(),
                "fastq_dir": cls._string_input("fastq"),
                "metadata_csv": cls._string_input("sample_metadata.csv"),
                "output_dir": cls._string_input("qc"),
                "threads": ("INT", {"default": 2, "min": 1, "max": 64}),
                "extra_command": cls._extra_command_input(),
            }
        }
```

`FastpTrimNode`:

```python
        return {
            "required": {
                "fastp_qc_json": cls._upstream_input(),
                "fastq_dir": cls._string_input("fastq"),
                "metadata_csv": cls._string_input("sample_metadata.csv"),
                "output_dir": cls._string_input("trimmed"),
                "threads": ("INT", {"default": 2, "min": 1, "max": 64}),
                "extra_command": cls._extra_command_input(),
            }
        }
```

`SalmonQuantNode`:

```python
        return {
            "required": {
                "salmon_index_dir": cls._upstream_input(),
                "index_dir": cls._string_input("salmon_index"),
                "fastq_dir": cls._string_input("fastq"),
                "metadata_csv": cls._string_input("sample_metadata.csv"),
                "output_dir": cls._string_input("salmon_quant"),
                "read_layout": ("STRING", {"default": "A"}),
                "threads": ("INT", {"default": 2, "min": 1, "max": 64}),
                "extra_command": cls._extra_command_input(),
            }
        }
```

`TximportNode`:

```python
        return {
            "required": {
                "salmon_quant_dir_path": cls._upstream_input(),
                "salmon_quant_dir": cls._string_input("salmon_quant"),
                "metadata_csv": cls._string_input("sample_metadata.csv"),
                "output_count_matrix": cls._string_input("deseq2/count_matrix.csv"),
                "extra_command": cls._extra_command_input(),
            }
        }
```

- [ ] **Step 4: Update node_catalog widgets to match**

In `harness/src/bioflow_harness/comfy/node_catalog.py`, replace the five entries' widget arrays (keep `inputs`/`outputs`; only the trailing widgets list changes):

```python
        "SampleMetadataValidatorNode": NodeDefinition("SampleMetadataValidatorNode", "Validate Sample Metadata", "ComfyBIO/Input", [{"name": "workflow_request", "type": "STRING"}], [{"name": "sample_metadata_csv", "type": "STRING"}], ["harness/examples/fixtures/quickstart", "harness/examples/fixtures/quickstart/sample_metadata.csv", ""]),
        "FastpQCNode": NodeDefinition("FastpQCNode", "FASTQ QC", "ComfyBIO/QC", [{"name": "fastq_pair", "type": "STRING"}], [{"name": "fastp_qc_json", "type": "STRING"}], ["harness/examples/fixtures/quickstart", "harness/examples/fixtures/quickstart/sample_metadata.csv", "harness/examples/runs/quickstart/qc", 2, ""]),
        "FastpTrimNode": NodeDefinition("FastpTrimNode", "Optional FASTQ Trimming", "ComfyBIO/QC", [{"name": "fastp_qc_json", "type": "STRING"}], [{"name": "trimmed_fastq_dir", "type": "STRING"}], ["harness/examples/fixtures/quickstart", "harness/examples/fixtures/quickstart/sample_metadata.csv", "harness/examples/runs/quickstart/trimmed", 2, "--length_required 1"]),
        "SalmonQuantNode": NodeDefinition("SalmonQuantNode", "Salmon Quant", "ComfyBIO/Quantification", [{"name": "salmon_index_dir", "type": "STRING"}], [{"name": "salmon_quant_dir", "type": "STRING"}], ["harness/examples/runs/quickstart/salmon_index", "harness/examples/fixtures/quickstart", "harness/examples/fixtures/quickstart/sample_metadata.csv", "harness/examples/runs/quickstart/salmon_quant", "A", 2, ""]),
        "TximportNode": NodeDefinition("TximportNode", "Import Counts For DESeq2", "ComfyBIO/Differential Expression", [{"name": "salmon_quant_dir_path", "type": "STRING"}], [{"name": "deseq2_count_matrix", "type": "STRING"}], ["harness/examples/runs/quickstart/salmon_quant", "harness/examples/fixtures/quickstart/sample_metadata.csv", "harness/examples/runs/quickstart/deseq2/count_matrix.csv", ""]),
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_comfybio_node_contract.py -v && python -m pytest -q`
Expected: PASS (arity guard green for all nodes; `fastq_dir` present). The Slice 1 `test_generate_workflow_returns_valid_export` stays green — `validate_workflow_export` checks node/link structure, not widget arity, and the builder emits the new catalog widgets automatically.

- [ ] **Step 6: Commit**

```bash
git add nodes/ref_nodes.py harness/src/bioflow_harness/comfy/node_catalog.py tests/test_comfybio_node_contract.py
git commit -m "feat: fold FASTQ folder + metadata into bulk node contract"
```

---

### Task 4: ResourceBindings value object

**Files:**
- Create: `harness/src/bioflow_harness/comfy/resource_binding.py`
- Test: `tests/test_comfybio_resource_binding.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `ResourceBindings` dataclass with fields `input_fastq_dir, output_base_dir, metadata_csv, transcriptome_fasta: str` and `defaulted: frozenset[str]`, plus derived properties `qc_dir, trimmed_dir, salmon_index_dir, salmon_quant_dir, count_matrix, results_csv, plot_dir, report_path`.
  - `ResourceBindings.from_resources(resources: list[dict]) -> ResourceBindings`
  - `REQUIRED_ROLES_BY_ROUTE: dict[str, tuple[str, ...]]`
  - `validate_bindings(route_id: str, bindings: ResourceBindings) -> list[str]`

- [ ] **Step 1: Write the failing test**

Create `tests/test_comfybio_resource_binding.py`:

```python
from bioflow_harness.comfy.resource_binding import ResourceBindings, validate_bindings


def test_from_resources_maps_roles():
    bindings = ResourceBindings.from_resources(
        [
            {"label": "input_path", "type": "path", "path": "/data/fastq"},
            {"label": "output_path", "type": "path", "path": "/data/out"},
            {"label": "metadata_csv", "type": "metadata", "path": "/data/meta.csv"},
            {"label": "transcriptome", "type": "index", "path": "/data/tx.fasta"},
        ]
    )
    assert bindings.input_fastq_dir == "/data/fastq"
    assert bindings.metadata_csv == "/data/meta.csv"
    assert bindings.transcriptome_fasta == "/data/tx.fasta"
    assert bindings.salmon_quant_dir == "/data/out/salmon_quant"
    assert bindings.count_matrix == "/data/out/deseq2/count_matrix.csv"
    assert bindings.defaulted == frozenset()


def test_from_resources_falls_back_to_fixture_defaults():
    bindings = ResourceBindings.from_resources([])
    assert bindings.input_fastq_dir == "harness/examples/fixtures/quickstart"
    assert "input_fastq_dir" in bindings.defaulted
    assert "transcriptome_fasta" in bindings.defaulted


def test_validate_bindings_warns_on_missing_required():
    bindings = ResourceBindings.from_resources(
        [{"label": "input_path", "type": "path", "path": "/data/fastq"}]
    )
    warnings = validate_bindings("bulk_rna_seq_salmon_ref", bindings)
    joined = " ".join(warnings)
    assert "metadata_csv" in joined
    assert "transcriptome_fasta" in joined
    assert "input_fastq_dir" not in joined
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_comfybio_resource_binding.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement the module**

Create `harness/src/bioflow_harness/comfy/resource_binding.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field

_DEFAULTS = {
    "input_fastq_dir": "harness/examples/fixtures/quickstart",
    "output_base_dir": "harness/examples/runs/quickstart",
    "metadata_csv": "harness/examples/fixtures/quickstart/sample_metadata.csv",
    "transcriptome_fasta": "harness/examples/fixtures/quickstart/toy_transcriptome.fasta",
}

REQUIRED_ROLES_BY_ROUTE = {
    "bulk_rna_seq_salmon_ref": ("input_fastq_dir", "metadata_csv", "transcriptome_fasta"),
}


@dataclass(frozen=True)
class ResourceBindings:
    input_fastq_dir: str
    output_base_dir: str
    metadata_csv: str
    transcriptome_fasta: str
    defaulted: frozenset[str] = field(default_factory=frozenset)

    @property
    def qc_dir(self) -> str:
        return f"{self.output_base_dir}/qc"

    @property
    def trimmed_dir(self) -> str:
        return f"{self.output_base_dir}/trimmed"

    @property
    def salmon_index_dir(self) -> str:
        return f"{self.output_base_dir}/salmon_index"

    @property
    def salmon_quant_dir(self) -> str:
        return f"{self.output_base_dir}/salmon_quant"

    @property
    def count_matrix(self) -> str:
        return f"{self.output_base_dir}/deseq2/count_matrix.csv"

    @property
    def results_csv(self) -> str:
        return f"{self.output_base_dir}/deseq2/results.csv"

    @property
    def plot_dir(self) -> str:
        return f"{self.output_base_dir}/plots"

    @property
    def report_path(self) -> str:
        return f"{self.output_base_dir}/report/comfybio_report.md"

    @classmethod
    def from_resources(cls, resources: list[dict]) -> "ResourceBindings":
        resolved: dict[str, str] = {}
        for resource in resources or []:
            label = str(resource.get("label", "")).strip()
            rtype = str(resource.get("type", "")).strip().lower()
            path = str(resource.get("path", "")).strip()
            if not path:
                continue
            if label == "input_path":
                resolved.setdefault("input_fastq_dir", path)
            elif label == "output_path":
                resolved.setdefault("output_base_dir", path)
            elif label == "metadata_csv" or rtype == "metadata":
                resolved.setdefault("metadata_csv", path)
            elif rtype in {"index", "reference"}:
                resolved.setdefault("transcriptome_fasta", path)

        defaulted = frozenset(role for role in _DEFAULTS if role not in resolved)
        return cls(
            input_fastq_dir=resolved.get("input_fastq_dir", _DEFAULTS["input_fastq_dir"]),
            output_base_dir=resolved.get("output_base_dir", _DEFAULTS["output_base_dir"]),
            metadata_csv=resolved.get("metadata_csv", _DEFAULTS["metadata_csv"]),
            transcriptome_fasta=resolved.get("transcriptome_fasta", _DEFAULTS["transcriptome_fasta"]),
            defaulted=defaulted,
        )


def validate_bindings(route_id: str, bindings: ResourceBindings) -> list[str]:
    required = REQUIRED_ROLES_BY_ROUTE.get(route_id, ())
    return [
        f"Resource '{role}' was not provided; using the fixture default."
        for role in required
        if role in bindings.defaulted
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_comfybio_resource_binding.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add harness/src/bioflow_harness/comfy/resource_binding.py tests/test_comfybio_resource_binding.py
git commit -m "feat: add ResourceBindings for panel resource injection"
```

---

### Task 5: Builder path injection

**Files:**
- Modify: `harness/src/bioflow_harness/comfy/workflow_builder.py`
- Test: `tests/test_comfybio_builder_injection.py`

**Interfaces:**
- Consumes: `ResourceBindings` (Task 4); `WorkflowPlan`, `NodeDefinition`.
- Produces: `WorkflowBuilder.build(self, plan, bindings: ResourceBindings | None = None) -> dict`. With `bindings=None`, widgets equal the catalog defaults (unchanged behavior).

- [ ] **Step 1: Write the failing test**

Create `tests/test_comfybio_builder_injection.py`:

```python
from bioflow_harness.comfy.node_catalog import default_node_catalog
from bioflow_harness.comfy.resource_binding import ResourceBindings
from bioflow_harness.comfy.workflow_builder import WorkflowBuilder
from bioflow_harness.comfy.workflow_schema import validate_workflow_export
from bioflow_harness.parser.prompt_parser import parse_prompt
from bioflow_harness.planner.tool_selector import load_registry
from bioflow_harness.planner.workflow_planner import WorkflowPlanner

from pathlib import Path

REGISTRY = Path("harness/registry/tool_selection_registry.yaml")


def _bulk_plan():
    registry = load_registry(REGISTRY)
    brief = parse_prompt("bulk RNA-seq human treated vs control with DESeq2 plots and report")
    return WorkflowPlanner(registry).plan(brief)


def test_build_without_bindings_uses_catalog_defaults():
    plan = _bulk_plan()
    workflow = WorkflowBuilder(default_node_catalog()).build(plan)
    salmon = next(n for n in workflow["nodes"] if n["type"] == "SalmonQuantNode")
    assert salmon["widgets_values"] == default_node_catalog()["SalmonQuantNode"].widgets


def test_build_injects_panel_paths():
    plan = _bulk_plan()
    bindings = ResourceBindings.from_resources(
        [
            {"label": "input_path", "path": "/data/fastq"},
            {"label": "output_path", "path": "/data/out"},
            {"label": "metadata_csv", "type": "metadata", "path": "/data/meta.csv"},
            {"label": "tx", "type": "index", "path": "/data/tx.fasta"},
        ]
    )
    workflow = WorkflowBuilder(default_node_catalog()).build(plan, bindings)
    salmon = next(n for n in workflow["nodes"] if n["type"] == "SalmonQuantNode")
    # widgets order: index_dir, fastq_dir, metadata_csv, output_dir, read_layout, threads, extra
    assert salmon["widgets_values"][1] == "/data/fastq"
    assert salmon["widgets_values"][2] == "/data/meta.csv"
    assert salmon["widgets_values"][3] == "/data/out/salmon_quant"
    index = next(n for n in workflow["nodes"] if n["type"] == "SalmonIndexNode")
    assert index["widgets_values"][0] == "/data/tx.fasta"
    validate_workflow_export(workflow)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_comfybio_builder_injection.py -v`
Expected: FAIL — `build()` takes no `bindings` argument.

- [ ] **Step 3: Add the injection map and thread bindings through build**

In `harness/src/bioflow_harness/comfy/workflow_builder.py`, add this module-level map after the imports:

```python
# node_type -> {widget_index: attribute name on ResourceBindings}
_BULK_INJECTION = {
    "SampleMetadataValidatorNode": {0: "input_fastq_dir", 1: "metadata_csv"},
    "FastpQCNode": {0: "input_fastq_dir", 1: "metadata_csv", 2: "qc_dir"},
    "FastpTrimNode": {0: "input_fastq_dir", 1: "metadata_csv", 2: "trimmed_dir"},
    "SalmonIndexNode": {0: "transcriptome_fasta", 1: "salmon_index_dir"},
    "SalmonQuantNode": {0: "salmon_index_dir", 1: "input_fastq_dir", 2: "metadata_csv", 3: "salmon_quant_dir"},
    "TximportNode": {0: "salmon_quant_dir", 1: "metadata_csv", 2: "count_matrix"},
    "DESeq2AnalysisNode": {0: "count_matrix", 1: "metadata_csv", 2: "results_csv"},
    "DESeq2VisualizationNode": {0: "count_matrix", 1: "results_csv", 2: "plot_dir"},
    "ComfyBIOReportNode": {0: "results_csv", 1: "plot_dir", 2: "report_path"},
}
```

Change the `build` signature and pass `bindings` into `_widgets_for_stage`:

```python
    def build(self, plan: WorkflowPlan, bindings=None) -> dict:
```

Find the call `widgets = self._widgets_for_stage(definition, plan)` inside `build` and change it to:

```python
            widgets = self._widgets_for_stage(definition, plan, bindings)
```

Replace `_widgets_for_stage`:

```python
    def _widgets_for_stage(self, definition: NodeDefinition, plan: WorkflowPlan, bindings=None) -> list[str | int | bool]:
        if definition.node_type == "WorkflowRequestLoader":
            return [self._request_text(plan)]
        if definition.node_type == "WorkflowJSONOutput":
            return [f"harness/examples/workflows/{plan.route_id}.json"]
        widgets = list(definition.widgets)
        if bindings is not None:
            for index, attribute in _BULK_INJECTION.get(definition.node_type, {}).items():
                if index < len(widgets):
                    widgets[index] = getattr(bindings, attribute)
        return widgets
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_comfybio_builder_injection.py -v && python -m pytest -q`
Expected: PASS, including the Slice 1 `test_generate_workflow_returns_valid_export` (now re-enabled).

- [ ] **Step 5: Commit**

```bash
git add harness/src/bioflow_harness/comfy/workflow_builder.py tests/test_comfybio_builder_injection.py
git commit -m "feat: inject ResourceBindings paths into workflow node widgets"
```

---

### Task 6: Wire bindings through the generate handler

**Files:**
- Modify: `harness/src/bioflow_harness/server/handlers.py` (`generate_workflow`)
- Test: `tests/test_comfybio_handlers.py`

**Interfaces:**
- Consumes: `ResourceBindings`, `validate_bindings` (Task 4); `WorkflowBuilder.build(plan, bindings)` (Task 5).
- Produces: `generate_workflow` builds bindings from `request.resources`, passes them to the builder, and merges `validate_bindings` warnings into the response `message`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_comfybio_handlers.py`:

```python
def test_generate_workflow_injects_resource_paths():
    payload = {
        "request_text": "bulk RNA-seq human treated vs control with DESeq2 plots and report",
        "resources": [
            {"label": "input_path", "path": "/data/fastq"},
            {"label": "output_path", "path": "/data/out"},
            {"label": "metadata_csv", "type": "metadata", "path": "/data/meta.csv"},
            {"label": "tx", "type": "index", "path": "/data/tx.fasta"},
        ],
    }
    result = generate_workflow(payload)
    assert result["status"] == "ok"
    salmon = next(n for n in result["workflow"]["nodes"] if n["type"] == "SalmonQuantNode")
    assert salmon["widgets_values"][1] == "/data/fastq"
    assert result["message"] is None


def test_generate_workflow_warns_on_missing_resources():
    payload = {"request_text": "bulk RNA-seq treated vs control with DESeq2 plots and report"}
    result = generate_workflow(payload)
    assert result["status"] == "ok"
    assert "transcriptome_fasta" in (result["message"] or "")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_comfybio_handlers.py -k "injects_resource or warns_on_missing" -v`
Expected: FAIL (paths not injected; `message` is None).

- [ ] **Step 3: Wire bindings into generate_workflow**

In `harness/src/bioflow_harness/server/handlers.py`, add the import:

```python
from bioflow_harness.comfy.resource_binding import ResourceBindings, validate_bindings
```

Replace the body of `generate_workflow` after the `plan` is computed (the `workflow = ...` line onward):

```python
    bindings = ResourceBindings.from_resources([r.__dict__ for r in request.resources])
    workflow = WorkflowBuilder(default_node_catalog()).build(plan, bindings)
    warnings = validate_bindings(plan.route_id, bindings)
    deterministic_steps = [
        registry.tool_by_id(stage.selected_tool_id).label for stage in plan.stages
    ]
    if request.steps and list(request.steps) != deterministic_steps:
        warnings.append(
            "Your step edits (reordering/replacement) are not applied in Slice 1; "
            "the workflow was generated from the deterministic default route."
        )
    return {
        "status": "ok",
        "domain": plan.domain,
        "route_id": plan.route_id,
        "workflow": workflow,
        "message": " ".join(warnings) if warnings else None,
    }
```

(`ResourceDTO` is a frozen dataclass, so `r.__dict__` yields `{"label","type","path"}` — the shape `from_resources` expects.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_comfybio_handlers.py -v && python -m pytest -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add harness/src/bioflow_harness/server/handlers.py tests/test_comfybio_handlers.py
git commit -m "feat: inject panel resources and surface binding warnings on generate"
```

---

### Task 7: Panel — pre-populate the transcriptome resource

**Files:**
- Modify: `web/js/comfybio_panel.js`

**Interfaces:**
- Consumes: `/comfybio/generate` (unchanged shape).
- Produces: the initial resource list includes a `transcriptome_fasta` (type `index`) row so the bulk demo injects a transcriptome without manual entry.

**Note:** No JS test runner; ends with manual verification.

- [ ] **Step 1: Add a default transcriptome resource row**

In `web/js/comfybio_panel.js`, find the `resourceList.append(` call in `initializePanel` that appends the initial resources:

```javascript
  resourceList.append(
    createPathPicker("input_path", "/data/project/fastq", true),
    createPathPicker("output_path", "/data/project/results", true),
    createExtraResource(),
  );
```

Add a transcriptome extra resource after `createExtraResource()`. Insert this helper next to `createExtraResource` (near line 651):

```javascript
function createTranscriptomeResource() {
  const row = el("div", { class: "cb-resource-row extra" });
  row.innerHTML = `
    <div class="cb-field">
      <label>Label</label>
      <input class="cb-resource-label" value="transcriptome_fasta">
    </div>
    <div class="cb-field">
      <label>Type</label>
      <select class="cb-resource-type">
        <option>index</option>
        <option>reference</option>
        <option>metadata</option>
        <option>annotation</option>
        <option>contrast</option>
        <option>other</option>
      </select>
    </div>
    <div class="cb-field">
      <label>Path</label>
      <input class="cb-resource-path" value="/data/project/transcriptome.fasta">
    </div>
    <div class="cb-path-wrap">
      <button class="cb-path-button cb-tiny" type="button">Browse</button>
      <div class="cb-path-menu">
        <button class="cb-tiny cb-path-choice" type="button" data-kind="file">File</button>
        <button class="cb-tiny cb-path-choice" type="button" data-kind="folder">Folder</button>
      </div>
    </div>
    <button class="cb-tiny cb-remove-resource" type="button">x</button>
  `;
  return row;
}
```

Then update the append call:

```javascript
  resourceList.append(
    createPathPicker("input_path", "/data/project/fastq", true),
    createPathPicker("output_path", "/data/project/results", true),
    createExtraResource(),
    createTranscriptomeResource(),
  );
```

- [ ] **Step 2: Manual verification**

1. Restart ComfyUI (reloads `__init__.py` and the web extension).
2. `curl -s http://127.0.0.1:<port>/comfybio/health` → `{"status": "ok"}`.
3. In the panel Prompt tab, set input/output/metadata/transcriptome paths, Submit, then Generate.
4. On the canvas, open the **Salmon Quant** node → confirm `fastq_dir` = your input path, `metadata_csv` = your metadata, `output_dir` = `<output>/salmon_quant`. Open **Salmon Index** → `transcriptome_fasta` = your transcriptome path.
5. Remove the transcriptome resource and Generate again → the Tool Select message area shows the "using the fixture default" warning; the graph still loads.

- [ ] **Step 3: Commit**

```bash
git add web/js/comfybio_panel.js
git commit -m "feat: pre-populate transcriptome resource in ComfyBIO panel"
```

---

## Self-Review

- **Spec coverage:** node contract redesign (Task 3), ResourceBindings + validation (Task 4), builder injection (Task 5), handler wiring (Task 6), migration + dependency decouple (Tasks 1–2), panel pre-populate (Task 7). Deferred items (execution, sample discovery, scRNA, existence checks) are out of scope per the spec.
- **Placeholder scan:** No TBD/TODO; every code step shows complete code; the JS task ends with explicit manual steps.
- **Type consistency:** `ResourceBindings` property names (`qc_dir`, `trimmed_dir`, `salmon_index_dir`, `salmon_quant_dir`, `count_matrix`, `results_csv`, `plot_dir`, `report_path`, `input_fastq_dir`, `metadata_csv`, `transcriptome_fasta`) referenced by `_BULK_INJECTION` (Task 5) all exist on the dataclass (Task 4). The `_BULK_INJECTION` widget indices match the new `node_catalog` widget order defined in Task 3. `generate_workflow` (Task 6) passes `bindings` to `build(plan, bindings)` as defined in Task 5, and reads `ResourceDTO.__dict__` matching `from_resources`' expected `{label,type,path}` keys.
- **Ordering:** Task 1 (decouple) precedes Task 2 (migrate) so `workflow_schema` does not break on the moved path; Task 3 (schema) precedes Task 5 (injection indices depend on the new widget order); Task 4 precedes Tasks 5–6.
```
