from __future__ import annotations

import shlex
import subprocess
import tempfile
from pathlib import Path
# pyrefly: ignore [missing-import]
from comfy_api.latest import io


class _Base(io.ComfyNode):
    OUTPUT_NODE = True


class Medaka_polish(_Base):
    """Oxford Nanopore assembly polishing with Medaka.

    Aligns raw reads back to assembly and corrects consensus.
    Choose a model matching your basecaller version and pore chemistry.

    Example extra_args:
        --batch 100 --chunk_len 800000
    """

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Medaka_polish",
            display_name="Medaka polish",
            category="GenomeAssembly/Polish",
            inputs=[
                io.String.Input("assembly_path",
                    display_name="Draft assembly FASTA",
                    multiline=False, default=""),
                io.String.Input("reads_path",
                    display_name="Nanopore reads FASTQ",
                    multiline=False, default=""),
                io.String.Input("output_dir",
                    display_name="Output directory",
                    multiline=False, default=""),
                io.Combo.Input("model",
                    display_name="Medaka model",
                    options=[
                        "r941_min_hac_g507",
                        "r1041_e82_400bps_hac_v4.3.0",
                        "r941_min_sup_g507",
                    ],
                    default="r941_min_hac_g507",
                    tooltip="Select model matching your basecaller and pore chemistry"),
                io.Int.Input("threads",
                    display_name="Threads",
                    default=4, min=1, max=64),
                io.String.Input("extra_args",
                    display_name="Extra Medaka arguments",
                    multiline=True, default=""),
            ],
            outputs=[
                io.String.Output("output_dir"),
                io.String.Output("consensus_path"),
                io.String.Output("summary_text"),
            ],
        )

    @classmethod
    def execute(
        cls, assembly_path, reads_path, output_dir, model, threads, extra_args,
    ) -> io.NodeOutput:
        out_dir = Path(output_dir) if output_dir else Path(tempfile.mkdtemp())
        out_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            "medaka_consensus",
            "-i", reads_path,
            "-d", assembly_path,
            "-o", str(out_dir),
            "-m", model,
            "-t", str(threads),
        ]
        if extra_args.strip():
            cmd += shlex.split(extra_args)

        result = subprocess.run(cmd, capture_output=True, text=True)
        consensus = str(out_dir / "consensus.fasta")

        if result.returncode != 0:
            err = result.stderr[:500]
            return io.NodeOutput(str(out_dir), consensus, f"ERROR:\n{err}")

        summary = _polish_summary(consensus, "Medaka")
        return io.NodeOutput(str(out_dir), consensus, summary)


class Pilon_polish(_Base):
    """Illumina-based assembly polishing with Pilon.

    Aligns short reads to the draft assembly with BWA-MEM2, then runs Pilon
    to correct SNPs, indels, gaps, and local misassemblies.

    Example extra_args (Pilon):
        --mindepth 10 --minmq 20
    """

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Pilon_polish",
            display_name="Pilon polish",
            category="GenomeAssembly/Polish",
            inputs=[
                io.String.Input("assembly_path",
                    display_name="Draft assembly FASTA",
                    multiline=False, default=""),
                io.String.Input("r1_path",
                    display_name="R1 Illumina FASTQ",
                    multiline=False, default=""),
                io.String.Input("r2_path",
                    display_name="R2 Illumina FASTQ (optional)",
                    multiline=False, default=""),
                io.String.Input("output_dir",
                    display_name="Output directory",
                    multiline=False, default=""),
                io.Int.Input("threads",
                    display_name="Threads",
                    default=4, min=1, max=64),
                io.Combo.Input("fix",
                    display_name="Fix categories",
                    options=["all", "snps", "indels", "gaps", "local"],
                    default="all"),
                io.String.Input("extra_args",
                    display_name="Extra Pilon arguments",
                    multiline=True, default=""),
            ],
            outputs=[
                io.String.Output("output_dir"),
                io.String.Output("polished_path"),
                io.String.Output("changes_path"),
                io.String.Output("summary_text"),
            ],
        )

    @classmethod
    def execute(
        cls, assembly_path, r1_path, r2_path, output_dir, threads, fix, extra_args,
    ) -> io.NodeOutput:
        out_dir = Path(output_dir) if output_dir else Path(tempfile.mkdtemp())
        out_dir.mkdir(parents=True, exist_ok=True)

        paired = bool(r2_path and r2_path.strip())
        bam_path = str(out_dir / "aligned.bam")

        # Index assembly
        idx_result = subprocess.run(
            ["bwa-mem2", "index", assembly_path],
            capture_output=True, text=True
        )
        if idx_result.returncode != 0:
            return io.NodeOutput(str(out_dir), "", "", f"ERROR (bwa-mem2 index):\n{idx_result.stderr[:300]}")

        # Align reads
        bwa_cmd = ["bwa-mem2", "mem", "-t", str(threads), assembly_path, r1_path]
        if paired:
            bwa_cmd.append(r2_path)

        with subprocess.Popen(bwa_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as bwa_proc:
            sort_result = subprocess.run(
                ["samtools", "sort", "-@", str(threads), "-o", bam_path],
                stdin=bwa_proc.stdout,
                capture_output=True, text=True,
            )
            bwa_proc.stdout.close()
            bwa_proc.wait()

        if sort_result.returncode != 0:
            return io.NodeOutput(str(out_dir), "", "", f"ERROR (alignment):\n{sort_result.stderr[:300]}")

        subprocess.run(["samtools", "index", bam_path], capture_output=True)

        # Run Pilon
        out_prefix = str(out_dir / "pilon")
        pilon_cmd = [
            "pilon",
            "--genome", assembly_path,
            "--frags", bam_path,
            "--output", out_prefix,
            "--outdir", str(out_dir),
            "--fix", fix,
            "--changes",
            "--threads", str(threads),
        ]
        if extra_args.strip():
            pilon_cmd += shlex.split(extra_args)

        result = subprocess.run(pilon_cmd, capture_output=True, text=True)
        polished = out_prefix + ".fasta"
        changes = out_prefix + ".changes"

        if result.returncode != 0:
            err = result.stderr[:500]
            return io.NodeOutput(str(out_dir), polished, changes, f"ERROR (pilon):\n{err}")

        summary = _polish_summary(polished, "Pilon")
        changes_path = Path(changes)
        if changes_path.exists():
            n_changes = len(changes_path.read_text().splitlines())
            summary += f"\nChanges applied : {n_changes:,}"

        return io.NodeOutput(str(out_dir), polished, changes, summary)


# ── Summary helper ───────────────────────────────────────────────────────────

def _polish_summary(fasta_path: str, tool: str) -> str:
    p = Path(fasta_path)
    lines = [f"=== {tool} Polishing Summary ==="]
    if not p.exists():
        lines.append("Consensus FASTA not found.")
        return "\n".join(lines)
    lengths = []
    cur_len = 0
    for line in p.read_text().splitlines():
        if line.startswith(">"):
            if cur_len:
                lengths.append(cur_len)
            cur_len = 0
        else:
            cur_len += len(line.strip())
    if cur_len:
        lengths.append(cur_len)
    if lengths:
        total = sum(lengths)
        lines += [
            f"Sequences    : {len(lengths):,}",
            f"Total length : {total:,} bp",
        ]
    return "\n".join(lines)
