from __future__ import annotations

import shlex
import subprocess
import tempfile
from pathlib import Path
# pyrefly: ignore [missing-import]
from comfy_api.latest import io


class _Base(io.ComfyNode):
    OUTPUT_NODE = True


class Bismark_align(_Base):
    """Bisulfite-aware alignment with Bismark.

    Aligns WGBS or RRBS reads to a bisulfite-converted genome index
    (bismark_genome_preparation genome_dir/). Outputs BAM and alignment report.

    Example extra_args:
        --pbat --non_bs_mm --score_min L,0,-0.6
    """

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Bismark_align",
            display_name="Bismark align",
            category="Epigenomics/Methylation",
            inputs=[
                io.String.Input("r1_path",
                    display_name="R1 FASTQ",
                    multiline=False, default="",
                    tooltip="Read 1 FASTQ path (.fastq / .fastq.gz)"),
                io.String.Input("r2_path",
                    display_name="R2 FASTQ (paired-end, optional)",
                    multiline=False, default="",
                    tooltip="Read 2 path. Leave empty for single-end."),
                io.String.Input("genome_dir",
                    display_name="Bismark genome directory",
                    multiline=False, default="",
                    tooltip="Directory with bisulfite-converted genome index"),
                io.String.Input("output_dir",
                    display_name="Output directory",
                    multiline=False, default=""),
                io.Int.Input("threads",
                    display_name="Threads",
                    default=4, min=1, max=32),
                io.Boolean.Input("non_directional",
                    display_name="Non-directional library",
                    default=False,
                    tooltip="Enable for non-directional (random strand) libraries"),
                io.String.Input("extra_args",
                    display_name="Extra Bismark arguments",
                    multiline=True, default=""),
            ],
            outputs=[
                io.String.Output("output_dir"),
                io.String.Output("bam_path"),
                io.String.Output("report_path"),
                io.String.Output("summary_text"),
            ],
        )

    @classmethod
    def execute(
        cls, r1_path, r2_path, genome_dir, output_dir, threads,
        non_directional, extra_args,
    ) -> io.NodeOutput:
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

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return io.NodeOutput(str(out_dir), "", "", f"ERROR:\n{result.stderr[:500]}")

        r1_stem = Path(r1_path).name.replace(".fastq.gz", "").replace(".fastq", "")
        if paired:
            bam_path = str(out_dir / f"{r1_stem}_bismark_bt2_pe.bam")
            report_path = str(out_dir / f"{r1_stem}_bismark_bt2_PE_report.txt")
        else:
            bam_path = str(out_dir / f"{r1_stem}_bismark_bt2.bam")
            report_path = str(out_dir / f"{r1_stem}_bismark_bt2_SE_report.txt")

        summary = _bismark_align_summary(report_path)
        return io.NodeOutput(str(out_dir), bam_path, report_path, summary)


class Bismark_extract(_Base):
    """Extract per-base methylation from Bismark BAM.

    Runs bismark_methylation_extractor to produce CpG coverage files
    for downstream DMR analysis.

    Example extra_args:
        --bedGraph --CX_context --ignore 5 --ignore_3prime 5
    """

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Bismark_extract",
            display_name="Bismark methyl extract",
            category="Epigenomics/Methylation",
            inputs=[
                io.String.Input("bam_path",
                    display_name="Bismark BAM",
                    multiline=False, default="",
                    tooltip="BAM file from Bismark alignment"),
                io.String.Input("genome_dir",
                    display_name="Bismark genome directory",
                    multiline=False, default=""),
                io.String.Input("output_dir",
                    display_name="Output directory",
                    multiline=False, default=""),
                io.Boolean.Input("CpG_only",
                    display_name="CpG context only",
                    default=True,
                    tooltip="Extract only CpG methylation (recommended for WGBS)"),
                io.Boolean.Input("comprehensive",
                    display_name="Comprehensive (all strands)",
                    default=False,
                    tooltip="Merge all four cytosine strands"),
                io.Int.Input("threads",
                    display_name="Threads",
                    default=4, min=1, max=32),
                io.String.Input("extra_args",
                    display_name="Extra bismark_methylation_extractor arguments",
                    multiline=True, default=""),
            ],
            outputs=[
                io.String.Output("output_dir"),
                io.String.Output("coverage_path",
                    tooltip="CpG coverage file (.cov.gz)"),
                io.String.Output("bismark_cov_path",
                    tooltip="Bismark coverage file for methylKit"),
                io.String.Output("summary_text"),
            ],
        )

    @classmethod
    def execute(
        cls, bam_path, genome_dir, output_dir, CpG_only, comprehensive, threads, extra_args,
    ) -> io.NodeOutput:
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

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return io.NodeOutput(str(out_dir), "", "", f"ERROR:\n{result.stderr[:500]}")

        bam_stem = Path(bam_path).stem
        cov_files = list(out_dir.glob(f"*CpG_report*"))
        bismark_cov_files = list(out_dir.glob(f"*.bismark.cov.gz"))

        coverage_path = str(cov_files[0]) if cov_files else str(out_dir / f"{bam_stem}.CpG_report.txt")
        bismark_cov_path = str(bismark_cov_files[0]) if bismark_cov_files else ""

        summary = "\n".join([
            "=== Bismark Methylation Extraction Summary ===",
            f"Input BAM     : {Path(bam_path).name}",
            f"Context       : {'CpG only' if CpG_only else 'All contexts'}",
            f"Mode          : {'Paired-end' if paired else 'Single-end'}",
            f"Output dir    : {out_dir}",
        ])
        return io.NodeOutput(str(out_dir), coverage_path, bismark_cov_path, summary)


