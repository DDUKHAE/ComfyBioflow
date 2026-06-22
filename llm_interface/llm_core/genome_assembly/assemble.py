from __future__ import annotations

import shlex
import subprocess
import tempfile
from pathlib import Path


def run_spades(
    r1_path: str,
    r2_path: str | None = None,
    output_dir: str = "",
    threads: int = 8,
    memory_gb: int = 16,
    mode: str = "default",
    careful: bool = True,
    extra_args: str = "",
) -> tuple[str, str, str]:
    """Returns (contigs_path, scaffolds_path, summary)"""
    out_dir = Path(output_dir) if output_dir else Path(tempfile.mkdtemp())
    out_dir.mkdir(parents=True, exist_ok=True)

    paired = bool(r2_path and r2_path.strip())
    cmd = [
        "spades.py",
        "--threads", str(threads),
        "--memory", str(memory_gb),
        "-o", str(out_dir),
    ]
    if paired:
        cmd += ["-1", r1_path, "-2", r2_path]
    else:
        cmd += ["-s", r1_path]
    if mode != "default":
        cmd.append(f"--{mode}")
    if careful and mode not in ("meta", "rna"):
        cmd.append("--careful")
    if extra_args.strip():
        cmd += shlex.split(extra_args)

    result = subprocess.run(cmd, capture_output=True, text=True)
    contigs = str(out_dir / "contigs.fasta")
    scaffolds = str(out_dir / "scaffolds.fasta")

    if result.returncode != 0:
        return contigs, scaffolds, f"ERROR: {result.stderr[:400]}"

    summary = _fasta_summary(contigs, "SPAdes contigs")
    return contigs, scaffolds, summary


def run_flye(
    reads_path: str,
    output_dir: str = "",
    read_type: str = "nano-hq",
    genome_size: str = "5m",
    threads: int = 8,
    extra_args: str = "",
) -> tuple[str, str, str]:
    """Returns (assembly_path, assembly_info_path, summary)"""
    out_dir = Path(output_dir) if output_dir else Path(tempfile.mkdtemp())
    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "flye",
        f"--{read_type}", reads_path,
        "--genome-size", genome_size,
        "--out-dir", str(out_dir),
        "--threads", str(threads),
    ]
    if extra_args.strip():
        cmd += shlex.split(extra_args)

    result = subprocess.run(cmd, capture_output=True, text=True)
    assembly = str(out_dir / "assembly.fasta")
    info = str(out_dir / "assembly_info.txt")

    if result.returncode != 0:
        return assembly, info, f"ERROR: {result.stderr[:400]}"

    summary = _fasta_summary(assembly, "Flye assembly")
    return assembly, info, summary


def _fasta_summary(path: str, label: str) -> str:
    p = Path(path)
    if not p.exists():
        return f"{label}: file not found."
    lengths = []
    cur = 0
    for line in p.read_text().splitlines():
        if line.startswith(">"):
            if cur:
                lengths.append(cur)
            cur = 0
        else:
            cur += len(line.strip())
    if cur:
        lengths.append(cur)
    if not lengths:
        return f"{label}: empty FASTA."
    lengths.sort(reverse=True)
    total = sum(lengths)
    half = total / 2
    running = 0
    n50 = 0
    for l in lengths:
        running += l
        if running >= half:
            n50 = l
            break
    return (
        f"{label}: {len(lengths):,} sequences, "
        f"total={total:,} bp, N50={n50:,} bp, max={lengths[0]:,} bp"
    )
