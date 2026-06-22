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


class SPAdes_assemble(_Base):
    """De novo genome assembly with SPAdes.

    Supports short-read (Illumina), metagenomic, RNA, plasmid, and hybrid assembly.
    Requires paired-end reads for best results; single-end supported.

    Example extra_args:
        --cov-cutoff auto --phred-offset 33
        --pacbio /path/to/pacbio.fastq  (for hybrid)
    """

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="SPAdes_assemble",
            display_name="SPAdes assemble",
            category="GenomeAssembly/Assembly",
            inputs=[
                io.String.Input("r1_path",
                    display_name="R1 FASTQ",
                    multiline=False, default="",
                    tooltip="Read 1 FASTQ path (.fastq / .fastq.gz)"),
                io.String.Input("r2_path",
                    display_name="R2 FASTQ (paired-end, optional)",
                    multiline=False, default="",
                    tooltip="Read 2 FASTQ path. Leave empty for single-end."),
                io.String.Input("output_dir",
                    display_name="Output directory",
                    multiline=False, default=""),
                io.Int.Input("threads",
                    display_name="Threads",
                    default=8, min=1, max=128),
                io.Int.Input("memory_gb",
                    display_name="Memory limit (GB)",
                    default=16, min=1, max=512,
                    tooltip="Memory limit in GB"),
                io.Combo.Input("mode",
                    display_name="Assembly mode",
                    options=["default", "meta", "rna", "plasmid", "corona"],
                    default="default"),
                io.Boolean.Input("careful",
                    display_name="Careful mode (reduce mismatches)",
                    default=True,
                    tooltip="--careful: reduce mismatches (slow, not for meta/rna)"),
                io.String.Input("extra_args",
                    display_name="Extra SPAdes arguments",
                    multiline=True, default="",
                    tooltip="Additional SPAdes flags, e.g. --cov-cutoff auto"),
            ],
            outputs=[
                io.String.Output("output_dir"),
                io.String.Output("contigs_path"),
                io.String.Output("scaffolds_path"),
                io.String.Output("assembly_graph_path"),
                io.String.Output("summary_text"),
            ],
        )

    @classmethod
    def execute(
        cls, r1_path, r2_path, output_dir, threads, memory_gb,
        mode, careful, extra_args,
    ) -> io.NodeOutput:
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
        graph = str(out_dir / "assembly_graph.fastg")

        if result.returncode != 0:
            err = result.stderr[:500]
            return io.NodeOutput(str(out_dir), contigs, scaffolds, graph,
                                 f"ERROR:\n{err}")

        summary = _spades_summary(out_dir, contigs)
        return io.NodeOutput(str(out_dir), contigs, scaffolds, graph, summary)


class Flye_assemble(_Base):
    """De novo long-read assembly with Flye.

    Supports Oxford Nanopore and PacBio reads.
    Requires an estimated genome size for heuristics.

    Example extra_args:
        --iterations 3 --min-overlap 3000
    """

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Flye_assemble",
            display_name="Flye assemble",
            category="GenomeAssembly/Assembly",
            inputs=[
                io.String.Input("reads_path",
                    display_name="Reads FASTQ/FASTA",
                    multiline=False, default="",
                    tooltip="Long-read input file"),
                io.String.Input("output_dir",
                    display_name="Output directory",
                    multiline=False, default=""),
                io.Combo.Input("read_type",
                    display_name="Read type",
                    options=["nano-raw", "nano-hq", "nano-corr",
                             "pacbio-raw", "pacbio-hifi", "pacbio-corr",
                             "subassemblies"],
                    default="nano-hq"),
                io.String.Input("genome_size",
                    display_name="Estimated genome size",
                    multiline=False, default="5m",
                    tooltip="e.g. 5m, 500k, 1g"),
                io.Int.Input("threads",
                    display_name="Threads",
                    default=8, min=1, max=128),
                io.String.Input("extra_args",
                    display_name="Extra Flye arguments",
                    multiline=True, default=""),
            ],
            outputs=[
                io.String.Output("output_dir"),
                io.String.Output("assembly_path"),
                io.String.Output("assembly_info_path"),
                io.String.Output("summary_text"),
            ],
        )

    @classmethod
    def execute(
        cls, reads_path, output_dir, read_type, genome_size, threads, extra_args,
    ) -> io.NodeOutput:
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
            err = result.stderr[:500]
            return io.NodeOutput(str(out_dir), assembly, info, f"ERROR:\n{err}")

        summary = _flye_summary(info)
        return io.NodeOutput(str(out_dir), assembly, info, summary)


