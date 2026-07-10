# ComfyBIO Slice 3: Real Node Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the bulk RNA-seq ComfyUI nodes working `run()` methods so that loading and running the generated graph executes fastp → salmon → tximport → DESeq2 → report on real data in the `bulk_rna_seq` conda environment.

**Architecture:** Each bulk stage node runs its own tool via `conda run` and returns its output path as a STRING that flows to the next node. Sample discovery (CSV-first, folder-scan fallback), per-stage conda argv, and runtime glue live in three new `nodes/` modules. The conda environment and input files are validated once, at the entry node (`SampleMetadataValidatorNode`). The two panel-redundant orchestration nodes (`WorkflowRequestLoader`, `WorkflowJSONOutput`) are removed from generated graphs.

**Tech Stack:** Python 3.11+, pytest, ComfyUI custom-node contract (`INPUT_TYPES`/`RETURN_TYPES`/`FUNCTION`), conda, existing `bioflow_harness.runtime` helpers (`command_runner`, `environment`).

## Global Constraints

- Conda environment name: `bulk_rna_seq` (one per-domain env, all bulk tools). Verbatim.
- Reuse `bioflow_harness.runtime.command_runner` (`conda_command`, `parse_extra_command_tokens`, `CondaCommandRunner`, `DryRunCommandRunner`) and `bioflow_harness.runtime.environment` (`validate_bulk_rna_seq_environment`). Do NOT reuse `runtime/ref_nodes.py` (CLI path stays as-is).
- Dependency direction is one-way: `nodes/ → bioflow_harness`. Never import `nodes` from `bioflow_harness`.
- Node `run()` methods take optional `runner` / `probe` / `preview_loader` parameters (default to real implementations) so tests inject fakes and need no conda/torch.
- Tests must pass with no conda env and no torch installed. Real execution is verified manually.
- Commit identity: `ddukhae <dongjoon69@gmail.com>` (`git -c user.name=ddukhae -c user.email=dongjoon69@gmail.com commit`).
- Run tests with: `python -m pytest -q` from the repo root (`pyproject.toml` sets `pythonpath = ["harness/src", "."]`, `testpaths = ["tests"]`).
- Quickstart fixture (for tests): `harness/examples/fixtures/quickstart/` — `sample_metadata.csv` (4 samples: sample_a/b control, sample_c/d treatment) + `sample_X_R1.fastq`/`sample_X_R2.fastq` + `toy_transcriptome.fasta`.

---

### Task 1: Remove orchestration nodes from generated graphs

Removes `WorkflowRequestLoader` and `WorkflowJSONOutput` from both routes so every generated graph starts at its data-input node (`SampleMetadataValidatorNode` for bulk, `TenxCountNode` for scRNA) and ends at its report node. Registry is the source of truth; catalog/nodes/builder/regenerator are made consistent.

**Files:**
- Modify: `harness/registry/tool_selection_registry.yaml` (remove 2 route stages per route)
- Modify: `harness/src/bioflow_harness/comfy/node_catalog.py:16-17,33` (drop 2 entries; make roots)
- Modify: `nodes/ref_nodes.py` (drop `workflow_request`/`tenx_fastq_dir` forceInput; delete 2 classes)
- Modify: `nodes/registry.py` (drop 2 imports + mappings)
- Modify: `harness/src/bioflow_harness/comfy/workflow_builder.py:117-127` (remove 2 special cases + `_request_text`)
- Modify: `harness/src/bioflow_harness/comfy/workflow_regenerator.py:18-29,120-124` (drop 2 node specs)
- Test: `tests/test_comfybio_graph_structure.py` (new)

**Interfaces:**
- Consumes: `bioflow_harness.server.handlers.generate_workflow(payload: dict) -> dict` (existing).
- Produces: generated bulk graph `nodes[0].type == "SampleMetadataValidatorNode"`, no `WorkflowRequestLoader`/`WorkflowJSONOutput`; `SampleMetadataValidatorNode.INPUT_TYPES()["required"]` no longer contains `workflow_request`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_comfybio_graph_structure.py`:

```python
from bioflow_harness.server.handlers import generate_workflow


def _types(request_text: str) -> list[str]:
    workflow = generate_workflow({"request_text": request_text})["workflow"]
    return [node["type"] for node in workflow["nodes"]]


def test_bulk_graph_starts_at_metadata_validator_no_orchestration():
    types = _types("bulk RNA-seq human treated vs control with DESeq2 plots and report")
    assert types[0] == "SampleMetadataValidatorNode"
    assert types[-1] == "PreviewImage"
    assert types[-2] == "ComfyBIOReportNode"
    assert "WorkflowRequestLoader" not in types
    assert "WorkflowJSONOutput" not in types


def test_scrna_graph_starts_at_tenx_count_no_orchestration():
    types = _types("single-cell RNA-seq with scanpy, clustering and umap and marker genes")
    assert types[0] == "TenxCountNode"
    assert "WorkflowRequestLoader" not in types
    assert "WorkflowJSONOutput" not in types


def test_metadata_validator_has_no_upstream_input():
    import nodes

    required = nodes.NODE_CLASS_MAPPINGS["SampleMetadataValidatorNode"].INPUT_TYPES()["required"]
    assert "workflow_request" not in required
    assert "fastq_dir" in required
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_comfybio_graph_structure.py -q`
Expected: FAIL — `types[0]` is `"WorkflowRequestLoader"`, and `workflow_request` still present.

- [ ] **Step 3a: Edit the registry** — in `harness/registry/tool_selection_registry.yaml`, delete these four lines (the `request_loading` and `workflow_export` stages in both routes):

```
      {"stage_id": "request_loading", "stage_label": "Prompt or request payload loading", "tool_id": "workflow_request_loader", "operation_id": "load_request"},
