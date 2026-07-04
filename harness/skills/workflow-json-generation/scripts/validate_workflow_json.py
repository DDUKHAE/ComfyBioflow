import argparse
import json
from pathlib import Path

from bioflow_harness.comfy.workflow_schema import validate_workflow_export


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("workflow_json", type=Path)
    args = parser.parse_args()
    validate_workflow_export(json.loads(args.workflow_json.read_text(encoding="utf-8")))
    print("valid")


if __name__ == "__main__":
    main()

