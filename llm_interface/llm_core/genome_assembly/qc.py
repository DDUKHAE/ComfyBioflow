from __future__ import annotations

import re
import shlex
import subprocess
import tempfile
from pathlib import Path


def run_quast(
    assembly_path: str,
    output_dir: str = "",
    reference_fa: str = "",
    threads: int = 4,
    min_contig: int = 500,
    extra_args: str = "",
) -> tuple[str, str]:
    """Returns (report_path, summary)"""
    out_dir = Path(output_dir) if output_dir else Path(tempfile.mkdtemp())
    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "quast.py",
        assembly_path,
        "--output-dir", str(out_dir),
        "--threads", str(threads),
        "--min-contig", str(min_contig),
    ]
    if reference_fa and reference_fa.strip():
        cmd += ["-r", reference_fa]
    if extra_args.strip():
        cmd += shlex.split(extra_args)

    result = subprocess.run(cmd, capture_output=True, text=True)
    report_path = str(out_dir / "report.txt")

    if result.returncode != 0:
        return report_path, f"ERROR: {result.stderr[:400]}"

    return report_path, _parse_quast_report(report_path)


def run_busco(
    assembly_path: str,
    output_dir: str = "",
    lineage: str = "bacteria_odb10",
    mode: str = "genome",
    threads: int = 4,
    extra_args: str = "",
) -> tuple[str, float, str]:
    """Returns (summary_path, completeness_pct, summary)"""
    out_dir = Path(output_dir) if output_dir else Path(tempfile.mkdtemp())
    out_dir.mkdir(parents=True, exist_ok=True)

    run_name = "busco_run"
    cmd = [
        "busco",
        "-i", assembly_path,
        "-l", lineage,
        "-m", mode,
        "-o", run_name,
        "--out_path", str(out_dir),
        "--cpu", str(threads),
        "-f",
    ]
    if extra_args.strip():
        cmd += shlex.split(extra_args)

    result = subprocess.run(cmd, capture_output=True, text=True)

    run_dir = out_dir / run_name
    summary_files = list(run_dir.glob("short_summary*.txt")) if run_dir.exists() else []
    summary_path = str(summary_files[0]) if summary_files else str(out_dir / "short_summary.txt")

    if result.returncode != 0:
        return summary_path, 0.0, f"ERROR: {result.stderr[:400]}"

    completeness, summary = _parse_busco_summary(summary_path)
    return summary_path, completeness, summary


def _parse_quast_report(report_path: str) -> str:
    p = Path(report_path)
    if not p.exists():
        return "report.txt not found."
    text = p.read_text()
    wanted = ["# contigs", "Total length", "N50", "L50", "GC (%)"]
    lines = ["=== QUAST Report ==="]
    for kw in wanted:
        for line in text.splitlines():
            if line.strip().startswith(kw):
                lines.append("  " + line.strip())
                break
    return "\n".join(lines)


def _parse_busco_summary(summary_path: str) -> tuple[float, str]:
    p = Path(summary_path)
    if not p.exists():
        return 0.0, "short_summary not found."
    text = p.read_text()
    complete = 0.0
    lines = ["=== BUSCO Summary ==="]
    for line in text.splitlines():
        if line.strip():
            lines.append("  " + line.rstrip())
        m = re.search(r"C:(\d+\.\d+)%", line)
        if m:
            complete = float(m.group(1))
    return complete, "\n".join(lines[:20])
