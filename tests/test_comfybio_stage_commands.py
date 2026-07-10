from pathlib import Path

from nodes.sample_loading import Sample
from nodes.stage_commands import (
    fastp_qc_argv,
    salmon_index_argv,
    salmon_quant_argv,
    tximport_argv,
    report_argv,
)

SAMPLE = Sample("sample_a", "control", Path("/data/a_R1.fastq"), Path("/data/a_R2.fastq"))


def test_fastp_qc_argv_wraps_conda_and_includes_paired_reads():
    argv = fastp_qc_argv(SAMPLE, Path("/out/qc"), 2)
    assert argv[:5] == ["conda", "run", "-n", "bulk_rna_seq", "fastp"]
    assert "-i" in argv and "/data/a_R1.fastq" in argv
    assert "-I" in argv and "/data/a_R2.fastq" in argv
    assert "/out/qc/sample_a.fastp.json" in argv


def test_salmon_index_argv():
    argv = salmon_index_argv("/refs/tx.fa", "/out/idx", 4)
    assert argv[:6] == ["conda", "run", "-n", "bulk_rna_seq", "salmon", "index"]
    assert "-t" in argv and "/refs/tx.fa" in argv


def test_salmon_quant_argv_single_end_omits_read2():
    argv = salmon_quant_argv("/out/idx", "/t/R1.fastq", None, "/out/q", "A", 2)
    assert "-1" in argv and "/t/R1.fastq" in argv
    assert "-2" not in argv


def test_extra_command_tokens_are_appended():
    argv = tximport_argv("/out/q", "/out/m.csv", extra_command="--flag value")
    assert argv[-2:] == ["--flag", "value"]


def test_report_argv_is_plain_python_not_conda():
    argv = report_argv("/out/results.csv", "/out/plots", "/out/report.md")
    assert argv[0].endswith("python") or "python" in argv[0]
    assert "conda" not in argv
    assert argv[-2:] == ["--output", "/out/report.md"]
