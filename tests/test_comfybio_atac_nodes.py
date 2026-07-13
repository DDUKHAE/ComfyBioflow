from pathlib import Path

import pytest

from bioflow_harness.runtime.command_runner import DryRunCommandRunner
from nodes.execution import EnvironmentNotReadyError
from nodes.atac_nodes import (
    AtacBwaMem2IndexNode, AtacFastpTrimNode, AtacInputValidatorNode,
    AtacBwaMem2AlignNode, AtacMarkDuplicatesNode, AtacQualityFilterNode
)

ATAC_FIXTURES = "harness/examples/fixtures/atac"
ATAC_META = "harness/examples/fixtures/atac/sample_metadata.csv"
ATAC_REF = "harness/examples/fixtures/atac/reference.fasta"


class _ReadyProbe:
    def env_exists(self, name): return True
    def executable_exists(self, name, exe): return True
    def executable_version(self, name, exe): return "1.0"


class _MissingProbe:
    def env_exists(self, name): return False
    def executable_exists(self, name, exe): return False
    def executable_version(self, name, exe): return None


def test_atac_input_validator_returns_metadata_path_when_env_ready():
    node = AtacInputValidatorNode()
    result = node.run(
        fastq_dir=ATAC_FIXTURES, reference_fasta=ATAC_REF, metadata_csv=ATAC_META,
        extra_command="", probe=_ReadyProbe(),
    )
    assert result == (ATAC_META,)


def test_atac_input_validator_raises_when_env_not_ready():
    node = AtacInputValidatorNode()
    with pytest.raises(EnvironmentNotReadyError):
        node.run(
            fastq_dir=ATAC_FIXTURES, reference_fasta=ATAC_REF, metadata_csv=ATAC_META,
            extra_command="", probe=_MissingProbe(),
        )


def test_atac_input_validator_raises_on_missing_reference():
    node = AtacInputValidatorNode()
    with pytest.raises(FileNotFoundError):
        node.run(
            fastq_dir=ATAC_FIXTURES, reference_fasta="harness/examples/fixtures/atac/missing.fasta",
            metadata_csv=ATAC_META, extra_command="", probe=_ReadyProbe(),
        )


def test_atac_fastp_trim_creates_per_sample_dir(tmp_path):
    runner = DryRunCommandRunner()
    out = tmp_path / "trimmed"
    node = AtacFastpTrimNode()
    result = node.run(
        sample_metadata_csv="upstream", fastq_dir=ATAC_FIXTURES, metadata_csv=ATAC_META,
        output_dir=str(out), threads=2, extra_command="", runner=runner,
    )
    assert result == (str(out),)
    assert (out / "sample_a").exists()
    assert len(runner.commands) == 1
    assert runner.commands[0].argv[:5] == ["conda", "run", "-n", "epigenomics", "fastp"]


def test_atac_bwa_mem2_index_runs_when_index_missing(tmp_path):
    reference = tmp_path / "reference.fasta"
    reference.write_text(">chr_toy\nACGT\n", encoding="utf-8")
    runner = DryRunCommandRunner()
    node = AtacBwaMem2IndexNode()
    result = node.run(trimmed_fastq_dir="upstream", reference_fasta=str(reference), extra_command="", runner=runner)
    assert result == (str(reference),)
    assert len(runner.commands) == 1
    assert runner.commands[0].argv[:5] == ["conda", "run", "-n", "epigenomics", "bwa-mem2"]


def test_atac_bwa_mem2_index_skips_when_index_present(tmp_path):
    reference = tmp_path / "reference.fasta"
    reference.write_text(">chr_toy\nACGT\n", encoding="utf-8")
    for suffix in [".0123", ".amb", ".ann", ".bwt.2bit.64", ".pac"]:
        (tmp_path / f"reference.fasta{suffix}").write_text("stub", encoding="utf-8")
    runner = DryRunCommandRunner()
    node = AtacBwaMem2IndexNode()
    node.run(trimmed_fastq_dir="upstream", reference_fasta=str(reference), extra_command="", runner=runner)
    assert len(runner.commands) == 0


def _trimmed_fixture(tmp_path):
    trimmed = tmp_path / "trimmed" / "sample_a"
    trimmed.mkdir(parents=True)
    (trimmed / "R1.fastq").write_text("@r1\nACGT\n+\nFFFF\n", encoding="utf-8")
    (trimmed / "R2.fastq").write_text("@r1\nACGT\n+\nFFFF\n", encoding="utf-8")
    return tmp_path / "trimmed"


def test_atac_bwa_mem2_align_runs_three_commands_per_sample(tmp_path):
    runner = DryRunCommandRunner()
    trimmed_dir = _trimmed_fixture(tmp_path)
    out = tmp_path / "aligned"
    node = AtacBwaMem2AlignNode()
    result = node.run(
        reference_fasta_indexed="upstream", fastq_dir=ATAC_FIXTURES, reference_fasta=ATAC_REF,
        metadata_csv=ATAC_META, trimmed_dir=str(trimmed_dir), output_dir=str(out),
        threads=4, extra_command="", runner=runner,
    )
    assert result == (str(out),)
    assert len(runner.commands) == 3
    assert runner.commands[0].argv[:5] == ["conda", "run", "-n", "epigenomics", "bwa-mem2"]
    # aligned.sam is written by the node itself (from captured stdout), so it exists even
    # under DryRunCommandRunner; sorted.bam is only produced by the (unexecuted) dry-run
    # samtools sort subprocess, so it must NOT be asserted here.
    assert (out / "sample_a" / "aligned.sam").exists()