```
(appears twice — bulk and scRNA route `stages` arrays)
```
      {"stage_id": "workflow_export", "stage_label": "ComfyUI workflow JSON export", "tool_id": "workflow_json_output", "operation_id": "workflow_json_export"}
```
(appears twice). Ensure the preceding line's trailing comma is fixed so each `stages` array remains valid JSON (the stage before `workflow_export` must lose its trailing comma).

- [ ] **Step 3b: Edit `node_catalog.py`** — delete the `"WorkflowRequestLoader"` entry (line 16) and the `"WorkflowJSONOutput"` entry (line 33). Change the `SampleMetadataValidatorNode` entry's `inputs` from `[{"name": "workflow_request", "type": "STRING"}]` to `[]`, and the `TenxCountNode` entry's `inputs` from `[{"name": "tenx_fastq_dir", "type": "STRING"}]` to `[]`.

- [ ] **Step 3c: Edit `nodes/ref_nodes.py`** — delete the `WorkflowRequestLoader` class (lines 19-28) and the `WorkflowJSONOutput` class (lines 316-322). In `SampleMetadataValidatorNode.INPUT_TYPES`, remove the `"workflow_request": cls._upstream_input(),` line. In `TenxCountNode.INPUT_TYPES`, remove the `"tenx_fastq_dir": cls._upstream_input(),` line.

- [ ] **Step 3d: Edit `nodes/registry.py`** — remove `WorkflowJSONOutput` and `WorkflowRequestLoader` from the `from nodes.ref_nodes import (...)` block and from `NODE_CLASS_MAPPINGS`.

- [ ] **Step 3e: Edit `workflow_builder.py`** — in `_widgets_for_stage`, delete the two `if definition.node_type == "WorkflowRequestLoader": ...` / `... == "WorkflowJSONOutput": ...` blocks (lines 118-121), and delete the now-unused `_request_text` method (lines 129-132).

- [ ] **Step 3f: Edit `workflow_regenerator.py`** — in `regenerate_bulk_rna_seq_workflow`, remove the `WorkflowRequestLoader` tuple from the initial `node_specs` list (lines 19-23) and remove the `WorkflowJSONOutput` tuple from the `node_specs.extend([...])` block (lines 120-124).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_comfybio_graph_structure.py tests/test_comfybio_node_contract.py tests/test_comfybio_builder_injection.py tests/test_comfybio_handlers.py -q`
Expected: PASS (graph-structure new tests + slice 1/2 suites, incl. the schema-drift guard, still green).

- [ ] **Step 5: Commit**

```bash
git add harness/registry/tool_selection_registry.yaml harness/src/bioflow_harness/comfy/node_catalog.py harness/src/bioflow_harness/comfy/workflow_builder.py harness/src/bioflow_harness/comfy/workflow_regenerator.py nodes/ref_nodes.py nodes/registry.py tests/test_comfybio_graph_structure.py
git -c user.name=ddukhae -c user.email=dongjoon69@gmail.com commit -m "feat: remove orchestration nodes from generated graphs

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Sample loading (CSV-first, folder-scan fallback)

**Files:**
- Create: `nodes/sample_loading.py`
- Test: `tests/test_comfybio_sample_loading.py`

**Interfaces:**
- Produces: `Sample(sample_id: str, condition: str, fastq_1: Path, fastq_2: Path | None)` (frozen dataclass); `load_samples(fastq_dir, metadata_csv=None) -> list[Sample]`; `SampleDiscoveryError(ValueError)`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_comfybio_sample_loading.py`:

```python
from pathlib import Path

import pytest

from nodes.sample_loading import Sample, SampleDiscoveryError, load_samples

QS = Path("harness/examples/fixtures/quickstart")
QS_META = QS / "sample_metadata.csv"


def test_load_from_csv_returns_all_samples_with_conditions():
    samples = load_samples(QS, QS_META)
    assert [s.sample_id for s in samples] == ["sample_a", "sample_b", "sample_c", "sample_d"]
    assert samples[0].condition == "control"
    assert samples[2].condition == "treatment"
    assert samples[0].fastq_1 == QS / "sample_a_R1.fastq"
    assert samples[0].fastq_2 == QS / "sample_a_R2.fastq"


def test_folder_scan_fallback_pairs_reads_with_unknown_condition():
    samples = load_samples(QS, None)
    assert {s.sample_id for s in samples} == {"sample_a", "sample_b", "sample_c", "sample_d"}
    assert all(s.condition == "unknown" for s in samples)
    assert all(s.fastq_2 is not None for s in samples)


def test_missing_fastq_dir_raises():
    with pytest.raises(SampleDiscoveryError):
        load_samples(Path("harness/examples/fixtures/does_not_exist"), None)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_comfybio_sample_loading.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'nodes.sample_loading'`.

- [ ] **Step 3: Write the implementation**

Create `nodes/sample_loading.py`:

