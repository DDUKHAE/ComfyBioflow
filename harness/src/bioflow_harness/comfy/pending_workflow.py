import json
from pathlib import Path


class PendingWorkflowError(ValueError):
    pass


def write_pending_workflow_record(
    workflow_path: Path,
    generated_node_paths: list[Path],
    validation_status: str,
    restart_required: bool,
    output_dir: Path,
) -> Path:
    record_path = output_dir / "pending_workflow.json"
    payload = {
        "workflow_path": str(workflow_path),
        "generated_node_paths": [str(path) for path in generated_node_paths],
        "validation_status": validation_status,
        "restart_required": restart_required,
        "manual_open_fallback": f"Open this workflow JSON manually in ComfyUI: {workflow_path}",
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    record_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return record_path


def validate_pending_workflow_record(record_path: Path) -> dict:
    payload = json.loads(record_path.read_text(encoding="utf-8"))
    required = {
        "workflow_path",
        "generated_node_paths",
        "validation_status",
        "restart_required",
        "manual_open_fallback",
    }
    missing = required - payload.keys()
    if missing:
        raise PendingWorkflowError(f"Pending workflow record is missing fields: {sorted(missing)}")
    if payload["validation_status"] not in {"validated", "failed"}:
        raise PendingWorkflowError(f"Unsupported validation_status: {payload['validation_status']}")
    if payload["restart_required"] is not True:
        raise PendingWorkflowError("Pending workflow records are only required when restart_required is true.")
    if not payload["manual_open_fallback"]:
        raise PendingWorkflowError("manual_open_fallback must not be empty.")
    return payload
