import argparse
from pathlib import Path


def write_atac_report(peaks_dir: Path, plot_dir: Path, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "# ComfyBIO ATAC-seq Report\n\n"
        "## Called Peaks\n\n"
        f"- Peaks directory: `{peaks_dir}`\n"
        f"- Peak summary plot: `{Path(plot_dir) / 'atac_summary.png'}`\n",
        encoding="utf-8",
    )
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Write a ComfyBIO ATAC-seq markdown report.")
    parser.add_argument("--peaks-dir", type=Path, required=True)
    parser.add_argument("--plot-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    write_atac_report(args.peaks_dir, args.plot_dir, args.output)


if __name__ == "__main__":
    main()
