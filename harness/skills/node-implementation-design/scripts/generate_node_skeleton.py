import argparse


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("class_name")
    parser.add_argument("category")
    args = parser.parse_args()
    print(f"class {args.class_name}:")
    print("    RETURN_TYPES = ('STRING',)")
    print("    FUNCTION = 'run'")
    print(f"    CATEGORY = '{args.category}'")


if __name__ == "__main__":
    main()

