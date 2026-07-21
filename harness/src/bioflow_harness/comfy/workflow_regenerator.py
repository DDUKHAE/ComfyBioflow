import copy
from pathlib import Path

from bioflow_harness.comfy.node_catalog import NodeDefinition, default_node_catalog
from bioflow_harness.comfy.workflow_schema import validate_workflow_export
from bioflow_harness.runtime.fixture_validation import QuickstartFixture, validate_quickstart_fixture


def regenerate_bulk_rna_seq_workflow(
    workflow: dict,
    fixture_dir: Path,
    apply_safe_defaults: bool = True,
) -> dict:
    fixture = validate_quickstart_fixture(fixture_dir)
    catalog = default_node_catalog()
    base_metadata = _metadata_by_type(workflow)
    # Derived from the actual fixture directory name, not a hardcoded "quickstart" literal —
    # this function is reachable with any --fixture-dir, not just the quickstart default.
    run_root = fixture.fixture_dir.parent.parent / "runs" / fixture.fixture_dir.name

    node_specs: list[tuple[str, list[object], str | None]] = [
        (
            "SampleMetadataValidatorNode",
            [str(fixture.sample_metadata), ""],
            None,
        ),
    ]

    for sample in fixture.samples:
        sample_widgets = [
            str(sample.fastq_1),
            str(sample.fastq_2) if sample.fastq_2 is not None else "",
            str(run_root / "qc" / f"{sample.sample_id}.fastp.json"),
            2,
            "",
        ]
        node_specs.append(("FastpQCNode", sample_widgets, sample.sample_id))
        trim_widgets = [
            str(sample.fastq_1),
            str(sample.fastq_2) if sample.fastq_2 is not None else "",
            str(run_root / "trimmed" / sample.sample_id),
            2,
            _trim_policy() if apply_safe_defaults else "--length_required 1",
        ]
        node_specs.append(("FastpTrimNode", trim_widgets, sample.sample_id))

    node_specs.append(
        (
            "SalmonIndexNode",
            [
                str(fixture.transcriptome_fasta),
                str(run_root / "salmon_index"),
                2,
                "-k 7",
            ],
            None,
        )
    )
    for sample in fixture.samples:
        node_specs.append(
            (
                "SalmonQuantNode",
                [
                    str(run_root / "salmon_index"),
                    str(run_root / "trimmed" / sample.sample_id / "R1.fastq"),
                    str(run_root / "trimmed" / sample.sample_id / "R2.fastq"),
                    str(run_root / "salmon_quant" / sample.sample_id),
                    "A",
                    2,
                    "",
                ],
                sample.sample_id,
            )
        )

    node_specs.extend(
        [
            (
                "TximportNode",
                [
                    str(run_root / "salmon_quant"),
                    str(run_root / "deseq2" / "count_matrix.csv"),
                    "",
                ],
                None,
            ),
            (
                "DESeq2AnalysisNode",
                [
                    str(run_root / "deseq2" / "count_matrix.csv"),
                    str(fixture.sample_metadata),
                    str(run_root / "deseq2" / "results.csv"),
                    "~ condition",
                    _deseq2_policy() if apply_safe_defaults else "",
                ],
                None,
            ),
            (
                "DESeq2VisualizationNode",
                [
                    str(run_root / "deseq2" / "count_matrix.csv"),
                    str(run_root / "deseq2" / "results.csv"),
                    str(run_root / "plots"),
                    "pca,ma,volcano,heatmap",
                ],
                None,
            ),
            (
                "ComfyBIOReportNode",
                [
                    str(run_root / "deseq2" / "results.csv"),
                    str(run_root / "plots"),
                    str(run_root / "report" / "comfybio_report.md"),
                    _report_contract() if apply_safe_defaults else "",
                ],
                None,
            ),
        ]
    )
    return _build_workflow_from_specs(workflow, catalog, base_metadata, fixture, node_specs)


