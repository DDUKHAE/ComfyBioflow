from pathlib import Path

import pytest

from bioflow_harness.runtime.command_runner import DryRunCommandRunner
from nodes.execution import EnvironmentNotReadyError
from nodes.variant_nodes import BcftoolsCallNode, BcftoolsFilterNode, BwaMem2AlignNode, BwaMem2IndexNode, MarkDuplicatesNode, VariantInputValidatorNode

VARIANT_FIXTURES = "harness/examples/fixtures/variant"
VARIANT_META = "harness/examples/fixtures/variant/sample_metadata.csv"
VARIANT_REF = "harness/examples/fixtures/variant/reference.fasta"


class _ReadyProbe:
    def env_exists(self, name): return True
    def executable_exists(self, name, exe): return True
    def executable_version(self, name, exe): return "1.0"


class _MissingProbe:
    def env_exists(self, name): return False
    def executable_exists(self, name, exe): return False
    def executable_version(self, name, exe): return None


def test_variant_input_validator_returns_metadata_path_when_env_ready():
    node = VariantInputValidatorNode()
    result = node.run(
        fastq_dir=VARIANT_FIXTURES, reference_fasta=VARIANT_REF, metadata_csv=VARIANT_META,
        extra_command="", probe=_ReadyProbe(),
    )
    assert result == (VARIANT_META,)


def test_variant_input_validator_raises_when_env_not_ready():
    node = VariantInputValidatorNode()
    with pytest.raises(EnvironmentNotReadyError):
        node.run(
            fastq_dir=VARIANT_FIXTURES, reference_fasta=VARIANT_REF, metadata_csv=VARIANT_META,
            extra_command="", probe=_MissingProbe(),
        )


def test_variant_input_validator_raises_on_missing_reference():
    node = VariantInputValidatorNode()
    with pytest.raises(FileNotFoundError):
        node.run(
            fastq_dir=VARIANT_FIXTURES, reference_fasta="harness/examples/fixtures/variant/missing.fasta",
            metadata_csv=VARIANT_META, extra_command="", probe=_ReadyProbe(),
        )


def test_bwa_mem2_index_runs_when_index_missing(tmp_path):
    reference = tmp_path / "reference.fasta"
    reference.write_text(">chr_toy\nACGT\n", encoding="utf-8")
    runner = DryRunCommandRunner()
    node = BwaMem2IndexNode()
    result = node.run(sample_metadata_csv="upstream", reference_fasta=str(reference), extra_command="", runner=runner)
    assert result == (str(reference),)
    assert len(runner.commands) == 1
    assert runner.commands[0].argv[:5] == ["conda", "run", "-n", "variant_analysis", "bwa-mem2"]


def test_bwa_mem2_index_skips_when_index_present(tmp_path):
    reference = tmp_path / "reference.fasta"
    reference.write_text(">chr_toy\nACGT\n", encoding="utf-8")
    for suffix in [".0123", ".amb", ".ann", ".bwt.2bit.64", ".pac"]:
        (tmp_path / f"reference.fasta{suffix}").write_text("stub", encoding="utf-8")
    runner = DryRunCommandRunner()
    node = BwaMem2IndexNode()
    node.run(sample_metadata_csv="upstream", reference_fasta=str(reference), extra_command="", runner=runner)
    assert len(runner.commands) == 0


def test_bwa_mem2_align_runs_three_commands_per_sample(tmp_path):
    runner = DryRunCommandRunner()
    out = tmp_path / "aligned"
    node = BwaMem2AlignNode()
    result = node.run(
        reference_fasta_indexed="upstream", fastq_dir=VARIANT_FIXTURES, reference_fasta=VARIANT_REF,
        metadata_csv=VARIANT_META, output_dir=str(out), threads=4, extra_command="", runner=runner,
    )
    assert result == (str(out),)
    assert (out / "sample_a").exists()
    assert len(runner.commands) == 3
    assert runner.commands[0].argv[:5] == ["conda", "run", "-n", "variant_analysis", "bwa-mem2"]
    # aligned.sam is written by the node itself (from captured stdout), so it exists even
    # under DryRunCommandRunner; sorted.bam is only produced by the (unexecuted) dry-run
    # samtools sort subprocess, so it must NOT be asserted here.
    assert (out / "sample_a" / "aligned.sam").exists()


def _aligned_fixture(tmp_path):
    aligned = tmp_path / "aligned" / "sample_a"
    aligned.mkdir(parents=True)
    (aligned / "sorted.bam").write_bytes(b"stub-bam")
    return tmp_path / "aligned"


def test_mark_duplicates_runs_five_commands_per_sample(tmp_path):
    runner = DryRunCommandRunner()
    input_dir = _aligned_fixture(tmp_path)
    out = tmp_path / "dedup"
    node = MarkDuplicatesNode()
    result = node.run(sorted_bam_dir="upstream", input_dir=str(input_dir), output_dir=str(out), threads=4, extra_command="", runner=runner)
    assert result == (str(out),)
    assert len(runner.commands) == 5
    assert (out / "sample_a" / "dedup.bam").parent.exists()


def _dedup_fixture(tmp_path):
    dedup = tmp_path / "dedup" / "sample_a"
    dedup.mkdir(parents=True)
    (dedup / "dedup.bam").write_bytes(b"stub-bam")
    return tmp_path / "dedup"


def test_bcftools_call_runs_two_commands_per_sample(tmp_path):
    runner = DryRunCommandRunner()
    input_dir = _dedup_fixture(tmp_path)
    out = tmp_path / "calls"
    node = BcftoolsCallNode()
    result = node.run(
        dedup_bam_dir="upstream", input_dir=str(input_dir), reference_fasta=VARIANT_REF,
        output_dir=str(out), extra_command="", runner=runner,
    )
    assert result == (str(out),)
    assert len(runner.commands) == 2
    assert runner.commands[0].argv[:5] == ["conda", "run", "-n", "variant_analysis", "bcftools"]


def _calls_fixture(tmp_path):
    calls = tmp_path / "calls" / "sample_a"
    calls.mkdir(parents=True)
    (calls / "raw.vcf").write_text("##fileformat=VCFv4.2\n", encoding="utf-8")
    return tmp_path / "calls"


def test_bcftools_filter_runs_one_command_per_sample(tmp_path):
    runner = DryRunCommandRunner()
    input_dir = _calls_fixture(tmp_path)
    out = tmp_path / "filtered"
    node = BcftoolsFilterNode()
    result = node.run(
        raw_vcf_dir="upstream", input_dir=str(input_dir), output_dir=str(out),
        exclude_expression="QUAL<20 || DP<10", extra_command="", runner=runner,
    )
    assert result == (str(out),)
    assert len(runner.commands) == 1
    assert "QUAL<20 || DP<10" in runner.commands[0].argv
