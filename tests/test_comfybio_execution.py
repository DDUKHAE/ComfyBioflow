import pytest

from nodes.execution import EnvironmentNotReadyError, require_environment, resolve_runner
from bioflow_harness.runtime.command_runner import DryRunCommandRunner


class _ReadyProbe:
    def env_exists(self, name): return True
    def executable_exists(self, name, exe): return True
    def executable_version(self, name, exe): return "1.0"


class _MissingProbe:
    def env_exists(self, name): return False
    def executable_exists(self, name, exe): return False
    def executable_version(self, name, exe): return None


def test_resolve_runner_returns_injected_runner():
    runner = DryRunCommandRunner()
    assert resolve_runner(runner) is runner


def test_require_environment_passes_when_ready():
    report = require_environment(_ReadyProbe())
    assert report.ready is True


def test_require_environment_raises_when_missing():
    with pytest.raises(EnvironmentNotReadyError):
        require_environment(_MissingProbe())


from bioflow_harness.runtime.environment import VARIANT_ANALYSIS_REQUIREMENTS


def test_require_environment_accepts_variant_analysis_requirements():
    report = require_environment(_ReadyProbe(), requirements=VARIANT_ANALYSIS_REQUIREMENTS)
    assert report.ready is True
    assert report.conda_env_name == "variant_analysis"


def test_require_environment_raises_for_variant_analysis_when_missing():
    with pytest.raises(EnvironmentNotReadyError):
        require_environment(_MissingProbe(), requirements=VARIANT_ANALYSIS_REQUIREMENTS)


def test_environment_not_ready_error_message_reflects_env_name():
    try:
        require_environment(_MissingProbe(), requirements=VARIANT_ANALYSIS_REQUIREMENTS)
    except EnvironmentNotReadyError as error:
        assert "variant_analysis" in str(error)
    else:
        raise AssertionError("expected EnvironmentNotReadyError")
