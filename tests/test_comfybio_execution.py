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
