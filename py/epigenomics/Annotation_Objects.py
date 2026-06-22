from __future__ import annotations

import shlex
import subprocess
import tempfile
from pathlib import Path
# pyrefly: ignore [missing-import]
from comfy_api.latest import io


class _Base(io.ComfyNode):
    OUTPUT_NODE = True


class Deeptools_heatmap(_Base):
    """Generate heatmap/profile plots with deeptools computeMatrix + plotHeatmap.

    Computes signal matrix over regions of interest, then plots a heatmap.
    Commonly used to visualize ChIP/ATAC signal at peaks, TSSs, or gene bodies.

    Example extra_args (computeMatrix):
        --skipZeros --missingDataAsZero --averageTypeBins mean
    """

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Deeptools_heatmap",
            display_name="deeptools heatmap",
            category="Epigenomics/Annotation",
            inputs=[
                io.String.Input("bigwig_paths",
                    display_name="BigWig paths (one per line)",
                    multiline=True, default="",
                    tooltip="One BigWig file path per line"),
                io.String.Input("bed_path",
                    display_name="Regions BED file",
                    multiline=False, default="",
                    tooltip="BED file with regions (peaks, TSS, gene bodies)"),
                io.String.Input("output_dir",
                    display_name="Output directory",
                    multiline=False, default=""),
                io.Combo.Input("reference_point",
                    display_name="Reference point",
                    options=["center", "TES", "TSS"],
                    default="center"),
                io.Int.Input("before_region",
                    display_name="Upstream window (bp)",
                    default=3000, min=0, max=100000),
                io.Int.Input("after_region",
                    display_name="Downstream window (bp)",
                    default=3000, min=0, max=100000),
                io.Int.Input("threads",
                    display_name="Threads",
                    default=4, min=1, max=64),
                io.String.Input("extra_args",
                    display_name="Extra computeMatrix arguments",
                    multiline=True, default=""),
            ],
            outputs=[
                io.String.Output("heatmap_path"),
                io.String.Output("matrix_path"),
                io.String.Output("summary_text"),
            ],
        )

    @classmethod
    def execute(
        cls, bigwig_paths, bed_path, output_dir, reference_point,
        before_region, after_region, threads, extra_args,
    ) -> io.NodeOutput:
        out_dir = Path(output_dir) if output_dir else Path(tempfile.mkdtemp())
        out_dir.mkdir(parents=True, exist_ok=True)

        bws = [b.strip() for b in bigwig_paths.strip().splitlines() if b.strip()]
        if not bws:
            return io.NodeOutput("", "", "ERROR: No BigWig paths provided.")

        matrix_path = str(out_dir / "matrix.gz")
        heatmap_path = str(out_dir / "heatmap.png")

        # Step 1: computeMatrix
        matrix_cmd = [
            "computeMatrix", "reference-point",
            "--scoreFileName", *bws,
            "--regionsFileName", bed_path,
            "--outFileName", matrix_path,
            "--referencePoint", reference_point,
            "--beforeRegionStartLength", str(before_region),
            "--afterRegionStartLength", str(after_region),
            "--numberOfProcessors", str(threads),
        ]
        if extra_args.strip():
            matrix_cmd += shlex.split(extra_args)

        r1 = subprocess.run(matrix_cmd, capture_output=True, text=True)
        if r1.returncode != 0:
            return io.NodeOutput("", "", f"ERROR computeMatrix:\n{r1.stderr[:500]}")

        # Step 2: plotHeatmap
        heatmap_cmd = [
            "plotHeatmap",
            "--matrixFile", matrix_path,
            "--outFileName", heatmap_path,
        ]
        r2 = subprocess.run(heatmap_cmd, capture_output=True, text=True)
        if r2.returncode != 0:
            return io.NodeOutput(heatmap_path, matrix_path, f"ERROR plotHeatmap:\n{r2.stderr[:500]}")

        summary = "\n".join([
            "=== deeptools Heatmap Summary ===",
            f"BigWig tracks : {len(bws)}",
            f"Regions BED   : {Path(bed_path).name}",
            f"Reference pt  : {reference_point}",
            f"Window        : -{before_region/1000:.1f}kb / +{after_region/1000:.1f}kb",
            f"Heatmap       : {Path(heatmap_path).name}",
        ])
        return io.NodeOutput(heatmap_path, matrix_path, summary)


