import argparse
import json
from pathlib import Path

from bioflow_harness.comfy.node_catalog import default_node_catalog
from bioflow_harness.comfy.workflow_builder import WorkflowBuilder
from bioflow_harness.llm.brief_extractor import extract_brief
from bioflow_harness.planner.tool_selector import load_registry
from bioflow_harness.planner.workflow_planner import WorkflowPlanner


def build_workflow_json(prompt: str, registry_path: Path, output_path: Path) -> Path:
    brief, _meta = extract_brief(prompt)
    plan = WorkflowPlanner(load_registry(registry_path)).plan(brief)
    workflow = WorkflowBuilder(default_node_catalog()).build(plan)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(workflow, indent=2), encoding="utf-8")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt")
    parser.add_argument("--registry", type=Path, default=Path("registry/tool_selection_registry.yaml"))
    parser.add_argument("--output", type=Path, default=Path("examples/workflows/bulk_rna_seq_salmon_ref.json"))
    args = parser.parse_args()
    print(build_workflow_json(args.prompt, args.registry, args.output))


if __name__ == "__main__":
    main()
