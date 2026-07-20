import argparse
from pathlib import Path

from bioflow_harness.comfy.node_catalog import default_node_catalog
from bioflow_harness.planner.tool_selector import load_registry


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("tool_id")
    parser.add_argument("--registry", type=Path, default=Path("registry/tool_selection_registry.yaml"))
    args = parser.parse_args()
    tool = load_registry(args.registry).tool_by_id(args.tool_id)
    catalog = default_node_catalog()
    for operation in tool.operations:
        node = catalog.get(operation.node_type)
        if node is None:
            print(
                f"{operation.node_type}: not yet in node_catalog "
                f"(registry types only: inputs={operation.input_types} outputs={operation.output_types})"
            )
            continue
        inputs = ", ".join(f"{i['name']}:{i['type']}" for i in node.inputs) or "(none)"
        outputs = ", ".join(f"{o['name']}:{o['type']}" for o in node.outputs) or "(none)"
        print(f"{operation.node_type}: inputs=[{inputs}] outputs=[{outputs}]")


if __name__ == "__main__":
    main()

