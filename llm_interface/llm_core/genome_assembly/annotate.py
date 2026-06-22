from __future__ import annotations

import re
import shlex
import subprocess
import tempfile
from pathlib import Path


def run_prokka(
    assembly_path: str,
    output_dir: str = "",
    prefix: str = "PROKKA",
    kingdom: str = "Bacteria",
    genus: str = "",
    species: str = "",
    rfam: bool = False,
    threads: int = 4,
    extra_args: str = "",
) -> tuple[str, str, str, int, str]:
    """Returns (gff_path, gbk_path, faa_path, n_genes, summary)"""
    out_dir = Path(output_dir) if output_dir else Path(tempfile.mkdtemp())
    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "prokka",
        "--outdir", str(out_dir),
        "--prefix", prefix,
        "--kingdom", kingdom,
        "--cpus", str(threads),
        "--force",
        assembly_path,
    ]
    if genus:
        cmd += ["--genus", genus]
    if species:
        cmd += ["--species", species]
    if rfam:
        cmd.append("--rfam")
    if extra_args.strip():
        cmd += shlex.split(extra_args)

    result = subprocess.run(cmd, capture_output=True, text=True)

    gff = str(out_dir / f"{prefix}.gff")
    gbk = str(out_dir / f"{prefix}.gbk")
    faa = str(out_dir / f"{prefix}.faa")

    if result.returncode != 0:
        return gff, gbk, faa, 0, f"ERROR: {result.stderr[:400]}"

    n_genes, summary = _prokka_summary(out_dir, prefix)
    return gff, gbk, faa, n_genes, summary


def _prokka_summary(out_dir: Path, prefix: str) -> tuple[int, str]:
    txt_path = out_dir / f"{prefix}.txt"
    lines = ["=== Prokka Annotation Summary ==="]
    n_genes = 0
    if txt_path.exists():
        for line in txt_path.read_text().splitlines():
            lines.append("  " + line.strip())
            m = re.search(r"^CDS\s+:\s+(\d+)", line.strip())
            if m:
                n_genes = int(m.group(1))
    else:
        lines.append("Summary .txt not found.")
    return n_genes, "\n".join(lines)
