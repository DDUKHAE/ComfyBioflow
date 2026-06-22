from __future__ import annotations

from pathlib import Path
from typing import Any

from llm_core.biopython_comfy_adapter import load_registry
from llm_core.workflow_guidance.template_registry import list_templates
from llm_core.workflow_guidance.workflow_equivalence import score_workflow_against_template
from llm_core.workflow_guidance.workflow_repair import repair_workflow_spec


def _build_exact_spec(template: dict[str, Any]) -> dict[str, Any]:
    required_nodes = template.get("required_nodes", [])
    nodes = [{"id": f"n{i + 1}", "class_type": class_type} for i, class_type in enumerate(required_nodes)]
    class_to_id = {node["class_type"]: node["id"] for node in nodes}
    edges = [
        {
            "from": f"{class_to_id[item['from_class']]}.{item['from_port']}",
            "to": f"{class_to_id[item['to_class']]}.{item['to_port']}",
        }
        for item in template.get("required_edges", [])
        if item["from_class"] in class_to_id and item["to_class"] in class_to_id
    ]
    return {"goal": template.get("intent", ""), "nodes": nodes, "edges": edges}


def _build_missing_edge_spec(exact_spec: dict[str, Any]) -> dict[str, Any]:
    edges = list(exact_spec.get("edges", []))
    if edges:
        edges = edges[:-1]
    return {"goal": exact_spec.get("goal", ""), "nodes": list(exact_spec.get("nodes", [])), "edges": edges}


def _build_extra_node_spec(template: dict[str, Any], exact_spec: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
    nodes = list(exact_spec.get("nodes", []))
    edges = list(exact_spec.get("edges", []))
    candidate = None
    disallowed = set(template.get("required_nodes", [])) | set(template.get("optional_nodes", [])) | set(template.get("forbidden_nodes", []))
    for class_type in sorted(registry):
        if class_type not in disallowed:
            candidate = class_type
            break
    if candidate:
        nodes.append({"id": f"n{len(nodes) + 1}", "class_type": candidate})
    return {"goal": exact_spec.get("goal", ""), "nodes": nodes, "edges": edges}


def compute_template_benchmark(template: dict[str, Any], registry: dict[str, Any] | None = None) -> dict[str, Any]:
    if registry is None:
        registry = load_registry()

    exact_spec = _build_exact_spec(template)
    missing_edge_spec = _build_missing_edge_spec(exact_spec)
    extra_node_spec = _build_extra_node_spec(template, exact_spec, registry)
    repaired_spec, repair_meta = repair_workflow_spec(extra_node_spec, template, registry)

    exact_score = score_workflow_against_template(exact_spec, template)["score"]
    missing_edge_score = score_workflow_against_template(missing_edge_spec, template)["score"]
    extra_node_score = score_workflow_against_template(extra_node_spec, template)["score"]
    repaired_score = score_workflow_against_template(repaired_spec, template)["score"]
    covered_categories = sorted({registry[class_type].get("category", "") for class_type in template.get("required_nodes", []) if class_type in registry})

    return {
        "template_id": template["template_id"],
        "intent": template["intent"],
        "covered_category": ", ".join(category for category in covered_categories if category),
        "required_node_count": len(template.get("required_nodes", [])),
        "required_edge_count": len(template.get("required_edges", [])),
        "optional_node_count": len(template.get("optional_nodes", [])),
        "exact_score": round(exact_score, 4),
        "missing_edge_score": round(missing_edge_score, 4),
        "extra_node_score": round(extra_node_score, 4),
        "repaired_score": round(repaired_score, 4),
        "repair_applied": bool(repair_meta.get("repair_applied", False)),
        "repair_summary": repair_meta.get("repair_summary", []),
        "repair_actions": repair_meta.get("repair_actions", []),
    }


def render_template_benchmark_markdown(rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Template Coverage and Quality Benchmark",
        "",
        "| template_id | intent | category | req_nodes | req_edges | opt_nodes | exact | missing_edge | extra_node | repaired | repair_applied |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['template_id']} | {row['intent']} | {row['covered_category']} | {row['required_node_count']} | {row['required_edge_count']} | {row['optional_node_count']} | {row['exact_score']:.2f} | {row['missing_edge_score']:.2f} | {row['extra_node_score']:.2f} | {row['repaired_score']:.2f} | {str(row['repair_applied']).lower()} |"
        )
    lines.extend([
        "",
        "## Notes",
        "",
        "- `exact`: score for the synthetic canonical spec built from required nodes/edges.",
        "- `missing_edge`: score after removing one required edge when available.",
        "- `extra_node`: score after injecting one non-template node.",
        "- `repaired`: score after running `repair_workflow_spec()` on the extra-node case.",
    ])
    return "\n".join(lines) + "\n"


def write_template_benchmark_report(output_path: str | Path) -> Path:
    registry = load_registry()
    rows = [compute_template_benchmark(template, registry) for template in list_templates()]
    rows.sort(key=lambda item: item["template_id"])
    out = Path(output_path)
    out.write_text(render_template_benchmark_markdown(rows), encoding="utf-8")
    return out