```python
import csv
from dataclasses import dataclass
from pathlib import Path


class SampleDiscoveryError(ValueError):
    pass


@dataclass(frozen=True)
class Sample:
    sample_id: str
    condition: str
    fastq_1: Path
    fastq_2: Path | None


_R1_TOKENS = ("_R1", "_1")
_R2_TOKENS = ("_R2", "_2")


def load_samples(fastq_dir, metadata_csv=None) -> list[Sample]:
    fastq_dir = Path(fastq_dir)
    if metadata_csv is not None and Path(metadata_csv).exists():
        return _load_from_csv(Path(metadata_csv))
    return _scan_fastq_dir(fastq_dir)


def _load_from_csv(metadata_csv: Path) -> list[Sample]:
    base = metadata_csv.parent
    samples: list[Sample] = []
    with metadata_csv.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = {"sample_id", "condition", "fastq_1"} - set(reader.fieldnames or [])
        if missing:
            raise SampleDiscoveryError(f"Metadata CSV is missing columns: {sorted(missing)}")
        for row in reader:
            fastq_2 = _resolve(base, row["fastq_2"]) if row.get("fastq_2") else None
            samples.append(Sample(row["sample_id"], row["condition"], _resolve(base, row["fastq_1"]), fastq_2))
    if not samples:
        raise SampleDiscoveryError(f"Metadata CSV has no samples: {metadata_csv}")
    return samples


def _resolve(base: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else base / path


def _scan_fastq_dir(fastq_dir: Path) -> list[Sample]:
    if not fastq_dir.exists():
        raise SampleDiscoveryError(f"FASTQ directory not found: {fastq_dir}")
    read1: dict[str, Path] = {}
    read2: dict[str, Path] = {}
    for path in sorted(fastq_dir.iterdir()):
        name = path.name.lower()
        if not path.is_file() or (".fastq" not in name and ".fq" not in name):
            continue
        for token in _R1_TOKENS:
            if token in path.name:
                read1[path.name.replace(token, "", 1).split(".")[0]] = path
                break
        else:
            for token in _R2_TOKENS:
                if token in path.name:
                    read2[path.name.replace(token, "", 1).split(".")[0]] = path
                    break
    samples = [Sample(sid, "unknown", read1[sid], read2.get(sid)) for sid in sorted(read1)]
    if not samples:
        raise SampleDiscoveryError(f"No FASTQ read files found in {fastq_dir}")
    return samples
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_comfybio_sample_loading.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add nodes/sample_loading.py tests/test_comfybio_sample_loading.py
git -c user.name=ddukhae -c user.email=dongjoon69@gmail.com commit -m "feat: add sample loading with CSV-first + folder-scan fallback

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Runtime glue (runner resolution, env gate, preview loader)

**Files:**
- Create: `nodes/execution.py`
- Test: `tests/test_comfybio_execution.py`

**Interfaces:**
- Produces: `resolve_runner(runner=None)` → the given runner or a new `CondaCommandRunner`; `require_environment(probe=None) -> EnvironmentReport` (raises `EnvironmentNotReadyError` when not ready); `load_preview_tensor(png_path)` (lazy torch/PIL, returns a 4-D tensor). Re-exports `EnvironmentNotReadyError`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_comfybio_execution.py`:

```python
import pytest

from nodes.execution import EnvironmentNotReadyError, require_environment, resolve_runner
from bioflow_harness.runtime.command_runner import DryRunCommandRunner


class _ReadyProbe:
    def env_exists(self, name): return True
    def executable_exists(self, name, exe): return True
    def executable_version(self, name, exe): return "1.0"


class _MissingProbe:
    def env_exists(self, name): return False
    def executable_exists(self, name, exe): return False
    def executable_version(self, name, exe): return None


def test_resolve_runner_returns_injected_runner():
    runner = DryRunCommandRunner()
    assert resolve_runner(runner) is runner


def test_require_environment_passes_when_ready():
    report = require_environment(_ReadyProbe())
    assert report.ready is True


def test_require_environment_raises_when_missing():
    with pytest.raises(EnvironmentNotReadyError):
        require_environment(_MissingProbe())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_comfybio_execution.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'nodes.execution'`.

- [ ] **Step 3: Write the implementation**

Create `nodes/execution.py`:

```python
from pathlib import Path

from bioflow_harness.runtime.command_runner import CondaCommandRunner
from bioflow_harness.runtime.environment import validate_bulk_rna_seq_environment
from bioflow_harness.runtime.ref_workflow import EnvironmentNotReadyError

__all__ = ["EnvironmentNotReadyError", "resolve_runner", "require_environment", "load_preview_tensor"]


def resolve_runner(runner=None):
    return runner if runner is not None else CondaCommandRunner()


def require_environment(probe=None):
    report = validate_bulk_rna_seq_environment(probe)
    if not report.ready:
        raise EnvironmentNotReadyError(report)
    return report


def load_preview_tensor(png_path):
    import numpy as np
    import torch
    from PIL import Image

    path = Path(png_path)
    if path.exists() and path.stat().st_size > 0:
        try:
            array = np.asarray(Image.open(path).convert("RGB"), dtype="float32") / 255.0
        except Exception:
            array = np.zeros((64, 64, 3), dtype="float32")
    else:
        array = np.zeros((64, 64, 3), dtype="float32")
    return torch.from_numpy(array)[None,]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_comfybio_execution.py -q`
Expected: PASS (3 tests). `load_preview_tensor` is not exercised here (torch-free CI).

- [ ] **Step 5: Commit**

