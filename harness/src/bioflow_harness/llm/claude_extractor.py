from __future__ import annotations

import json
import subprocess

from bioflow_harness.llm.brief_schema import (
    SYSTEM_PROMPT,
    BriefExtractionError,
    brief_from_payload,
    extract_json_object,
)
from bioflow_harness.models.prompt_contract import AnalysisBrief

DEFAULT_MODEL = "claude-opus-4-8"
_TIMEOUT_SECONDS = 120


def _default_runner(argv: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(argv, capture_output=True, text=True, timeout=_TIMEOUT_SECONDS)


class ClaudeBriefExtractor:
    """Extracts an AnalysisBrief from free text via the logged-in Claude Code CLI."""

    def __init__(self, model: str, *, runner=None):
        self._model = model or DEFAULT_MODEL
        self._runner = runner or _default_runner

    def extract(self, request_text: str) -> AnalysisBrief:
        argv = [
            "claude",
            "-p",
            request_text,
            "--output-format",
            "json",
            "--model",
            self._model,
            "--system-prompt",
            SYSTEM_PROMPT,
            "--disallowedTools",
            "*",
        ]
        completed = self._runner(argv)
        if getattr(completed, "returncode", 1) != 0:
            raise BriefExtractionError(
                f"claude CLI exited {completed.returncode}: {(completed.stderr or '').strip()}"
            )
        try:
            envelope = json.loads(completed.stdout)
        except (ValueError, TypeError) as exc:
            raise BriefExtractionError(f"Unparseable CLI envelope: {exc}") from exc
        if envelope.get("is_error") or envelope.get("subtype") != "success":
            raise BriefExtractionError(f"claude CLI returned an error envelope: {envelope.get('subtype')}")
        result_text = envelope.get("result")
        if not isinstance(result_text, str):
            raise BriefExtractionError("CLI envelope missing a string 'result'")
        data = extract_json_object(result_text, source="Claude CLI")
        return brief_from_payload(data)
