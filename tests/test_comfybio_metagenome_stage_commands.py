from pathlib import Path

from nodes.sample_loading import Sample
from nodes.metagenome_stage_commands import (
    bracken_abundance_argv,
    fastp_trim_argv,
    kraken2_classify_argv,
    metagenome_report_argv,
    metagenome_visualization_argv,
)

SAMPLE = Sample("sample_a", "gut_microbiome", Path("/data/a_R1.fastq"), Path("/data/a_R2.fastq"))


def test_fastp_trim_argv_wraps_conda_and_includes_paired_reads():
    argv = fastp_trim_argv(SAMPLE, Path("/out/sample_a"), 2)
    assert argv[:5] == ["conda", "run", "-n", "metagenome", "fastp"]
    assert "--out1" in argv and "/out/sample_a/R1.fastq" in argv
    assert "--out2" in argv and "/out/sample_a/R2.fastq" in argv


def test_kraken2_classify_argv_uses_paired_flag_and_native_output_flags():
    argv = kraken2_classify_argv(
        "/dbs/k2", "/trimmed/a/R1.fastq", "/trimmed/a/R2.fastq",
        "/out/a/kraken2_report.txt", "/out/a/kraken2_output.txt", 4, 0.1,
    )
    assert argv[:5] == ["conda", "run", "-n", "metagenome", "kraken2"]
    assert "--db" in argv and "/dbs/k2" in argv
    assert "--paired" in argv
    assert "--report" in argv and "/out/a/kraken2_report.txt" in argv
    assert "--output" in argv and "/out/a/kraken2_output.txt" in argv
    assert "/trimmed/a/R1.fastq" in argv and "/trimmed/a/R2.fastq" in argv


def test_kraken2_classify_argv_single_end_omits_paired_flag_and_read2():
    argv = kraken2_classify_argv(
        "/dbs/k2", "/trimmed/a/R1.fastq", None,
        "/out/a/kraken2_report.txt", "/out/a/kraken2_output.txt", 4, 0.1,
    )
    assert "--paired" not in argv
    assert not any("R2" in item for item in argv)


def test_bracken_abundance_argv_uses_native_output_flags():
    argv = bracken_abundance_argv(
        "/dbs/k2", "/out/a/kraken2_report.txt",
        "/out/a/bracken_output.txt", "/out/a/bracken_report.txt", 100, "S", 10,
    )
    assert argv[:5] == ["conda", "run", "-n", "metagenome", "bracken"]
    assert "-d" in argv and "/dbs/k2" in argv
    assert "-i" in argv and "/out/a/kraken2_report.txt" in argv
    assert "-o" in argv and "/out/a/bracken_output.txt" in argv
    assert "-w" in argv and "/out/a/bracken_report.txt" in argv
    assert "-r" in argv and "100" in argv
    assert "-l" in argv and "S" in argv
    assert "-t" in argv and "10" in argv


def test_metagenome_visualization_argv_points_at_script():
    argv = metagenome_visualization_argv("/tmp/bracken", "/tmp/plots")
    assert argv[:5] == ["conda", "run", "-n", "metagenome", "python"]
    assert argv[5].endswith("metagenome_visualization.py")
    assert "--reports-dir" in argv and "/tmp/bracken" in argv
    assert "--output" in argv and "/tmp/plots/metagenome_summary.png" in argv


def test_metagenome_report_argv_is_plain_python_not_conda():
    argv = metagenome_report_argv("/tmp/bracken", "/tmp/plots", "/tmp/report.md")
    assert "conda" not in argv
    assert argv[-2:] == ["--output", "/tmp/report.md"]


def test_extra_command_tokens_are_appended():
    argv = fastp_trim_argv(SAMPLE, Path("/out/sample_a"), 2, extra_command="--length_required 50")
    assert argv[-2:] == ["--length_required", "50"]
