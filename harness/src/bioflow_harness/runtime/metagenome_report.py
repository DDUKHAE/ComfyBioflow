import argparse
from pathlib import Path


def write_metagenome_report(bracken_dir: Path, plot_dir: Path, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "# ComfyBIO Metagenome Taxonomic Profiling Report\n\n"
        "## Bracken Abundance Estimates\n\n"
        f"- Bracken output directory: `{bracken_dir}`\n"
        f"- Taxonomic summary plot: `{Path(plot_dir) / 'metagenome_summary.png'}`\n",
        encoding="utf-8",
    )
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Write a ComfyBIO metagenome taxonomic profiling markdown report.")
    parser.add_argument("--bracken-dir", type=Path, required=True)
    parser.add_argument("--plot-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    write_metagenome_report(args.bracken_dir, args.plot_dir, args.output)


if __name__ == "__main__":
    main()
