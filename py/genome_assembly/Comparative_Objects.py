from __future__ import annotations

import shlex
import subprocess
import tempfile
from pathlib import Path
# pyrefly: ignore [missing-import]
from comfy_api.latest import io


class _Base(io.ComfyNode):
    OUTPUT_NODE = True


class MUMmer_align(_Base):
    """Whole-genome alignment with MUMmer (nucmer).

    Aligns a query assembly to a reference assembly using NUCmer,
    then generates a human-readable coordinates report.

    Example extra_args (nucmer):
        --maxmatch --breaklen 1000
    """

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="MUMmer_align",
            display_name="MUMmer nucmer align",
            category="GenomeAssembly/Comparative",
            inputs=[
                io.String.Input("reference_fa",
                    display_name="Reference FASTA",
                    multiline=False, default=""),
                io.String.Input("query_fa",
                    display_name="Query FASTA",
                    multiline=False, default=""),
                io.String.Input("output_dir",
                    display_name="Output directory",
                    multiline=False, default=""),
                io.String.Input("prefix",
                    display_name="Output prefix",
                    multiline=False, default="out"),
                io.Int.Input("min_cluster",
                    display_name="Min cluster size",
                    default=65, min=1, max=10000,
                    tooltip="Minimum cluster size for nucmer (--mincluster)"),
                io.String.Input("extra_args",
                    display_name="Extra nucmer arguments",
                    multiline=True, default=""),
            ],
            outputs=[
                io.String.Output("output_dir"),
                io.String.Output("delta_path"),
                io.String.Output("coords_path"),
                io.String.Output("summary_text"),
            ],
        )

    @classmethod
    def execute(
        cls, reference_fa, query_fa, output_dir, prefix, min_cluster, extra_args,
    ) -> io.NodeOutput:
        out_dir = Path(output_dir) if output_dir else Path(tempfile.mkdtemp())
        out_dir.mkdir(parents=True, exist_ok=True)

        out_prefix = str(out_dir / prefix)
        delta_path = out_prefix + ".delta"
        coords_path = out_prefix + ".coords"

        # Run nucmer
        nucmer_cmd = [
            "nucmer",
            "--prefix", out_prefix,
            "--mincluster", str(min_cluster),
            reference_fa, query_fa,
        ]
        if extra_args.strip():
            nucmer_cmd += shlex.split(extra_args)

        result = subprocess.run(nucmer_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            err = result.stderr[:500]
            return io.NodeOutput(str(out_dir), delta_path, coords_path,
                                 f"ERROR (nucmer):\n{err}")

        # Generate coords report
        with open(coords_path, "w") as fh:
            coords_result = subprocess.run(
                ["show-coords", "-rcl", delta_path],
                stdout=fh, capture_output=False,
            )

        summary = _mummer_summary(coords_path)
        return io.NodeOutput(str(out_dir), delta_path, coords_path, summary)


class Minimap2_asm(_Base):
    """Pairwise assembly-to-assembly alignment with minimap2.

    Uses assembly presets (asm5/asm10/asm20) optimised for comparing
    assemblies with different divergence levels. Outputs both PAF and SAM.

    Example extra_args:
        --secondary=no --eqx
    """

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Minimap2_asm",
            display_name="minimap2 asm align",
            category="GenomeAssembly/Comparative",
            inputs=[
                io.String.Input("reference_fa",
                    display_name="Reference FASTA",
                    multiline=False, default=""),
                io.String.Input("query_fa",
                    display_name="Query FASTA",
                    multiline=False, default=""),
                io.String.Input("output_dir",
                    display_name="Output directory",
                    multiline=False, default=""),
                io.Combo.Input("preset",
                    display_name="Assembly preset",
                    options=["asm5", "asm10", "asm20"],
                    default="asm5",
                    tooltip="asm5=<5% divergence, asm10=<10%, asm20=<20%"),
                io.Int.Input("threads",
                    display_name="Threads",
                    default=4, min=1, max=64),
                io.String.Input("extra_args",
                    display_name="Extra minimap2 arguments",
                    multiline=True, default=""),
            ],
            outputs=[
                io.String.Output("output_dir"),
                io.String.Output("paf_path"),
                io.String.Output("sam_path"),
                io.String.Output("summary_text"),
            ],
        )

    @classmethod
    def execute(
        cls, reference_fa, query_fa, output_dir, preset, threads, extra_args,
    ) -> io.NodeOutput:
        out_dir = Path(output_dir) if output_dir else Path(tempfile.mkdtemp())
        out_dir.mkdir(parents=True, exist_ok=True)

        paf_path = str(out_dir / "alignment.paf")
        sam_path = str(out_dir / "alignment.sam")

        # PAF output
        paf_cmd = [
            "minimap2",
            "-x", preset,
            "--cs",
            "-t", str(threads),
            reference_fa, query_fa,
        ]
        if extra_args.strip():
            paf_cmd += shlex.split(extra_args)

        with open(paf_path, "w") as fh:
            paf_result = subprocess.run(paf_cmd, stdout=fh, stderr=subprocess.PIPE, text=True)

        if paf_result.returncode != 0:
            return io.NodeOutput(str(out_dir), paf_path, sam_path,
                                 f"ERROR (PAF):\n{paf_result.stderr[:400]}")

        # SAM output
        sam_cmd = [
            "minimap2",
            "-x", preset,
            "--cs", "-a",
            "-t", str(threads),
            reference_fa, query_fa,
        ]
        if extra_args.strip():
            sam_cmd += shlex.split(extra_args)

        with open(sam_path, "w") as fh:
            sam_result = subprocess.run(sam_cmd, stdout=fh, stderr=subprocess.PIPE, text=True)

        summary = _minimap2_summary(paf_path, preset)
        return io.NodeOutput(str(out_dir), paf_path, sam_path, summary)


# ── Summary helpers ──────────────────────────────────────────────────────────

def _mummer_summary(coords_path: str) -> str:
    p = Path(coords_path)
    lines = ["=== MUMmer (nucmer) Alignment Summary ==="]
    if not p.exists():
        lines.append("Coords file not found.")
        return "\n".join(lines)
    data_lines = [l for l in p.read_text().splitlines() if l.strip() and not l.startswith("=") and not l.startswith("[")]
    lines.append(f"Alignment blocks : {len(data_lines):,}")
    return "\n".join(lines)


def _minimap2_summary(paf_path: str, preset: str) -> str:
    p = Path(paf_path)
    lines = ["=== minimap2 Assembly Alignment ===", f"Preset : {preset}"]
    if not p.exists():
        lines.append("PAF file not found.")
        return "\n".join(lines)
    records = [l for l in p.read_text().splitlines() if l.strip()]
    mapped = len(records)
    total_aligned = sum(
        int(r.split("\t")[9]) for r in records
        if len(r.split("\t")) > 9
    )
    lines += [
        f"Alignment records : {mapped:,}",
        f"Total aligned bp  : {total_aligned:,}",
    ]
    return "\n".join(lines)
