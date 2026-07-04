import argparse
import json
from dataclasses import asdict
from pathlib import Path

from bioflow_harness.parser.prompt_parser import parse_prompt
from bioflow_harness.planner.tool_selector import load_registry
from bioflow_harness.planner.workflow_planner import WorkflowPlanner


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt")
    parser.add_argument("--registry", type=Path, default=Path("registry/tool_selection_registry.yaml"))
    args = parser.parse_args()
    plan = WorkflowPlanner(load_registry(args.registry)).plan(parse_prompt(args.prompt))
    print(json.dumps(asdict(plan), indent=2))


if __name__ == "__main__":
    main()

