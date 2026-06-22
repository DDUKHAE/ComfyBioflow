import json


class LLMContractError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def extract_json_blocks(text: str) -> list[dict]:
    candidates = []
    n = len(text)
    i = 0
    while i < n:
        if text[i] == '{':
            bracket_count = 0
            in_string = False
            escape = False
            for j in range(i, n):
                char = text[j]
                if escape:
                    escape = False
                    continue
                if char == '\\':
                    escape = True
                    continue
                if char == '"':
                    in_string = not in_string
                    continue
                if not in_string:
                    if char == '{':
                        bracket_count += 1
                    elif char == '}':
                        bracket_count -= 1
                        if bracket_count == 0:
                            sub = text[i:j+1]
                            try:
                                obj = json.loads(sub)
                                if isinstance(obj, dict):
                                    candidates.append(obj)
                            except json.JSONDecodeError:
                                pass
                            i = j
                            break
            else:
                break
        i += 1
    return candidates


def validate_biopython_workflow_spec_schema(spec: dict) -> None:
    if not isinstance(spec, dict):
        raise LLMContractError("invalid_schema", "Biopython workflow spec must be a JSON object")

    missing = [k for k in ("goal", "nodes", "edges") if k not in spec]
    if missing:
        raise LLMContractError(
            "missing_required_keys",
            f"Biopython workflow spec missing required keys: {', '.join(missing)}"
        )

    if not isinstance(spec["nodes"], list) or not spec["nodes"]:
        raise LLMContractError("invalid_schema", "'nodes' must be a non-empty list")
    if not isinstance(spec["edges"], list):
        raise LLMContractError("invalid_schema", "'edges' must be a list")

    seen_node_ids: set[str] = set()
    for i, node in enumerate(spec["nodes"]):
        if not isinstance(node, dict):
            raise LLMContractError("invalid_schema", f"nodes[{i}] must be a dict")
        for field in ("id", "class_type"):
            if field not in node:
                raise LLMContractError("invalid_schema", f"nodes[{i}] missing field '{field}'")
        if not node["id"] or not node["class_type"]:
            raise LLMContractError("invalid_schema", f"nodes[{i}] has empty id or class_type")
        if node["id"] in seen_node_ids:
            raise LLMContractError("invalid_schema", f"Duplicate node id: {node['id']}")
        seen_node_ids.add(node["id"])

    for i, edge in enumerate(spec["edges"]):
        if not isinstance(edge, dict):
            raise LLMContractError("invalid_schema", f"edges[{i}] must be a dict")
        for field in ("from", "to"):
            if field not in edge:
                raise LLMContractError("invalid_schema", f"edges[{i}] missing field '{field}'")
            if "." not in edge[field]:
                raise LLMContractError(
                    "invalid_schema",
                    f"edges[{i}].{field} must be 'nodeId.portName', got: {edge[field]!r}"
                )


def parse_and_validate_llm_output(text: str, expected_type: str = None) -> tuple[str, dict]:
    if not text or not text.strip():
        raise LLMContractError("empty_output", "LLM output is empty")

    stripped = text.strip()
    if stripped and stripped[-1] not in ["}", "]", ".", '"']:
        opened_braces = text.count("{") - text.count("}")
        if opened_braces > 0:
            raise LLMContractError("partial_output", "LLM output appears to be truncated or incomplete")

    candidates = extract_json_blocks(text)

    if not candidates:
        raise LLMContractError("invalid_json", "No valid JSON object could be extracted from LLM output")

    valid: list[dict] = []
    for cand in candidates:
        try:
            validate_biopython_workflow_spec_schema(cand)
            valid.append(cand)
        except LLMContractError:
            pass

    if expected_type == "biopython_workflow_spec":
        if len(valid) == 1:
            return "biopython_workflow_spec", valid[0]
        if len(valid) > 1:
            raise LLMContractError("ambiguous_json_output", "Multiple valid biopython workflow spec blocks found")
        validate_biopython_workflow_spec_schema(candidates[0])

    if valid:
        return "biopython_workflow_spec", valid[0]

    validate_biopython_workflow_spec_schema(candidates[0])
