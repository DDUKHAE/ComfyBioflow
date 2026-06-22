from __future__ import annotations

import re
import shlex
import subprocess
import tempfile
from pathlib import Path
# pyrefly: ignore [missing-import]
from comfy_api.latest import io


class _Base(io.ComfyNode):
    OUTPUT_NODE = True


class QUAST_qc(_Base):
    """Assembly quality assessment with QUAST.

    Reports N50, L50, total length, number of contigs, and (with reference)
    misassemblies and genome fraction covered.

    Example extra_args:
        --eukaryote --large --min-identity 90
    """

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="QUAST_qc",
            display_name="QUAST assembly QC",
            category="GenomeAssembly/QC",
            inputs=[
                io.String.Input("assembly_path",
                    display_name="Assembly FASTA",
                    multiline=False, default=""),
                io.String.Input("output_dir",
                    display_name="Output directory",
                    multiline=False, default=""),
                io.String.Input("reference_fa",
                    display_name="Reference genome (optional)",
                    multiline=False, default="",
                    tooltip="Reference genome FASTA for comparison metrics"),
                io.Int.Input("threads",
                    display_name="Threads",
                    default=4, min=1, max=64),
                io.Int.Input("min_contig",
                    display_name="Min contig length",
                    default=500, min=0, max=100000,
                    tooltip="Minimum contig length to include in report"),
                io.String.Input("extra_args",
                    display_name="Extra QUAST arguments",
                    multiline=True, default="",
                    tooltip="e.g. --eukaryote --large"),
            ],
            outputs=[
                io.String.Output("output_dir"),
                io.String.Output("report_path"),
                io.String.Output("summary_text"),
            ],
        )

    @classmethod
    def execute(
        cls, assembly_path, output_dir, reference_fa, threads, min_contig, extra_args,
    ) -> io.NodeOutput:
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
            err = result.stderr[:500]
            return io.NodeOutput(str(out_dir), report_path, f"ERROR:\n{err}")

        summary = _quast_summary(report_path)
        return io.NodeOutput(str(out_dir), report_path, summary)


class BUSCO_evaluate(_Base):
    """Assembly completeness assessment with BUSCO.

    Evaluates genome/transcriptome completeness using conserved single-copy
    ortholog genes from OrthoDB lineage databases.

    Example extra_args:
        --augustus_species human --long
    """

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="BUSCO_evaluate",
            display_name="BUSCO evaluate",
            category="GenomeAssembly/QC",
            inputs=[
                io.String.Input("assembly_path",
                    display_name="Assembly/Transcriptome/Proteins FASTA",
                    multiline=False, default=""),
                io.String.Input("output_dir",
                    display_name="Output directory",
                    multiline=False, default=""),
                io.String.Input("lineage",
                    display_name="Lineage dataset",
                    multiline=False, default="bacteria_odb10",
                    tooltip="e.g. bacteria_odb10, eukaryota_odb10, vertebrata_odb10"),
                io.Combo.Input("mode",
                    display_name="Mode",
                    options=["genome", "transcriptome", "proteins"],
                    default="genome"),
                io.Int.Input("threads",
                    display_name="Threads",
                    default=4, min=1, max=64),
                io.String.Input("extra_args",
                    display_name="Extra BUSCO arguments",
                    multiline=True, default=""),
            ],
            outputs=[
                io.String.Output("output_dir"),
                io.String.Output("summary_path"),
                io.Float.Output("completeness",
                    tooltip="Complete BUSCO percentage (C%)"),
                io.String.Output("summary_text"),
            ],
        )

    @classmethod
    def execute(
        cls, assembly_path, output_dir, lineage, mode, threads, extra_args,
    ) -> io.NodeOutput:
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
            "-f",  # force overwrite
        ]
        if extra_args.strip():
            cmd += shlex.split(extra_args)

        result = subprocess.run(cmd, capture_output=True, text=True)

        run_dir = out_dir / run_name
        summary_files = list(run_dir.glob("short_summary*.txt")) if run_dir.exists() else []
        summary_path = str(summary_files[0]) if summary_files else str(out_dir / "short_summary.txt")

        if result.returncode != 0:
            err = result.stderr[:500]
            return io.NodeOutput(str(out_dir), summary_path, 0.0, f"ERROR:\n{err}")

        completeness, summary = _busco_summary(summary_path)
        return io.NodeOutput(str(out_dir), summary_path, completeness, summary)


# ── Summary helpers ──────────────────────────────────────────────────────────

def _quast_summary(report_path: str) -> str:
    p = Path(report_path)
    if not p.exists():
        return "report.txt not found."
    text = p.read_text()
    lines = ["=== QUAST Assembly QC ==="]
    keywords = [
        "# contigs (>= 0 bp)",
        "# contigs (>= 500 bp)",
        "Total length (>= 0 bp)",
        "Total length (>= 500 bp)",
        "N50",
        "N90",
        "L50",
        "L90",
        "# misassemblies",
        "Genome fraction (%)",
        "GC (%)",
    ]
    for kw in keywords:
        for line in text.splitlines():
            if line.strip().startswith(kw):
                lines.append("  " + line.strip())
                break
    return "\n".join(lines)


def _busco_summary(summary_path: str) -> tuple[float, str]:
    p = Path(summary_path)
    if not p.exists():
        return 0.0, "BUSCO short_summary not found."
    text = p.read_text()
    lines = ["=== BUSCO Completeness ==="]

    complete = 0.0
    for line in text.splitlines():
        lines.append("  " + line.rstrip())
        m = re.search(r"C:(\d+\.\d+)%", line)
        if m:
            complete = float(m.group(1))

    return complete, "\n".join(lines[:20])
