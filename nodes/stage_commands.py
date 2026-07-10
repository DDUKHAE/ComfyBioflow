import sys
from pathlib import Path

from bioflow_harness.runtime.command_runner import conda_command, parse_extra_command_tokens

ENV_NAME = "bulk_rna_seq"
_REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = _REPO_ROOT / "harness" / "scripts"
REPORT_SCRIPT = _REPO_ROOT / "harness" / "src" / "bioflow_harness" / "runtime" / "report.py"


def _extra(extra_command: str) -> list[str]:
    return parse_extra_command_tokens(extra_command) if extra_command else []


def fastp_qc_argv(sample, output_dir, threads, extra_command="") -> list[str]:
    out = Path(output_dir)
    args = ["-i", str(sample.fastq_1)]
    if sample.fastq_2 is not None:
        args += ["-I", str(sample.fastq_2)]
    args += [
        "-w", str(threads),
        "--json", str(out / f"{sample.sample_id}.fastp.json"),
        "--html", str(out / f"{sample.sample_id}.fastp.html"),
    ]
    return conda_command(ENV_NAME, "fastp", *args, *_extra(extra_command))


def fastp_trim_argv(sample, sample_output_dir, threads, extra_command="") -> list[str]:
    out = Path(sample_output_dir)
    args = ["-i", str(sample.fastq_1)]
    if sample.fastq_2 is not None:
        args += ["-I", str(sample.fastq_2)]
    args += ["--out1", str(out / "R1.fastq")]
    if sample.fastq_2 is not None:
        args += ["--out2", str(out / "R2.fastq")]
    args += ["-w", str(threads)]
    return conda_command(ENV_NAME, "fastp", *args, *_extra(extra_command))


def salmon_index_argv(transcriptome_fasta, index_dir, threads, extra_command="") -> list[str]:
    return conda_command(
        ENV_NAME, "salmon", "index",
        "-t", str(transcriptome_fasta),
        "-i", str(index_dir),
        "-p", str(threads),
        *_extra(extra_command),
    )


def salmon_quant_argv(index_dir, read1, read2, output_dir, read_layout, threads, extra_command="") -> list[str]:
    args = ["-i", str(index_dir), "-l", str(read_layout), "-1", str(read1)]
    if read2 is not None:
        args += ["-2", str(read2)]
    args += ["-p", str(threads), "-o", str(output_dir)]
    return conda_command(ENV_NAME, "salmon", "quant", *args, *_extra(extra_command))


def tximport_argv(salmon_quant_dir, count_matrix, extra_command="") -> list[str]:
    return conda_command(
        ENV_NAME, "Rscript", str(SCRIPT_DIR / "tximport_import.R"),
        str(salmon_quant_dir), str(count_matrix),
        *_extra(extra_command),
    )


def deseq2_argv(count_matrix, sample_metadata, results_csv, extra_command="") -> list[str]:
    return conda_command(
        ENV_NAME, "Rscript", str(SCRIPT_DIR / "deseq2_analysis.R"),
        str(count_matrix), str(sample_metadata), str(results_csv),
        *_extra(extra_command),
    )


def deseq2_viz_argv(count_matrix, results_csv, plot_dir, extra_command="") -> list[str]:
    return conda_command(
        ENV_NAME, "Rscript", str(SCRIPT_DIR / "deseq2_visualization.R"),
        str(count_matrix), str(results_csv), str(plot_dir),
        *_extra(extra_command),
    )


def report_argv(results_csv, plot_dir, report_path) -> list[str]:
    return [
        sys.executable, str(REPORT_SCRIPT),
        "--results", str(results_csv),
        "--plot-dir", str(plot_dir),
        "--output", str(report_path),
    ]
