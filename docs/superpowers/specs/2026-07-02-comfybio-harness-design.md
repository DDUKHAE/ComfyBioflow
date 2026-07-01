# ComfyBIO Harness Design

## Objective

Build an MVP harness that turns a user's natural-language genomics request into a ComfyUI-compatible workflow JSON. The first milestone prioritizes harness engineering rather than full execution of bioinformatics tools. The harness should:

- parse analysis intent from natural language
- select tools through an extensible YAML registry
- plan a genomics workflow, starting with bulk RNA-seq
- emit a ComfyUI workflow JSON that can be loaded and inspected visually

This MVP does not need to execute the actual analysis tools end to end inside ComfyUI yet.

## Scope

### In Scope

- Directory structure for a reusable harness project
- Skill packages and example documents for:
  - workflow discovery
  - workflow generation
  - ComfyUI custom node specification
  - ComfyUI workflow JSON generation
- YAML-based tool selection registry
- Python package for prompt parsing, registry-driven planning, and ComfyUI JSON emission
- Support for genomics-oriented workflows with `bulk RNA-seq` as the first fully modeled path
- Inclusion of common Python ecosystem assumptions such as `biopython` in project configuration and docs
- Example prompts and generated workflow JSON artifacts

### Out of Scope for MVP

- Real execution of aligners, quantifiers, or downstream genomics tools inside ComfyUI
- Full custom node implementations for every registry entry
- Production-grade natural language understanding
- First-class workflow coverage for `scRNA-seq`, `metagenome`, and `WGS`

Those domains will be represented in the registry and documentation as future extension targets, but only `bulk RNA-seq` will be fully wired through parsing, planning, and JSON generation in the first iteration.

## Recommended Architecture

The harness will use a `registry + planner` architecture.

### Why this approach

- It matches the product goal better than hard-coded workflow templates.
- It keeps the registry human-editable and easy to expand as new genomics domains are added.
- It gives a clear path from natural-language intent to future ComfyUI custom node implementations.
- It supports incremental evolution from "specification only" to "runnable node graph" without replacing the project structure.

### High-level flow

1. User provides a natural-language analysis request.
2. A prompt parser extracts:
   - analysis goal
   - domain
   - input types
   - expected outputs
   - constraints
3. A workflow planner maps the parsed request to canonical pipeline stages.
4. A tool selector chooses candidate tools for each stage from the YAML registry.
5. A ComfyUI workflow builder converts the planned stages into ComfyUI-compatible node and link structures.
6. The harness writes a workflow JSON file for user inspection and manual execution testing.

## Target MVP Workflow

The first modeled workflow is `bulk RNA-seq`.

### Canonical stage sequence

1. Input specification
2. Sample metadata validation
3. Read QC
4. Adapter or quality trimming
5. Alignment or pseudoalignment
6. Quantification
7. Differential expression analysis
8. Summary and report output

The planner should be able to omit or swap optional stages based on request constraints, but the default path should follow this sequence.

## Directory Structure

```text
ComfyBIO/
  docs/
    superpowers/
      specs/
        2026-07-02-comfybio-harness-design.md
  harness/
    docs/
    examples/
      prompts/
      workflows/
    registry/
      tool_selection_registry.yaml
    skills/
      workflow-discovery/
        SKILL.md
        examples.md
      workflow-generation/
        SKILL.md
        examples.md
      custom-node-spec/
        SKILL.md
        examples.md
      workflow-json-generation/
        SKILL.md
        examples.md
    src/
      bioflow_harness/
        __init__.py
        cli.py
        models/
          __init__.py
          prompt_contract.py
          workflow_plan.py
        parser/
          __init__.py
          prompt_parser.py
        planner/
          __init__.py
          stage_mapper.py
          tool_selector.py
          workflow_planner.py
        comfy/
          __init__.py
          node_catalog.py
          workflow_builder.py
          workflow_schema.py
    tests/
      test_prompt_parser.py
      test_tool_selector.py
      test_workflow_builder.py
  pyproject.toml
  README.md
```

## Component Responsibilities

### 1. Workflow Discovery Skill

Purpose:
Guide the agent in identifying the user's analysis intent, required biological context, accepted inputs, expected outputs, and major workflow constraints.