class MethylKit_dmr(_Base):
    """Differentially methylated region (DMR) analysis with methylKit (R).

    Requires R with methylKit package installed. Input Bismark coverage
    files (one per sample, one per line).

    R installation: install.packages("BiocManager"); BiocManager::install("methylKit")
    """

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="MethylKit_dmr",
            display_name="methylKit DMR",
            category="Epigenomics/Methylation",
            inputs=[
                io.String.Input("sample_files",
                    display_name="Coverage files (one per line)",
                    multiline=True, default="",
                    tooltip="One Bismark coverage file path per line"),
                io.String.Input("sample_ids",
                    display_name="Sample IDs (comma-separated)",
                    multiline=False, default="s1,s2,c1,c2",
                    tooltip="IDs matching coverage file order"),
                io.String.Input("treatment",
                    display_name="Treatment vector (1=treat, 0=ctrl)",
                    multiline=False, default="1,1,0,0",
                    tooltip="Comma-separated 1/0 values matching sample order"),
                io.String.Input("output_dir",
                    display_name="Output directory",
                    multiline=False, default=""),
                io.Float.Input("difference",
                    display_name="Min methylation difference (%)",
                    default=25.0, min=0.0, max=100.0,
                    tooltip="Minimum methylation difference for DMR calling"),
                io.Float.Input("q_value",
                    display_name="q-value cutoff",
                    default=0.01, min=0.0, max=1.0),
                io.String.Input("extra_args",
                    display_name="Extra R script arguments (key=value)",
                    multiline=True, default="",
                    tooltip="Extra parameters passed to R script as key=value pairs"),
            ],
            outputs=[
                io.String.Output("output_dir"),
                io.String.Output("dmr_path",
                    tooltip="DMR results TSV file"),
                io.Int.Output("n_dmr",
                    tooltip="Number of significant DMRs"),
                io.String.Output("summary_text"),
            ],
        )

    @classmethod
    def execute(
        cls, sample_files, sample_ids, treatment, output_dir,
        difference, q_value, extra_args,
    ) -> io.NodeOutput:
        out_dir = Path(output_dir) if output_dir else Path(tempfile.mkdtemp())
        out_dir.mkdir(parents=True, exist_ok=True)

        files = [f.strip() for f in sample_files.strip().splitlines() if f.strip()]
        if not files:
            return io.NodeOutput(str(out_dir), "", 0, "ERROR: No sample files provided.")

        r_script = _build_methylkit_rscript(
            files, sample_ids, treatment, str(out_dir), difference, q_value
        )
        r_script_path = out_dir / "methylkit_dmr.R"
        r_script_path.write_text(r_script)

        result = subprocess.run(
            ["Rscript", str(r_script_path)],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            return io.NodeOutput(str(out_dir), "", 0, f"ERROR Rscript:\n{result.stderr[:500]}")

        dmr_path = str(out_dir / "dmr_results.tsv")
        n_dmr = 0
        if Path(dmr_path).exists():
            lines = Path(dmr_path).read_text().splitlines()
            n_dmr = max(0, len(lines) - 1)

        summary = "\n".join([
            "=== methylKit DMR Summary ===",
            f"Samples       : {len(files)}",
            f"IDs           : {sample_ids}",
            f"Min difference: {difference}%",
            f"q-value cutoff: {q_value}",
            f"DMRs found    : {n_dmr:,}",
        ])
        return io.NodeOutput(str(out_dir), dmr_path, n_dmr, summary)


# ── helpers ─────────────────────────────────────────────────────────────────

def _bismark_align_summary(report_path: str) -> str:
    p = Path(report_path)
    if not p.exists():
        return "Alignment complete. Report file not found."
    text = p.read_text()
    lines = ["=== Bismark Alignment Summary ==="]
    for keyword in [
        "Sequences analysed in total",
        "Number of paired-end alignments",
        "Number of alignments",
        "Mapping efficiency",
        "C methylated in CpG context",
        "C methylated in CHG context",
        "C methylated in CHH context",
    ]:
        for line in text.splitlines():
            if keyword in line:
                lines.append("  " + line.strip())
                break
    return "\n".join(lines)


def _build_methylkit_rscript(
    files: list, sample_ids: str, treatment: str,
    out_dir: str, difference: float, q_value: float,
) -> str:
    file_list = ", ".join(f'"{f}"' for f in files)
    id_list = ", ".join(f'"{s.strip()}"' for s in sample_ids.split(","))
    treat_list = ", ".join(t.strip() for t in treatment.split(","))
    return f"""
library(methylKit)
file.list <- list({file_list})
sample.ids <- c({id_list})
treatment <- c({treat_list})
myobj <- methRead(file.list, sample.id=sample.ids, assembly="genome",
                  treatment=treatment, context="CpG", mincov=10)
meth <- unite(myobj, destrand=FALSE)
myDiff <- calculateDiffMeth(meth)
myDiff25p <- getMethylDiff(myDiff, difference={difference}, qvalue={q_value})
out_path <- file.path("{out_dir}", "dmr_results.tsv")
write.table(as.data.frame(myDiff25p), out_path, sep="\\t", row.names=FALSE, quote=FALSE)
cat("DMR analysis complete. Results:", out_path, "\\n")
"""