```bash
git add nodes/execution.py tests/test_comfybio_execution.py
git -c user.name=ddukhae -c user.email=dongjoon69@gmail.com commit -m "feat: add node execution glue (runner, env gate, preview loader)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Per-stage conda argv builders

**Files:**
- Create: `nodes/stage_commands.py`
- Test: `tests/test_comfybio_stage_commands.py`

**Interfaces:**
- Consumes: `nodes.sample_loading.Sample`.
- Produces: `ENV_NAME`, `SCRIPT_DIR`, `REPORT_SCRIPT`; `fastp_qc_argv(sample, output_dir, threads, extra_command="")`, `fastp_trim_argv(sample, sample_output_dir, threads, extra_command="")`, `salmon_index_argv(transcriptome_fasta, index_dir, threads, extra_command="")`, `salmon_quant_argv(index_dir, read1, read2, output_dir, read_layout, threads, extra_command="")`, `tximport_argv(salmon_quant_dir, count_matrix, extra_command="")`, `deseq2_argv(count_matrix, sample_metadata, results_csv, extra_command="")`, `deseq2_viz_argv(count_matrix, results_csv, plot_dir, extra_command="")`, `report_argv(results_csv, plot_dir, report_path)` — all return `list[str]`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_comfybio_stage_commands.py`:

```python
from pathlib import Path

from nodes.sample_loading import Sample
from nodes.stage_commands import (
    fastp_qc_argv,
    salmon_index_argv,
    salmon_quant_argv,
    tximport_argv,
    report_argv,
)

SAMPLE = Sample("sample_a", "control", Path("/data/a_R1.fastq"), Path("/data/a_R2.fastq"))


def test_fastp_qc_argv_wraps_conda_and_includes_paired_reads():
    argv = fastp_qc_argv(SAMPLE, Path("/out/qc"), 2)
    assert argv[:5] == ["conda", "run", "-n", "bulk_rna_seq", "fastp"]
    assert "-i" in argv and "/data/a_R1.fastq" in argv
    assert "-I" in argv and "/data/a_R2.fastq" in argv
    assert "/out/qc/sample_a.fastp.json" in argv


def test_salmon_index_argv():
    argv = salmon_index_argv("/refs/tx.fa", "/out/idx", 4)
    assert argv[:6] == ["conda", "run", "-n", "bulk_rna_seq", "salmon", "index"]
    assert "-t" in argv and "/refs/tx.fa" in argv


def test_salmon_quant_argv_single_end_omits_read2():
    argv = salmon_quant_argv("/out/idx", "/t/R1.fastq", None, "/out/q", "A", 2)
    assert "-1" in argv and "/t/R1.fastq" in argv
    assert "-2" not in argv


def test_extra_command_tokens_are_appended():
    argv = tximport_argv("/out/q", "/out/m.csv", extra_command="--flag value")
    assert argv[-2:] == ["--flag", "value"]


def test_report_argv_is_plain_python_not_conda():
    argv = report_argv("/out/results.csv", "/out/plots", "/out/report.md")
    assert argv[0].endswith("python") or "python" in argv[0]
    assert "conda" not in argv
    assert argv[-2:] == ["--output", "/out/report.md"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_comfybio_stage_commands.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'nodes.stage_commands'`.

- [ ] **Step 3: Write the implementation**

Create `nodes/stage_commands.py`:

```python
import sys
from pathlib import Path

from bioflow_harness.runtime.command_runner import conda_command, parse_extra_command_tokens

ENV_NAME = "bulk_rna_seq"
_REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = _REPO_ROOT / "harness" / "scripts"
REPORT_SCRIPT = _REPO_ROOT / "harness" / "src" / "bioflow_harness" / "runtime" / "report.py"


def _extra(extra_command: str) -> list[str]:
    return parse_extra_command_tokens(extra_command) if extra_command else []


def fastp_qc_argv(sample, output_dir, threads, extra_command="") -> list[str]:
    out = Path(output_dir)
    args = ["-i", str(sample.fastq_1)]
    if sample.fastq_2 is not None:
        args += ["-I", str(sample.fastq_2)]
    args += [
        "-w", str(threads),
        "--json", str(out / f"{sample.sample_id}.fastp.json"),
        "--html", str(out / f"{sample.sample_id}.fastp.html"),
    ]
    return conda_command(ENV_NAME, "fastp", *args, *_extra(extra_command))


def fastp_trim_argv(sample, sample_output_dir, threads, extra_command="") -> list[str]:
    out = Path(sample_output_dir)
    args = ["-i", str(sample.fastq_1)]
    if sample.fastq_2 is not None:
        args += ["-I", str(sample.fastq_2)]
    args += ["--out1", str(out / "R1.fastq")]
    if sample.fastq_2 is not None:
        args += ["--out2", str(out / "R2.fastq")]
    args += ["-w", str(threads)]
    return conda_command(ENV_NAME, "fastp", *args, *_extra(extra_command))


def salmon_index_argv(transcriptome_fasta, index_dir, threads, extra_command="") -> list[str]:
    return conda_command(
        ENV_NAME, "salmon", "index",
        "-t", str(transcriptome_fasta),
        "-i", str(index_dir),
        "-p", str(threads),
        *_extra(extra_command),
    )


def salmon_quant_argv(index_dir, read1, read2, output_dir, read_layout, threads, extra_command="") -> list[str]:
    args = ["-i", str(index_dir), "-l", str(read_layout), "-1", str(read1)]
    if read2 is not None:
        args += ["-2", str(read2)]
    args += ["-p", str(threads), "-o", str(output_dir)]
    return conda_command(ENV_NAME, "salmon", "quant", *args, *_extra(extra_command))


def tximport_argv(salmon_quant_dir, count_matrix, extra_command="") -> list[str]:
    return conda_command(
        ENV_NAME, "Rscript", str(SCRIPT_DIR / "tximport_import.R"),
        str(salmon_quant_dir), str(count_matrix),
        *_extra(extra_command),
    )


def deseq2_argv(count_matrix, sample_metadata, results_csv, extra_command="") -> list[str]:
    return conda_command(
        ENV_NAME, "Rscript", str(SCRIPT_DIR / "deseq2_analysis.R"),
        str(count_matrix), str(sample_metadata), str(results_csv),
        *_extra(extra_command),
    )


def deseq2_viz_argv(count_matrix, results_csv, plot_dir, extra_command="") -> list[str]:
    return conda_command(
        ENV_NAME, "Rscript", str(SCRIPT_DIR / "deseq2_visualization.R"),
        str(count_matrix), str(results_csv), str(plot_dir),
        *_extra(extra_command),
    )


def report_argv(results_csv, plot_dir, report_path) -> list[str]:
    return [
        sys.executable, str(REPORT_SCRIPT),
        "--results", str(results_csv),
        "--plot-dir", str(plot_dir),
        "--output", str(report_path),
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_comfybio_stage_commands.py -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add nodes/stage_commands.py tests/test_comfybio_stage_commands.py
git -c user.name=ddukhae -c user.email=dongjoon69@gmail.com commit -m "feat: add per-stage conda argv builders

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: SampleMetadataValidatorNode.run() — entry gate

**Files:**
- Modify: `nodes/ref_nodes.py` (`SampleMetadataValidatorNode`)
- Test: `tests/test_comfybio_node_execution.py` (new)

**Interfaces:**
- Consumes: `nodes.execution.require_environment`, `nodes.execution.EnvironmentNotReadyError`, `nodes.sample_loading.load_samples`.
- Produces: `SampleMetadataValidatorNode().run(fastq_dir, metadata_csv, extra_command="", probe=None) -> tuple[str]` returning the metadata path (or fastq dir when no metadata).

- [ ] **Step 1: Write the failing test**

Create `tests/test_comfybio_node_execution.py`:

```python
from pathlib import Path

