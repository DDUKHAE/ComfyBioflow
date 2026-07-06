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

## Validation Agent Loop

The validation loop turns audit issues into repair suggestions. Each suggestion records:

- the issue id it responds to
- the node type to change, when the issue maps to a specific node
- the recommended action and rationale
- whether the fix can be applied automatically
- the concrete widget-level changes for safe fixes

Safe automatic fixes are limited to deterministic widget edits. The loop can currently patch QC artifact paths, trimming policy, DESeq2 contrast/filter settings, and report section declarations. Issues that require real user/reference data or graph expansion remain manual suggestions, such as replacing the toy Salmon reference or expanding sample-level QC/trim/quant branches for every metadata sample.

Run the validation agent loop:

```bash
PYTHONPATH=harness/src python3 -m bioflow_harness.cli \
  --audit-workflow harness/examples/workflows/bulk_rna_seq_salmon_ref.json \
  --audit-mode execution \
  --fixture-dir harness/examples/fixtures/quickstart \
  --validation-loop \
  --repair-output harness/examples/workflows/bulk_rna_seq_salmon_ref.regenerated.json
```

The validation loop is connected by default. It audits the workflow, creates repair suggestions, applies deterministic safe fixes, regenerates the graph from the audit context, writes the regenerated workflow when `--repair-output` is provided, and audits the regenerated workflow again.

For debugging only, the automatic repair or graph regeneration stages can be disabled:

```bash
PYTHONPATH=harness/src python3 -m bioflow_harness.cli \
  --audit-workflow harness/examples/workflows/bulk_rna_seq_salmon_ref.json \
  --audit-mode execution \
  --fixture-dir harness/examples/fixtures/quickstart \
  --validation-loop \
  --no-regenerate-workflow \
  --repair-output harness/examples/workflows/bulk_rna_seq_salmon_ref.repaired.json
```

To inspect suggestions without applying deterministic fixes:

```bash
PYTHONPATH=harness/src python3 -m bioflow_harness.cli \
  --audit-workflow harness/examples/workflows/bulk_rna_seq_salmon_ref.json \
  --audit-mode execution \
  --fixture-dir harness/examples/fixtures/quickstart \
  --validation-loop \
  --no-apply-workflow-repairs \
  --no-regenerate-workflow
```

Regeneration reads `sample_metadata.csv` and expands sample-level processing so QC, trimming, and Salmon quantification nodes are created for every metadata sample. It also recalculates node ids, link ids, visible LiteGraph connections, node positions, and workflow metadata before writing the regenerated JSON.

The regenerated quickstart workflow can remove sample coverage, QC artifact contract, trimming, DESeq2, and report-contract issues. It still flags the toy Salmon reference in `execution` mode until the user supplies a real transcriptome/reference bundle.
