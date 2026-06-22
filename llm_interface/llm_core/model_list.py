# ──────────────────────────────────────────────────────────────────────────────
# ComfyBIO — LLM model lists
#
# Edit this file to add / remove / rename models for each provider.
# Each list is ordered: first entry = default selection in the UI.
# ──────────────────────────────────────────────────────────────────────────────

CLAUDE_MODELS: list[str] = [
    "claude-sonnet-4-6",
    "claude-opus-4-8",
    "claude-haiku-4-5",
]

CODEX_MODELS: list[str] = [
    "gpt-5.5",
    "gpt-5.4",
    "gpt-5.3",
]

GEMINI_MODELS: list[str] = [
    "gemini-3.1-pro",
    "gemini-3.5-flash",
    "gemini-3.1-flash",
]

DETERMINISTIC_MODELS: list[str] = [
    "rule-based",
]
