from pathlib import Path

from nodes.sample_loading import Sample
from nodes.atac_stage_commands import (
    atac_peak_visualization_argv,
    atac_report_argv,
    bwa_mem2_align_argv,
    bwa_mem2_index_argv,
    fastp_trim_argv,
    macs3_callpeak_argv,
    samtools_collate_argv,
    samtools_fixmate_argv,
    samtools_index_argv,
    samtools_markdup_argv,
    samtools_quality_filter_argv,
    samtools_sort_argv,
)

SAMPLE = Sample("sample_a", "open_chromatin", Path("/data/a_R1.fastq"), Path("/data/a_R2.fastq"))


def test_fastp_trim_argv_wraps_conda_and_includes_paired_reads():
    argv = fastp_trim_argv(SAMPLE, Path("/out/sample_a"), 2)
    assert argv[:5] == ["conda", "run", "-n", "epigenomics", "fastp"]
    assert "-i" in argv and "/data/a_R1.fastq" in argv
    assert "--out1" in argv and "/out/sample_a/R1.fastq" in argv
    assert "--out2" in argv and "/out/sample_a/R2.fastq" in argv


def test_bwa_mem2_index_argv_wraps_conda():
    argv = bwa_mem2_index_argv("/refs/reference.fasta")
    assert argv[:5] == ["conda", "run", "-n", "epigenomics", "bwa-mem2"]
    assert argv[5:] == ["index", "/refs/reference.fasta"]


def test_bwa_mem2_align_argv_includes_paired_reads():
    argv = bwa_mem2_align_argv("/refs/reference.fasta", "/trimmed/a/R1.fastq", "/trimmed/a/R2.fastq", 4)
    assert argv[:5] == ["conda", "run", "-n", "epigenomics", "bwa-mem2"]
    assert "mem" in argv
    assert "/trimmed/a/R1.fastq" in argv and "/trimmed/a/R2.fastq" in argv


def test_bwa_mem2_align_argv_single_end_omits_read2():
    argv = bwa_mem2_align_argv("/refs/reference.fasta", "/trimmed/a/R1.fastq", None, 4)
    assert "/trimmed/a/R1.fastq" in argv
    assert not any("R2" in item for item in argv)


def test_samtools_sort_and_index_argv():
    sort_argv = samtools_sort_argv("/tmp/in.sam", "/tmp/out.bam", 4)
    index_argv = samtools_index_argv("/tmp/out.bam")
    assert "-o" in sort_argv and "/tmp/out.bam" in sort_argv
    assert index_argv[4:] == ["samtools", "index", "/tmp/out.bam"]


def test_samtools_collate_fixmate_markdup_argv():
    collate = samtools_collate_argv("/tmp/in.bam", "/tmp/collated.bam", 4)
    fixmate = samtools_fixmate_argv("/tmp/collated.bam", "/tmp/fixmate.bam")
    markdup = samtools_markdup_argv("/tmp/sorted.bam", "/tmp/dedup.bam")
    assert "-o" in collate and "/tmp/collated.bam" in collate
    assert fixmate[4:] == ["samtools", "fixmate", "-m", "/tmp/collated.bam", "/tmp/fixmate.bam"]
    assert markdup[4:] == ["samtools", "markdup", "/tmp/sorted.bam", "/tmp/dedup.bam"]


def test_samtools_quality_filter_argv_uses_mapq_flags_and_mito_exclusion():
    argv = samtools_quality_filter_argv("/tmp/dedup.bam", "/tmp/final.bam", 30, "1804", "chrM")
    assert "-q" in argv and "30" in argv
    assert "-F" in argv and "1804" in argv
    assert "-e" in argv and 'rname != "chrM"' in argv
    assert "-o" in argv and "/tmp/final.bam" in argv


def test_macs3_callpeak_argv_uses_bampe_and_genome_size():
    argv = macs3_callpeak_argv("/tmp/final.bam", "/tmp/peaks/sample_a", "sample_a", "hs")
    assert argv[:5] == ["conda", "run", "-n", "epigenomics", "macs3"]
    assert "callpeak" in argv
    assert "-f" in argv and "BAMPE" in argv
    assert "-g" in argv and "hs" in argv
    assert "--outdir" in argv and "/tmp/peaks/sample_a" in argv
    assert "-n" in argv and "sample_a" in argv


def test_atac_peak_visualization_argv_points_at_script():
    argv = atac_peak_visualization_argv("/tmp/peaks", "/tmp/plots")
    assert argv[:5] == ["conda", "run", "-n", "epigenomics", "python"]
    assert argv[5].endswith("atac_peak_visualization.py")
    assert "--peaks-dir" in argv and "/tmp/peaks" in argv
    assert "--output" in argv and "/tmp/plots/atac_summary.png" in argv


def test_atac_report_argv_is_plain_python_not_conda():
    argv = atac_report_argv("/tmp/peaks", "/tmp/plots", "/tmp/report.md")
    assert "conda" not in argv
    assert argv[-2:] == ["--output", "/tmp/report.md"]


def test_extra_command_tokens_are_appended():
    argv = bwa_mem2_index_argv("/refs/reference.fasta", extra_command="-p custom_prefix")
    assert argv[-2:] == ["-p", "custom_prefix"]
