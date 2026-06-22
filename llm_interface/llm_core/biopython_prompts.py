"""
biopython_prompts.py — LLM prompt builder for Biopython workflow generation.
Loads node_registry.json and builds a compact catalog string for the LLM.
"""
from __future__ import annotations
import json
from functools import lru_cache
from pathlib import Path

REGISTRY_PATH = Path(__file__).resolve().parent / "node_registry.json"

_TYPE_ABBREV = {
    "STRING":  "S",
    "INT":     "I",
    "FLOAT":   "F",
    "BOOLEAN": "B",
    "COMBO":   "C",
}


@lru_cache(maxsize=1)
def _load_registry() -> dict:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def build_node_catalog(registry: dict | None = None) -> str:
    """
    Return a compact multi-line catalog string grouped by category.

    Each line:  NodeClassName: in[name:T,...] out[name:T,...]
    where T is S/I/F/B/C.
    """
    if registry is None:
        registry = _load_registry()

    by_cat: dict[str, list[str]] = {}
    for node_id, info in registry.items():
        cat = info.get("category", "Biopython/Other")
        ins  = ",".join(
            f"{i['name']}:{_TYPE_ABBREV.get(i['type'], 'S')}"
            for i in info.get("inputs", [])
        )
        outs = ",".join(
            f"{o['name']}:{_TYPE_ABBREV.get(o['type'], 'S')}"
            for o in info.get("outputs", [])
        )
        by_cat.setdefault(cat, []).append(f"  {node_id}: in[{ins}] out[{outs}]")

    lines: list[str] = []
    for cat in sorted(by_cat):
        lines.append(f"### {cat}")
        lines.extend(sorted(by_cat[cat]))
        lines.append("")

    return "\n".join(lines)


def get_biopython_workflow_prompt(
    goal: str,
    input_path: str = "",
    output_dir: str = "./output",
    similar_workflow: dict | None = None,
) -> str:
    catalog = build_node_catalog()
    input_note = input_path if input_path else "(not specified — user will set in the GUI)"
    reuse_note = ""
    if similar_workflow:
        previous_spec = similar_workflow.get("workflow_spec")
        if previous_spec:
            previous_query = similar_workflow.get("query", "")
            similarity = similar_workflow.get("similarity", 0)
            spec_json = json.dumps(previous_spec, ensure_ascii=False, indent=2)
            reuse_note = f"""

## Similar Prior Workflow
A previous successful workflow may be relevant. Use it only as a starting point; fix or adapt it to satisfy the current user request exactly.
Previous request: {previous_query}
Similarity score: {similarity}
Previous canonical workflow spec:
{spec_json}
"""

    return f"""You are a Biopython workflow designer for ComfyUI.

Given the user's analysis goal, select the minimum set of Biopython nodes that accomplish it and connect them in the correct data-flow order.

## Available Nodes
Type legend: S=STRING  I=INT  F=FLOAT  B=BOOLEAN  C=COMBO

Biopython objects (SeqRecord, Alignment, BLAST result, etc.) are serialised as STRING.
Connect them S→S.  Parameter inputs (COMBO, BOOLEAN, INT, FLOAT) are set by the user in the GUI — do NOT wire them unless a numeric result from one node is genuinely needed as a parameter in another.

{catalog}

## Connection Rules
1. Only connect output→input when types match exactly (S→S, I→I, F→F).
2. Only add an edge when the data produced by one node is directly consumed by another.
3. Use the minimum number of nodes needed.  Do not add display or summary nodes unless the goal requires them.
4. First node in a chain: use a node whose inputs include a file/source path (is_input_node).
5. Last node in a chain: ideally a node that writes output to a file (is_output_node), unless the goal is purely in-memory analysis.
6. Prefer standard Biopython analysis flows over unusual detours.
7. Avoid decorative, redundant, or disconnected nodes.

## Output Format
Return ONLY a valid JSON object — no markdown fences, no explanation:
{{
  "goal": "<one-line description of what this workflow does>",
  "nodes": [
    {{"id": "n1", "class_type": "<ExactNodeClassName>"}},
    {{"id": "n2", "class_type": "<ExactNodeClassName>"}}
  ],
  "edges": [
    {{"from": "n1.<output_port_name>", "to": "n2.<input_port_name>"}}
  ]
}}

Additional rules:
- Node IDs MUST be "n1", "n2", "n3", … in sequential order.
- class_type MUST exactly match a name from the catalog above.
- Port names in edges MUST exactly match names shown in in[…] / out[…].
- Include only edges where data actually flows.{reuse_note}

## User Request
Goal       : {goal}
Input file : {input_note}
Output dir : {output_dir}
"""