import pytest

import nodes
from nodes.execution import EnvironmentNotReadyError

QS = "harness/examples/fixtures/quickstart"
QS_META = "harness/examples/fixtures/quickstart/sample_metadata.csv"


class _ReadyProbe:
    def env_exists(self, name): return True
    def executable_exists(self, name, exe): return True
    def executable_version(self, name, exe): return "1.0"


class _MissingProbe:
    def env_exists(self, name): return False
    def executable_exists(self, name, exe): return False
    def executable_version(self, name, exe): return None


def test_metadata_validator_returns_metadata_path_when_env_ready():
    node = nodes.NODE_CLASS_MAPPINGS["SampleMetadataValidatorNode"]()
    result = node.run(fastq_dir=QS, metadata_csv=QS_META, extra_command="", probe=_ReadyProbe())
    assert result == (QS_META,)


def test_metadata_validator_raises_when_env_not_ready():
    node = nodes.NODE_CLASS_MAPPINGS["SampleMetadataValidatorNode"]()
    with pytest.raises(EnvironmentNotReadyError):
        node.run(fastq_dir=QS, metadata_csv=QS_META, extra_command="", probe=_MissingProbe())


def test_metadata_validator_raises_on_missing_fastq_dir():
    node = nodes.NODE_CLASS_MAPPINGS["SampleMetadataValidatorNode"]()
    with pytest.raises(FileNotFoundError):
        node.run(fastq_dir="harness/examples/fixtures/missing", metadata_csv="", extra_command="", probe=_ReadyProbe())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_comfybio_node_execution.py -q`
Expected: FAIL — `SampleMetadataValidatorNode` has no `run` (AttributeError).

- [ ] **Step 3: Write the implementation**

At the very top of `nodes/ref_nodes.py`, above `class _BaseComfyBIONode` (line 1), add these imports (they follow the existing absolute `from nodes.X import` style in `registry.py`; the three imported modules only depend on `bioflow_harness`/stdlib, so there is no import cycle):

```python
from pathlib import Path

from nodes.execution import require_environment, resolve_runner, load_preview_tensor
from nodes.sample_loading import load_samples
from nodes import stage_commands
```

Add the `run` method to `SampleMetadataValidatorNode` (after its `INPUT_TYPES`):

```python
    def run(self, fastq_dir, metadata_csv, extra_command="", probe=None) -> tuple[str]:
        require_environment(probe)
        fastq_path = Path(fastq_dir)
        if not fastq_path.exists():
            raise FileNotFoundError(f"FASTQ directory not found: {fastq_dir}")
        metadata_path = Path(metadata_csv) if metadata_csv else None
        load_samples(fastq_path, metadata_path)  # raises if no samples resolvable
        return (str(metadata_path) if metadata_path else str(fastq_path),)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_comfybio_node_execution.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add nodes/ref_nodes.py tests/test_comfybio_node_execution.py
git -c user.name=ddukhae -c user.email=dongjoon69@gmail.com commit -m "feat: add SampleMetadataValidatorNode.run entry gate

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: FastpQCNode + FastpTrimNode run()

**Files:**
- Modify: `nodes/ref_nodes.py` (`FastpQCNode`, `FastpTrimNode`)
- Test: `tests/test_comfybio_node_execution.py` (append)

