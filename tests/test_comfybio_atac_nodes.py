from pathlib import Path

import pytest

from bioflow_harness.runtime.command_runner import DryRunCommandRunner
from nodes.execution import EnvironmentNotReadyError
from nodes.atac_nodes import AtacBwaMem2IndexNode, AtacFastpTrimNode, AtacInputValidatorNode

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
