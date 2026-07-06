import copy
from dataclasses import dataclass, field
from pathlib import Path

from bioflow_harness.comfy.workflow_auditor import WorkflowAuditReport, audit_workflow
from bioflow_harness.comfy.workflow_regenerator import regenerate_bulk_rna_seq_workflow


@dataclass(frozen=True)
class WorkflowRepairSuggestion:
    issue_id: str
    node_type: str | None
    action: str
    rationale: str
    autofixable: bool
    changes: list[dict[str, object]] = field(default_factory=list)


@dataclass(frozen=True)
class WorkflowValidationLoopResult:
    agent_name: str
    mode: str
    initial_report: WorkflowAuditReport
    suggestions: list[WorkflowRepairSuggestion]
    applied_suggestions: list[WorkflowRepairSuggestion]
    final_report: WorkflowAuditReport
    workflow: dict


def run_workflow_validation_loop(
    workflow: dict,
    fixture_dir: Path | None = None,
    mode: str = "demo",
    apply_fixes: bool = True,
    regenerate_workflow: bool = True,
) -> WorkflowValidationLoopResult:
    repaired_workflow = copy.deepcopy(workflow)
    initial_report = audit_workflow(repaired_workflow, fixture_dir=fixture_dir, mode=mode)
    suggestions = suggest_workflow_repairs(initial_report)
    applied_suggestions: list[WorkflowRepairSuggestion] = []

    if regenerate_workflow:
        if fixture_dir is None:
            raise ValueError("fixture_dir is required when regenerate_workflow=True")
        repaired_workflow = regenerate_bulk_rna_seq_workflow(
            repaired_workflow,
            fixture_dir=fixture_dir,
            apply_safe_defaults=apply_fixes,
        )
        if apply_fixes:
            applied_suggestions = [suggestion for suggestion in suggestions if suggestion.autofixable]
    elif apply_fixes:
        for suggestion in suggestions:
            if suggestion.autofixable and _apply_suggestion(repaired_workflow, suggestion):
                applied_suggestions.append(suggestion)

    final_report = audit_workflow(repaired_workflow, fixture_dir=fixture_dir, mode=mode)
    return WorkflowValidationLoopResult(
        agent_name="workflow_validation_agent",
        mode=mode,
        initial_report=initial_report,
        suggestions=suggestions,
        applied_suggestions=applied_suggestions,
        final_report=final_report,
        workflow=repaired_workflow,
    )


def suggest_workflow_repairs(report: WorkflowAuditReport) -> list[WorkflowRepairSuggestion]:
    suggestions = []
    for issue in report.issues:
        suggestion = _suggestion_for_issue(issue.id)
        if suggestion is not None:
            suggestions.append(suggestion)
    return suggestions


