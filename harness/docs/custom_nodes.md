# ComfyBIO Custom Nodes

The package exposes ComfyUI-style node mappings from:

```python
bioflow_harness.custom_nodes.NODE_CLASS_MAPPINGS
bioflow_harness.custom_nodes.NODE_DISPLAY_NAME_MAPPINGS
```

The official `bulk_rna_seq_salmon_ref` workflow has Python classes for every node type emitted by the default workflow builder:

- `WorkflowRequestLoader`
- `SampleMetadataValidatorNode`
- `FastpQCNode`
- `FastpTrimNode`
- `SalmonIndexNode`
- `SalmonQuantNode`
- `TximportNode`
- `DESeq2AnalysisNode`
- `DESeq2VisualizationNode`
- `ComfyBIOReportNode`
- `WorkflowJSONOutput`

External-tool nodes expose an `extra_command` string input alongside core path and parameter inputs. Normal bioinformatics artifacts return `STRING` paths. Visualization nodes may additionally return `IMAGE` previews.

