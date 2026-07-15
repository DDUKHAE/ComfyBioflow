from pathlib import Path

from nodes.sample_loading import Sample
from nodes.assembly_stage_commands import (
    assembly_report_argv,
    assembly_visualization_argv,
    fastp_trim_argv,
    quast_qc_argv,
    spades_assemble_argv,
)

SAMPLE = Sample("sample_a", "bacterial_isolate", Path("/data/a_R1.fastq"), Path("/data/a_R2.fastq"))


def test_fastp_trim_argv_wraps_conda_and_includes_paired_reads():
    argv = fastp_trim_argv(SAMPLE, Path("/out/sample_a"), 2)
    assert argv[:5] == ["conda", "run", "-n", "genome_assembly", "fastp"]
    assert "--out1" in argv and "/out/sample_a/R1.fastq" in argv
    assert "--out2" in argv and "/out/sample_a/R2.fastq" in argv


def test_spades_assemble_argv_paired_end_uses_pe1_flags():
    argv = spades_assemble_argv("/trimmed/a/R1.fastq", "/trimmed/a/R2.fastq", "/out/a", 4, 8)
    assert argv[:5] == ["conda", "run", "-n", "genome_assembly", "spades.py"]
    assert "--pe1-1" in argv and "/trimmed/a/R1.fastq" in argv
    assert "--pe1-2" in argv and "/trimmed/a/R2.fastq" in argv
    assert "--s1" not in argv
    assert "-o" in argv and "/out/a" in argv
    assert "--isolate" in argv


def test_spades_assemble_argv_single_end_uses_s1_flag():
    argv = spades_assemble_argv("/trimmed/a/R1.fastq", None, "/out/a", 4, 8)
    assert "--s1" in argv and "/trimmed/a/R1.fastq" in argv
    assert "--pe1-1" not in argv and "--pe1-2" not in argv


def test_quast_qc_argv_uses_native_output_flag():
    argv = quast_qc_argv("/out/a/contigs.fasta", "/qc/a")
    assert argv[:5] == ["conda", "run", "-n", "genome_assembly", "quast.py"]
    assert "/out/a/contigs.fasta" in argv
    assert "-o" in argv and "/qc/a" in argv


def test_assembly_visualization_argv_points_at_script():
    argv = assembly_visualization_argv("/tmp/qc", "/tmp/plots")
    assert argv[:5] == ["conda", "run", "-n", "genome_assembly", "python"]
    assert argv[5].endswith("assembly_visualization.py")
    assert "--qc-dir" in argv and "/tmp/qc" in argv
    assert "--output" in argv and "/tmp/plots/assembly_summary.png" in argv


def test_assembly_report_argv_is_plain_python_not_conda():
    argv = assembly_report_argv("/tmp/qc", "/tmp/plots", "/tmp/report.md")
    assert "conda" not in argv
    assert argv[-2:] == ["--output", "/tmp/report.md"]


def test_extra_command_tokens_are_appended():
    argv = quast_qc_argv("/out/a/contigs.fasta", "/qc/a", extra_command="--min-contig 200")
    assert argv[-2:] == ["--min-contig", "200"]