class ChIPQC_summary(_Base):
    """ChIP-seq quality control summary using samtools flagstat and FRiP.

    Calculates FRiP (Fraction of Reads in Peaks) score, a key ChIP-seq
    QC metric. Requires BAM (with index) and optionally a peaks BED file.

    FRiP > 0.01 is the ENCODE minimum; > 0.05 is preferred.
    """

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="ChIPQC_summary",
            display_name="ChIP-seq QC summary",
            category="Epigenomics/Annotation",
            inputs=[
                io.String.Input("bam_path",
                    display_name="BAM file",
                    multiline=False, default=""),
                io.String.Input("peaks_path",
                    display_name="Peaks BED/narrowPeak (optional)",
                    multiline=False, default="",
                    tooltip="Peak file for FRiP score calculation"),
                io.String.Input("output_dir",
                    display_name="Output directory",
                    multiline=False, default=""),
                io.Combo.Input("genome",
                    display_name="Reference genome",
                    options=["hg38", "hg19", "mm10", "mm39"],
                    default="hg38"),
                io.String.Input("extra_args",
                    display_name="Extra samtools arguments",
                    multiline=True, default=""),
            ],
            outputs=[
                io.String.Output("output_dir"),
                io.String.Output("report_path"),
                io.String.Output("summary_text"),
            ],
        )

    @classmethod
    def execute(
        cls, bam_path, peaks_path, output_dir, genome, extra_args,
    ) -> io.NodeOutput:
        out_dir = Path(output_dir) if output_dir else Path(tempfile.mkdtemp())
        out_dir.mkdir(parents=True, exist_ok=True)

        report_path = str(out_dir / "chipqc_report.txt")

        # flagstat
        flagstat = subprocess.run(
            ["samtools", "flagstat", bam_path],
            capture_output=True, text=True,
        )
        if flagstat.returncode != 0:
            return io.NodeOutput(str(out_dir), "", f"ERROR samtools flagstat:\n{flagstat.stderr[:500]}")

        flagstat_text = flagstat.stdout
        total_reads = _parse_flagstat_total(flagstat_text)

        # FRiP
        frip = None
        if peaks_path and peaks_path.strip() and Path(peaks_path).exists():
            intersect = subprocess.run(
                ["bedtools", "intersect", "-a", bam_path, "-b", peaks_path, "-u", "-f", "0.5"],
                capture_output=True, text=True,
            )
            count_in_peaks = subprocess.run(
                ["samtools", "view", "-c"],
                input=intersect.stdout,
                capture_output=True, text=True,
            )
            try:
                reads_in_peaks = int(count_in_peaks.stdout.strip())
                frip = reads_in_peaks / total_reads if total_reads else 0
            except (ValueError, ZeroDivisionError):
                frip = None

        summary = _chipqc_summary(flagstat_text, frip, genome, Path(bam_path).name)
        Path(report_path).write_text(summary)

        return io.NodeOutput(str(out_dir), report_path, summary)


# ── helpers ─────────────────────────────────────────────────────────────────

def _parse_flagstat_total(flagstat_text: str) -> int:
    for line in flagstat_text.splitlines():
        if "in total" in line:
            try:
                return int(line.split()[0])
            except (ValueError, IndexError):
                pass
    return 0


def _chipqc_summary(flagstat_text: str, frip, genome: str, bam_name: str) -> str:
    lines = [
        "=== ChIP-seq QC Summary ===",
        f"BAM file      : {bam_name}",
        f"Genome        : {genome}",
        "",
        "--- samtools flagstat ---",
    ]
    for line in flagstat_text.splitlines()[:8]:
        lines.append("  " + line.strip())

    if frip is not None:
        lines.append("")
        lines.append(f"FRiP score    : {frip:.4f}  ({frip*100:.2f}%)")
        if frip >= 0.05:
            lines.append("FRiP status   : PASS (≥5%)")
        elif frip >= 0.01:
            lines.append("FRiP status   : MARGINAL (1-5%, ENCODE minimum)")
        else:
            lines.append("FRiP status   : FAIL (<1%)")
    else:
        lines.append("")
        lines.append("FRiP score    : N/A (no peaks file provided)")

    return "\n".join(lines)
