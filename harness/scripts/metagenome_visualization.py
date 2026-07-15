import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def parse_bracken_report(report_path: Path, top_n: int = 5) -> list[tuple[str, float]]:
    rows: list[tuple[str, float]] = []
    with report_path.open(encoding="utf-8") as handle:
        header = handle.readline().rstrip("\n").split("\t")
        name_idx = header.index("name")
        fraction_idx = header.index("fraction_total_reads")
        for line in handle:
            fields = line.rstrip("\n").split("\t")
            rows.append((fields[name_idx], float(fields[fraction_idx])))
    rows.sort(key=lambda row: row[1], reverse=True)
    return rows[:top_n]


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot top taxa by abundance fraction per sample from Bracken reports.")
    parser.add_argument("--reports-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--top-n", type=int, default=5)
    args = parser.parse_args()

    report_files = sorted(args.reports_dir.glob("*/bracken_output.txt"))
    if not report_files:
        raise SystemExit(f"No bracken_output.txt files found under {args.reports_dir}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, len(report_files), figsize=(6 * len(report_files), 4), squeeze=False)
    for ax, report_path in zip(axes[0], report_files):
        sample_name = report_path.parent.name
        top_taxa = parse_bracken_report(report_path, args.top_n)
        names = [name for name, _ in top_taxa]
        fractions = [fraction for _, fraction in top_taxa]
        ax.barh(names, fractions)
        ax.set_title(sample_name)
        ax.set_xlabel("Fraction of total reads")
    fig.tight_layout()
    fig.savefig(args.output)


if __name__ == "__main__":
    main()
