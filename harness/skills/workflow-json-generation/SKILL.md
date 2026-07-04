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
