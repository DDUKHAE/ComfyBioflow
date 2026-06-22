from __future__ import annotations

import shlex
import subprocess
import tempfile
from pathlib import Path
# pyrefly: ignore [missing-import]
from comfy_api.latest import io


class _Base(io.ComfyNode):
    OUTPUT_NODE = True


class Bowtie2_chip(_Base):
    """ChIP-seq read alignment with Bowtie2.

    Aligns ChIP-seq reads to a reference genome, then sorts, optionally
    marks duplicates, and indexes the BAM. Requires a Bowtie2 index
    (bowtie2-build genome.fa index_prefix).

    Example extra_args:
        --no-mixed --no-discordant --dovetail
    """

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Bowtie2_chip",
            display_name="Bowtie2 ChIP align",
            category="Epigenomics/ChIPseq",
            inputs=[
                io.String.Input("r1_path",
                    display_name="R1 FASTQ",
                    multiline=False, default="",
                    tooltip="Read 1 FASTQ path (.fastq / .fastq.gz)"),
                io.String.Input("r2_path",
                    display_name="R2 FASTQ (paired-end, optional)",
                    multiline=False, default="",
                    tooltip="Read 2 path. Leave empty for single-end."),
                io.String.Input("index_prefix",
                    display_name="Bowtie2 index prefix",
                    multiline=False, default="",
                    tooltip="Prefix for Bowtie2 index (e.g. /path/to/genome)"),
                io.String.Input("output_dir",
                    display_name="Output directory",
                    multiline=False, default=""),
                io.Int.Input("threads",
                    display_name="Threads",
                    default=4, min=1, max=64),
                io.Combo.Input("preset",
                    display_name="Alignment preset",
                    options=["sensitive", "very-sensitive", "sensitive-local", "very-sensitive-local"],
                    default="sensitive"),
                io.Int.Input("max_fragment_size",
                    display_name="Max fragment size",
                    default=2000, min=0, max=10000,
                    tooltip="Maximum fragment size for paired-end alignment (-X)"),
                io.Boolean.Input("remove_duplicates",
                    display_name="Mark duplicates",
                    default=True,
                    tooltip="Mark PCR duplicates with samtools markdup"),
                io.String.Input("extra_args",
                    display_name="Extra Bowtie2 arguments",
                    multiline=True, default="",
                    tooltip="Additional Bowtie2 flags, e.g. --no-mixed --dovetail"),
            ],
            outputs=[
                io.String.Output("output_dir"),
                io.String.Output("bam_path"),
                io.String.Output("summary_text"),
            ],
        )

    @classmethod
    def execute(
        cls, r1_path, r2_path, index_prefix, output_dir, threads,
        preset, max_fragment_size, remove_duplicates, extra_args,
    ) -> io.NodeOutput:
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

        result = subprocess.run(cmd, capture_output=True, text=True)
        alignment_summary = result.stderr[:1000] if result.stderr else ""
        if result.returncode != 0:
            return io.NodeOutput(str(out_dir), "", f"ERROR bowtie2:\n{result.stderr[:500]}")

        # sam → sorted bam
        r2 = subprocess.run(
            ["samtools", "view", "-bS", "-o", bam_unsorted, sam_path],
            capture_output=True, text=True,
        )
        if r2.returncode != 0:
            return io.NodeOutput(str(out_dir), "", f"ERROR samtools view:\n{r2.stderr[:500]}")

        r3 = subprocess.run(
            ["samtools", "sort", "-o", bam_sorted, "-@", str(threads), bam_unsorted],
            capture_output=True, text=True,
        )
        if r3.returncode != 0:
            return io.NodeOutput(str(out_dir), "", f"ERROR samtools sort:\n{r3.stderr[:500]}")

        if remove_duplicates:
            tmp_bam = str(out_dir / "markdup_tmp.bam")
            r4 = subprocess.run(
                ["samtools", "markdup", bam_sorted, bam_final],
                capture_output=True, text=True,
            )
            if r4.returncode != 0:
                return io.NodeOutput(str(out_dir), "", f"ERROR samtools markdup:\n{r4.stderr[:500]}")
        else:
            import shutil
            shutil.copy(bam_sorted, bam_final)

        subprocess.run(["samtools", "index", bam_final], capture_output=True)

        flagstat = subprocess.run(
            ["samtools", "flagstat", bam_final],
            capture_output=True, text=True,
        )
        summary = _bowtie2_summary(alignment_summary, flagstat.stdout)
        return io.NodeOutput(str(out_dir), bam_final, summary)


