from dataclasses import dataclass, field


SUPPORTED_TIERS = {"REF", "ALT"}
SUPPORTED_STATUSES = {"runnable", "planned", "stubbed"}
# Evidence hierarchy for tier assignment (paper.md Section 3.2.1):
# 1. primary_openebench       - backed by an ELIXIR OpenEBench/bio.tools community benchmarking
#                               challenge or adoption-frequency statistic for this exact comparison.
# 2. secondary_literature      - OpenEBench/bio.tools has no dedicated challenge for this comparison;
#                               backed by a specific cited benchmark paper instead.
# 3. not_applicable_internal_node - this entry is a ComfyBIO-authored glue/reporting/validation
#                               node (or a bespoke parameter step) with no competing external
#                               algorithm to benchmark against — there was never a REF-vs-ALT
#                               choice to justify, so no citation is owed. Distinct from
#                               pending_citation_review: this is a permanent classification, not
#                               a to-do.
# 4. pending_citation_review  - a real REF-vs-ALT choice between external tools whose
#                               tier_rationale is written but not yet backed by a verified
#                               citation from tier 1 or 2 above.
SUPPORTED_EVIDENCE_TIERS = {
    "primary_openebench",
    "secondary_literature",
    "not_applicable_internal_node",
    "pending_citation_review",
}


@dataclass(frozen=True)
class Operation:
    id: str
    label: str
    input_types: list[str]
    output_types: list[str]
    node_type: str


@dataclass(frozen=True)
class ToolEntry:
    id: str
    label: str
    domain_tags: list[str]
    stage_tags: list[str]
    input_types: list[str]
    output_types: list[str]
    language: str
    python_bindings: list[str]
    summary: str
    tier: str
    tier_rationale: str
    context_routing_rules: list[str]
    applicability_constraints: list[str]
    selection_rules: list[str]
    operations: list[Operation]
    future_comfy_node: str
    runnable_node_status: str
    evidence_tier: str = "pending_citation_review"
    evidence_citation: str = ""

    def validate(self) -> None:
        if self.tier not in SUPPORTED_TIERS:
            raise ValueError(f"Unsupported tier for {self.id}: {self.tier}")
        if self.runnable_node_status not in SUPPORTED_STATUSES:
            raise ValueError(f"Unsupported runnable status for {self.id}: {self.runnable_node_status}")
        if not self.operations:
            raise ValueError(f"Tool {self.id} must declare at least one operation.")
        if self.evidence_tier not in SUPPORTED_EVIDENCE_TIERS:
            raise ValueError(f"Unsupported evidence_tier for {self.id}: {self.evidence_tier}")


@dataclass(frozen=True)
class RouteStage:
    stage_id: str
    stage_label: str
    tool_id: str
    operation_id: str
    optional: bool = False


@dataclass(frozen=True)
class ToolRegistry:
    metadata: dict[str, str]
    supported_domains: list[str]
    routes: dict[str, list[RouteStage]]
    tools: list[ToolEntry] = field(default_factory=list)
    domain_routes: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for tool in self.tools:
            tool.validate()

    def tool_by_id(self, tool_id: str) -> ToolEntry:
        for tool in self.tools:
            if tool.id == tool_id:
                return tool
        raise KeyError(f"Unknown tool id: {tool_id}")

    def official_route(self, route_id: str) -> list[RouteStage]:
        if route_id not in self.routes:
            raise KeyError(f"Unknown route id: {route_id}")
        return self.routes[route_id]

    def route_id_for_domain(self, domain: str) -> str:
        try:
            return self.domain_routes[domain]
        except KeyError as error:
            raise KeyError(f"Unsupported workflow domain: {domain}") from error

