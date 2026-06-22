from __future__ import annotations

import shlex
import subprocess
import tempfile
from pathlib import Path


def run_bowtie2_chip(
    r1_path: str,
    r2_path: str | None = None,
    index_prefix: str = "",
    output_dir: str = "",
    threads: int = 4,
    preset: str = "sensitive",
    max_fragment_size: int = 2000,
    remove_duplicates: bool = True,
    extra_args: str = "",
) -> tuple[str, str]:
    """Align ChIP-seq reads with Bowtie2, sort, optionally markdup.

    Returns (bam_path, flagstat_summary).
    """
    out_dir = Path(output_dir) if output_dir else Path(tempfile.mkdtemp())
    out_dir.mkdir(parents=True, exist_ok=True)

    paired = bool(r2_path and r2_path.strip())
    sam_path = str(out_dir / "aligned.sam")
    bam_unsorted = str(out_dir / "aligned_unsorted.bam")
    bam_sorted = str(out_dir / "aligned_sorted.bam")
    bam_final = str(out_dir / "aligned_final.bam")

    cmd = [
        "bowtie2",
        f"--{preset}",
        "-x", index_prefix,
        "-p", str(threads),
        "-X", str(max_fragment_size),
        "-S", sam_path,
    ]
    if paired:
        cmd += ["-1", r1_path, "-2", r2_path]
    else:
        cmd += ["-U", r1_path]
    if extra_args.strip():
        cmd += shlex.split(extra_args)

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)

    subprocess.run(
        ["samtools", "view", "-bS", "-o", bam_unsorted, sam_path],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["samtools", "sort", "-o", bam_sorted, "-@", str(threads), bam_unsorted],
        check=True, capture_output=True,
    )

    if remove_duplicates:
        subprocess.run(
            ["samtools", "markdup", bam_sorted, bam_final],
            check=True, capture_output=True,
        )
    else:
        import shutil
        shutil.copy(bam_sorted, bam_final)

    subprocess.run(["samtools", "index", bam_final], capture_output=True)

    flagstat = subprocess.run(
        ["samtools", "flagstat", bam_final],
        capture_output=True, text=True,
    )
    return bam_final, flagstat.stdout


def run_macs3_callpeak(
    treatment_bam: str,
    control_bam: str | None = None,
    output_dir: str = "",
    name: str = "sample",
    genome_size: str = "hs",
    q_value: float = 0.05,
    keep_dup: str = "auto",
    broad: bool = False,
    extra_args: str = "",
) -> tuple[str, str, int, str]:
    """Call peaks with MACS3.

    Returns (peaks_path, summit_path, n_peaks, summary).
    """
    out_dir = Path(output_dir) if output_dir else Path(tempfile.mkdtemp())
    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "macs3", "callpeak",
        "-t", treatment_bam,
        "-n", name,
        "--outdir", str(out_dir),
        "-g", genome_size,
        "-q", str(q_value),
        "--keep-dup", keep_dup,
    ]
    if control_bam and control_bam.strip():
        cmd += ["-c", control_bam]
    if broad:
        cmd.append("--broad")
    if extra_args.strip():
        cmd += shlex.split(extra_args)

    subprocess.run(cmd, capture_output=True, text=True, check=True)

    ext = "broadPeak" if broad else "narrowPeak"
    peaks_path = str(out_dir / f"{name}_peaks.{ext}")
    summit_path = str(out_dir / f"{name}_summits.bed") if not broad else ""

    n_peaks = 0
    p = Path(peaks_path)
    if p.exists():
        n_peaks = sum(
            1 for line in p.read_text().splitlines()
            if not line.startswith("#") and line.strip()
        )

    summary = "\n".join([
        f"Sample: {name}",
        f"Genome: {genome_size}",
        f"Mode: {'Broad' if broad else 'Narrow'}",
        f"Peaks: {n_peaks:,}",
    ])
    return peaks_path, summit_path, n_peaks, summary
