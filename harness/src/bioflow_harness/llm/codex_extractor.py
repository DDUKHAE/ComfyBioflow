from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from bioflow_harness.llm.brief_schema import (
    BRIEF_SCHEMA,
    SYSTEM_PROMPT,
    BriefExtractionError,
    brief_from_payload,
    extract_json_object,
)
from bioflow_harness.models.prompt_contract import AnalysisBrief

DEFAULT_MODEL = "gpt-5.5"
_TIMEOUT_SECONDS = 120


def _default_runner(argv: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        argv, capture_output=True, text=True, timeout=_TIMEOUT_SECONDS, stdin=subprocess.DEVNULL
    )


def _last_agent_message(stdout: str) -> str:
    """Codex's --json mode prints one JSONL event per line; the final
    item.completed/agent_message event carries the model's response text."""
    text = None
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except (ValueError, TypeError):
            continue
        item = event.get("item") if isinstance(event, dict) else None
        if isinstance(item, dict) and item.get("type") == "agent_message" and isinstance(item.get("text"), str):
            text = item["text"]
    if text is None:
        raise BriefExtractionError("No agent_message event found in codex CLI --json output")
    return text


class CodexBriefExtractor:
    """Extracts an AnalysisBrief from free text via the logged-in Codex CLI (`codex exec`).

    Unlike Claude's `--system-prompt`/envelope-JSON flags, Codex has no separate system-prompt
    flag, so the instructions and request text are combined into one prompt. `--output-schema`
    constrains the model's final response to BRIEF_SCHEMA. `--json` prints one JSONL event per
    line to stdout; the last `agent_message` event's `text` field is the model's final response.
    """

    def __init__(self, model: str, *, runner=None):
        self._model = model or DEFAULT_MODEL
        self._runner = runner or _default_runner

    def extract(self, request_text: str) -> AnalysisBrief:
        prompt = f"{SYSTEM_PROMPT}\n\nResearcher's request:\n{request_text}"
        with tempfile.TemporaryDirectory() as tmp:
            schema_path = Path(tmp) / "brief_schema.json"
            schema_path.write_text(json.dumps(BRIEF_SCHEMA), encoding="utf-8")
            argv = [
                "codex",
                "exec",
                prompt,
                "--skip-git-repo-check",
                "--sandbox",
                "read-only",
                "--model",
                self._model,
                "--output-schema",
                str(schema_path),
                "--json",
            ]
            completed = self._runner(argv)
        if getattr(completed, "returncode", 1) != 0:
            raise BriefExtractionError(
                f"codex CLI exited {completed.returncode}: {(getattr(completed, 'stderr', '') or '').strip()}"
            )
        result_text = _last_agent_message(completed.stdout)
        data = extract_json_object(result_text, source="Codex CLI")
        return brief_from_payload(data)
