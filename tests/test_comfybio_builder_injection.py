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
