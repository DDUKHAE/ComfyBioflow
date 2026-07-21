import sys
from pathlib import Path

from bioflow_harness.runtime.command_runner import conda_command, parse_extra_command_tokens

ENV_NAME = "epigenomics"
_REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = _REPO_ROOT / "harness" / "scripts"
REPORT_SCRIPT = _REPO_ROOT / "harness" / "src" / "bioflow_harness" / "runtime" / "atac_report.py"


def _extra(extra_command: str) -> list[str]:
    return parse_extra_command_tokens(extra_command) if extra_command else []


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


def bwa_mem2_index_argv(reference_fasta, extra_command="") -> list[str]:
    return conda_command(ENV_NAME, "bwa-mem2", "index", str(reference_fasta), *_extra(extra_command))


def bwa_mem2_align_argv(reference_fasta, read1, read2, threads, extra_command="") -> list[str]:
    args = ["mem", "-t", str(threads), str(reference_fasta), str(read1)]
    if read2 is not None:
        args.append(str(read2))
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


def samtools_quality_filter_argv(input_bam, output_bam, min_mapq, exclude_flags, mito_contig, extra_command="") -> list[str]:
    return conda_command(
        ENV_NAME, "samtools", "view", "-b",
        "-q", str(min_mapq), "-F", str(exclude_flags),
        "-e", f'rname != "{mito_contig}"',
        "-o", str(output_bam), str(input_bam),
        *_extra(extra_command),
    )


def samtools_count_paired_argv(bam_path) -> list[str]:
    """Counts reads with SAM flag 0x1 (paired) set; a nonzero count means the BAM is paired-end.
    Used by Macs3PeakCallingNode to pick -f BAM vs -f BAMPE instead of assuming paired-end."""
    return conda_command(ENV_NAME, "samtools", "view", "-c", "-f", "1", str(bam_path))


def macs3_callpeak_argv(input_bam, outdir, sample_name, genome_size, format_flag="BAMPE", extra_command="") -> list[str]:
    return conda_command(
        ENV_NAME, "macs3", "callpeak",
        "-t", str(input_bam), "-f", format_flag, "-g", str(genome_size),
        "--outdir", str(outdir), "-n", str(sample_name), "--keep-dup", "all",
        *_extra(extra_command),
    )


def atac_peak_visualization_argv(peaks_dir, plot_dir, extra_command="") -> list[str]:
    return conda_command(
        ENV_NAME, "python", str(SCRIPT_DIR / "atac_peak_visualization.py"),
        "--peaks-dir", str(peaks_dir),
        "--output", str(Path(plot_dir) / "atac_summary.png"),
        *_extra(extra_command),
    )


def atac_report_argv(peaks_dir, plot_dir, report_path) -> list[str]:
    return [
        sys.executable, str(REPORT_SCRIPT),
        "--peaks-dir", str(peaks_dir),
        "--plot-dir", str(plot_dir),
        "--output", str(report_path),
    ]
