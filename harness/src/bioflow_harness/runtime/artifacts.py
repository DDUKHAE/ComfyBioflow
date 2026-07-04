from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RuntimeArtifact:
    artifact_id: str
    artifact_type: str
    path: Path
    producer_stage_id: str


def write_text_artifact(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def ensure_dir_artifact(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path

