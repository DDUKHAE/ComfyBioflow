import os
from pathlib import Path

COMFYBIO_ROOT = Path(__file__).resolve().parent.parent

def get_comfyui_output_dir() -> Path:
    # 1. Environment variable override (highest priority, useful for tests)
    env_dir = os.environ.get("COMFYUI_OUTPUT_DIR")
    if env_dir:
        return Path(env_dir).expanduser().resolve()
        
    # 2. Try importing folder_paths (from ComfyUI context)
    try:
        import folder_paths
        return Path(folder_paths.get_output_directory()).resolve()
    except ImportError:
        pass
        
    # 3. Default fallbacks
    parent_comfy = COMFYBIO_ROOT.parent.parent / "output"
    # If the parent is a ComfyUI workspace
    if parent_comfy.parent.name == "ComfyUI" or parent_comfy.exists():
        return parent_comfy
        
    # Standard fallback
    fallback_dir = Path("/tmp/comfybio_output")
    fallback_dir.mkdir(parents=True, exist_ok=True)
    return fallback_dir

def get_comfyui_input_dir() -> Path:
    # 1. Environment variable override
    env_dir = os.environ.get("COMFYUI_INPUT_DIR")
    if env_dir:
        return Path(env_dir).expanduser().resolve()

    # 2. Try importing folder_paths (from ComfyUI context)
    try:
        import folder_paths
        return Path(folder_paths.get_input_directory()).resolve()
    except ImportError:
        pass

    # 3. Derive from COMFYBIO_ROOT location (custom_nodes/ComfyBIO → ComfyUI/input)
    candidate = COMFYBIO_ROOT.parent.parent / "input"
    if candidate.exists():
        return candidate

    fallback_dir = Path("/tmp/comfybio_input")
    fallback_dir.mkdir(parents=True, exist_ok=True)
    return fallback_dir

def staging_root(job_id: str) -> Path:
    return COMFYBIO_ROOT / ".generated" / job_id

def workflow_result_root(workflow_id: str) -> Path:
    return get_comfyui_output_dir() / workflow_id

def run_root(workflow_id: str, run_id: str) -> Path:
    return workflow_result_root(workflow_id) / run_id
