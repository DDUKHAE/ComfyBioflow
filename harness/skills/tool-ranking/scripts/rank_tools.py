import argparse
from pathlib import Path

from bioflow_harness.planner.tool_selector import load_registry


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage")
    parser.add_argument("--registry", type=Path, default=Path("registry/tool_selection_registry.yaml"))
    args = parser.parse_args()
    registry = load_registry(args.registry)
    for tool in registry.tools:
        if args.stage in tool.stage_tags:
            print(f"{tool.tier}\t{tool.id}\t{tool.tier_rationale}")


if __name__ == "__main__":
    main()

