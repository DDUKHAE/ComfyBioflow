import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from bioflow_harness.comfy.node_catalog import NodeDefinition
from bioflow_harness.models.registry_contract import ToolRegistry
from bioflow_harness.registry_validator import RegistryValidationError, RegistryValidationReport, validate_official_route


@dataclass(frozen=True)
class DomainPromotionReport:
    route_id: str
    ready: bool
    stub_node_types: list[str]
    route_report: RegistryValidationReport | None
    error: str | None


def check_domain_promotion(
    registry: ToolRegistry,
    route_id: str,
    node_catalog: dict[str, NodeDefinition],
    node_class_mappings: dict[str, type],
) -> DomainPromotionReport:
    try:
        route_report = validate_official_route(registry, route_id, node_catalog)
    except (RegistryValidationError, KeyError) as error:
        return DomainPromotionReport(route_id=route_id, ready=False, stub_node_types=[], route_report=None, error=str(error))

    stub_node_types = [
        node_type
        for node_type in route_report.node_types
        if node_type not in node_class_mappings or "run" not in vars(node_class_mappings[node_type])
    ]

    return DomainPromotionReport(
        route_id=route_id,
        ready=not stub_node_types,
        stub_node_types=stub_node_types,
        route_report=route_report,
        error=None,
    )


def main() -> None:
    import nodes
    from bioflow_harness.comfy.node_catalog import default_node_catalog
    from bioflow_harness.planner.tool_selector import load_registry

    parser = argparse.ArgumentParser(description="Gate a domain's promotion from planned_domains to supported_domains.")
    parser.add_argument("--route-id", required=True)
    parser.add_argument("--registry", type=Path, default=Path("harness/registry/tool_selection_registry.yaml"))
    args = parser.parse_args()

    report = check_domain_promotion(
        load_registry(args.registry), args.route_id, default_node_catalog(), nodes.NODE_CLASS_MAPPINGS
    )
    print(json.dumps(asdict(report), indent=2))
    raise SystemExit(0 if report.ready else 1)


if __name__ == "__main__":
    main()