**Interfaces:**
- Consumes: `resolve_runner`, `load_samples`, `stage_commands.fastp_qc_argv`, `stage_commands.fastp_trim_argv`, `bioflow_harness.runtime.command_runner.DryRunCommandRunner`.
- Produces: `FastpQCNode().run(fastq_pair, fastq_dir, metadata_csv, output_dir, threads=2, extra_command="", runner=None) -> tuple[str]` (returns `output_dir`); `FastpTrimNode().run(fastp_qc_json, fastq_dir, metadata_csv, output_dir, threads=2, extra_command="", runner=None) -> tuple[str]` (returns `output_dir`).

- [ ] **Step 1: Write the failing test** — append to `tests/test_comfybio_node_execution.py`:

```python
from bioflow_harness.runtime.command_runner import DryRunCommandRunner


def test_fastp_qc_runs_one_command_per_sample_and_creates_output(tmp_path):
    runner = DryRunCommandRunner()
    out = tmp_path / "qc"
    node = nodes.NODE_CLASS_MAPPINGS["FastpQCNode"]()
    result = node.run(
        fastq_pair="upstream", fastq_dir=QS, metadata_csv=QS_META,
        output_dir=str(out), threads=2, extra_command="", runner=runner,
    )
    assert result == (str(out),)
    assert out.exists()
    assert len(runner.commands) == 4
    assert runner.commands[0].argv[:5] == ["conda", "run", "-n", "bulk_rna_seq", "fastp"]


def test_fastp_trim_creates_per_sample_dirs(tmp_path):
    runner = DryRunCommandRunner()
    out = tmp_path / "trimmed"
    node = nodes.NODE_CLASS_MAPPINGS["FastpTrimNode"]()
    result = node.run(
        fastp_qc_json="upstream", fastq_dir=QS, metadata_csv=QS_META,
        output_dir=str(out), threads=2, extra_command="", runner=runner,
    )
    assert result == (str(out),)
    assert (out / "sample_a").exists()
    assert len(runner.commands) == 4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_comfybio_node_execution.py -k "fastp" -q`
Expected: FAIL — `FastpQCNode` has no `run`.

- [ ] **Step 3: Write the implementation** — add `run` to `FastpQCNode`:

```python
    def run(self, fastq_pair, fastq_dir, metadata_csv, output_dir, threads=2, extra_command="", runner=None) -> tuple[str]:
        runner = resolve_runner(runner)
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        for sample in load_samples(Path(fastq_dir), Path(metadata_csv) if metadata_csv else None):
            runner.run(stage_commands.fastp_qc_argv(sample, out, threads, extra_command), out)
        return (str(out),)
```

Add `run` to `FastpTrimNode`:

```python
    def run(self, fastp_qc_json, fastq_dir, metadata_csv, output_dir, threads=2, extra_command="", runner=None) -> tuple[str]:
        runner = resolve_runner(runner)
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        for sample in load_samples(Path(fastq_dir), Path(metadata_csv) if metadata_csv else None):
            sample_dir = out / sample.sample_id
            sample_dir.mkdir(parents=True, exist_ok=True)
            runner.run(stage_commands.fastp_trim_argv(sample, sample_dir, threads, extra_command), out)
        return (str(out),)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_comfybio_node_execution.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add nodes/ref_nodes.py tests/test_comfybio_node_execution.py
git -c user.name=ddukhae -c user.email=dongjoon69@gmail.com commit -m "feat: add FastpQC and FastpTrim node execution

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: SalmonIndexNode + SalmonQuantNode run()

**Files:**
- Modify: `nodes/ref_nodes.py` (`SalmonIndexNode`, `SalmonQuantNode`)
- Test: `tests/test_comfybio_node_execution.py` (append)

**Interfaces:**
- Consumes: `stage_commands.salmon_index_argv`, `stage_commands.salmon_quant_argv`.
- Produces: `SalmonIndexNode().run(transcriptome_fasta_path, transcriptome_fasta, index_dir, threads=2, extra_command="", runner=None) -> tuple[str]` (returns `index_dir`); `SalmonQuantNode().run(salmon_index_dir, index_dir, fastq_dir, metadata_csv, output_dir, read_layout="A", threads=2, extra_command="", runner=None) -> tuple[str]` (returns `output_dir`). Quant reads trimmed FASTQs from `Path(output_dir).parent / "trimmed" / <sample_id> / R1.fastq|R2.fastq`.

- [ ] **Step 1: Write the failing test** — append:

```python
def test_salmon_index_runs_once_and_creates_dir(tmp_path):
    runner = DryRunCommandRunner()
    idx = tmp_path / "salmon_index"
    node = nodes.NODE_CLASS_MAPPINGS["SalmonIndexNode"]()
    result = node.run(
        transcriptome_fasta_path="upstream",
        transcriptome_fasta="harness/examples/fixtures/quickstart/toy_transcriptome.fasta",
        index_dir=str(idx), threads=2, extra_command="", runner=runner,
    )
    assert result == (str(idx),)
    assert idx.exists()
    assert len(runner.commands) == 1
    assert runner.commands[0].argv[:6] == ["conda", "run", "-n", "bulk_rna_seq", "salmon", "index"]


