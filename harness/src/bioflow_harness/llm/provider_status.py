from __future__ import annotations

import json
import subprocess
from typing import Callable


def _default_runner(argv: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(argv, capture_output=True, text=True, timeout=10)


def _claude_status(runner: Callable) -> dict[str, str | bool]:
    completed = runner(["claude", "auth", "status", "--json"])
    if getattr(completed, "returncode", 1) != 0:
        raise RuntimeError((getattr(completed, "stderr", "") or "").strip())
    payload = json.loads(completed.stdout)
    connected = payload.get("loggedIn") is True
    return {
        "provider": "claude",
        "connected": connected,
        "status": "connected" if connected else "login_required",
        "message": "Claude is connected." if connected else "Sign in with `claude auth login`.",
    }


def _codex_status(runner: Callable) -> dict[str, str | bool]:
    completed = runner(["codex", "login", "status"])
    if getattr(completed, "returncode", 1) != 0:
        raise RuntimeError((getattr(completed, "stderr", "") or "").strip())
    # `codex login status` prints plain text (e.g. "Logged in using ChatGPT") to stderr,
    # not stdout, and is not JSON — check both streams to be safe either way.
    output = ((getattr(completed, "stdout", "") or "") + (getattr(completed, "stderr", "") or "")).strip().lower()
    connected = "logged in" in output and "not logged in" not in output
    return {
        "provider": "codex",
        "connected": connected,
        "status": "connected" if connected else "login_required",
        "message": "Codex is connected." if connected else "Sign in with `codex login`.",
    }


def _gemini_status(runner: Callable) -> dict[str, str | bool]:
    # NOTE: unverified — no `gemini` binary was available to confirm its login-status
    # command/output shape when this was written. Any failure here (including a wrong
    # command) is caught by the same broad except below and reported as "unavailable".
    completed = runner(["gemini", "auth", "status"])
    if getattr(completed, "returncode", 1) != 0:
        raise RuntimeError((getattr(completed, "stderr", "") or "").strip())
    output = (getattr(completed, "stdout", "") or "").strip().lower()
    connected = "logged in" in output or "authenticated" in output
    return {
        "provider": "gemini",
        "connected": connected,
        "status": "connected" if connected else "login_required",
        "message": "Gemini is connected." if connected else "Sign in with `gemini auth login`.",
    }


_STATUS_CHECKS = {
    "claude": _claude_status,
    "codex": _codex_status,
    "gemini": _gemini_status,
}


def provider_login_status(
    provider: str, *, runner: Callable | None = None
) -> dict[str, str | bool]:
    """Return provider connectivity without exposing account or token details."""
    check = _STATUS_CHECKS.get(provider)
    if check is None:
        return {
            "provider": provider,
            "connected": False,
            "status": "not_configured",
            "message": f"{provider} is not connected to an external provider yet.",
        }

    try:
        return check(runner or _default_runner)
    except (FileNotFoundError, RuntimeError, ValueError, TypeError, subprocess.SubprocessError):
        return {
            "provider": provider,
            "connected": False,
            "status": "unavailable",
            "message": f"{provider.capitalize()} login status could not be checked.",
        }
