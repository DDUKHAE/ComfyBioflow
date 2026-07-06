# Domain Expansion Workflow

ComfyBIO currently has one runnable supported domain: `bulk_rna_seq`.

Domains that are not implemented must not be silently routed to an existing workflow. When a prompt asks for a planned or unmodeled domain, the harness should stop workflow generation and return a `planning_required` response.

## Required Flow

Before a new domain can generate workflow JSON, complete these steps:

1. Domain exploration
   - define the biological analysis goal
   - identify common input assets, metadata, and expected outputs
   - list candidate tools and accepted analysis patterns
   - record uncertainty and unsupported assumptions

2. Workflow design
   - define canonical stages
   - define artifact contracts between stages
   - choose REF and ALT routes
   - decide which outputs prove the workflow is successful

3. Registry update
   - add a route under `routes`
   - add tool entries with domain tags, tier rationale, operation contracts, and node types
   - keep planned or stubbed tools out of runnable REF routes

4. Node implementation
   - implement ComfyBIO custom nodes for each required operation
   - register node classes
   - add input widgets, output types, and `extra_command` behavior where applicable

5. Validation
   - add fixtures
   - add workflow JSON schema tests
   - add domain-readiness audit rules
   - verify generated workflow JSON opens in ComfyUI and exposes meaningful node parameters

Only after those steps should the domain move from `planned_domains` to `supported_domains`.

## Planned-Domain Behavior

A planned domain prompt should produce a machine-readable response like:

```json
{
  "status": "planning_required",
  "domain": "scrna_seq",
  "route_id": null,
  "next_steps": [
    "create a domain exploration document",
    "design the workflow stages and artifact contract",
    "add registry route and tool entries",
    "implement and register ComfyBIO nodes",
    "add fixtures, validation rules, and workflow generation tests"
  ]
}
```

This response is the correct behavior until the domain has an implemented route and registered nodes.
