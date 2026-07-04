import argparse
import importlib


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("module")
    parser.add_argument("class_name")
    args = parser.parse_args()
    cls = getattr(importlib.import_module(args.module), args.class_name)
    for attr in ["RETURN_TYPES", "FUNCTION", "CATEGORY", "INPUT_TYPES"]:
        if not hasattr(cls, attr):
            raise SystemExit(f"missing {attr}")
    print("valid")


if __name__ == "__main__":
    main()
