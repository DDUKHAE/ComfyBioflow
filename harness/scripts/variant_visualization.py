import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def parse_stats(stats_path: Path) -> dict:
    snps = 0
    indels = 0
    ts_tv_ratio = 0.0
    for line in stats_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("SN\t"):
            fields = line.split("\t")
            label = fields[2].strip()
            if label == "number of SNPs:":
                snps = int(fields[3])
            elif label == "number of indels:":
                indels = int(fields[3])
        elif line.startswith("TSTV\t"):
            fields = line.split("\t")
            ts_tv_ratio = float(fields[4])
    return {"snps": snps, "indels": indels, "ts_tv_ratio": ts_tv_ratio}


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot bcftools stats summaries across samples.")
    parser.add_argument("--stats-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    stats_files = sorted(args.stats_dir.glob("*.stats.txt"))
    if not stats_files:
        raise SystemExit(f"No bcftools stats files found in {args.stats_dir}")

    samples = [path.name.removesuffix(".stats.txt") for path in stats_files]
    summaries = [parse_stats(path) for path in stats_files]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    snp_counts = [s["snps"] for s in summaries]
    indel_counts = [s["indels"] for s in summaries]
    axes[0].bar(samples, snp_counts, label="SNPs")
    axes[0].bar(samples, indel_counts, bottom=snp_counts, label="Indels")
    axes[0].set_title("Variant counts")
    axes[0].legend()
    axes[1].bar(samples, [s["ts_tv_ratio"] for s in summaries])
    axes[1].set_title("Ts/Tv ratio")
    fig.tight_layout()
    fig.savefig(args.output)


if __name__ == "__main__":
    main()
