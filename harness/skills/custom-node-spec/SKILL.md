# Custom Node Specification

Use this skill to describe how a registry operation maps to a ComfyBIO custom node.

## Required Fields

- Node class name
- Operation id
- File inputs
- File outputs
- Core UI parameters
- `extra_command` policy
- Runtime dependencies
- Runnable or planned status

## Rules

- One node should represent one functional operation.
- File and directory artifacts should use `STRING` outputs.
- Plot previews may use `IMAGE` outputs.

