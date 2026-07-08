"""ComfyUI custom-node entrypoint for ComfyBIO.

Place this repository at `ComfyUI/custom_nodes/ComfyBIO`. ComfyUI imports this
file and discovers the node mappings exported below.
"""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
HARNESS_SRC = ROOT / "harness" / "src"
if str(HARNESS_SRC) not in sys.path:
    sys.path.insert(0, str(HARNESS_SRC))

from bioflow_harness.custom_nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS  # noqa: E402


WEB_DIRECTORY = "./web"


__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
