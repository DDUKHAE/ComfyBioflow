"""
Gemini CLI adapter.

Supports both `gemini` (google-gemini/gemini-cli) and `agy` binary names.
Auth is handled via `gemini auth login` (browser OAuth).
"""
import asyncio
import json
import os
import re
import shutil

from llm_core.llm_adapters import LLMProviderAdapter, register_adapter
from llm_core.llm_contracts import LLMContractError
from llm_core import exec_log
from llm_core.model_list import GEMINI_MODELS


def find_gemini_binary() -> str:
    for name in ("gemini", "agy"):
        path = shutil.which(name)
        if path:
            return path
    home = os.path.expanduser("~")
    for name in ("gemini", "agy"):
        for base in (os.path.join(home, ".local/bin"), "/usr/local/bin", "/opt/homebrew/bin"):
            p = os.path.join(base, name)
            if os.path.exists(p):
                return p
    return "gemini"


class GeminiCLIAdapter(LLMProviderAdapter):

    def __init__(self):
        self.binary = find_gemini_binary()
        self._login_proc = None

    def _is_installed(self) -> bool:
        return bool(shutil.which(self.binary) or os.path.exists(self.binary))

    async def status(self) -> dict:
        if not self._is_installed():
            return {
                "installed": False, "authenticated": False, "ready": False,
                "model": "unknown",
                "message": f"Gemini CLI not found (tried 'gemini' and 'agy')",
            }
        # Try several status sub-commands
        for cmd in (
            [self.binary, "auth", "status"],
            [self.binary, "status"],
        ):
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=8)
                if proc.returncode == 0:
                    out = (stdout.decode() + "\n" + stderr.decode()).strip()
                    # Heuristic: look for "logged in", "authenticated", email address
                    logged_in = any(
                        tok in out.lower()
                        for tok in ("logged in", "authenticated", "signed in")
                    ) or re.search(r'\b[\w.+-]+@[\w-]+\.\w+\b', out)
                    logged_in = bool(logged_in)
                    return {
                        "installed": True, "authenticated": logged_in, "ready": logged_in,
                        "model": "gemini-2.5-pro",
                        "message": out if logged_in else "Authentication required",
                    }
            except asyncio.TimeoutError:
                continue
            except Exception:
                continue

        return {
            "installed": True, "authenticated": False, "ready": False,
            "model": "gemini-2.5-pro",
            "message": "Could not determine auth status",
        }

    async def login(self) -> dict:
        stat = await self.status()
        if stat["authenticated"]:
            return {"status": "already_logged_in", "message": "Already logged in"}

        # Try running in xterm first
        from llm_core.llm_adapters import run_in_terminal
        # Try 'auth login' in xterm
        if await run_in_terminal(self.binary, ["auth", "login"]):
            return {
                "status": "authenticating",
                "message": "Login started in xterm window. Please authenticate in the terminal.",
            }

        if self._login_proc:
            try:
                self._login_proc.terminate()
            except ProcessLookupError:
                pass
            self._login_proc = None

        for login_args in (
            [self.binary, "auth", "login"],
            [self.binary, "login"],
        ):
            try:
                self._login_proc = await asyncio.create_subprocess_exec(
                    *login_args,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    stdin=asyncio.subprocess.DEVNULL,
                )
                url = None
                for _ in range(50):
                    if self._login_proc.stdout.at_eof():
                        break
                    line = (await self._login_proc.stdout.readline()).decode()
                    match = re.search(r'https?://[^\s]+', line)
                    if match:
                        url = match.group(0)
                        break
                    await asyncio.sleep(0.1)

                return {
                    "status": "authenticating",
                    "login_url": url,
                    "message": "Login URL generated" if url else "Login started. Check browser.",
                }
            except Exception:
                continue

        return {"status": "error", "message": "Failed to start Gemini login"}

    async def poll_login(self) -> dict:
        return await self.status()

    async def list_models(self) -> list[str]:
        return GEMINI_MODELS

    async def generate(self, prompt: str, expected_type: str = None, model: str = None) -> str:
        stat = await self.status()
        if not stat["ready"]:
            raise LLMContractError("provider_not_ready", "Gemini CLI is not authenticated or ready")

        model_to_use = model or "gemini-2.5-pro"
        exec_log.write("INFO", f"[gemini] model={model_to_use}")

        arg_variants = [
            [self.binary, "-p", prompt, "--model", model_to_use, "--print"],
            [self.binary, "run", "--prompt", prompt, "--model", model_to_use],
            [self.binary, "prompt", prompt, "--model", model_to_use],
            [self.binary, "-p", prompt],
        ]

        proc = None
        last_err = "Unknown error"
        for args in arg_variants:
            try:
                proc = await asyncio.create_subprocess_exec(
                    *args,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    stdin=asyncio.subprocess.DEVNULL,
                )

                async def _drain_stderr():
                    async for raw in proc.stderr:
                        line = raw.decode().rstrip()
                        if line:
                            exec_log.write("INFO", f"[gemini] {line}")

                stdout_data, _ = await asyncio.gather(
                    proc.stdout.read(),
                    _drain_stderr(),
                )
                await proc.wait()

                if proc.returncode == 0 and stdout_data.strip():
                    exec_log.write("INFO", f"[gemini] response received ({len(stdout_data)} bytes)")
                    return stdout_data.decode()
                last_err = f"exit {proc.returncode}"
                exec_log.write("WARN", f"[gemini] {last_err}, trying next invocation style…")
            except asyncio.CancelledError:
                if proc:
                    try:
                        proc.terminate()
                    except ProcessLookupError:
                        pass
                raise
            except Exception as e:
                last_err = str(e)
                exec_log.write("WARN", f"[gemini] {e}")
                continue

        exec_log.write("ERROR", f"[gemini] all invocation styles failed: {last_err}")
        raise LLMContractError("generation_failed", f"Gemini CLI generation failed: {last_err}")


register_adapter("gemini", GeminiCLIAdapter)
