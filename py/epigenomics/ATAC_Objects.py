from __future__ import annotations

import shlex
import subprocess
import tempfile
from pathlib import Path
# pyrefly: ignore [missing-import]
from comfy_api.latest import io


class _Base(io.ComfyNode):
    OUTPUT_NODE = True


class ATAC_trim(_Base):
    """ATAC-seq adapter trimming with fastp.

    Uses ATAC-seq optimized fastp settings: short minimum length (20 bp),
    paired-end adapter auto-detection enabled. Removes Nextera/Tn5 adapters.

    Example extra_args:
        --cut_front --cut_tail --trim_poly_x
    """

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="ATAC_trim",
            display_name="ATAC fastp trim",
            category="Epigenomics/ATACseq",
            inputs=[
                io.String.Input("r1_path",
                    display_name="R1 FASTQ",
                    multiline=False, default="",
                    tooltip="Read 1 FASTQ path (.fastq / .fastq.gz)"),
                io.String.Input("r2_path",
                    display_name="R2 FASTQ (paired-end, optional)",
                    multiline=False, default="",
                    tooltip="Read 2 path. Leave empty for single-end."),
                io.String.Input("output_dir",
                    display_name="Output directory",
                    multiline=False, default=""),
                io.Int.Input("threads",
                    display_name="Threads",
                    default=4, min=1, max=32),
                io.String.Input("extra_args",
                    display_name="Extra fastp arguments",
                    multiline=True, default="",
                    tooltip="Additional fastp flags"),
            ],
            outputs=[
                io.String.Output("output_dir"),
                io.String.Output("r1_trimmed"),
                io.String.Output("r2_trimmed"),
                io.String.Output("summary_text"),
            ],
        )

    @classmethod
    def execute(
        cls, r1_path, r2_path, output_dir, threads, extra_args,
    ) -> io.NodeOutput:
        import json

        out_dir = Path(output_dir) if output_dir else Path(tempfile.mkdtemp())
        out_dir.mkdir(parents=True, exist_ok=True)

        paired = bool(r2_path and r2_path.strip())
        r1_out = str(out_dir / "R1_trimmed.fastq.gz")
        r2_out = str(out_dir / "R2_trimmed.fastq.gz") if paired else ""
        json_out = str(out_dir / "fastp.json")
        html_out = str(out_dir / "fastp.html")

        cmd = [
            "fastp",
            "--in1", r1_path,
            "--out1", r1_out,
            "--json", json_out,
            "--html", html_out,
            "--thread", str(threads),
            "--length_required", "20",
        ]
        if paired:
            cmd += ["--in2", r2_path, "--out2", r2_out, "--detect_adapter_for_pe"]
        if extra_args.strip():
            cmd += shlex.split(extra_args)

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return io.NodeOutput(str(out_dir), r1_out, r2_out, f"ERROR:\n{result.stderr[:500]}")

        try:
            stats = json.loads(Path(json_out).read_text())
            summary = _atac_trim_summary(stats, paired)
        except Exception as e:
            summary = f"Trimming completed. Summary parse error: {e}"

        return io.NodeOutput(str(out_dir), r1_out, r2_out, summary)


class MACS3_atac(_Base):
    """ATAC-seq peak calling with MACS3 (--nomodel mode).

    Uses shift-and-extend model optimized for Tn5 insertion sites.
    Default shift=-100, extsize=200 centers signal on Tn5 cut sites.

    Example extra_args:
        --call-summits --min-length 150 --max-gap 100
    """

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="MACS3_atac",
            display_name="MACS3 ATAC peaks",
            category="Epigenomics/ATACseq",
            inputs=[
                io.String.Input("treatment_bam",
                    display_name="ATAC BAM",
                    multiline=False, default="",
                    tooltip="Aligned and deduplicated ATAC-seq BAM"),
                io.String.Input("output_dir",
                    display_name="Output directory",
                    multiline=False, default=""),
                io.String.Input("name",
                    display_name="Sample name",
                    multiline=False, default="atac",
                    tooltip="Prefix for output files"),
                io.Combo.Input("genome_size",
                    display_name="Effective genome size",
                    options=["hs", "mm", "ce", "dm"],
                    default="hs"),
                io.Int.Input("shift",
                    display_name="Tn5 shift (bp)",
                    default=-100, min=-500, max=0,
                    tooltip="Read shift for Tn5 sites (default -100)"),
                io.Int.Input("extsize",
                    display_name="Extension size (bp)",
                    default=200, min=1, max=2000,
                    tooltip="Extension for reads after shift (default 200)"),
                io.String.Input("extra_args",
                    display_name="Extra MACS3 arguments",
                    multiline=True, default=""),
            ],
            outputs=[
                io.String.Output("output_dir"),
                io.String.Output("peaks_path"),
                io.Int.Output("n_peaks"),
                io.String.Output("summary_text"),
            ],
        )

    @classmethod
    def execute(
        cls, treatment_bam, output_dir, name, genome_size, shift, extsize, extra_args,
    ) -> io.NodeOutput:
        out_dir = Path(output_dir) if output_dir else Path(tempfile.mkdtemp())
        out_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            "macs3", "callpeak",
            "-t", treatment_bam,
            "-n", name,
            "--outdir", str(out_dir),
            "-g", genome_size,
            "--nomodel",
            "--shift", str(shift),
            "--extsize", str(extsize),
            "--nolambda",
            "--keep-dup", "all",
        ]
        if extra_args.strip():
            cmd += shlex.split(extra_args)

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return io.NodeOutput(str(out_dir), "", 0, f"ERROR:\n{result.stderr[:500]}")

        peaks_path = str(out_dir / f"{name}_peaks.narrowPeak")
        n_peaks = 0
        p = Path(peaks_path)
        if p.exists():
            n_peaks = sum(1 for line in p.read_text().splitlines() if line.strip())

        summary = "\n".join([
            "=== MACS3 ATAC-seq Peak Summary ===",
            f"Sample        : {name}",
            f"Genome size   : {genome_size}",
            f"Tn5 shift     : {shift} bp",
            f"Extension     : {extsize} bp",
            f"Peaks called  : {n_peaks:,}",
        ])
        return io.NodeOutput(str(out_dir), peaks_path, n_peaks, summary)


