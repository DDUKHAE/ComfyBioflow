import json
from pathlib import Path

from bioflow_harness.runtime.artifacts import RuntimeArtifact


class ArtifactSidecarError(ValueError):
    pass


def write_artifact_sidecar(route_id: str, output_dir: Path, artifacts: list[RuntimeArtifact]) -> Path:
    sidecar_path = output_dir / "artifacts.sidecar.json"
    payload = {
        "route_id": route_id,
        "artifact_count": len(artifacts),
        "artifacts": [
            {
                "artifact_id": artifact.artifact_id,
                "artifact_type": artifact.artifact_type,
                "path": str(artifact.path),
                "producer_stage_id": artifact.producer_stage_id,
                "exists_at_validation_time": artifact.path.exists(),
            }
            for artifact in artifacts
        ],
    }
    sidecar_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return sidecar_path


def validate_artifact_sidecar(sidecar_path: Path) -> dict:
    payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
    if payload.get("artifact_count") != len(payload.get("artifacts", [])):
        raise ArtifactSidecarError("artifact_count does not match artifacts length")
    for entry in payload.get("artifacts", []):
        path = Path(entry["path"])
        if not path.exists():
            raise ArtifactSidecarError(f"Artifact path does not exist: {path}")
        if not entry.get("artifact_id"):
            raise ArtifactSidecarError("Artifact entry is missing artifact_id")
        if not entry.get("artifact_type"):
            raise ArtifactSidecarError(f"Artifact {entry.get('artifact_id')} is missing artifact_type")
        if not entry.get("producer_stage_id"):
            raise ArtifactSidecarError(f"Artifact {entry.get('artifact_id')} is missing producer_stage_id")
        if entry.get("exists_at_validation_time") is not True:
            raise ArtifactSidecarError(f"Artifact was not marked present at validation time: {path}")
    return payload