class MACS3_callpeak(_Base):
    """ChIP-seq peak calling with MACS3.

    Calls peaks from ChIP-seq BAM files. Optionally accepts a control/input
    BAM for background correction.

    Example extra_args:
        --nomodel --extsize 200 --shift -100
        --call-summits --min-length 200
    """

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="MACS3_callpeak",
            display_name="MACS3 callpeak",
            category="Epigenomics/ChIPseq",
            inputs=[
                io.String.Input("treatment_bam",
                    display_name="Treatment BAM",
                    multiline=False, default="",
                    tooltip="ChIP BAM file path"),
                io.String.Input("control_bam",
                    display_name="Control/Input BAM (optional)",
                    multiline=False, default="",
                    tooltip="Input or IgG control BAM. Leave empty for no control."),
                io.String.Input("output_dir",
                    display_name="Output directory",
                    multiline=False, default=""),
                io.String.Input("name",
                    display_name="Sample name",
                    multiline=False, default="sample",
                    tooltip="Prefix for output files"),
                io.Combo.Input("genome_size",
                    display_name="Effective genome size",
                    options=["hs", "mm", "ce", "dm"],
                    default="hs",
                    tooltip="hs=human, mm=mouse, ce=C.elegans, dm=Drosophila"),
                io.Float.Input("q_value",
                    display_name="q-value cutoff",
                    default=0.05, min=0.0, max=1.0,
                    tooltip="Minimum FDR cutoff for peak calling"),
                io.Combo.Input("keep_dup",
                    display_name="Keep duplicates",
                    options=["auto", "all", "1"],
                    default="auto",
                    tooltip="auto=auto-remove, all=keep all, 1=keep one"),
                io.Boolean.Input("broad",
                    display_name="Broad peak mode",
                    default=False,
                    tooltip="Call broad peaks (H3K27me3, H3K9me3, etc.)"),
                io.String.Input("extra_args",
                    display_name="Extra MACS3 arguments",
                    multiline=True, default="",
                    tooltip="Additional MACS3 flags"),
            ],
            outputs=[
                io.String.Output("output_dir"),
                io.String.Output("peaks_path",
                    tooltip="narrowPeak or broadPeak file"),
                io.String.Output("summit_path",
                    tooltip="Summit BED file (narrow peaks only)"),
                io.Int.Output("n_peaks",
                    tooltip="Number of called peaks"),
                io.String.Output("summary_text"),
            ],
        )

    @classmethod
    def execute(
        cls, treatment_bam, control_bam, output_dir, name, genome_size,
        q_value, keep_dup, broad, extra_args,
    ) -> io.NodeOutput:
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

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return io.NodeOutput(str(out_dir), "", "", 0, f"ERROR:\n{result.stderr[:500]}")

        ext = "broadPeak" if broad else "narrowPeak"
        peaks_path = str(out_dir / f"{name}_peaks.{ext}")
        summit_path = str(out_dir / f"{name}_summits.bed") if not broad else ""

        n_peaks = 0
        p = Path(peaks_path)
        if p.exists():
            n_peaks = sum(1 for line in p.read_text().splitlines() if not line.startswith("#") and line.strip())

        summary = "\n".join([
            "=== MACS3 Peak Calling Summary ===",
            f"Sample name   : {name}",
            f"Genome size   : {genome_size}",
            f"Mode          : {'Broad' if broad else 'Narrow'} peaks",
            f"q-value cutoff: {q_value}",
            f"Peaks called  : {n_peaks:,}",
        ])
        return io.NodeOutput(str(out_dir), peaks_path, summit_path, n_peaks, summary)


