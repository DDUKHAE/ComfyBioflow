# ComfyBIO Custom Nodes

The package exposes ComfyUI-style node mappings from:

```python
bioflow_harness.custom_nodes.NODE_CLASS_MAPPINGS
bioflow_harness.custom_nodes.NODE_DISPLAY_NAME_MAPPINGS
```

When the repository is installed directly under ComfyUI, use this layout:

```text
ComfyUI/
  custom_nodes/
    ComfyBIO/
      __init__.py
      harness/
```

The repository-root `__init__.py` adds `harness/src` to `sys.path` and re-exports:

```python
NODE_CLASS_MAPPINGS
NODE_DISPLAY_NAME_MAPPINGS
```

This is the entrypoint ComfyUI expects when loading `/custom_nodes/ComfyBIO`.

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

External-tool nodes expose an `extra_command` string input alongside core path and parameter inputs. `extra_command` is declared with `multiline: True`, so ComfyUI opens it as an expanded text area. The harness parses it with shell-style tokenization:

- one-line input such as `--threads 4 --length_required 1`
- one option fragment per line, such as:

```text
--threads 4
--length_required 1
```

Blank lines and lines starting with `#` are ignored.

The official workflow also gives every downstream ComfyBIO node an `upstream` `STRING` input with `forceInput: True`. This socket carries the visible graph edge between nodes, while file paths and command options remain editable widgets. Normal bioinformatics artifacts return `STRING` paths. Visualization nodes may additionally return `IMAGE` previews.
