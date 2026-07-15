from pathlib import Path

import pytest

from bioflow_harness.runtime.command_runner import DryRunCommandRunner
from nodes.execution import EnvironmentNotReadyError
from nodes.metagenome_nodes import Kraken2ClassifyNode, MetagenomeFastpTrimNode, MetagenomeInputValidatorNode

META_FIXTURES = "harness/examples/fixtures/metagenome"
META_CSV = "harness/examples/fixtures/metagenome/sample_metadata.csv"
META_DB = "harness/examples/fixtures/metagenome/kraken2_db"


class _ReadyProbe:
    def env_exists(self, name): return True
    def executable_exists(self, name, exe): return True
    def executable_version(self, name, exe): return "1.0"


class _MissingProbe:
    def env_exists(self, name): return False
    def executable_exists(self, name, exe): return False
    def executable_version(self, name, exe): return None


def test_metagenome_input_validator_returns_metadata_path_when_env_ready():
    node = MetagenomeInputValidatorNode()
    result = node.run(
        fastq_dir=META_FIXTURES, kraken2_db_dir=META_DB, metadata_csv=META_CSV,
        extra_command="", probe=_ReadyProbe(),
    )
    assert result == (META_CSV,)


def test_metagenome_input_validator_raises_when_env_not_ready():
    node = MetagenomeInputValidatorNode()
    with pytest.raises(EnvironmentNotReadyError):
        node.run(
            fastq_dir=META_FIXTURES, kraken2_db_dir=META_DB, metadata_csv=META_CSV,
            extra_command="", probe=_MissingProbe(),
        )


def test_metagenome_input_validator_raises_on_missing_db_dir():
    node = MetagenomeInputValidatorNode()
    with pytest.raises(FileNotFoundError):
        node.run(
            fastq_dir=META_FIXTURES, kraken2_db_dir="harness/examples/fixtures/metagenome/missing_db",
            metadata_csv=META_CSV, extra_command="", probe=_ReadyProbe(),
        )


def test_metagenome_fastp_trim_creates_per_sample_dir(tmp_path):
    runner = DryRunCommandRunner()
    out = tmp_path / "trimmed"
    node = MetagenomeFastpTrimNode()
    result = node.run(
        sample_metadata_csv="upstream", fastq_dir=META_FIXTURES, metadata_csv=META_CSV,
        output_dir=str(out), threads=2, extra_command="", runner=runner,
    )
    assert result == (str(out),)
    assert (out / "sample_a").exists()
    assert len(runner.commands) == 1
    assert runner.commands[0].argv[:5] == ["conda", "run", "-n", "metagenome", "fastp"]


def _trimmed_fixture(tmp_path):
    trimmed = tmp_path / "trimmed" / "sample_a"
    trimmed.mkdir(parents=True)
    (trimmed / "R1.fastq").write_text("@r1\nACGT\n+\nFFFF\n", encoding="utf-8")
    (trimmed / "R2.fastq").write_text("@r1\nACGT\n+\nFFFF\n", encoding="utf-8")
    return tmp_path / "trimmed"


def test_kraken2_classify_runs_one_command_per_sample(tmp_path):
    runner = DryRunCommandRunner()
    trimmed_dir = _trimmed_fixture(tmp_path)
    out = tmp_path / "kraken2"
    node = Kraken2ClassifyNode()
    result = node.run(
        trimmed_fastq_dir="upstream", fastq_dir=META_FIXTURES, metadata_csv=META_CSV,
        trimmed_dir=str(trimmed_dir), kraken2_db_dir=META_DB, output_dir=str(out),
        threads=4, confidence=0.1, extra_command="", runner=runner,
    )
    assert result == (str(out),)
    assert len(runner.commands) == 1
    assert runner.commands[0].argv[:5] == ["conda", "run", "-n", "metagenome", "kraken2"]
    assert (out / "sample_a").exists()