class Deeptools_bamcoverage(_Base):
    """Generate BigWig signal track from BAM with deeptools bamCoverage.

    Normalizes coverage and outputs a BigWig file for visualization
    in genome browsers (IGV, UCSC).

    Example extra_args:
        --blackListFileName blacklist.bed --minMappingQuality 20
    """

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Deeptools_bamcoverage",
            display_name="deeptools bamCoverage",
            category="Epigenomics/ChIPseq",
            inputs=[
                io.String.Input("bam_path",
                    display_name="BAM file",
                    multiline=False, default=""),
                io.String.Input("output_dir",
                    display_name="Output directory",
                    multiline=False, default=""),
                io.Int.Input("bin_size",
                    display_name="Bin size (bp)",
                    default=10, min=1, max=10000,
                    tooltip="Resolution of the BigWig in base pairs"),
                io.Combo.Input("normalize_using",
                    display_name="Normalization method",
                    options=["RPKM", "CPM", "BPM", "RPGC", "None"],
                    default="RPKM"),
                io.Boolean.Input("ignore_duplicates",
                    display_name="Ignore duplicates",
                    default=True),
                io.Int.Input("effective_genome_size",
                    display_name="Effective genome size",
                    default=2700000000, min=1000000,
                    tooltip="Required for RPGC normalization (human GRCh38: 2913022398)"),
                io.Int.Input("threads",
                    display_name="Threads",
                    default=4, min=1, max=64),
                io.String.Input("extra_args",
                    display_name="Extra bamCoverage arguments",
                    multiline=True, default=""),
            ],
            outputs=[
                io.String.Output("bigwig_path"),
                io.String.Output("summary_text"),
            ],
        )

    @classmethod
    def execute(
        cls, bam_path, output_dir, bin_size, normalize_using,
        ignore_duplicates, effective_genome_size, threads, extra_args,
    ) -> io.NodeOutput:
        out_dir = Path(output_dir) if output_dir else Path(tempfile.mkdtemp())
        out_dir.mkdir(parents=True, exist_ok=True)

        bam_stem = Path(bam_path).stem
        bw_path = str(out_dir / f"{bam_stem}.bw")

        cmd = [
            "bamCoverage",
            "-b", bam_path,
            "-o", bw_path,
            "--binSize", str(bin_size),
            "--numberOfProcessors", str(threads),
        ]
        if normalize_using != "None":
            cmd += ["--normalizeUsing", normalize_using]
        if normalize_using == "RPGC":
            cmd += ["--effectiveGenomeSize", str(effective_genome_size)]
        if ignore_duplicates:
            cmd.append("--ignoreDuplicates")
        if extra_args.strip():
            cmd += shlex.split(extra_args)

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return io.NodeOutput("", f"ERROR:\n{result.stderr[:500]}")

        summary = "\n".join([
            "=== bamCoverage Summary ===",
            f"Input BAM     : {Path(bam_path).name}",
            f"Output BigWig : {Path(bw_path).name}",
            f"Bin size      : {bin_size} bp",
            f"Normalization : {normalize_using}",
        ])
        return io.NodeOutput(bw_path, summary)


# ── helpers ─────────────────────────────────────────────────────────────────

def _bowtie2_summary(bowtie2_stderr: str, flagstat_stdout: str) -> str:
    lines = ["=== Bowtie2 ChIP-seq Alignment Summary ==="]
    for line in bowtie2_stderr.splitlines():
        line = line.strip()
        if any(k in line for k in ["overall alignment", "aligned concordantly", "aligned discordantly", "aligned exactly", "0 times"]):
            lines.append("  " + line)
    if flagstat_stdout:
        lines.append("")
        lines.append("samtools flagstat:")
        for fl in flagstat_stdout.splitlines()[:6]:
            lines.append("  " + fl.strip())
    return "\n".join(lines)
