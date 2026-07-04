from dataclasses import dataclass, field


SUPPORTED_TIERS = {"REF", "ALT"}
SUPPORTED_STATUSES = {"runnable", "planned", "stubbed"}


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

    def validate(self) -> None:
        if self.tier not in SUPPORTED_TIERS:
            raise ValueError(f"Unsupported tier for {self.id}: {self.tier}")
        if self.runnable_node_status not in SUPPORTED_STATUSES:
            raise ValueError(f"Unsupported runnable status for {self.id}: {self.runnable_node_status}")
        if not self.operations:
            raise ValueError(f"Tool {self.id} must declare at least one operation.")


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