def test_salmon_quant_uses_trimmed_reads_sibling_of_output(tmp_path):
    runner = DryRunCommandRunner()
    base = tmp_path / "run"
    quant = base / "salmon_quant"
    node = nodes.NODE_CLASS_MAPPINGS["SalmonQuantNode"]()
    result = node.run(
        salmon_index_dir="upstream", index_dir=str(base / "salmon_index"),
        fastq_dir=QS, metadata_csv=QS_META, output_dir=str(quant),
        read_layout="A", threads=2, extra_command="", runner=runner,
    )
    assert result == (str(quant),)
    assert len(runner.commands) == 4
    joined = " ".join(runner.commands[0].argv)
    assert str(base / "trimmed" / "sample_a" / "R1.fastq") in joined
    assert (quant / "sample_a").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_comfybio_node_execution.py -k "salmon" -q`
Expected: FAIL — nodes have no `run`.

- [ ] **Step 3: Write the implementation** — add `run` to `SalmonIndexNode`:

```python
    def run(self, transcriptome_fasta_path, transcriptome_fasta, index_dir, threads=2, extra_command="", runner=None) -> tuple[str]:
        runner = resolve_runner(runner)
        idx = Path(index_dir)
        idx.mkdir(parents=True, exist_ok=True)
        runner.run(stage_commands.salmon_index_argv(transcriptome_fasta, idx, threads, extra_command), idx)
        return (str(idx),)
```

Add `run` to `SalmonQuantNode`:

```python
    def run(self, salmon_index_dir, index_dir, fastq_dir, metadata_csv, output_dir, read_layout="A", threads=2, extra_command="", runner=None) -> tuple[str]:
        runner = resolve_runner(runner)
        quant = Path(output_dir)
        quant.mkdir(parents=True, exist_ok=True)
        trimmed = quant.parent / "trimmed"
        for sample in load_samples(Path(fastq_dir), Path(metadata_csv) if metadata_csv else None):
            sample_out = quant / sample.sample_id
            sample_out.mkdir(parents=True, exist_ok=True)
            read1 = trimmed / sample.sample_id / "R1.fastq"
            read2 = trimmed / sample.sample_id / "R2.fastq" if sample.fastq_2 is not None else None
            runner.run(
                stage_commands.salmon_quant_argv(index_dir, read1, read2, sample_out, read_layout, threads, extra_command),
                quant,
            )
        return (str(quant),)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_comfybio_node_execution.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add nodes/ref_nodes.py tests/test_comfybio_node_execution.py
git -c user.name=ddukhae -c user.email=dongjoon69@gmail.com commit -m "feat: add SalmonIndex and SalmonQuant node execution

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 8: TximportNode + DESeq2AnalysisNode run()

**Files:**
- Modify: `nodes/ref_nodes.py` (`TximportNode`, `DESeq2AnalysisNode`)
- Test: `tests/test_comfybio_node_execution.py` (append)

**Interfaces:**
- Consumes: `stage_commands.tximport_argv`, `stage_commands.deseq2_argv`.
- Produces: `TximportNode().run(salmon_quant_dir_path, salmon_quant_dir, metadata_csv, output_count_matrix, extra_command="", runner=None) -> tuple[str]` (returns `output_count_matrix`); `DESeq2AnalysisNode().run(deseq2_count_matrix, count_matrix, sample_metadata, results_csv, design_formula="~ condition", extra_command="", runner=None) -> tuple[str]` (returns `results_csv`). `design_formula` is accepted but not passed to the R script (parity with the existing `deseq2_analysis.R` 3-arg contract).

- [ ] **Step 1: Write the failing test** — append:

```python
def test_tximport_runs_once_and_creates_matrix_parent(tmp_path):
    runner = DryRunCommandRunner()
    matrix = tmp_path / "deseq2" / "count_matrix.csv"
    node = nodes.NODE_CLASS_MAPPINGS["TximportNode"]()
    result = node.run(
        salmon_quant_dir_path="upstream", salmon_quant_dir=str(tmp_path / "salmon_quant"),
        metadata_csv=QS_META, output_count_matrix=str(matrix), extra_command="", runner=runner,
    )
    assert result == (str(matrix),)
    assert matrix.parent.exists()
    assert len(runner.commands) == 1
    assert "Rscript" in runner.commands[0].argv


def test_deseq2_analysis_runs_once_and_returns_results(tmp_path):
    runner = DryRunCommandRunner()
    results = tmp_path / "deseq2" / "results.csv"
    node = nodes.NODE_CLASS_MAPPINGS["DESeq2AnalysisNode"]()
    result = node.run(
        deseq2_count_matrix="upstream", count_matrix=str(tmp_path / "count_matrix.csv"),
        sample_metadata=QS_META, results_csv=str(results),
        design_formula="~ condition", extra_command="", runner=runner,
    )
    assert result == (str(results),)
    assert results.parent.exists()
    assert len(runner.commands) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_comfybio_node_execution.py -k "tximport or deseq2_analysis" -q`
Expected: FAIL — nodes have no `run`.

- [ ] **Step 3: Write the implementation** — add `run` to `TximportNode`:

```python
    def run(self, salmon_quant_dir_path, salmon_quant_dir, metadata_csv, output_count_matrix, extra_command="", runner=None) -> tuple[str]:
        runner = resolve_runner(runner)
        matrix = Path(output_count_matrix)
        matrix.parent.mkdir(parents=True, exist_ok=True)
        runner.run(stage_commands.tximport_argv(salmon_quant_dir, matrix, extra_command), matrix.parent)
        return (str(matrix),)
```

Add `run` to `DESeq2AnalysisNode`:

