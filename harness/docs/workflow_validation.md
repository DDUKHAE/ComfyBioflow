# Workflow JSON Validation

The workflow JSON validator checks more than file shape. It rejects workflows that would be unsafe to load or execute as the official REF path.

Validation rules:

- top-level keys must include `metadata`, `nodes`, and `links`
- node ids must be sequential from `1`
- link ids must be sequential from `1`
- link `origin_id` and `target_id` must refer to existing nodes
- every node type must resolve through `bioflow_harness.custom_nodes.NODE_CLASS_MAPPINGS`
- each node must preserve stage metadata
- output and link types must use ComfyUI-native MVP types: `STRING` or `IMAGE`

Run validation:

```bash
PYTHONPATH=harness/src python3 harness/skills/workflow-json-generation/scripts/validate_workflow_json.py harness/examples/workflows/bulk_rna_seq_salmon_ref.json
```
