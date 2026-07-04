# Artifact Sidecar Metadata

ComfyUI receives normal bioinformatics file and directory outputs as `STRING` paths. ComfyBIO records richer artifact meaning in `artifacts.sidecar.json` beside each run output directory.

Each sidecar contains:

- `route_id`
- `artifact_count`
- artifact entries with:
  - `artifact_id`
  - `artifact_type`
  - `path`
  - `producer_stage_id`
  - `exists_at_validation_time`

Validate a sidecar from Python:

```python
from pathlib import Path
from bioflow_harness.runtime.artifact_sidecar import validate_artifact_sidecar

validate_artifact_sidecar(Path("harness/examples/runs/quickstart/artifacts.sidecar.json"))
```
