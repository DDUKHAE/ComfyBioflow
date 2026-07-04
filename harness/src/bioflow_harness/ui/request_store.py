import json
from pathlib import Path

from bioflow_harness.ui.request_contract import PromptSubmission


def save_submission(submission: PromptSubmission, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(submission.__dict__, indent=2), encoding="utf-8")
    return target

