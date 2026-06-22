from __future__ import annotations

from llm_core.workflow_guidance.workflow_equivalence import score_workflow_against_template
from llm_core.workflow_guidance.workflow_normalizer import normalize_workflow_spec


def _next_node_id(nodes: list[dict]) -> str:
    return f"n{len(nodes) + 1}"


def repair_workflow_spec(spec: dict, template: dict, registry: dict) -> tuple[dict, dict]:
    repaired = {
        "goal": spec.get("goal", ""),
        "nodes": [dict(node) for node in spec.get("nodes", [])],
        "edges": [dict(edge) for edge in spec.get("edges", [])],
    }
    summary: list[str] = []
    actions: list[dict[str, str]] = []

    allowed_nodes = set(template.get("required_nodes", [])) | set(template.get("optional_nodes", []))
    forbidden_nodes = set(template.get("forbidden_nodes", []))
    before_nodes = list(repaired["nodes"])
    repaired["nodes"] = [
        node for node in repaired["nodes"]
        if node.get("class_type") in allowed_nodes and node.get("class_type") not in forbidden_nodes
    ]
    removed_nodes = [node["class_type"] for node in before_nodes if node not in repaired["nodes"]]
    if removed_nodes:
        summary.append(f"removed extra nodes: {', '.join(removed_nodes)}")
        for class_type in removed_nodes:
            actions.append({"action": "removed_extra_node", "class_type": class_type})

    class_to_node_id = {node["class_type"]: node["id"] for node in repaired["nodes"]}
    for missing_class in template.get("required_nodes", []):
        if missing_class in class_to_node_id or missing_class not in registry:
            continue
        new_id = _next_node_id(repaired["nodes"])
        repaired["nodes"].append({"id": new_id, "class_type": missing_class})
        class_to_node_id[missing_class] = new_id
        summary.append(f"added required node: {missing_class}")
        actions.append({"action": "added_required_node", "class_type": missing_class})

    edge_set = {(edge["from"], edge["to"]) for edge in repaired["edges"]}
    for required_edge in template.get("required_edges", []):
        src_class = required_edge["from_class"]
        dst_class = required_edge["to_class"]
        src_id = class_to_node_id.get(src_class)
        dst_id = class_to_node_id.get(dst_class)
        if not src_id or not dst_id:
            continue
        edge = (f"{src_id}.{required_edge['from_port']}", f"{dst_id}.{required_edge['to_port']}")
        if edge in edge_set:
            continue
        repaired["edges"].append({"from": edge[0], "to": edge[1]})
        edge_set.add(edge)
        summary.append(f"added required edge: {edge[0]} -> {edge[1]}")
        actions.append({"action": "added_required_edge", "from": edge[0], "to": edge[1]})

    repaired = normalize_workflow_spec(repaired, registry)
    score = score_workflow_against_template(repaired, template)
    return repaired, {
        "repair_applied": bool(summary),
        "repair_summary": summary,
        "repair_actions": actions,
        "equivalence_score": score["score"],
    }
