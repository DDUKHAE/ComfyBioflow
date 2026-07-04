import argparse
from pathlib import Path

from bioflow_harness.cli import build_workflow


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt")
    parser.add_argument("--registry", type=Path, default=Path("registry/tool_selection_registry.yaml"))
    parser.add_argument("--output", type=Path, default=Path("examples/workflows/bulk_rna_seq_salmon_ref.json"))
    args = parser.parse_args()
    print(build_workflow(args.prompt, args.registry, args.output))


if __name__ == "__main__":
    main()

