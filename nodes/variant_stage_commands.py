import sys
from pathlib import Path

from bioflow_harness.runtime.command_runner import conda_command, parse_extra_command_tokens

ENV_NAME = "variant_analysis"
_REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = _REPO_ROOT / "harness" / "scripts"
REPORT_SCRIPT = _REPO_ROOT / "harness" / "src" / "bioflow_harness" / "runtime" / "variant_report.py"


def _extra(extra_command: str) -> list[str]:
    return parse_extra_command_tokens(extra_command) if extra_command else []


def bwa_mem2_index_argv(reference_fasta, extra_command="") -> list[str]:
    return conda_command(ENV_NAME, "bwa-mem2", "index", str(reference_fasta), *_extra(extra_command))


def bwa_mem2_align_argv(reference_fasta, sample, threads, extra_command="") -> list[str]:
    args = ["mem", "-t", str(threads), str(reference_fasta), str(sample.fastq_1)]
    if sample.fastq_2 is not None:
        args.append(str(sample.fastq_2))
    return conda_command(ENV_NAME, "bwa-mem2", *args, *_extra(extra_command))


def samtools_sort_argv(input_path, output_path, threads, extra_command="") -> list[str]:
    return conda_command(
        ENV_NAME, "samtools", "sort",
        "-@", str(threads), "-o", str(output_path), str(input_path),
        *_extra(extra_command),
    )


def samtools_index_argv(bam_path, extra_command="") -> list[str]:
    return conda_command(ENV_NAME, "samtools", "index", str(bam_path), *_extra(extra_command))


def samtools_collate_argv(input_path, output_path, threads, extra_command="") -> list[str]:
    return conda_command(
        ENV_NAME, "samtools", "collate",
        "-@", str(threads), "-o", str(output_path), str(input_path),
        *_extra(extra_command),
    )


def samtools_fixmate_argv(input_path, output_path, extra_command="") -> list[str]:
    return conda_command(ENV_NAME, "samtools", "fixmate", "-m", str(input_path), str(output_path), *_extra(extra_command))


def samtools_markdup_argv(input_path, output_path, extra_command="") -> list[str]:
    return conda_command(ENV_NAME, "samtools", "markdup", str(input_path), str(output_path), *_extra(extra_command))


def bcftools_mpileup_argv(reference_fasta, bam_path, output_bcf, extra_command="") -> list[str]:
    return conda_command(
        ENV_NAME, "bcftools", "mpileup",
        "-f", str(reference_fasta), "-Ob", "-o", str(output_bcf), str(bam_path),
        *_extra(extra_command),
    )


def bcftools_call_argv(input_bcf, output_vcf, extra_command="") -> list[str]:
    return conda_command(
        ENV_NAME, "bcftools", "call",
        "-mv", "-Ov", "-o", str(output_vcf), str(input_bcf),
        *_extra(extra_command),
    )


def bcftools_filter_argv(input_vcf, output_vcf, exclude_expression, extra_command="") -> list[str]:
    return conda_command(
        ENV_NAME, "bcftools", "filter",
        "-e", str(exclude_expression), "-s", "LOWQUAL",
        "-Ov", "-o", str(output_vcf), str(input_vcf),
        *_extra(extra_command),
    )


def bcftools_stats_argv(vcf_path, extra_command="") -> list[str]:
    return conda_command(ENV_NAME, "bcftools", "stats", str(vcf_path), *_extra(extra_command))


def variant_visualization_argv(stats_dir, plot_dir, extra_command="") -> list[str]:
    return conda_command(
        ENV_NAME, "python", str(SCRIPT_DIR / "variant_visualization.py"),
        "--stats-dir", str(stats_dir),
        "--output", str(Path(plot_dir) / "variant_summary.png"),
        *_extra(extra_command),
    )


def variant_report_argv(vcf_dir, plot_dir, report_path) -> list[str]:
    return [
        sys.executable, str(REPORT_SCRIPT),
        "--vcf-dir", str(vcf_dir),
        "--plot-dir", str(plot_dir),
        "--output", str(report_path),
    ]
