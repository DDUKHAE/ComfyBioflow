---
name: workflow-json-generation
description: Use when emitting ComfyUI UI-oriented workflow export JSON from a validated workflow plan — preserving node ids, links, widget values, tier and restart metadata, using deterministic Python from the workflow builder, and validating the generated JSON before reporting success.
---

# Workflow JSON Generation

Use this skill to emit ComfyUI UI-oriented workflow export JSON from a validated workflow plan.

## Rules

- Do not let an LLM directly author final workflow JSON.
- Use deterministic Python code from `bioflow_harness.comfy.workflow_builder`.
- Preserve node ids, titles, widget values, links, selected tier metadata, and restart metadata.
- Emit `STRING` outputs for bioinformatics file paths and `IMAGE` outputs only for visual previews.
- Validate generated JSON before reporting success:
  - node ids must be sequential from 1
  - link ids must be sequential from 1
  - link origin and target ids must refer to real nodes
  - each node type must resolve through `NODE_CLASS_MAPPINGS`
  - outputs and links must use supported ComfyUI-native types

## How to run scripts

`build_workflow_json.py` routes any request to whichever of the 6 supported domains it matches — the `--output` path below is just an example filename, not a bulk-only restriction. `WorkflowBuilder.build()` already calls `validate_workflow_export()` internally, so a successful build is already validated; `validate_workflow_json.py` is for re-checking a JSON file after it's been hand-edited or loaded from disk, not a required second step after a fresh build.

Run from the repository root:

    PYTHONPATH="harness/src:." python harness/skills/workflow-json-generation/scripts/build_workflow_json.py "<request text>" --registry harness/registry/tool_selection_registry.yaml --output harness/examples/workflows/bulk_rna_seq_salmon_ref.json
    PYTHONPATH="harness/src:." python harness/skills/workflow-json-generation/scripts/validate_workflow_json.py <path-to-workflow.json>

See [references/examples.md](references/examples.md) for a worked node/link count and validation example.