class Hifiasm_assemble(_Base):
    """De novo assembly with Hifiasm (optimized for PacBio HiFi).

    Outputs GFA format; this node auto-converts primary assembly to FASTA.

    Example extra_args:
        --h1 hic_R1.fastq --h2 hic_R2.fastq  (Hi-C phasing)
        -l 0  (disable purge)
    """

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Hifiasm_assemble",
            display_name="Hifiasm assemble",
            category="GenomeAssembly/Assembly",
            inputs=[
                io.String.Input("reads_path",
                    display_name="HiFi reads FASTQ",
                    multiline=False, default=""),
                io.String.Input("output_dir",
                    display_name="Output directory",
                    multiline=False, default=""),
                io.Int.Input("threads",
                    display_name="Threads",
                    default=8, min=1, max=128),
                io.Int.Input("min_coverage",
                    display_name="Min coverage for unitig",
                    default=4, min=1, max=100),
                io.String.Input("extra_args",
                    display_name="Extra Hifiasm arguments",
                    multiline=True, default=""),
            ],
            outputs=[
                io.String.Output("output_dir"),
                io.String.Output("primary_asm_path"),
                io.String.Output("summary_text"),
            ],
        )

    @classmethod
    def execute(
        cls, reads_path, output_dir, threads, min_coverage, extra_args,
    ) -> io.NodeOutput:
        out_dir = Path(output_dir) if output_dir else Path(tempfile.mkdtemp())
        out_dir.mkdir(parents=True, exist_ok=True)

        prefix = str(out_dir / "asm")
        cmd = [
            "hifiasm",
            "-o", prefix,
            "-t", str(threads),
            f"--min-hist-cnt", str(min_coverage),
            reads_path,
        ]
        if extra_args.strip():
            cmd += shlex.split(extra_args)

        result = subprocess.run(cmd, capture_output=True, text=True)

        primary_gfa = prefix + ".bp.p_ctg.gfa"
        primary_fa = prefix + ".bp.p_ctg.fa"

        if result.returncode != 0:
            err = result.stderr[:500]
            return io.NodeOutput(str(out_dir), primary_fa, f"ERROR:\n{err}")

        # Convert GFA to FASTA
        gfa_path = Path(primary_gfa)
        if gfa_path.exists():
            awk_cmd = ["awk", "/^S/{print \">\"$2\"\\n\"$3}", primary_gfa]
            with open(primary_fa, "w") as fh:
                subprocess.run(awk_cmd, stdout=fh, check=False)

        summary = _fasta_summary(primary_fa, "Hifiasm primary assembly")
        return io.NodeOutput(str(out_dir), primary_fa, summary)


# ── Summary helpers ──────────────────────────────────────────────────────────

def _spades_summary(out_dir: Path, contigs_path: str) -> str:
    lines = ["=== SPAdes Assembly Summary ==="]
    log_path = out_dir / "spades.log"
    if log_path.exists():
        log_text = log_path.read_text()
        for kw in ["Finished!", "Total length", "N50", "Number of contigs"]:
            for line in log_text.splitlines():
                if kw in line:
                    lines.append("  " + line.strip())
                    break
    # Also scan contigs.fasta directly
    p = Path(contigs_path)
    if p.exists():
        stats = _fasta_stats(p)
        lines += [
            f"Contigs         : {stats['n_contigs']:,}",
            f"Total length    : {stats['total_len']:,} bp",
            f"N50             : {stats['n50']:,} bp",
            f"Longest contig  : {stats['max_len']:,} bp",
        ]
    return "\n".join(lines)


def _flye_summary(info_path: str) -> str:
    p = Path(info_path)
    lines = ["=== Flye Assembly Summary ==="]
    if not p.exists():
        lines.append("assembly_info.txt not found.")
        return "\n".join(lines)
    rows = [l.split("\t") for l in p.read_text().splitlines() if not l.startswith("#") and l.strip()]
    if rows:
        lengths = []
        for row in rows:
            try:
                lengths.append(int(row[1]))
            except (IndexError, ValueError):
                pass
        if lengths:
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
            lines += [
                f"Contigs/scaffolds : {len(lengths):,}",
                f"Total length      : {total:,} bp",
                f"N50               : {n50:,} bp",
                f"Longest           : {lengths[0]:,} bp",
            ]
    return "\n".join(lines)


def _fasta_summary(fasta_path: str, label: str) -> str:
    p = Path(fasta_path)
    lines = [f"=== {label} ==="]
    if not p.exists():
        lines.append("Output FASTA not found.")
        return "\n".join(lines)
    stats = _fasta_stats(p)
    lines += [
        f"Sequences    : {stats['n_contigs']:,}",
        f"Total length : {stats['total_len']:,} bp",
        f"N50          : {stats['n50']:,} bp",
        f"Longest      : {stats['max_len']:,} bp",
    ]
    return "\n".join(lines)


def _fasta_stats(path: Path) -> dict:
    lengths = []
    cur_len = 0
    for line in path.read_text().splitlines():
        if line.startswith(">"):
            if cur_len:
                lengths.append(cur_len)
            cur_len = 0
        else:
            cur_len += len(line.strip())
    if cur_len:
        lengths.append(cur_len)
    if not lengths:
        return {"n_contigs": 0, "total_len": 0, "n50": 0, "max_len": 0}
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
    return {
        "n_contigs": len(lengths),
        "total_len": total,
        "n50": n50,
        "max_len": lengths[0],
    }