class Deeptools_plotfingerprint(_Base):
    """Assess ChIP/ATAC enrichment quality with deeptools plotFingerprint.

    Generates fingerprint (Lorenz curve) plots to evaluate signal enrichment.
    Input multiple BAM files (one per line) to compare IP vs. Input.

    Example extra_args:
        --minMappingQuality 20 --skipZeros
    """

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Deeptools_plotfingerprint",
            display_name="deeptools Fingerprint",
            category="Epigenomics/ATACseq",
            inputs=[
                io.String.Input("bam_paths",
                    display_name="BAM paths (one per line)",
                    multiline=True, default="",
                    tooltip="One BAM file path per line"),
                io.String.Input("output_dir",
                    display_name="Output directory",
                    multiline=False, default=""),
                io.String.Input("labels",
                    display_name="Sample labels (space-separated)",
                    multiline=False, default="",
                    tooltip="Space-separated labels matching BAM order"),
                io.Int.Input("threads",
                    display_name="Threads",
                    default=4, min=1, max=64),
                io.String.Input("extra_args",
                    display_name="Extra plotFingerprint arguments",
                    multiline=True, default=""),
            ],
            outputs=[
                io.String.Output("plot_path"),
                io.String.Output("metrics_path"),
                io.String.Output("summary_text"),
            ],
        )

    @classmethod
    def execute(
        cls, bam_paths, output_dir, labels, threads, extra_args,
    ) -> io.NodeOutput:
        out_dir = Path(output_dir) if output_dir else Path(tempfile.mkdtemp())
        out_dir.mkdir(parents=True, exist_ok=True)

        bams = [b.strip() for b in bam_paths.strip().splitlines() if b.strip()]
        if not bams:
            return io.NodeOutput("", "", "ERROR: No BAM paths provided.")

        plot_path = str(out_dir / "fingerprint.png")
        metrics_path = str(out_dir / "fingerprint_metrics.tab")

        cmd = [
            "plotFingerprint",
            "-b", *bams,
            "-p", str(threads),
            "--plotFile", plot_path,
            "--outQualityMetrics", metrics_path,
        ]
        if labels.strip():
            cmd += ["--labels"] + labels.strip().split()
        if extra_args.strip():
            cmd += shlex.split(extra_args)

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return io.NodeOutput("", "", f"ERROR:\n{result.stderr[:500]}")

        summary = "\n".join([
            "=== plotFingerprint Summary ===",
            f"BAM files     : {len(bams)}",
            f"Plot          : {Path(plot_path).name}",
            f"Metrics       : {Path(metrics_path).name}",
        ])
        return io.NodeOutput(plot_path, metrics_path, summary)


# ── helpers ─────────────────────────────────────────────────────────────────

def _atac_trim_summary(stats: dict, paired: bool) -> str:
    bf = stats.get("summary", {}).get("before_filtering", {})
    af = stats.get("summary", {}).get("after_filtering", {})
    total_in = bf.get("total_reads", 0)
    total_out = af.get("total_reads", 0)
    pass_rate = (total_out / total_in * 100) if total_in else 0
    return "\n".join([
        "=== ATAC fastp Trim Summary ===",
        f"Mode           : {'Paired-end' if paired else 'Single-end'}",
        f"Input reads    : {total_in:,}",
        f"Output reads   : {total_out:,}  ({pass_rate:.1f}% pass)",
        f"Q20 rate (out) : {af.get('q20_rate', 0)*100:.1f}%",
        f"Q30 rate (out) : {af.get('q30_rate', 0)*100:.1f}%",
        f"GC content     : {af.get('gc_content', 0)*100:.1f}%",
    ])
