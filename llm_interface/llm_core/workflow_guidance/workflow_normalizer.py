from __future__ import annotations


def normalize_workflow_spec(spec: dict, registry: dict) -> dict:
    nodes = spec.get("nodes", [])
    edges = spec.get("edges", [])
    valid_nodes: list[dict] = []
    id_map: dict[str, str] = {}
    seen_old_ids: set[str] = set()

    for node in nodes:
        old_id = node.get("id")
        class_type = node.get("class_type")
        if not old_id or old_id in seen_old_ids or class_type not in registry:
            continue
        seen_old_ids.add(old_id)
        new_id = f"n{len(valid_nodes) + 1}"
        id_map[old_id] = new_id
        valid_nodes.append({"id": new_id, "class_type": class_type})

    valid_outputs = {
        node["id"]: {out["name"] for out in registry[node["class_type"]].get("outputs", [])}
        for node in valid_nodes
    }
    valid_inputs = {
        node["id"]: {inp["name"] for inp in registry[node["class_type"]].get("inputs", [])}
        for node in valid_nodes
    }

    normalized_edges: list[dict] = []
    seen_edges: set[tuple[str, str]] = set()
    for edge in edges:
        from_ref = edge.get("from", "")
        to_ref = edge.get("to", "")
        if "." not in from_ref or "." not in to_ref:
            continue
        old_src, src_port = from_ref.split(".", 1)
        old_dst, dst_port = to_ref.split(".", 1)
        new_src = id_map.get(old_src)
        new_dst = id_map.get(old_dst)
        if not new_src or not new_dst:
            continue
        if src_port not in valid_outputs.get(new_src, set()) or dst_port not in valid_inputs.get(new_dst, set()):
            continue
        key = (f"{new_src}.{src_port}", f"{new_dst}.{dst_port}")
        if key in seen_edges:
            continue
        seen_edges.add(key)
        normalized_edges.append({"from": key[0], "to": key[1]})

    normalized_edges.sort(key=lambda item: (item["from"], item["to"]))
    return {
        "goal": spec.get("goal", ""),
        "nodes": valid_nodes,
        "edges": normalized_edges,
    }
