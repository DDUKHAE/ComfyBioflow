import asyncio
import json
import os
import re
import shutil
import tempfile

from llm_core.llm_adapters import LLMProviderAdapter, register_adapter
from llm_core.llm_contracts import LLMContractError
from llm_core import exec_log
from llm_core.model_list import CODEX_MODELS


def find_codex_binary() -> str:
    path = shutil.which("codex")
    if path:
        return path
    home = os.path.expanduser("~")
    for p in (
        os.path.join(home, ".local/bin/codex"),
        "/usr/local/bin/codex",
        "/opt/homebrew/bin/codex",
    ):
        if os.path.exists(p):
            return p
    return "codex"


class CodexCLIAdapter(LLMProviderAdapter):

    def __init__(self):
        self.binary = find_codex_binary()
        self._login_proc = None

    def _is_installed(self) -> bool:
        return bool(shutil.which(self.binary) or os.path.exists(self.binary))

    async def status(self) -> dict:
        if not self._is_installed():
            return {
                "installed": False, "authenticated": False, "ready": False,
                "model": "unknown",
                "message": f"Codex CLI not found at '{self.binary}'",
            }
        try:
            proc = await asyncio.create_subprocess_exec(
                self.binary, "login", "status",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=8)
            except asyncio.TimeoutError:
                proc.kill()
                return {
                    "installed": True, "authenticated": False, "ready": False,
                    "model": CODEX_MODELS[0],
                    "message": "Timed out while checking Codex auth status",
                }
            if proc.returncode == 0:
                out_str = (stdout.decode() + "\n" + stderr.decode()).strip()
                logged_in = "logged in" in out_str.lower() or "Logged in" in out_str
                return {
                    "installed": True, "authenticated": logged_in, "ready": logged_in,
                    "model": CODEX_MODELS[0],
                    "message": out_str if logged_in else "Authentication required",
                }
            return {
                "installed": True, "authenticated": False, "ready": False,
                "model": CODEX_MODELS[0],
                "message": f"Not authenticated: {stderr.decode().strip()}",
            }
        except Exception as e:
            return {
                "installed": True, "authenticated": False, "ready": False,
                "model": CODEX_MODELS[0],
                "message": f"Error checking auth: {e}",
            }

    async def login(self) -> dict:
        stat = await self.status()
        if stat["authenticated"]:
            return {"status": "already_logged_in", "message": "Already logged in"}

        # Try running in xterm first
        from llm_core.llm_adapters import run_in_terminal
        if await run_in_terminal(self.binary, ["login", "--device-auth"]):
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
                self.binary, "login", "--device-auth",
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
                "message": "Login URL generated" if url else "Login started. Check terminal.",
            }
        except Exception as e:
            return {"status": "error", "message": f"Failed to start login: {e}"}

    async def poll_login(self) -> dict:
        return await self.status()

    async def list_models(self) -> list[str]:
        return CODEX_MODELS

    async def generate(self, prompt: str, expected_type: str = None, model: str = None) -> str:
        stat = await self.status()
        if not stat["ready"]:
            raise LLMContractError("provider_not_ready", "Codex CLI is not authenticated or ready")

        fd, temp_path = tempfile.mkstemp(suffix=".txt")
        os.close(fd)

        model_to_use = model or CODEX_MODELS[0]
        exec_log.write("INFO", f"[codex] model={model_to_use}")
        args = [
            self.binary, "exec", prompt,
            "--dangerously-bypass-approvals-and-sandbox",
            "--ignore-rules",
            "--ephemeral",
            "-o", temp_path,
        ]
        if model:
            args.extend(["--model", model])

        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.DEVNULL,
            )

            stderr_lines: list[str] = []

            async def _drain_stderr():
                async for raw in proc.stderr:
                    line = raw.decode().rstrip()
                    if line:
                        stderr_lines.append(line)
                        exec_log.write("INFO", f"[codex] {line}")

            stdout_data, _ = await asyncio.gather(
                proc.stdout.read(),
                _drain_stderr(),
            )
            await proc.wait()

            if proc.returncode != 0:
                err_text = " | ".join(stderr_lines[-5:]).strip() or stdout_data.decode(errors="ignore").strip()
                exec_log.write("ERROR", f"[codex] exit {proc.returncode}: {err_text[:200]}")
                raise LLMContractError(
                    "generation_failed",
                    f"Codex CLI failed (exit {proc.returncode}): {err_text}" if err_text else f"Codex CLI failed (exit {proc.returncode})",
                )
            if os.path.exists(temp_path):
                with open(temp_path, encoding="utf-8") as f:
                    content = f.read()
                exec_log.write("INFO", f"[codex] response received ({len(content)} bytes)")
                return content
            return ""
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
            exec_log.write("ERROR", f"[codex] {e}")
            raise LLMContractError("generation_failed", f"Codex CLI error: {e}")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


register_adapter("codex", CodexCLIAdapter)
