import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def parse_quast_report(report_path: Path) -> dict[str, float]:
    # QUAST's report.tsv has ONE row per metric (label \t value), including both
    # length-thresholded variants ("# contigs (>= 1000 bp)") and exact un-thresholded
    # labels ("# contigs"). We want the exact un-thresholded labels only.
    metrics: dict[str, str] = {}
    with report_path.open(encoding="utf-8") as handle:
        next(handle)  # header row: "Assembly\t<assembly_name>"
        for line in handle:
            fields = line.rstrip("\n").split("\t")
            if len(fields) >= 2:
                metrics[fields[0]] = fields[1]
    return {
        "contigs": float(metrics.get("# contigs", 0)),
        "total_length": float(metrics.get("Total length", 0)),
        "n50": float(metrics.get("N50", 0)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot key QUAST assembly-quality metrics per sample.")
    parser.add_argument("--qc-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    report_files = sorted(args.qc_dir.glob("*/report.tsv"))
    if not report_files:
        raise SystemExit(f"No report.tsv files found under {args.qc_dir}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    samples = [path.parent.name for path in report_files]
    metrics = [parse_quast_report(path) for path in report_files]

    fig, axes = plt.subplots(1, 3, figsize=(15, 4))
    axes[0].bar(samples, [m["contigs"] for m in metrics])
    axes[0].set_title("# contigs")
    axes[1].bar(samples, [m["total_length"] for m in metrics])
    axes[1].set_title("Total length (bp)")
    axes[2].bar(samples, [m["n50"] for m in metrics])
    axes[2].set_title("N50 (bp)")
    fig.tight_layout()
    fig.savefig(args.output)


if __name__ == "__main__":
    main()
