import argparse
import json
from dataclasses import asdict
from pathlib import Path

from bioflow_harness.comfy.node_catalog import default_node_catalog
from bioflow_harness.comfy.pending_workflow import write_pending_workflow_record
from bioflow_harness.comfy.workflow_auditor import audit_workflow
from bioflow_harness.comfy.workflow_builder import WorkflowBuilder
from bioflow_harness.comfy.workflow_validation_loop import run_workflow_validation_loop
from bioflow_harness.parser.prompt_parser import parse_prompt
from bioflow_harness.planner.tool_selector import load_registry
from bioflow_harness.planner.workflow_planner import WorkflowPlanner
from bioflow_harness.registry_validator import validate_official_route
from bioflow_harness.runtime.environment import validate_bulk_rna_seq_environment
from bioflow_harness.runtime.ref_workflow import EnvironmentNotReadyError, run_ref_fixture


def build_workflow(
    prompt: str,
    registry_path: Path,
    output_path: Path,
    write_pending_record: bool = False,
    generated_node_paths: list[Path] | None = None,
) -> Path:
    brief = parse_prompt(prompt)
    try:
        plan = WorkflowPlanner(load_registry(registry_path)).plan(brief)
    except ValueError as error:
        raise WorkflowPlanningRequired(brief.domain, brief.confidence_notes) from error
    workflow = WorkflowBuilder(default_node_catalog()).build(plan)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(workflow, indent=2), encoding="utf-8")
    if write_pending_record:
        write_pending_workflow_record(
            workflow_path=output_path,
            generated_node_paths=generated_node_paths or [],
            validation_status="validated",
            restart_required=True,
            output_dir=output_path.parent,
        )
    return output_path


class WorkflowPlanningRequired(ValueError):
    def __init__(self, domain: str, confidence_notes: list[str]) -> None:
        super().__init__(f"Workflow planning is required before generating domain: {domain}")
        self.domain = domain
        self.confidence_notes = confidence_notes


def _planning_required_payload(error: WorkflowPlanningRequired) -> dict:
    return {
        "status": "planning_required",
        "domain": error.domain,
        "route_id": None,
        "message": str(error),
        "confidence_notes": error.confidence_notes,
        "next_steps": [
            "create a domain exploration document",
            "design the workflow stages and artifact contract",
            "add registry route and tool entries",
            "implement and register ComfyBIO nodes",
            "add fixtures, validation rules, and workflow generation tests",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a ComfyBIO workflow JSON from a prompt.")
    parser.add_argument("prompt", nargs="?")
    parser.add_argument("--registry", type=Path, default=Path("registry/tool_selection_registry.yaml"))
    parser.add_argument("--output", type=Path, default=Path("examples/workflows/bulk_rna_seq_salmon_ref.json"))
    parser.add_argument("--write-pending-record", action="store_true")
    parser.add_argument("--generated-node-path", type=Path, action="append", default=[])
    parser.add_argument("--run-fixture-dry-run", action="store_true")
    parser.add_argument("--run-fixture", action="store_true")
    parser.add_argument("--validate-registry", action="store_true")
    parser.add_argument("--check-env", action="store_true")
    parser.add_argument("--audit-workflow", type=Path)
    parser.add_argument("--audit-mode", choices=["demo", "execution"], default="demo")
    parser.add_argument("--validation-loop", action="store_true")
    parser.add_argument("--apply-workflow-repairs", dest="apply_workflow_repairs", action="store_true", default=True)
    parser.add_argument("--no-apply-workflow-repairs", dest="apply_workflow_repairs", action="store_false")
    parser.add_argument("--regenerate-workflow", dest="regenerate_workflow", action="store_true", default=True)
    parser.add_argument("--no-regenerate-workflow", dest="regenerate_workflow", action="store_false")
    parser.add_argument("--repair-output", type=Path)
    parser.add_argument("--fixture-dir", type=Path, default=Path("examples/fixtures/quickstart"))
    parser.add_argument("--run-output-dir", type=Path, default=Path("examples/runs/quickstart"))
    args = parser.parse_args()
    if args.audit_workflow:
        workflow = json.loads(args.audit_workflow.read_text(encoding="utf-8"))
        if args.validation_loop:
            result = run_workflow_validation_loop(
                workflow,
                fixture_dir=args.fixture_dir,
                mode=args.audit_mode,
                apply_fixes=args.apply_workflow_repairs,
                regenerate_workflow=args.regenerate_workflow,
            )
            payload = asdict(result)
            payload.pop("workflow", None)
            if args.repair_output:
                args.repair_output.parent.mkdir(parents=True, exist_ok=True)
                args.repair_output.write_text(json.dumps(result.workflow, indent=2), encoding="utf-8")
                payload["repair_output"] = str(args.repair_output)
            print(json.dumps(payload, indent=2))
            return
        report = audit_workflow(workflow, fixture_dir=args.fixture_dir, mode=args.audit_mode)
        print(json.dumps(asdict(report), indent=2))
        return
    if args.check_env:
        print(json.dumps(asdict(validate_bulk_rna_seq_environment()), indent=2))
        return
    if args.validate_registry:
        report = validate_official_route(
            load_registry(args.registry),
            "bulk_rna_seq_salmon_ref",
            default_node_catalog(),
        )
        print(json.dumps(asdict(report), indent=2))
        return
    if args.run_fixture:
        try:
            result = run_ref_fixture(args.fixture_dir, args.run_output_dir, dry_run=False)
        except EnvironmentNotReadyError as error:
            print(json.dumps({"error": str(error), "environment": asdict(error.report)}, indent=2))
            raise SystemExit(2) from error
        print(
            json.dumps(
                {
                    "route_id": result.route_id,
                    "sidecar_path": str(result.sidecar_path),
                    "artifacts": [str(artifact.path) for artifact in result.artifacts],
                },
                indent=2,
            )
        )
        return
    if args.run_fixture_dry_run:
        result = run_ref_fixture(args.fixture_dir, args.run_output_dir, dry_run=True)
        print(
            json.dumps(
                {
                    "route_id": result.route_id,
                    "sidecar_path": str(result.sidecar_path),
                    "artifacts": [str(artifact.path) for artifact in result.artifacts],
                },
                indent=2,
            )
        )
        return
    if not args.prompt:
        parser.error("prompt is required unless an inspection or fixture command is used")
    try:
        build_workflow(
            args.prompt,
            args.registry,
            args.output,
            write_pending_record=args.write_pending_record,
            generated_node_paths=args.generated_node_path,
        )
    except WorkflowPlanningRequired as error:
        print(json.dumps(_planning_required_payload(error), indent=2))
        raise SystemExit(2) from error


if __name__ == "__main__":
    main()
