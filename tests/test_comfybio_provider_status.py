import json
from dataclasses import dataclass

from bioflow_harness.llm.provider_status import provider_login_status


@dataclass
class _Completed:
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""


class _FakeRunner:
    def __init__(self, completed=None, exc=None):
        self._completed = completed
        self._exc = exc
        self.calls = []

    def __call__(self, argv):
        self.calls.append(argv)
        if self._exc is not None:
            raise self._exc
        return self._completed


def test_claude_connected():
    runner = _FakeRunner(completed=_Completed(stdout=json.dumps({"loggedIn": True})))
    result = provider_login_status("claude", runner=runner)
    assert result == {
        "provider": "claude",
        "connected": True,
        "status": "connected",
        "message": "Claude is connected.",
    }


def test_claude_not_logged_in():
    runner = _FakeRunner(completed=_Completed(stdout=json.dumps({"loggedIn": False})))
    result = provider_login_status("claude", runner=runner)
    assert result["connected"] is False
    assert result["status"] == "login_required"


def test_codex_connected_reads_stderr():
    # codex login status prints its message to stderr, not stdout.
    runner = _FakeRunner(completed=_Completed(returncode=0, stdout="", stderr="Logged in using ChatGPT\n"))
    result = provider_login_status("codex", runner=runner)
    assert result["provider"] == "codex"
    assert result["connected"] is True
    assert result["status"] == "connected"


def test_codex_not_logged_in():
    runner = _FakeRunner(completed=_Completed(returncode=0, stdout="", stderr="Not logged in\n"))
    result = provider_login_status("codex", runner=runner)
    assert result["connected"] is False
    assert result["status"] == "login_required"


def test_codex_missing_binary_is_unavailable():
    runner = _FakeRunner(exc=FileNotFoundError("codex"))
    result = provider_login_status("codex", runner=runner)
    assert result["connected"] is False
    assert result["status"] == "unavailable"


def test_gemini_missing_binary_is_unavailable():
    runner = _FakeRunner(exc=FileNotFoundError("gemini"))
    result = provider_login_status("gemini", runner=runner)
    assert result["provider"] == "gemini"
    assert result["connected"] is False
    assert result["status"] == "unavailable"


def test_unknown_provider_is_not_configured():
    result = provider_login_status("mistral")
    assert result == {
        "provider": "mistral",
        "connected": False,
        "status": "not_configured",
        "message": "mistral is not connected to an external provider yet.",
    }
