from __future__ import annotations

import shlex
import subprocess
import tempfile
from pathlib import Path


def run_bismark_align(
    r1_path: str,
    r2_path: str | None = None,
    genome_dir: str = "",
    output_dir: str = "",
    threads: int = 4,
    non_directional: bool = False,
    extra_args: str = "",
) -> tuple[str, str, str]:
    """Bisulfite-aware alignment with Bismark.

    Returns (bam_path, report_path, summary).
    """
    out_dir = Path(output_dir) if output_dir else Path(tempfile.mkdtemp())
    out_dir.mkdir(parents=True, exist_ok=True)

    paired = bool(r2_path and r2_path.strip())

    cmd = [
        "bismark",
        "--genome", genome_dir,
        "--output_dir", str(out_dir),
        "--parallel", str(max(1, threads // 4)),
    ]
    if non_directional:
        cmd.append("--non_directional")
    if extra_args.strip():
        cmd += shlex.split(extra_args)

    if paired:
        cmd += ["-1", r1_path, "-2", r2_path]
    else:
        cmd.append(r1_path)

    subprocess.run(cmd, capture_output=True, text=True, check=True)

    r1_stem = Path(r1_path).name.replace(".fastq.gz", "").replace(".fastq", "")
    if paired:
        bam_path = str(out_dir / f"{r1_stem}_bismark_bt2_pe.bam")
        report_path = str(out_dir / f"{r1_stem}_bismark_bt2_PE_report.txt")
    else:
        bam_path = str(out_dir / f"{r1_stem}_bismark_bt2.bam")
        report_path = str(out_dir / f"{r1_stem}_bismark_bt2_SE_report.txt")

    summary_lines = ["Bismark alignment complete."]
    p = Path(report_path)
    if p.exists():
        text = p.read_text()
        for kw in ["Mapping efficiency", "C methylated in CpG context"]:
            for line in text.splitlines():
                if kw in line:
                    summary_lines.append(line.strip())
                    break

    return bam_path, report_path, "\n".join(summary_lines)


def run_bismark_extract(
    bam_path: str,
    genome_dir: str = "",
    output_dir: str = "",
    CpG_only: bool = True,
    comprehensive: bool = False,
    threads: int = 4,
    extra_args: str = "",
) -> tuple[str, str, str]:
    """Extract methylation from Bismark BAM.

    Returns (coverage_path, bismark_cov_path, summary).
    """
    out_dir = Path(output_dir) if output_dir else Path(tempfile.mkdtemp())
    out_dir.mkdir(parents=True, exist_ok=True)

    paired = "_pe" in Path(bam_path).name or "_PE" in Path(bam_path).name

    cmd = [
        "bismark_methylation_extractor",
        bam_path,
        "--output", str(out_dir),
        "--genome_folder", genome_dir,
        "--parallel", str(max(1, threads // 4)),
        "--bedGraph",
        "--cytosine_report",
    ]
    if paired:
        cmd.append("--paired-end")
    if CpG_only:
        cmd.append("--CpG_only")
    if comprehensive:
        cmd.append("--comprehensive")
    if extra_args.strip():
        cmd += shlex.split(extra_args)

    subprocess.run(cmd, capture_output=True, text=True, check=True)

    cov_files = list(out_dir.glob("*CpG_report*"))
    bismark_cov_files = list(out_dir.glob("*.bismark.cov.gz"))

    bam_stem = Path(bam_path).stem
    coverage_path = str(cov_files[0]) if cov_files else str(out_dir / f"{bam_stem}.CpG_report.txt")
    bismark_cov_path = str(bismark_cov_files[0]) if bismark_cov_files else ""

    summary = "\n".join([
        "Bismark methylation extraction complete.",
        f"Coverage file : {Path(coverage_path).name}",
        f"Context       : {'CpG only' if CpG_only else 'All contexts'}",
    ])
    return coverage_path, bismark_cov_path, summary
