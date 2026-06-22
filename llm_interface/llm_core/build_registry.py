"""
build_registry.py — parse py/*.py and emit node_registry.json

Usage:
    python build_registry.py
    python build_registry.py --py-dir /path/to/py --out /path/to/node_registry.json
"""
from __future__ import annotations
import ast
import json
import argparse
from pathlib import Path

PY_DIR = Path(__file__).resolve().parent.parent.parent / "py"
OUT_FILE = Path(__file__).resolve().parent / "node_registry.json"

_TYPE_MAP = {
    "String": "STRING",
    "Int": "INT",
    "Float": "FLOAT",
    "Boolean": "BOOLEAN",
    "Combo": "COMBO",
}


def _detect_io_flags(inputs: list[dict], outputs: list[dict]) -> tuple[bool, bool]:
    """
    Determine if a node needs an input file path (is_input_node) or
    writes to an output file path (is_output_node).

    Rules:
    - is_input_node : has 'source' or 'input_path' input
                      OR has 'file_path' input but NOT 'file_path' in outputs
                      (i.e. file_path is the source, not the destination)
    - is_output_node: has 'output_path' or 'output_file' input
                      OR has 'file_path' input AND 'file_path' in outputs
                      (i.e. file_path is the write destination)
    """
    in_names  = {i["name"] for i in inputs}
    out_names = {o["name"] for o in outputs}

    is_input = (
        "source"     in in_names or
        "input_path" in in_names or
        ("file_path" in in_names and "file_path" not in out_names)
    )
    is_output = (
        "output_path" in in_names or
        "output_file" in in_names or
        ("file_path" in in_names and "file_path" in out_names)
    )
    return is_input, is_output


def _get_str(node: ast.expr) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _get_default(node: ast.expr) -> object:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        if isinstance(node.operand, ast.Constant):
            return -node.operand.value
    if isinstance(node, ast.List):
        return [_get_default(e) for e in node.elts]
    return None


def _parse_io_call(call: ast.Call) -> dict | None:
    """Parse a single io.TYPE.Input(name, ...) or io.TYPE.Output(name) call."""
    func = call.func
    if not isinstance(func, ast.Attribute):
        return None

    method_name = func.attr  # "Input" or "Output"
    if method_name not in ("Input", "Output"):
        return None

    type_node = func.value
    if not isinstance(type_node, ast.Attribute):
        return None

    registry_type = _TYPE_MAP.get(type_node.attr, "STRING")

    if not call.args:
        return None
    name = _get_str(call.args[0])
    if name is None:
        return None

    entry: dict = {"name": name, "type": registry_type}

    if method_name == "Input":
        for kw in call.keywords:
            if kw.arg == "default":
                val = _get_default(kw.value)
                if val is not None:
                    entry["default"] = val
                break
        # Fallback defaults by type
        if "default" not in entry:
            entry["default"] = {
                "STRING": "",
                "INT": 0,
                "FLOAT": 0.0,
                "BOOLEAN": False,
                "COMBO": "",
            }.get(registry_type, "")

    return entry


def _parse_schema_call(call: ast.Call) -> dict | None:
    """Parse io.Schema(...) and return structured node info dict."""
    info: dict = {}

    for kw in call.keywords:
        if kw.arg == "node_id":
            info["node_id"] = _get_str(kw.value)
        elif kw.arg == "display_name":
            info["display_name"] = _get_str(kw.value)
        elif kw.arg == "category":
            info["category"] = _get_str(kw.value)
        elif kw.arg == "inputs":
            inputs = []
            if isinstance(kw.value, ast.List):
                for elt in kw.value.elts:
                    if isinstance(elt, ast.Call):
                        parsed = _parse_io_call(elt)
                        if parsed:
                            inputs.append(parsed)
            info["inputs"] = inputs
        elif kw.arg == "outputs":
            outputs = []
            if isinstance(kw.value, ast.List):
                for elt in kw.value.elts:
                    if isinstance(elt, ast.Call):
                        parsed = _parse_io_call(elt)
                        if parsed:
                            outputs.append(parsed)
            info["outputs"] = outputs

    if "node_id" not in info or not info["node_id"]:
        return None

    info.setdefault("inputs", [])
    info.setdefault("outputs", [])

    is_in, is_out = _detect_io_flags(info["inputs"], info["outputs"])
    info["is_input_node"]  = is_in
    info["is_output_node"] = is_out

    return info


def parse_file(path: Path) -> list[dict]:
    """Return a list of node_info dicts extracted from a single .py file."""
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except SyntaxError as exc:
        print(f"  [SKIP] {path.name}: SyntaxError: {exc}")
        return []

    nodes = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Return) and isinstance(node.value, ast.Call)):
            continue
        call = node.value
        func = call.func
        if isinstance(func, ast.Attribute) and func.attr == "Schema":
            info = _parse_schema_call(call)
            if info:
                nodes.append(info)

    return nodes


def build_registry(py_dir: Path) -> dict:
    registry: dict = {}
    for py_file in sorted(py_dir.glob("*.py")):
        print(f"Parsing {py_file.name} ...")
        nodes = parse_file(py_file)
        for node_info in nodes:
            nid = node_info["node_id"]
            registry[nid] = node_info
            print(f"  + {nid}")
    return registry


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Biopython node registry JSON")
    parser.add_argument("--py-dir", type=Path, default=PY_DIR)
    parser.add_argument("--out", type=Path, default=OUT_FILE)
    args = parser.parse_args()

    print(f"Scanning {args.py_dir} ...")
    registry = build_registry(args.py_dir)
    args.out.write_text(json.dumps(registry, indent=2, ensure_ascii=False))
    print(f"\nDone. {len(registry)} nodes → {args.out}")


if __name__ == "__main__":
    main()
