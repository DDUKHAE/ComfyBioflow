# Node Implementation Design

Use this skill when designing or validating ComfyBIO Python custom nodes.

## Rules

- Expose shared essential settings as core UI parameters.
- Put route-specific or advanced CLI fragments in `extra_command`.
- Reject duplicated options that appear in both core UI and `extra_command`.
- Validate file paths at runtime before launching an external tool.
- Treat newly generated node types as restart-required until ComfyUI reloads them.