def _suggestion_for_issue(issue_id: str) -> WorkflowRepairSuggestion | None:
    suggestions = {
        "sample_coverage_mismatch": WorkflowRepairSuggestion(
            issue_id=issue_id,
            node_type=None,
            action=(
                "Expand sample-processing graph coverage: create per-sample QC/trim/quant nodes or replace "
                "single-sample widgets with batch-aware nodes that consume sample_metadata.csv."
            ),
            rationale=(
                "tximport must only consume quant directories produced by the workflow, otherwise results can "
                "depend on stale pre-existing files."
            ),
            autofixable=False,
            changes=[
                {
                    "target": "FastpQCNode/FastpTrimNode/SalmonQuantNode",
                    "operation": "graph_expansion_required",
                    "value": "one reproducible processing branch per metadata sample",
                }
            ],
        ),
        "qc_artifact_contract_mismatch": WorkflowRepairSuggestion(
            issue_id=issue_id,
            node_type="FastpQCNode",
            action="Align FastpQCNode output_json with the runtime sidecar artifact path.",
            rationale="The report and artifact sidecar expect the aggregate QC artifact at qc/fastp.json.",
            autofixable=True,
            changes=[
                {
                    "node_type": "FastpQCNode",
                    "widget_index": 2,
                    "operation": "replace_suffix",
                    "old_suffix": "qc/sample_a.fastp.json",
                    "new_suffix": "qc/fastp.json",
                }
            ],
        ),
        "demo_reference_used_for_execution": WorkflowRepairSuggestion(
            issue_id=issue_id,
            node_type="SalmonIndexNode",
            action=(
                "Replace toy_transcriptome.fasta and -k 7 with a versioned transcriptome FASTA, decoy-aware "
                "index policy, tx2gene source, and recorded reference version."
            ),
            rationale="Reference choice changes quantification and downstream DESeq2 interpretation.",
            autofixable=False,
            changes=[
                {
                    "node_type": "SalmonIndexNode",
                    "operation": "requires_reference_inputs",
                    "value": "transcriptome FASTA, decoy list, GTF/GFF tx2gene, reference version",
                }
            ],
        ),
        "weak_deseq2_design": WorkflowRepairSuggestion(
            issue_id=issue_id,
            node_type="DESeq2AnalysisNode",
            action="Add explicit DESeq2 contrast, reference level, and low-count filtering policy.",
            rationale="The workflow must define treatment direction and filtering so log-fold changes are interpretable.",
            autofixable=True,
            changes=[
                {
                    "node_type": "DESeq2AnalysisNode",
                    "widget_index": 4,
                    "operation": "set",
                    "value": (
                        "--contrast condition treatment control\n"
                        "--reference-level condition:control\n"
                        "--filter-min-count 10\n"
                        "--filter-min-samples 2"
                    ),
                }
            ],
        ),
        "weak_trimming_policy": WorkflowRepairSuggestion(
            issue_id=issue_id,
            node_type="FastpTrimNode",
            action="Replace demo-only permissive trimming with an explicit quality and minimum-length policy.",
            rationale="Reads of length 1 are useful for tiny fixtures but not credible for real read QC.",
            autofixable=True,
            changes=[
                {
                    "node_type": "FastpTrimNode",
                    "widget_index": 4,
                    "operation": "set",
                    "value": "--detect_adapter_for_pe\n--qualified_quality_phred 20\n--length_required 20",
                }
            ],
        ),
        "thin_report_contract": WorkflowRepairSuggestion(
            issue_id=issue_id,
            node_type="ComfyBIOReportNode",
            action="Declare the minimum analysis report sections in the report node extra_command field.",
            rationale="A real analysis report needs QC, quantification, DESeq2 diagnostics, hits, and provenance.",
            autofixable=True,
            changes=[
                {
                    "node_type": "ComfyBIOReportNode",
                    "widget_index": 3,
                    "operation": "set",
                    "value": (
                        "sample table; fastp summary; salmon qc; size factor diagnostics; "
                        "significant gene summary; session info"
                    ),
                }
            ],
        ),
    }
    return suggestions.get(issue_id)


def _apply_suggestion(workflow: dict, suggestion: WorkflowRepairSuggestion) -> bool:
    applied = False
    for change in suggestion.changes:
        node_type = change.get("node_type")
        widget_index = change.get("widget_index")
        operation = change.get("operation")
        if not isinstance(node_type, str) or not isinstance(widget_index, int):
            continue
        node = _first_node(workflow, node_type)
        if node is None:
            continue
        widgets = node.get("widgets_values")
        if not isinstance(widgets, list) or widget_index >= len(widgets):
            continue
        if operation == "set":
            widgets[widget_index] = change["value"]
            applied = True
        elif operation == "replace_suffix":
            current_value = str(widgets[widget_index]).replace("\\", "/")
            old_suffix = str(change["old_suffix"])
            new_suffix = str(change["new_suffix"])
            if current_value.endswith(old_suffix):
                widgets[widget_index] = current_value[: -len(old_suffix)] + new_suffix
            else:
                parent_prefix = current_value.rsplit("/", 2)[0] if "/" in current_value else ""
                widgets[widget_index] = f"{parent_prefix}/{new_suffix}" if parent_prefix else new_suffix
            applied = True
    return applied


def _first_node(workflow: dict, node_type: str) -> dict | None:
    return next((node for node in workflow.get("nodes", []) if node.get("type") == node_type), None)
