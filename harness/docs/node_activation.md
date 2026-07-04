# Node Activation

ComfyUI discovers custom node classes when it starts. ComfyBIO therefore treats newly generated node classes as restart-required until a restarted ComfyUI process exposes them through its node catalog.

## Already Loaded Nodes

The official `bulk_rna_seq_salmon_ref` path currently resolves through `NODE_CLASS_MAPPINGS`, so it can be exported without a pending workflow record.

## Restart-Required Nodes

When a workflow references newly generated node code that has been validated but is not loaded in the current ComfyUI session, write a pending workflow record:

```bash
PYTHONPATH=harness/src python3 -m bioflow_harness.cli \
  "Bulk RNA-seq through salmon, DESeq2, plots, and report." \
  --registry harness/registry/tool_selection_registry.yaml \
  --output harness/examples/workflows/bulk_rna_seq_salmon_ref.json \
  --write-pending-record \
  --generated-node-path harness/src/bioflow_harness/custom_nodes/ref_nodes.py
```

The record is written beside the workflow JSON as `pending_workflow.json` and includes:

- `workflow_path`
- `generated_node_paths`
- `validation_status`
- `restart_required`
- `manual_open_fallback`

The manual fallback path is required so users can open the workflow JSON directly if automatic pending-workflow loading is unavailable.