```python
    def run(self, deseq2_count_matrix, count_matrix, sample_metadata, results_csv, design_formula="~ condition", extra_command="", runner=None) -> tuple[str]:
        runner = resolve_runner(runner)
        results = Path(results_csv)
        results.parent.mkdir(parents=True, exist_ok=True)
        runner.run(stage_commands.deseq2_argv(count_matrix, sample_metadata, results, extra_command), results.parent)
        return (str(results),)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_comfybio_node_execution.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add nodes/ref_nodes.py tests/test_comfybio_node_execution.py
git -c user.name=ddukhae -c user.email=dongjoon69@gmail.com commit -m "feat: add Tximport and DESeq2 analysis node execution

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 9: DESeq2VisualizationNode + ComfyBIOReportNode run()

**Files:**
- Modify: `nodes/ref_nodes.py` (`DESeq2VisualizationNode`, `ComfyBIOReportNode`)
- Test: `tests/test_comfybio_node_execution.py` (append)

**Interfaces:**
- Consumes: `stage_commands.deseq2_viz_argv`, `stage_commands.report_argv`, `load_preview_tensor`.
- Produces: `DESeq2VisualizationNode().run(deseq2_results_table, count_matrix, results_csv, plot_dir, extra_command="", runner=None, preview_loader=None) -> tuple[str, object]` (returns `(plot_dir, IMAGE)`; `preview_loader` defaults to `load_preview_tensor`, loads `<plot_dir>/pca.png`); `ComfyBIOReportNode().run(plot_dir_path, results_csv, plot_dir, report_path, extra_command="", runner=None) -> tuple[str]` (returns `report_path`).

- [ ] **Step 1: Write the failing test** — append:

```python
def test_deseq2_visualization_returns_plot_dir_and_image(tmp_path):
    runner = DryRunCommandRunner()
    plots = tmp_path / "plots"
    node = nodes.NODE_CLASS_MAPPINGS["DESeq2VisualizationNode"]()
    result = node.run(
        deseq2_results_table="upstream", count_matrix=str(tmp_path / "count_matrix.csv"),
        results_csv=str(tmp_path / "results.csv"), plot_dir=str(plots),
        extra_command="", runner=runner, preview_loader=lambda path: "IMAGE_STUB",
    )
    assert result == (str(plots), "IMAGE_STUB")
    assert plots.exists()
    assert len(runner.commands) == 1


def test_comfybio_report_runs_report_script(tmp_path):
    runner = DryRunCommandRunner()
    report = tmp_path / "report" / "comfybio_report.md"
    node = nodes.NODE_CLASS_MAPPINGS["ComfyBIOReportNode"]()
    result = node.run(
        plot_dir_path="upstream", results_csv=str(tmp_path / "results.csv"),
        plot_dir=str(tmp_path / "plots"), report_path=str(report),
        extra_command="", runner=runner,
    )
    assert result == (str(report),)
    assert report.parent.exists()
    assert len(runner.commands) == 1
    assert "conda" not in runner.commands[0].argv
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_comfybio_node_execution.py -k "visualization or report" -q`
Expected: FAIL — nodes have no `run`.

- [ ] **Step 3: Write the implementation** — add `run` to `DESeq2VisualizationNode`:

```python
    def run(self, deseq2_results_table, count_matrix, results_csv, plot_dir, extra_command="", runner=None, preview_loader=None) -> tuple[str, object]:
        runner = resolve_runner(runner)
        loader = preview_loader if preview_loader is not None else load_preview_tensor
        plots = Path(plot_dir)
        plots.mkdir(parents=True, exist_ok=True)
        runner.run(stage_commands.deseq2_viz_argv(count_matrix, results_csv, plots, extra_command), plots)
        return (str(plots), loader(plots / "pca.png"))
```

Add `run` to `ComfyBIOReportNode`:

```python
    def run(self, plot_dir_path, results_csv, plot_dir, report_path, extra_command="", runner=None) -> tuple[str]:
        runner = resolve_runner(runner)
        report = Path(report_path)
        report.parent.mkdir(parents=True, exist_ok=True)
        runner.run(stage_commands.report_argv(results_csv, plot_dir, report), report.parent)
        return (str(report),)
```

- [ ] **Step 4: Run the full suite to verify everything passes**

Run: `python -m pytest -q`
Expected: PASS (all slice 1/2/3 tests).

- [ ] **Step 5: Commit**

```bash
git add nodes/ref_nodes.py tests/test_comfybio_node_execution.py
git -c user.name=ddukhae -c user.email=dongjoon69@gmail.com commit -m "feat: add DESeq2 visualization and report node execution

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Manual Verification (after all tasks)

Requires the `bulk_rna_seq` conda env (`fastp`, `salmon`, `Rscript` + Bioconductor DESeq2/tximport) and a ComfyUI restart.

1. Restart ComfyUI so the new node `run()` methods load.
2. In the ComfyBIO panel, click Generate — confirm the graph loads starting at **Validate Sample Metadata** (no Workflow Request / Workflow JSON Export nodes).
3. Queue/Run the graph.
4. Confirm artifacts appear under the output directory (`qc/`, `trimmed/`, `salmon_index/`, `salmon_quant/`, `deseq2/`, `plots/`, `report/`) and the **Preview DESeq2 Plot** node renders an image.
5. Rename/remove the conda env and re-run: confirm the run fails at **Validate Sample Metadata** with the install-plan message.

## Notes / Known Limitations

- The folder-scan fallback sets `condition="unknown"`; DESeq2 still requires real condition metadata, so a metadata-less run succeeds only through tximport and then fails at DESeq2 with a clear error. This is expected (documented in the spec).
- `design_formula` on `DESeq2AnalysisNode` is accepted but not forwarded to `deseq2_analysis.R` (parity with the existing 3-arg script); wiring it through is out of scope.
- `workflow_regenerator.py` is a separate audit-path generator using the abandoned per-sample expansion model. Task 1 only keeps it consistent (drops the two removed node types); its broader reconciliation/removal is tracked as tech-debt.
```