Inputs:
- natural-language user request
- optional project context or dataset description

Outputs:
- a normalized analysis brief
- a candidate workflow family
- recognized assumptions and missing context

### 2. Workflow Generation Skill

Purpose:
Convert the normalized analysis brief into a concrete staged workflow plan using the registry and planning rules.

Inputs:
- normalized analysis brief
- registry definitions

Outputs:
- canonical stage list
- selected tools per stage
- planning rationale

### 3. Custom Node Specification Skill

Purpose:
Describe how a selected bioinformatics tool should be represented as a future ComfyUI custom node.

Inputs:
- tool registry entry
- workflow stage requirements

Outputs:
- node name
- expected inputs and outputs
- parameter schema
- execution assumptions
- implementation notes for future Python custom node work

### 4. Workflow JSON Generation Skill

Purpose:
Transform the selected staged workflow into a ComfyUI-compatible JSON graph.

Inputs:
- workflow plan
- node catalog and graph rules

Outputs:
- workflow JSON
- node-to-stage mapping
- validation notes

## Data Contracts

### Prompt Parse Contract

The parsed request should capture at least:

- `analysis_type`
- `domain`
- `input_assets`
- `organism` when available
- `expected_outputs`
- `constraints`
- `preferred_tools`
- `confidence_notes`

### Registry Contract

Each YAML registry entry should capture at least:

- `id`
- `label`
- `domain_tags`
- `stage_tags`
- `input_types`
- `output_types`
- `language`
- `python_bindings`
- `summary`
- `selection_rules`
- `future_comfy_node`

### Workflow Plan Contract

Each workflow stage should capture:

- stage id
- stage label
- required inputs
- selected tool id
- produced outputs
- optionality
- rationale

## Tool Selection Registry Design

The registry will be a YAML document with:

- global metadata
- supported domains
- canonical stages
- tool entries
- default routing rules

For the first MVP, the registry should include representative entries for:

- `FastQC`
- `Trim Galore` or equivalent trimming tool
- `STAR` and `salmon` as alternative alignment or pseudoalignment options
- `featureCounts`
- `DESeq2`
- `MultiQC`
- `Biopython` as a utility-oriented Python dependency rather than a primary aligner

`scRNA-seq`, `metagenome`, and `WGS` should appear as tagged future domains in the registry structure, even if their end-to-end stage mappings are not yet implemented.

## ComfyUI JSON Design

The emitter should produce a ComfyUI-style graph with stable node ids, node titles, widget values, and explicit links between outputs and inputs.

For MVP purposes, the graph can use a simplified node catalog:

- `NLPromptInput`
- `WorkflowIntentParser`
- `ToolRegistryLookup`
- `StagePlanner`
- `QCNodeSpec`
- `TrimmingNodeSpec`
- `AlignmentNodeSpec`
- `QuantificationNodeSpec`
- `DifferentialExpressionNodeSpec`
- `ReportNodeSpec`
- `WorkflowJSONOutput`

These nodes are specification nodes, not full execution nodes. Their main role is to make the planned workflow visually legible inside ComfyUI.

## Error Handling

The harness should fail clearly when:

- the request cannot be mapped to a supported domain
- required input information is missing
- no tool satisfies a required stage
- the planner produces a disconnected or invalid graph

Errors should be reported as structured messages that say:

- what failed
- which stage failed
- what information or registry entry is missing

## Testing Strategy

The MVP should include:

- parser tests for representative natural-language prompts
- selector tests for registry-driven stage and tool choice
- builder tests for graph shape and required JSON fields
- golden-file style examples for generated bulk RNA-seq workflow JSON

## Implementation Notes

- Python will be the implementation language for the harness and future custom nodes.
- The project should be structured so that future ComfyUI node packages can be added without reorganizing the repository.
- The first CLI path should be simple:
  - read prompt text
  - plan workflow
  - write JSON to `harness/examples/workflows/`

## Future Expansion Path

After the MVP works for `bulk RNA-seq`, the next extensions should be:

1. `scRNA-seq`
2. `metagenome`
3. `WGS`

Those should reuse the same parser, registry, and planner abstractions rather than introducing separate ad hoc generators.
