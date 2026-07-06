import csv
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class WorkflowAuditIssue:
    id: str
    severity: str
    message: str
    node_id: int | None = None
    node_type: str | None = None
    evidence: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkflowAuditReport:
    status: str
    mode: str
    issues: list[WorkflowAuditIssue]


def audit_workflow(
    workflow: dict,
    fixture_dir: Path | None = None,
    mode: str = "demo",
) -> WorkflowAuditReport:
    if mode not in {"demo", "execution"}:
        raise ValueError("workflow audit mode must be 'demo' or 'execution'")

    nodes = workflow.get("nodes", [])
    issues: list[WorkflowAuditIssue] = []
    metadata_samples = _metadata_sample_ids(workflow, fixture_dir)

    _audit_sample_coverage(nodes, metadata_samples, mode, issues)
    _audit_qc_artifact_contract(nodes, mode, issues)
    _audit_reference_readiness(nodes, mode, issues)
    _audit_deseq2_design(nodes, mode, issues)
    _audit_trimming_policy(nodes, mode, issues)
    _audit_report_contract(nodes, mode, issues)

    status = "pass"
    if any(issue.severity == "error" for issue in issues):
        status = "fail"
    elif issues:
        status = "warn"
    return WorkflowAuditReport(status=status, mode=mode, issues=issues)


def _metadata_sample_ids(workflow: dict, fixture_dir: Path | None) -> list[str]:
    metadata_path = None
    metadata_node = _first_node(workflow.get("nodes", []), "SampleMetadataValidatorNode")
    if metadata_node:
        widgets = _widgets(metadata_node)
        if widgets:
            metadata_path = Path(str(widgets[0]))
    if fixture_dir is not None:
        candidate = fixture_dir / "sample_metadata.csv"
        if candidate.exists():
            metadata_path = candidate
    if metadata_path is None or not metadata_path.exists():
        return []
    with metadata_path.open(newline="", encoding="utf-8") as handle:
        return [row["sample_id"] for row in csv.DictReader(handle) if row.get("sample_id")]


def _audit_sample_coverage(
    nodes: list[dict],
    metadata_samples: list[str],
    mode: str,
    issues: list[WorkflowAuditIssue],
) -> None:
    if len(metadata_samples) <= 1:
        return
    sample_nodes = [
        node
        for node in nodes
        if node.get("type") in {"FastpQCNode", "FastpTrimNode", "SalmonQuantNode"}
    ]
    referenced_samples = sorted(
        sample
        for sample in metadata_samples
        if any(sample in str(value) for node in sample_nodes for value in _widgets(node))
    )
    missing_samples = [sample for sample in metadata_samples if sample not in referenced_samples]
    if missing_samples:
        issues.append(
            WorkflowAuditIssue(
                id="sample_coverage_mismatch",
                severity=_execution_severity(mode),
                message=(
                    "Sample metadata defines multiple samples, but sample-processing nodes do not "
                    "materialize every sample. Downstream import can depend on pre-existing quant outputs."
                ),
                evidence={
                    "metadata_samples": metadata_samples,
                    "referenced_samples": referenced_samples,
                    "missing_samples": missing_samples,
                },
            )
        )


def _audit_qc_artifact_contract(nodes: list[dict], mode: str, issues: list[WorkflowAuditIssue]) -> None:
    qc_node = _first_node(nodes, "FastpQCNode")
    if not qc_node:
        return
    widgets = _widgets(qc_node)
    if len(widgets) < 3:
        return
    output_json = str(widgets[2])
    expected_suffix = "qc/fastp.json"
    if output_json.replace("\\", "/").endswith(expected_suffix):
        return
    issues.append(
        WorkflowAuditIssue(
            id="qc_artifact_contract_mismatch",
            severity=_execution_severity(mode),
            message=(
                "Fastp QC node output path differs from the runtime sidecar contract, so reports "
                "and reruns can track a different QC artifact."
            ),
            node_id=qc_node.get("id"),
            node_type=qc_node.get("type"),
            evidence={"workflow_output_json": output_json, "expected_suffix": expected_suffix},
        )
    )