def _build_workflow_from_specs(
    source_workflow: dict,
    catalog: dict[str, NodeDefinition],
    base_metadata: dict[str, dict],
    fixture: QuickstartFixture,
    node_specs: list[tuple[str, list[object], str | None]],
) -> dict:
    preview_link_id = len(node_specs)
    nodes = []
    links = []
    next_x = 80
    visualization_node_id = None

    for index, (node_type, widgets, sample_id) in enumerate(node_specs, start=1):
        definition = catalog[node_type]
        incoming_link_id = index - 1 if index > 1 else None
        output_links_by_slot = {0: [index] if index < len(node_specs) else []}
        if node_type == "DESeq2VisualizationNode":
            visualization_node_id = index
            output_links_by_slot[1] = [preview_link_id]
        size = _node_size(widgets)
        nodes.append(
            {
                "id": index,
                "type": node_type,
                "title": _title(definition.title, sample_id),
                "pos": [next_x, 120],
                "size": size,
                "flags": {},
                "order": index - 1,
                "mode": 0,
                "inputs": _inputs_with_link(definition.inputs, incoming_link_id),
                "outputs": _outputs_with_links(definition.outputs, output_links_by_slot),
                "properties": {"Node name for S&R": node_type},
                "widgets_values": widgets,
                "metadata": _node_metadata(base_metadata.get(node_type, {}), node_type, sample_id),
            }
        )
        next_x += size[0] + 100
        if index > 1:
            links.append([index - 1, index - 1, 0, index, 0, "STRING"])

    if visualization_node_id is None:
        raise ValueError("Regenerated workflow is missing DESeq2VisualizationNode.")

    preview_node_id = len(node_specs) + 1
    nodes.append(
        {
            "id": preview_node_id,
            "type": "PreviewImage",
            "title": "Preview DESeq2 Plot",
            "pos": [nodes[visualization_node_id - 1]["pos"][0], 420],
            "size": [280, 120],
            "flags": {},
            "order": preview_node_id - 1,
            "mode": 0,
            "inputs": [{"name": "images", "type": "IMAGE", "link": preview_link_id}],
            "outputs": [],
            "properties": {"Node name for S&R": "PreviewImage"},
            "widgets_values": [],
            "metadata": {
                "stage_id": "deseq2_preview",
                "stage_label": "DESeq2 visualization preview",
                "selected_tool_id": "comfyui_preview_image",
                "selected_tier": "BUILTIN",
                "source_operation": "preview_image",
                "restart_required": False,
            },
        }
    )
    links.append([preview_link_id, visualization_node_id, 1, preview_node_id, 0, "IMAGE"])

    regenerated = {
        "last_node_id": preview_node_id,
        "last_link_id": preview_link_id,
        "version": source_workflow.get("version", 0.4),
        "config": copy.deepcopy(source_workflow.get("config", {})),
        "extra": copy.deepcopy(source_workflow.get("extra", {})),
        "groups": copy.deepcopy(source_workflow.get("groups", [])),
        "metadata": {
            **copy.deepcopy(source_workflow.get("metadata", {})),
            "format": "comfyui_workflow_export",
            "route_id": source_workflow.get("metadata", {}).get("route_id", "bulk_rna_seq_salmon_ref"),
            "domain": source_workflow.get("metadata", {}).get("domain", "bulk_rna_seq"),
            "regenerated_from_audit": True,
            "sample_count": len(fixture.samples),
        },
        "nodes": nodes,
        "links": links,
    }
    validate_workflow_export(regenerated)
    return regenerated


def _metadata_by_type(workflow: dict) -> dict[str, dict]:
    return {
        node.get("type"): copy.deepcopy(node.get("metadata", {}))
        for node in workflow.get("nodes", [])
        if node.get("type")
    }


def _node_metadata(base: dict, node_type: str, sample_id: str | None) -> dict:
    metadata = copy.deepcopy(base)
    metadata.setdefault("stage_id", node_type)
    metadata.setdefault("stage_label", node_type)
    metadata.setdefault("selected_tool_id", node_type)
    metadata.setdefault("selected_tier", "REF")
    metadata.setdefault("source_operation", node_type)
    metadata.setdefault("restart_required", False)
    if sample_id:
        metadata["stage_id"] = f"{metadata['stage_id']}_{sample_id}"
        metadata["stage_label"] = f"{metadata['stage_label']} ({sample_id})"
        metadata["sample_id"] = sample_id
    return metadata


def _title(title: str, sample_id: str | None) -> str:
    return f"{title} ({sample_id})" if sample_id else title


def _node_size(widgets: list[object]) -> list[int]:
    string_values = [value for value in widgets if isinstance(value, str)]
    longest_value = max((len(value) for value in string_values), default=0)
    path_count = sum(1 for value in string_values if "/" in value)
    width = 280
    if path_count:
        width = max(520, min(760, 260 + longest_value * 6))
    height = max(140, 110 + len(widgets) * 24)
    return [width, height]


def _inputs_with_link(inputs: list[dict[str, str]], link_id: int | None) -> list[dict]:
    copied_inputs = [dict(input_def) for input_def in inputs]
    if copied_inputs and link_id is not None:
        copied_inputs[0]["link"] = link_id
    return copied_inputs


def _outputs_with_links(outputs: list[dict[str, str]], links_by_slot: dict[int, list[int]]) -> list[dict]:
    copied_outputs = []
    for slot_index, output in enumerate(outputs):
        copied_output = dict(output)
        copied_output["slot_index"] = slot_index
        copied_output["links"] = links_by_slot.get(slot_index) or []
        copied_outputs.append(copied_output)
    return copied_outputs


def _trim_policy() -> str:
    return "--detect_adapter_for_pe\n--qualified_quality_phred 20\n--length_required 20"


def _deseq2_policy() -> str:
    return (
        "--contrast condition treatment control\n"
        "--reference-level condition:control\n"
        "--filter-min-count 10\n"
        "--filter-min-samples 2"
    )


def _report_contract() -> str:
    return "sample table; fastp summary; salmon qc; size factor diagnostics; significant gene summary; session info"
