import asyncio
import json
import os
import re
import shutil

from llm_core.llm_adapters import LLMProviderAdapter, register_adapter
from llm_core.llm_contracts import LLMContractError
from llm_core import exec_log
from llm_core.model_list import CLAUDE_MODELS


def find_claude_binary() -> str:
    path = shutil.which("claude")
    if path:
        return path
    home = os.path.expanduser("~")
    for p in (
        os.path.join(home, ".local/bin/claude"),
        "/usr/local/bin/claude",
        "/opt/homebrew/bin/claude",
    ):
        if os.path.exists(p):
            return p
    return "claude"


class ClaudeCLIAdapter(LLMProviderAdapter):

    def __init__(self):
        self.binary = find_claude_binary()
        self._login_proc = None

    def _is_installed(self) -> bool:
        return bool(shutil.which(self.binary) or os.path.exists(self.binary))

    async def status(self) -> dict:
        if not self._is_installed():
            return {
                "installed": False, "authenticated": False, "ready": False,
                "model": "unknown",
                "message": f"Claude CLI not found at '{self.binary}'",
            }
        try:
            proc = await asyncio.create_subprocess_exec(
                self.binary, "auth", "status",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=8)
            except asyncio.TimeoutError:
                proc.kill()
                return {
                    "installed": True, "authenticated": False, "ready": False,
                    "model": "claude-sonnet-4-6",
                    "message": "Timed out while checking Claude auth status",
                }
            if proc.returncode == 0:
                try:
                    data = json.loads(stdout.decode().strip())
                    logged_in = data.get("loggedIn", False)
                    email = data.get("email", "unknown")
                    return {
                        "installed": True, "authenticated": logged_in, "ready": logged_in,
                        "model": "claude-sonnet-4-6",
                        "message": f"Logged in as {email}" if logged_in else "Authentication required",
                    }
                except (json.JSONDecodeError, ValueError):
                    out_str = stdout.decode()
                    logged_in = "Logged in" in out_str or "logged in" in out_str.lower()
                    return {
                        "installed": True, "authenticated": logged_in, "ready": logged_in,
                        "model": "claude-sonnet-4-6",
                        "message": out_str.strip() if logged_in else "Authentication required",
                    }
            return {
                "installed": True, "authenticated": False, "ready": False,
                "model": "claude-sonnet-4-6",
                "message": f"Not authenticated: {stderr.decode().strip()}",
            }
        except Exception as e:
            return {
                "installed": True, "authenticated": False, "ready": False,
                "model": "claude-sonnet-4-6",
                "message": f"Error checking auth: {e}",
            }

    async def login(self) -> dict:
        stat = await self.status()
        if stat["authenticated"]:
            return {"status": "already_logged_in", "message": "Already logged in"}

        # Try running in xterm first
        from llm_core.llm_adapters import run_in_terminal
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

        try:
            self._login_proc = await asyncio.create_subprocess_exec(
                self.binary, "auth", "login",
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
                "message": "Login URL generated" if url else "Login process started. Check browser.",
            }
        except Exception as e:
            return {"status": "error", "message": f"Failed to start login: {e}"}

    async def poll_login(self) -> dict:
        return await self.status()

    async def list_models(self) -> list[str]:
        return CLAUDE_MODELS

    async def generate(self, prompt: str, expected_type: str = None, model: str = None) -> str:
        stat = await self.status()
        if not stat["ready"]:
            raise LLMContractError("provider_not_ready", "Claude CLI is not authenticated or ready")

        model_to_use = model or "claude-sonnet-4-6"
        exec_log.write("INFO", f"[claude] model={model_to_use}")
        args = [
            self.binary, "-p", prompt,
            "--print",
            "--model", model_to_use,
            "--no-session-persistence",
            "--tools", "",
            "--dangerously-skip-permissions",
        ]
        proc = None
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
                        exec_log.write("INFO", f"[claude] {line}")

            stdout_data, _ = await asyncio.gather(
                proc.stdout.read(),
                _drain_stderr(),
            )
            await proc.wait()

            if proc.returncode != 0:
                err = stdout_data.decode().strip()
                exec_log.write("ERROR", f"[claude] exit {proc.returncode}: {err[:200]}")
                raise LLMContractError(
                    "generation_failed",
                    f"Claude CLI failed (exit {proc.returncode}): {err}",
                )
            exec_log.write("INFO", f"[claude] response received ({len(stdout_data)} bytes)")
            return stdout_data.decode()
        except asyncio.CancelledError:
            if proc:
                try:
                    proc.terminate()
                except ProcessLookupError:
                    pass
            raise
        except LLMContractError:
            raise
        except Exception as e:
            exec_log.write("ERROR", f"[claude] {e}")
            raise LLMContractError("generation_failed", f"Claude CLI error: {e}")


register_adapter("claude", ClaudeCLIAdapter)