def _audit_reference_readiness(
    nodes: list[dict],
    mode: str,
    issues: list[WorkflowAuditIssue],
) -> None:
    index_node = _first_node(nodes, "SalmonIndexNode")
    if not index_node:
        return
    widget_text = " ".join(str(value) for value in _widgets(index_node))
    if "toy_transcriptome.fasta" not in widget_text and "-k 7" not in widget_text:
        return
    issues.append(
        WorkflowAuditIssue(
            id="demo_reference_used_for_execution",
            severity=_execution_severity(mode),
            message=(
                "Salmon index uses the toy transcriptome or demo k-mer setting. Real analyses need "
                "a versioned transcriptome, decoy-aware index strategy, and tx2gene provenance."
            ),
            node_id=index_node.get("id"),
            node_type=index_node.get("type"),
            evidence={"widgets": list(_widgets(index_node))},
        )
    )


def _audit_deseq2_design(
    nodes: list[dict],
    mode: str,
    issues: list[WorkflowAuditIssue],
) -> None:
    deseq_node = _first_node(nodes, "DESeq2AnalysisNode")
    if not deseq_node:
        return
    widgets = [str(value).strip() for value in _widgets(deseq_node)]
    design = widgets[3] if len(widgets) > 3 else ""
    extra = widgets[4] if len(widgets) > 4 else ""
    has_contrast = any(token in extra.lower() for token in ["contrast", "reference", "ref-level", "batch"])
    if design == "~ condition" and not has_contrast:
        issues.append(
            WorkflowAuditIssue(
                id="weak_deseq2_design",
                severity=_execution_severity(mode),
                message=(
                    "DESeq2 design is minimal and lacks contrast direction, reference level, batch/covariate, "
                    "or filtering policy needed for interpretable execution."
                ),
                node_id=deseq_node.get("id"),
                node_type=deseq_node.get("type"),
                evidence={"design_formula": design, "extra_command": extra},
            )
        )


def _audit_trimming_policy(
    nodes: list[dict],
    mode: str,
    issues: list[WorkflowAuditIssue],
) -> None:
    trim_node = _first_node(nodes, "FastpTrimNode")
    if not trim_node:
        return
    extra = " ".join(str(value) for value in _widgets(trim_node))
    if "--length_required 1" not in extra:
        return
    issues.append(
        WorkflowAuditIssue(
            id="weak_trimming_policy",
            severity=_execution_severity(mode),
            message=(
                "Trimming permits reads of length 1, which is acceptable for a tiny demo but too loose "
                "for real QC without an explicit adapter/quality/min-length policy."
            ),
            node_id=trim_node.get("id"),
            node_type=trim_node.get("type"),
            evidence={"widgets": list(_widgets(trim_node))},
        )
    )


def _audit_report_contract(
    nodes: list[dict],
    mode: str,
    issues: list[WorkflowAuditIssue],
) -> None:
    report_node = _first_node(nodes, "ComfyBIOReportNode")
    if not report_node:
        return
    widget_text = " ".join(str(value).lower() for value in _widgets(report_node))
    expected_sections = ["sample", "fastp", "salmon", "size factor", "session", "significant"]
    present_sections = [section for section in expected_sections if section in widget_text]
    if len(present_sections) >= 3:
        return
    issues.append(
        WorkflowAuditIssue(
            id="thin_report_contract",
            severity=_execution_severity(mode),
            message=(
                "Report node only points to result and plot paths. Real analysis reports should include "
                "sample table, QC summaries, Salmon QC, DESeq2 diagnostics, significant gene summary, "
                "and software/session provenance."
            ),
            node_id=report_node.get("id"),
            node_type=report_node.get("type"),
            evidence={"present_sections": present_sections, "expected_sections": expected_sections},
        )
    )


def _first_node(nodes: list[dict], node_type: str) -> dict | None:
    return next((node for node in nodes if node.get("type") == node_type), None)


def _widgets(node: dict) -> list[object]:
    values = node.get("widgets_values")
    return values if isinstance(values, list) else []


def _execution_severity(mode: str) -> str:
    return "error" if mode == "execution" else "warning"
