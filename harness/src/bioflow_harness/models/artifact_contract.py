from dataclasses import dataclass


@dataclass(frozen=True)
class ArtifactMetadata:
    artifact_id: str
    artifact_type: str
    path: str
    producer_node_id: int
    producer_stage_id: str
    format: str
    exists_at_validation_time: bool = False
    sample_set_id: str | None = None
    reference_id: str | None = None

