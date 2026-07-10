from pathlib import Path

import pytest

import nodes
from nodes.execution import EnvironmentNotReadyError

QS = "harness/examples/fixtures/quickstart"
QS_META = "harness/examples/fixtures/quickstart/sample_metadata.csv"


class _ReadyProbe:
    def env_exists(self, name): return True
    def executable_exists(self, name, exe): return True
    def executable_version(self, name, exe): return "1.0"


class _MissingProbe:
    def env_exists(self, name): return False
    def executable_exists(self, name, exe): return False
    def executable_version(self, name, exe): return None


def test_metadata_validator_returns_metadata_path_when_env_ready():
    node = nodes.NODE_CLASS_MAPPINGS["SampleMetadataValidatorNode"]()
    result = node.run(fastq_dir=QS, metadata_csv=QS_META, extra_command="", probe=_ReadyProbe())
    assert result == (QS_META,)


def test_metadata_validator_raises_when_env_not_ready():
    node = nodes.NODE_CLASS_MAPPINGS["SampleMetadataValidatorNode"]()
    with pytest.raises(EnvironmentNotReadyError):
        node.run(fastq_dir=QS, metadata_csv=QS_META, extra_command="", probe=_MissingProbe())


def test_metadata_validator_raises_on_missing_fastq_dir():
    node = nodes.NODE_CLASS_MAPPINGS["SampleMetadataValidatorNode"]()
    with pytest.raises(FileNotFoundError):
        node.run(fastq_dir="harness/examples/fixtures/missing", metadata_csv="", extra_command="", probe=_ReadyProbe())


from bioflow_harness.runtime.command_runner import DryRunCommandRunner


def test_fastp_qc_runs_one_command_per_sample_and_creates_output(tmp_path):
    runner = DryRunCommandRunner()
    out = tmp_path / "qc"
    node = nodes.NODE_CLASS_MAPPINGS["FastpQCNode"]()
    result = node.run(
        fastq_pair="upstream", fastq_dir=QS, metadata_csv=QS_META,
        output_dir=str(out), threads=2, extra_command="", runner=runner,
    )
    assert result == (str(out),)
    assert out.exists()
    assert len(runner.commands) == 4
    assert runner.commands[0].argv[:5] == ["conda", "run", "-n", "bulk_rna_seq", "fastp"]


def test_fastp_trim_creates_per_sample_dirs(tmp_path):
    runner = DryRunCommandRunner()
    out = tmp_path / "trimmed"
    node = nodes.NODE_CLASS_MAPPINGS["FastpTrimNode"]()
    result = node.run(
        fastp_qc_json="upstream", fastq_dir=QS, metadata_csv=QS_META,
        output_dir=str(out), threads=2, extra_command="", runner=runner,
    )
    assert result == (str(out),)
    assert (out / "sample_a").exists()
    assert len(runner.commands) == 4
