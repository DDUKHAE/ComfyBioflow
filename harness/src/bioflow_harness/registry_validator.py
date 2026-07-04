from dataclasses import dataclass

from bioflow_harness.comfy.node_catalog import NodeDefinition
from bioflow_harness.models.registry_contract import ToolRegistry


class RegistryValidationError(ValueError):
    pass


@dataclass(frozen=True)
class RegistryValidationReport:
    route_id: str
    stage_count: int
    tool_ids: list[str]
    node_types: list[str]


def validate_official_route(
    registry: ToolRegistry,
    route_id: str,
    node_catalog: dict[str, NodeDefinition],
) -> RegistryValidationReport:
    tool_ids: list[str] = []
    node_types: list[str] = []
    seen_stage_ids: set[str] = set()

    for stage in registry.official_route(route_id):
        if stage.stage_id in seen_stage_ids:
            raise RegistryValidationError(f"Duplicate stage_id in official route: {stage.stage_id}")
        seen_stage_ids.add(stage.stage_id)

        try:
            tool = registry.tool_by_id(stage.tool_id)
        except KeyError as error:
            raise RegistryValidationError(f"Official route references unknown tool_id: {stage.tool_id}") from error

        if tool.tier != "REF":
            raise RegistryValidationError(f"Official route tool must be REF: {tool.id} has {tool.tier}")
        if tool.runnable_node_status != "runnable":
            raise RegistryValidationError(
                f"Official route tool must be runnable: {tool.id} has {tool.runnable_node_status}"
            )

        matching_operations = [operation for operation in tool.operations if operation.id == stage.operation_id]
        if not matching_operations:
            raise RegistryValidationError(
                f"Official route stage {stage.stage_id} references missing operation {stage.operation_id} on tool {tool.id}"
            )

        operation = matching_operations[0]
        if operation.node_type not in node_catalog:
            raise RegistryValidationError(
                f"Operation {operation.id} references node type missing from node catalog: {operation.node_type}"
            )
        if tool.future_comfy_node != operation.node_type:
            raise RegistryValidationError(
                f"Tool {tool.id} future_comfy_node {tool.future_comfy_node} does not match operation node type {operation.node_type}"
            )
        if not operation.input_types or not operation.output_types:
            raise RegistryValidationError(f"Operation {operation.id} must declare input and output artifact types.")

        tool_ids.append(tool.id)
        node_types.append(operation.node_type)

    return RegistryValidationReport(
        route_id=route_id,
        stage_count=len(tool_ids),
        tool_ids=tool_ids,
        node_types=node_types,
    )
