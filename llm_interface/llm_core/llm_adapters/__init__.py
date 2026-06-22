import abc
import json
from llm_core.model_list import DETERMINISTIC_MODELS


class LLMProviderAdapter(abc.ABC):

    @abc.abstractmethod
    async def status(self) -> dict:
        """
        Returns:
          {installed, authenticated, ready, model, message}
        """

    @abc.abstractmethod
    async def login(self) -> dict:
        """Trigger authentication. Returns {status, login_url?, message}."""

    @abc.abstractmethod
    async def poll_login(self) -> dict:
        """Check if login completed. Returns same shape as status()."""

    @abc.abstractmethod
    async def generate(self, prompt: str, expected_type: str = None, model: str = None) -> str:
        """Run the LLM and return raw response string."""

    @abc.abstractmethod
    async def list_models(self) -> list[str]:
        """Return available model IDs for this provider (from the user's environment)."""

    async def get_default_model(self) -> str:
        models = await self.list_models()
        return models[0] if models else ""


# ── Fallback deterministic adapter ────────────────────────────────────────────

class DeterministicAdapter(LLMProviderAdapter):

    async def status(self) -> dict:
        return {
            "installed": True,
            "authenticated": True,
            "ready": True,
            "model": "rule-based",
            "message": "Deterministic rules engine is active",
        }

    async def login(self) -> dict:
        return {"status": "already_logged_in"}

    async def poll_login(self) -> dict:
        return await self.status()

    async def list_models(self) -> list[str]:
        return DETERMINISTIC_MODELS

    async def generate(self, prompt: str, expected_type: str = None, model: str = None) -> str:
        return json.dumps({
            "goal": "Read FASTA file and display sequence info",
            "nodes": [
                {"id": "n1", "class_type": "SeqIO_parse"},
                {"id": "n2", "class_type": "SeqIO_records_info"},
            ],
            "edges": [
                {"from": "n1.records", "to": "n2.records"},
            ],
        })


# ── Registry ───────────────────────────────────────────────────────────────────

_registry: dict[str, type[LLMProviderAdapter]] = {}


def register_adapter(name: str, adapter_cls: type[LLMProviderAdapter]) -> None:
    _registry[name] = adapter_cls


import asyncio
import os
import shutil

async def run_in_terminal(binary_path: str, args: list[str]) -> bool:
    """
    Attempts to run a command in an interactive terminal window (xterm).
    Returns True if started successfully, False if xterm is not available or failed.
    """
    xterm_path = shutil.which("xterm")
    if not xterm_path:
        return False

    # Check if DISPLAY environment variable is set (required for xterm)
    if not os.environ.get("DISPLAY"):
        return False

    # Initialize / clean the temp log file
    import tempfile
    log_path = os.path.join(tempfile.gettempdir(), "comfybio_login.log")
    try:
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(f"[System] Terminal session initialized for {os.path.basename(binary_path)}\n")
            f.write(f"[System] Starting interactive CLI login inside xterm...\n\n")
    except Exception:
        pass

    cmd_str = " ".join([f"'{binary_path}'"] + [f"'{a}'" for a in args])
    bash_cmd = f"{cmd_str} 2>&1 | tee -a '{log_path}'; echo; echo 'Process finished. Press Enter to close this window...'; read"

    try:
        # Launch xterm as a detached subprocess
        await asyncio.create_subprocess_exec(
            xterm_path,
            "-title", f"ComfyBIO Login ({os.path.basename(binary_path)})",
            "-e", "bash", "-c", bash_cmd
        )
        return True
    except Exception:
        return False


def get_adapter(name: str) -> LLMProviderAdapter:
    if name not in _registry:
        raise ValueError(f"Unknown adapter: {name!r}. Available: {list(_registry)}")
    return _registry[name]()


def list_adapters() -> list[str]:
    return sorted(_registry.keys())



register_adapter("deterministic", DeterministicAdapter)

# Auto-register built-in adapters
import sys as _sys

for _mod in (
    "llm_core.llm_adapters.claude_cli",
    "llm_core.llm_adapters.codex_cli",
    "llm_core.llm_adapters.gemini_cli",
):
    try:
        __import__(_mod)
    except Exception as _e:
        print(f"[comfybio] adapter import failed: {_mod}: {_e}", file=_sys.stderr)
