# Workflow JSON Validation

The workflow JSON validator checks more than file shape. It rejects workflows that would be unsafe to load or execute as the official REF path.

Validation rules:

- top-level keys must include `metadata`, `nodes`, and `links`
- node ids must be sequential from `1`
- link ids must be sequential from `1`
- LiteGraph link arrays must carry `[id, origin_id, origin_slot, target_id, target_slot, type]`
- link `origin_id` and `target_id` must refer to existing nodes
- node `inputs[].link` and `outputs[].links` must refer to existing link ids so ComfyUI draws visible edges
- every custom node type must resolve through `bioflow_harness.custom_nodes.NODE_CLASS_MAPPINGS`
- ComfyUI builtin display nodes such as `PreviewImage` may appear as graph consumers
- each node must preserve stage metadata
- output and link types must use ComfyUI-native MVP types: `STRING` or `IMAGE`

The official workflow connects `DESeq2VisualizationNode` image output slot `1` to a builtin `PreviewImage` node so the visualization branch is visible when the JSON is opened in ComfyUI.

Run validation:

```bash
PYTHONPATH=harness/src python3 harness/skills/workflow-json-generation/scripts/validate_workflow_json.py harness/examples/workflows/bulk_rna_seq_salmon_ref.json
```