def _aligned_fixture(tmp_path):
    aligned = tmp_path / "aligned" / "sample_a"
    aligned.mkdir(parents=True)
    (aligned / "sorted.bam").write_bytes(b"stub-bam")
    return tmp_path / "aligned"


def test_atac_mark_duplicates_runs_five_commands_per_sample(tmp_path):
    runner = DryRunCommandRunner()
    input_dir = _aligned_fixture(tmp_path)
    out = tmp_path / "dedup"
    node = AtacMarkDuplicatesNode()
    result = node.run(sorted_bam_dir="upstream", input_dir=str(input_dir), output_dir=str(out), threads=4, extra_command="", runner=runner)
    assert result == (str(out),)
    assert len(runner.commands) == 5
    assert (out / "sample_a").exists()


def _dedup_fixture(tmp_path):
    dedup = tmp_path / "dedup" / "sample_a"
    dedup.mkdir(parents=True)
    (dedup / "dedup.bam").write_bytes(b"stub-bam")
    return tmp_path / "dedup"


def test_atac_quality_filter_runs_two_commands_per_sample(tmp_path):
    runner = DryRunCommandRunner()
    input_dir = _dedup_fixture(tmp_path)
    out = tmp_path / "filtered"
    node = AtacQualityFilterNode()
    result = node.run(
        dedup_bam_dir="upstream", input_dir=str(input_dir), output_dir=str(out),
        min_mapq=30, exclude_flags="1804", mito_contig="chrM", extra_command="", runner=runner,
    )
    assert result == (str(out),)
    assert len(runner.commands) == 2
    joined = " ".join(runner.commands[0].argv)
    assert "-q" in runner.commands[0].argv and "30" in runner.commands[0].argv
    assert 'rname != "chrM"' in joined


from nodes.atac_nodes import AtacReportNode, AtacPeakVisualizationNode, Macs3PeakCallingNode


def _filtered_fixture(tmp_path):
    filtered = tmp_path / "filtered" / "sample_a"
    filtered.mkdir(parents=True)
    (filtered / "final.bam").write_bytes(b"stub-bam")
    return tmp_path / "filtered"


def test_macs3_peak_calling_runs_one_command_per_sample(tmp_path):
    runner = DryRunCommandRunner()
    input_dir = _filtered_fixture(tmp_path)
    out = tmp_path / "peaks"
    node = Macs3PeakCallingNode()
    result = node.run(
        filtered_bam_dir="upstream", input_dir=str(input_dir), output_dir=str(out),
        genome_size="hs", extra_command="", runner=runner,
    )
    assert result == (str(out),)
    assert len(runner.commands) == 1
    assert runner.commands[0].argv[:5] == ["conda", "run", "-n", "epigenomics", "macs3"]
    assert (out / "sample_a").exists()


def _peaks_fixture(tmp_path):
    peaks = tmp_path / "peaks" / "sample_a"
    peaks.mkdir(parents=True)
    return tmp_path / "peaks"


def test_atac_peak_visualization_returns_plot_dir_and_image(tmp_path):
    runner = DryRunCommandRunner()
    input_dir = _peaks_fixture(tmp_path)
    plots = tmp_path / "plots"
    node = AtacPeakVisualizationNode()
    result = node.run(
        peaks_dir="upstream", input_dir=str(input_dir), plot_dir=str(plots),
        extra_command="", runner=runner, preview_loader=lambda path: "IMAGE_STUB",
    )
    assert result == (str(plots), "IMAGE_STUB")
    assert plots.exists()
    assert len(runner.commands) == 1


def test_atac_report_runs_report_script(tmp_path):
    runner = DryRunCommandRunner()
    report = tmp_path / "report" / "atac_report.md"
    node = AtacReportNode()
    result = node.run(
        plot_dir_path="upstream", peaks_dir=str(tmp_path / "peaks"),
        plot_dir=str(tmp_path / "plots"), report_path=str(report),
        extra_command="", runner=runner,
    )
    assert result == (str(report),)
    assert report.parent.exists()
    assert len(runner.commands) == 1
    assert "conda" not in runner.commands[0].argv


def test_all_atac_nodes_registered_in_node_class_mappings():
    import nodes

    expected = {
        "AtacInputValidatorNode", "AtacFastpTrimNode", "AtacBwaMem2IndexNode",
        "AtacBwaMem2AlignNode", "AtacMarkDuplicatesNode", "AtacQualityFilterNode",
        "Macs3PeakCallingNode", "AtacPeakVisualizationNode", "AtacReportNode",
    }
    assert expected.issubset(nodes.NODE_CLASS_MAPPINGS.keys())
