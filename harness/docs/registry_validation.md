# Registry Validation

The official MVP route is only successful when the selected REF path reaches DESeq2 analysis and DESeq2 visualization. Registry validation keeps that contract explicit before a workflow JSON is generated or a fixture run is attempted.

The validator checks the `bulk_rna_seq_salmon_ref` route for:

- every route stage references an existing tool and operation
- every selected tool is `REF`
- every selected tool has `runnable_node_status: runnable`
- each operation maps to a registered Comfy node type
- tool `future_comfy_node` and operation `node_type` stay aligned
- operation input and output artifact contracts are declared
- stage ids are unique

Run from the repository root:

```bash
PYTHONPATH=harness/src python3 -m bioflow_harness.cli \
  --validate-registry \
  --registry harness/registry/tool_selection_registry.yaml
```

Expected output includes `stage_count: 11` and node types for `DESeq2AnalysisNode`, `DESeq2VisualizationNode`, `ReportGenerationNode`, and `WorkflowJSONOutput`.

The same check is available inside the tool-ranking skill package:

```bash
PYTHONPATH=harness/src python3 harness/skills/tool-ranking/scripts/validate_registry.py \
  --registry harness/registry/tool_selection_registry.yaml
```
