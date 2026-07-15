import sys
from pathlib import Path

from bioflow_harness.runtime.command_runner import conda_command, parse_extra_command_tokens

ENV_NAME = "metagenome"
_REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = _REPO_ROOT / "harness" / "scripts"
REPORT_SCRIPT = _REPO_ROOT / "harness" / "src" / "bioflow_harness" / "runtime" / "metagenome_report.py"


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


def kraken2_classify_argv(db_dir, read1, read2, report_path, output_path, threads, confidence, extra_command="") -> list[str]:
    args = ["--db", str(db_dir), "--threads", str(threads), "--confidence", str(confidence)]
    if read2 is not None:
        args.append("--paired")
    args += ["--report", str(report_path), "--output", str(output_path), str(read1)]
    if read2 is not None:
        args.append(str(read2))
    return conda_command(ENV_NAME, "kraken2", *args, *_extra(extra_command))


def bracken_abundance_argv(db_dir, kraken2_report, output_path, report_path, read_length, level, threshold, extra_command="") -> list[str]:
    return conda_command(
        ENV_NAME, "bracken",
        "-d", str(db_dir), "-i", str(kraken2_report),
        "-o", str(output_path), "-w", str(report_path),
        "-r", str(read_length), "-l", str(level), "-t", str(threshold),
        *_extra(extra_command),
    )


def metagenome_visualization_argv(reports_dir, plot_dir, extra_command="") -> list[str]:
    return conda_command(
        ENV_NAME, "python", str(SCRIPT_DIR / "metagenome_visualization.py"),
        "--reports-dir", str(reports_dir),
        "--output", str(Path(plot_dir) / "metagenome_summary.png"),
        *_extra(extra_command),
    )


def metagenome_report_argv(bracken_dir, plot_dir, report_path) -> list[str]:
    return [
        sys.executable, str(REPORT_SCRIPT),
        "--bracken-dir", str(bracken_dir),
        "--plot-dir", str(plot_dir),
        "--output", str(report_path),
    ]
