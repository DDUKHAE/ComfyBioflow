import argparse
import json
from dataclasses import asdict
from pathlib import Path

from bioflow_harness.comfy.node_catalog import default_node_catalog
from bioflow_harness.planner.tool_selector import load_registry
from bioflow_harness.registry_validator import validate_official_route


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, default=Path("registry/tool_selection_registry.yaml"))
    parser.add_argument("--route-id", default="bulk_rna_seq_salmon_ref")
    args = parser.parse_args()
    report = validate_official_route(load_registry(args.registry), args.route_id, default_node_catalog())
    print(json.dumps(asdict(report), indent=2))


if __name__ == "__main__":
    main()
