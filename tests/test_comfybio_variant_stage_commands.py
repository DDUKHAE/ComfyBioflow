from pathlib import Path

from nodes.sample_loading import Sample
from nodes.variant_stage_commands import (
    bcftools_call_argv,
    bcftools_filter_argv,
    bcftools_mpileup_argv,
    bcftools_stats_argv,
    bwa_mem2_align_argv,
    bwa_mem2_index_argv,
    samtools_collate_argv,
    samtools_fixmate_argv,
    samtools_index_argv,
    samtools_markdup_argv,
    samtools_sort_argv,
    variant_report_argv,
    variant_visualization_argv,
)

SAMPLE = Sample("sample_a", "germline", Path("/data/a_R1.fastq"), Path("/data/a_R2.fastq"))


def test_bwa_mem2_index_argv_wraps_conda():
    argv = bwa_mem2_index_argv("/refs/reference.fasta")
    assert argv[:5] == ["conda", "run", "-n", "variant_analysis", "bwa-mem2"]
    assert argv[5:] == ["index", "/refs/reference.fasta"]


def test_bwa_mem2_align_argv_includes_paired_reads():
    argv = bwa_mem2_align_argv("/refs/reference.fasta", SAMPLE, 4)
    assert argv[:5] == ["conda", "run", "-n", "variant_analysis", "bwa-mem2"]
    assert "mem" in argv
    assert "/data/a_R1.fastq" in argv and "/data/a_R2.fastq" in argv


def test_bwa_mem2_align_argv_single_end_omits_read2():
    single = Sample("sample_a", "germline", Path("/data/a_R1.fastq"), None)
    argv = bwa_mem2_align_argv("/refs/reference.fasta", single, 4)
    assert "/data/a_R1.fastq" in argv
    assert "/data/a_R2.fastq" not in argv


def test_samtools_sort_argv_uses_output_flag():
    argv = samtools_sort_argv("/tmp/in.sam", "/tmp/out.bam", 4)
    assert argv[:5] == ["conda", "run", "-n", "variant_analysis", "samtools"]
    assert "-o" in argv and "/tmp/out.bam" in argv and "/tmp/in.sam" in argv


def test_samtools_index_argv():
    argv = samtools_index_argv("/tmp/sorted.bam")
    assert argv[4:] == ["samtools", "index", "/tmp/sorted.bam"]


def test_samtools_collate_and_fixmate_and_markdup_argv():
    collate = samtools_collate_argv("/tmp/in.bam", "/tmp/collated.bam", 4)
    fixmate = samtools_fixmate_argv("/tmp/collated.bam", "/tmp/fixmate.bam")
    markdup = samtools_markdup_argv("/tmp/sorted.bam", "/tmp/dedup.bam")
    assert "-o" in collate and "/tmp/collated.bam" in collate
    assert fixmate[4:] == ["samtools", "fixmate", "-m", "/tmp/collated.bam", "/tmp/fixmate.bam"]
    assert markdup[4:] == ["samtools", "markdup", "/tmp/sorted.bam", "/tmp/dedup.bam"]


def test_bcftools_mpileup_argv_uses_output_flag():
    argv = bcftools_mpileup_argv("/refs/reference.fasta", "/tmp/dedup.bam", "/tmp/raw.bcf")
    assert argv[:5] == ["conda", "run", "-n", "variant_analysis", "bcftools"]
    assert "-f" in argv and "/refs/reference.fasta" in argv
    assert "-o" in argv and "/tmp/raw.bcf" in argv


def test_bcftools_call_argv_uses_output_flag():
    argv = bcftools_call_argv("/tmp/raw.bcf", "/tmp/raw.vcf")
    assert "-mv" in argv and "-o" in argv and "/tmp/raw.vcf" in argv


def test_bcftools_filter_argv_uses_exclude_expression():
    argv = bcftools_filter_argv("/tmp/raw.vcf", "/tmp/filtered.vcf", "QUAL<20 || DP<10")
    assert "-e" in argv and "QUAL<20 || DP<10" in argv
    assert "-o" in argv and "/tmp/filtered.vcf" in argv


def test_bcftools_stats_argv_has_no_output_flag():
    argv = bcftools_stats_argv("/tmp/filtered.vcf")
    assert argv[4:] == ["bcftools", "stats", "/tmp/filtered.vcf"]


def test_variant_visualization_argv_points_at_script():
    argv = variant_visualization_argv("/tmp/plots", "/tmp/plots")
    assert argv[:5] == ["conda", "run", "-n", "variant_analysis", "python"]
    assert argv[5].endswith("variant_visualization.py")
    assert "--stats-dir" in argv and "/tmp/plots" in argv
    assert "--output" in argv and "/tmp/plots/variant_summary.png" in argv


def test_variant_report_argv_is_plain_python_not_conda():
    argv = variant_report_argv("/tmp/filtered", "/tmp/plots", "/tmp/report.md")
    assert "conda" not in argv
    assert argv[-2:] == ["--output", "/tmp/report.md"]


def test_extra_command_tokens_are_appended():
    argv = bwa_mem2_index_argv("/refs/reference.fasta", extra_command="-p custom_prefix")
    assert argv[-2:] == ["-p", "custom_prefix"]
