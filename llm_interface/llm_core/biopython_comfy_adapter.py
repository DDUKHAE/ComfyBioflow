"""
biopython_comfy_adapter.py — Convert LLM-generated canonical spec to ComfyUI workflow JSON.

Canonical spec format (from LLM):
{
  "goal": "...",
  "nodes": [{"id": "n1", "class_type": "SeqIO_parse"}, ...],
  "edges": [{"from": "n1.records", "to": "n2.source"}, ...]
}

ComfyUI workflow JSON format:
{
  "last_node_id": N,
  "last_link_id": M,
  "nodes": [...],
  "links": [[link_id, src_num, src_slot, tgt_num, tgt_slot, type], ...],
  ...
}
"""
from __future__ import annotations
import json
from functools import lru_cache
from pathlib import Path

REGISTRY_PATH = Path(__file__).resolve().parent / "node_registry.json"

# Inputs that carry file paths and should be auto-filled
_SRC_INPUT_NAMES  = {"source", "file_path", "input_path"}
_DST_INPUT_NAMES  = {"output_path", "output_file"}

# Nodes per row in the canvas layout
_COLS = 5
_COL_GAP = 340
_ROW_GAP = 280
_ORIGIN_X = 80
_ORIGIN_Y = 100


@lru_cache(maxsize=1)
def load_registry() -> dict:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def canonical_to_comfy_json(
    spec: dict,
    registry: dict | None = None,
    input_path: str = "",
    output_dir: str = "./output",
) -> dict:
    """
    Convert a canonical Biopython workflow spec into a ComfyUI-loadable JSON dict.

    Args:
        spec        : LLM-generated canonical spec (nodes + edges).
        registry    : Node registry dict (loaded from node_registry.json if None).
        input_path  : Source file path to auto-fill on is_input_node nodes.
        output_dir  : Output directory to auto-fill on is_output_node nodes.
    """
    if registry is None:
        registry = load_registry()

    nodes_spec: list[dict] = spec.get("nodes", [])
    edges_spec: list[dict] = spec.get("edges", [])

    # Map canonical node id ("n1") → ComfyUI numeric id (1)
    id_map: dict[str, int] = {n["id"]: i + 1 for i, n in enumerate(nodes_spec)}

    # ── Build links ──────────────────────────────────────────────────────────
    # connected_inputs : (canonical_node_id, input_name)  → link_id
    connected_inputs: dict[tuple[str, str], int] = {}
    # output_link_map  : (canonical_node_id, output_slot)  → [link_ids]
    output_link_map: dict[tuple[str, int], list[int]] = {}
    links: list[list] = []
    link_counter = 1

    for edge in edges_spec:
        from_str: str = edge.get("from", "")
        to_str: str   = edge.get("to", "")
        if "." not in from_str or "." not in to_str:
            continue

        src_nid, src_out_name = from_str.split(".", 1)
        tgt_nid, tgt_in_name  = to_str.split(".", 1)

        src_num = id_map.get(src_nid)
        tgt_num = id_map.get(tgt_nid)
        if not src_num or not tgt_num:
            continue

        src_class = next((n["class_type"] for n in nodes_spec if n["id"] == src_nid), None)
        tgt_class = next((n["class_type"] for n in nodes_spec if n["id"] == tgt_nid), None)

        src_outputs = registry.get(src_class, {}).get("outputs", [])
        tgt_inputs  = registry.get(tgt_class, {}).get("inputs", [])

        src_slot = next((i for i, o in enumerate(src_outputs) if o["name"] == src_out_name), 0)
        tgt_slot = next((i for i, inp in enumerate(tgt_inputs) if inp["name"] == tgt_in_name), 0)

        link_type = src_outputs[src_slot]["type"] if src_slot < len(src_outputs) else "STRING"

        link_id = link_counter
        link_counter += 1

        # [link_id, src_num, src_slot, tgt_num, tgt_slot, type]
        links.append([link_id, src_num, src_slot, tgt_num, tgt_slot, link_type])
        connected_inputs[(tgt_nid, tgt_in_name)] = link_id
        output_link_map.setdefault((src_nid, src_slot), []).append(link_id)

    # ── Build ComfyUI nodes ───────────────────────────────────────────────────
    comfy_nodes: list[dict] = []

    for idx, node_spec in enumerate(nodes_spec):
        nid        = node_spec["id"]
        class_type = node_spec["class_type"]
        num        = id_map[nid]
        schema     = registry.get(class_type, {})
        all_inputs  = schema.get("inputs", [])
        all_outputs = schema.get("outputs", [])

        # inputs: all schema inputs; connected ones carry a link_id
        comfy_inputs = [
            {
                "name": inp["name"],
                "type": inp["type"],
                "link": connected_inputs.get((nid, inp["name"])),
            }
            for inp in all_inputs
        ]

        # widgets_values: default value for every non-connected input (schema order)
        widgets_values: list = []
        for inp in all_inputs:
            if (nid, inp["name"]) in connected_inputs:
                continue  # value comes from a link, not a widget
            val = inp.get("default", "")
            # Auto-fill source path on read nodes
            if (
                schema.get("is_input_node")
                and inp["name"] in _SRC_INPUT_NAMES
                and input_path
            ):
                val = input_path
            # Auto-fill destination path on write nodes
            elif (
                schema.get("is_output_node")
                and inp["name"] in _DST_INPUT_NAMES
                and output_dir
            ):
                val = f"{output_dir.rstrip('/')}/{class_type}_output"
            widgets_values.append(val)

        # outputs: attach link_ids from edges
        comfy_outputs = [
            {
                "name": out["name"],
                "type": out["type"],
                "links": output_link_map.get((nid, slot), []),
                "slot_index": slot,
            }
            for slot, out in enumerate(all_outputs)
        ]

        # Canvas position: snake layout
        col = idx % _COLS
        row = idx // _COLS
        pos_x = _ORIGIN_X + col * _COL_GAP
        pos_y = _ORIGIN_Y + row * _ROW_GAP
        node_h = max(150, 60 + len(all_inputs) * 22 + len(all_outputs) * 22)

        comfy_nodes.append({
            "id": num,
            "type": class_type,
            "pos": [pos_x, pos_y],
            "size": [280, node_h],
            "flags": {},
            "order": idx,
            "mode": 0,
            "inputs": comfy_inputs,
            "outputs": comfy_outputs,
            "properties": {"node_id": nid},
            "widgets_values": widgets_values,
        })

    return {
        "last_node_id": len(comfy_nodes),
        "last_link_id": len(links),
        "nodes": comfy_nodes,
        "links": links,
        "groups": [],
        "config": {},
        "extra": {"comfybio_biopython_spec": spec},
        "version": 0.4,
    }
