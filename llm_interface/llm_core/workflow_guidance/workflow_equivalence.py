from __future__ import annotations


def _class_edges(spec: dict) -> set[tuple[str, str, str, str]]:
    class_by_id = {node["id"]: node["class_type"] for node in spec.get("nodes", [])}
    result: set[tuple[str, str, str, str]] = set()
    for edge in spec.get("edges", []):
        from_ref = edge.get("from", "")
        to_ref = edge.get("to", "")
        if "." not in from_ref or "." not in to_ref:
            continue
        src_id, src_port = from_ref.split(".", 1)
        dst_id, dst_port = to_ref.split(".", 1)
        src_class = class_by_id.get(src_id)
        dst_class = class_by_id.get(dst_id)
        if src_class and dst_class:
            result.add((src_class, src_port, dst_class, dst_port))
    return result


def score_workflow_against_template(spec: dict, template: dict) -> dict:
    required_nodes = set(template.get("required_nodes", []))
    optional_nodes = set(template.get("optional_nodes", []))
    forbidden_nodes = set(template.get("forbidden_nodes", []))
    spec_nodes = [node["class_type"] for node in spec.get("nodes", [])]
    spec_node_set = set(spec_nodes)

    required_edges = {
        (
            item["from_class"],
            item["from_port"],
            item["to_class"],
            item["to_port"],
        )
        for item in template.get("required_edges", [])
    }
    spec_edges = _class_edges(spec)

    missing_nodes = sorted(required_nodes - spec_node_set)
    missing_edges = sorted(required_edges - spec_edges)
    extra_nodes = sorted(node for node in spec_node_set if node not in required_nodes and node not in optional_nodes)
    extra_edges = sorted(spec_edges - required_edges)
    forbidden_hits = sorted(spec_node_set & forbidden_nodes)

    node_score = 1.0 if not required_nodes else 1.0 - (len(missing_nodes) / len(required_nodes))
    edge_score = 1.0 if not required_edges else 1.0 - (len(missing_edges) / len(required_edges))
    penalty = min(0.55, (len(extra_nodes) * 0.1) + (len(extra_edges) * 0.1) + (len(forbidden_hits) * 0.2))
    score = max(0.0, round((node_score * 0.4) + (edge_score * 0.6) - penalty, 4))

    return {
        "score": score,
        "missing_nodes": missing_nodes,
        "missing_edges": [
            {
                "from_class": src_class,
                "from_port": src_port,
                "to_class": dst_class,
                "to_port": dst_port,
            }
            for src_class, src_port, dst_class, dst_port in missing_edges
        ],
        "extra_nodes": extra_nodes,
        "extra_edges": [
            {
                "from_class": src_class,
                "from_port": src_port,
                "to_class": dst_class,
                "to_port": dst_port,
            }
            for src_class, src_port, dst_class, dst_port in extra_edges
        ],
        "forbidden_nodes": forbidden_hits,
    }
