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
