---
name: node-implementation-design
description: Use when specifying, designing, implementing, or validating a ComfyBIO Python custom node for a registry operation — mapping the operation to a node class and socket contract, deciding which settings are core UI widgets versus extra_command CLI fragments, rejecting duplicated options, validating file paths and the node contract, and handling restart-required newly generated node types.
---

# Node Implementation Design

Use this skill to go from a registry operation to a working ComfyBIO Python custom node: its class/socket contract and its widget/implementation design are one decision, not two — this skill covers both.

## Required Fields (contract)

- Node class name
- Operation id
- File inputs
- File outputs
- Core UI parameters
- `extra_command` policy
- Runtime dependencies
- Runnable or planned status

## Rules

- One node should represent one functional operation, even when two operations share the same underlying binary: `salmon_index` and `salmon_quant` are both the `salmon` CLI but are two separate registry tool entries and two separate nodes because they are two operations, not one.
- File and directory artifacts should use `STRING` outputs; plot previews may use `IMAGE` outputs.
- Socket *names* are not a consistent pattern across nodes and must be looked up, never guessed. A directory-path input is sometimes named `<thing>_dir` (`Kraken2ClassifyNode`'s `trimmed_fastq_dir`) and sometimes `<thing>_dir_path` (`TximportNode`'s `salmon_quant_dir_path`, `ComfyBIOReportNode`'s `plot_dir_path`) for the same semantic role — there is no rule that predicts which suffix a given node uses. Get the real name from `emit_node_spec.py` (below) or `ARCHITECTURE.md`'s node catalog table, not from the name of an analogous node elsewhere in the route.
- Expose shared essential settings as core UI parameters: inputs/outputs the node cannot run without, and options most users tune for every invocation (e.g. `SalmonQuantNode` widgets: index path, FASTQ paths, output directory, thread count, read layout, strandness).
- Put route-specific or advanced CLI fragments in `extra_command`: flags most users never touch, or ones specific to an uncommon use case.
- Reject duplicated options that appear in both core UI and `extra_command`.
- Validate file paths at runtime before launching an external tool.
- Treat newly generated node types as restart-required until ComfyUI reloads them.

## How to run scripts

`emit_node_spec.py` lists a tool's registry operations together with the real socket names and types from `comfy/node_catalog.py`'s `default_node_catalog()` — not just the registry's generic type list — so it's the authoritative source for socket names, not a pattern to infer from other nodes:

    PYTHONPATH="harness/src:." python harness/skills/node-implementation-design/scripts/emit_node_spec.py <tool_id> --registry harness/registry/tool_selection_registry.yaml

`generate_node_skeleton.py` is standalone and runs from anywhere. It only prints a bare `RETURN_TYPES`/`FUNCTION`/`CATEGORY` skeleton — treat its output as a starting stub, not a spec-complete node (it does not emit `INPUT_TYPES` or a `run()` body):

    python harness/skills/node-implementation-design/scripts/generate_node_skeleton.py <ClassName> <Category>

`validate_node_contract.py` imports the target module by dotted path, so run it from the repository root with the project on `PYTHONPATH`. It only checks that `RETURN_TYPES`/`FUNCTION`/`CATEGORY`/`INPUT_TYPES` exist on the class — it does not check `run()` presence (that's the domain-bootstrap promotion gate's job) or widget/`extra_command` placement (that's a manual review against the rules above):

    PYTHONPATH="harness/src:." python harness/skills/node-implementation-design/scripts/validate_node_contract.py <module> <ClassName>

See [references/examples.md](references/examples.md) for worked node-design examples.
