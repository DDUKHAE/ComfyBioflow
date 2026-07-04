import argparse
from pathlib import Path

from bioflow_harness.planner.tool_selector import load_registry


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("tool_id")
    parser.add_argument("--registry", type=Path, default=Path("registry/tool_selection_registry.yaml"))
    args = parser.parse_args()
    tool = load_registry(args.registry).tool_by_id(args.tool_id)
    for operation in tool.operations:
        print(f"{operation.node_type}: inputs={operation.input_types} outputs={operation.output_types}")


if __name__ == "__main__":
    main()

