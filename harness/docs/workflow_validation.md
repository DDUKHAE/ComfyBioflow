# Workflow JSON Validation

The workflow JSON validator checks more than file shape. It rejects workflows that would be unsafe to load or execute as the official REF path.

Validation rules:

- top-level keys must include `metadata`, `nodes`, and `links`
- node ids must be sequential from `1`
- link ids must be sequential from `1`
- LiteGraph link arrays must carry `[id, origin_id, origin_slot, target_id, target_slot, type]`
- link `origin_id` and `target_id` must refer to existing nodes
- node `inputs[].link` and `outputs[].links` must refer to existing link ids so ComfyUI draws visible edges
- saved workflow fields `last_node_id`, `last_link_id`, `version`, `config`, `extra`, and `groups` should be present for ComfyUI UI compatibility
- every custom node type must resolve through `bioflow_harness.custom_nodes.NODE_CLASS_MAPPINGS`
- ComfyUI builtin display nodes such as `PreviewImage` may appear as graph consumers
- each node must preserve stage metadata
- output and link types must use ComfyUI-native MVP types: `STRING` or `IMAGE`

The official workflow connects each stage through a forced `upstream` socket and connects `DESeq2VisualizationNode` image output slot `1` to a builtin `PreviewImage` node so both the main pipeline and visualization branch are visible when the JSON is opened in ComfyUI.

Nodes with file-path widgets are widened automatically during workflow generation. This keeps long path values readable enough to identify which parameter holds which input or output path, while compact display nodes such as `PreviewImage` stay narrow.

Run validation:

```bash
PYTHONPATH=harness/src python3 harness/skills/workflow-json-generation/scripts/validate_workflow_json.py harness/examples/workflows/bulk_rna_seq_salmon_ref.json
```

## Domain Readiness Audit

Schema validation only proves that ComfyUI can load and draw the workflow. The domain readiness audit checks whether the workflow is credible as an analysis plan and whether its artifacts can be reproduced from the graph itself.

The audit currently checks:

- sample coverage: metadata samples must be represented by sample-processing nodes, not only by pre-existing output directories
- artifact contract: workflow output paths must match runtime sidecar/report expectations
- reference readiness: toy transcriptomes and demo Salmon index parameters are flagged for execution
- DESeq2 readiness: design, contrast direction, reference level, covariates, and filtering policy must be explicit for real analysis
- trimming policy: demo-only permissive settings such as `--length_required 1` are flagged
- report contract: reports should include sample table, QC summaries, Salmon QC, DESeq2 diagnostics, significant gene summary, and software/session provenance

The audit has two modes:

- `demo`: demo shortcuts are warnings, so quickstart workflows can remain useful as small examples
- `execution`: analysis-readiness issues become failures when the workflow is intended for real data

Run the audit:

```bash
PYTHONPATH=harness/src python3 -m bioflow_harness.cli \
  --audit-workflow harness/examples/workflows/bulk_rna_seq_salmon_ref.json \
  --audit-mode execution \
  --fixture-dir harness/examples/fixtures/quickstart
```
