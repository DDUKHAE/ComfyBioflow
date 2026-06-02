"""
ComfyBIO Biopython — root package entry point for ComfyUI.

Dynamically loads all node classes from py/*.py and registers API routes
from llm_interface/harness_nodes/, then exposes them via a single ComfyExtension.
"""
from __future__ import annotations
import importlib.util
import sys
from functools import lru_cache
from pathlib import Path
from typing_extensions import override

from comfy_api.latest import ComfyExtension, io

_ROOT     = Path(__file__).parent
_PY_DIR   = _ROOT / "py"
_LLM_DIR  = _ROOT / "llm_interface"

# Add llm_interface to sys.path so harness_core / harness_nodes are importable
if str(_LLM_DIR) not in sys.path:
    sys.path.insert(0, str(_LLM_DIR))

# Web directory for frontend JS
WEB_DIRECTORY = "./llm_interface/harness_nodes/web"

# Import harness_nodes to register /comfybio/* API routes with PromptServer
import harness_nodes  # noqa: F401


@lru_cache(maxsize=1)
def _collect_biopython_nodes() -> list[type[io.ComfyNode]]:
    """Load py/*.py files and collect all concrete ComfyNode subclasses."""
    nodes: list[type[io.ComfyNode]] = []
    seen: set[str] = set()

    for py_file in sorted(_PY_DIR.glob("*.py")):
        if py_file.stem == "__init__":
            continue
        mod_name = f"comfybio_nodes.{py_file.stem}"
        spec = importlib.util.spec_from_file_location(mod_name, py_file)
        if spec is None:
            continue
        module = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = module
        try:
            spec.loader.exec_module(module)
        except Exception as exc:
            print(f"[ComfyBIO] Skipping {py_file.name}: {exc}")
            continue

        for attr_name in dir(module):
            if attr_name.startswith("_"):
                continue
            obj = getattr(module, attr_name)
            if (
                isinstance(obj, type)
                and issubclass(obj, io.ComfyNode)
                and obj is not io.ComfyNode
                and hasattr(obj, "define_schema")
                and attr_name not in seen
            ):
                seen.add(attr_name)
                nodes.append(obj)

    return nodes


class ComfyBIOExtension(ComfyExtension):
    @override
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return _collect_biopython_nodes()


async def comfy_entrypoint() -> ComfyBIOExtension:
    return ComfyBIOExtension()
