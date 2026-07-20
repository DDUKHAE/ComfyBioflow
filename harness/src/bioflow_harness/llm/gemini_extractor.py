from __future__ import annotations

import subprocess

from bioflow_harness.llm.brief_schema import (
    SYSTEM_PROMPT,
    BriefExtractionError,
    brief_from_payload,
    extract_json_object,
)
from bioflow_harness.models.prompt_contract import AnalysisBrief

DEFAULT_MODEL = "gemini-3.1-pro"
_TIMEOUT_SECONDS = 120


def _default_runner(argv: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        argv, capture_output=True, text=True, timeout=_TIMEOUT_SECONDS, stdin=subprocess.DEVNULL
    )


class GeminiBriefExtractor:
    """Extracts an AnalysisBrief from free text via the logged-in Gemini CLI (`gemini -p`).

    NOTE: unlike ClaudeBriefExtractor and CodexBriefExtractor, this integration has not been
    exercised against a real `gemini` binary — the CLI wasn't installed in the environment this
    was developed in, and installing an unreviewed npm package to test it was out of scope for
    that session. The invocation shape here (`gemini -p "<prompt>"`, plain-text stdout) follows
    Gemini CLI's documented non-interactive usage, and `extract_brief`'s caller already treats any
    exception here as a signal to fall back to the deterministic parser, so a wrong flag/output
    shape fails safe rather than crashing generation — but it should be verified against a real
    `gemini` login before being treated as equally proven as the Claude/Codex paths.
    """

    def __init__(self, model: str, *, runner=None):
        self._model = model or DEFAULT_MODEL
        self._runner = runner or _default_runner

    def extract(self, request_text: str) -> AnalysisBrief:
        prompt = f"{SYSTEM_PROMPT}\n\nResearcher's request:\n{request_text}"
        argv = ["gemini", "-p", prompt, "-m", self._model]
        completed = self._runner(argv)
        if getattr(completed, "returncode", 1) != 0:
            raise BriefExtractionError(
                f"gemini CLI exited {completed.returncode}: {(getattr(completed, 'stderr', '') or '').strip()}"
            )
        result_text = getattr(completed, "stdout", "") or ""
        data = extract_json_object(result_text, source="Gemini CLI")
        return brief_from_payload(data)
