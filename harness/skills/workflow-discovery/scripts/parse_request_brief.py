import argparse
import json
from dataclasses import asdict

from bioflow_harness.parser.prompt_parser import parse_prompt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt")
    args = parser.parse_args()
    print(json.dumps(asdict(parse_prompt(args.prompt)), indent=2))


if __name__ == "__main__":
    main()

