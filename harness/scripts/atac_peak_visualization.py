import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def count_peaks(peaks_dir: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    # MACS3 writes one file per sample at <peaks_dir>/<sample>/<sample>_peaks.narrowPeak;
    # narrowPeak is a stable 10-column BED+4 format, one called peak per line.
    for narrowpeak_path in sorted(peaks_dir.glob("*/*_peaks.narrowPeak")):
        sample_name = narrowpeak_path.name.removesuffix("_peaks.narrowPeak")
        with narrowpeak_path.open(encoding="utf-8") as handle:
            counts[sample_name] = sum(1 for _ in handle)
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot peak counts per sample from MACS3 narrowPeak output.")
    parser.add_argument("--peaks-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    counts = count_peaks(args.peaks_dir)
    if not counts:
        raise SystemExit(f"No narrowPeak files found under {args.peaks_dir}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(list(counts.keys()), list(counts.values()))
    ax.set_title("Peak count per sample")
    ax.set_ylabel("Peaks")
    fig.tight_layout()
    fig.savefig(args.output)


if __name__ == "__main__":
    main()
