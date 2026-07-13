from pathlib import Path

from bioflow_harness.runtime.command_runner import CondaCommandRunner
from bioflow_harness.runtime.environment import BULK_RNA_SEQ_REQUIREMENTS, validate_environment
from bioflow_harness.runtime.ref_workflow import EnvironmentNotReadyError

__all__ = ["EnvironmentNotReadyError", "resolve_runner", "require_environment", "load_preview_tensor"]


def resolve_runner(runner=None):
    return runner if runner is not None else CondaCommandRunner()


def require_environment(probe=None, requirements=BULK_RNA_SEQ_REQUIREMENTS):
    report = validate_environment(requirements, probe)
    if not report.ready:
        raise EnvironmentNotReadyError(report)
    return report


def load_preview_tensor(png_path):
    import numpy as np
    import torch
    from PIL import Image

    path = Path(png_path)
    if path.exists() and path.stat().st_size > 0:
        try:
            array = np.asarray(Image.open(path).convert("RGB"), dtype="float32") / 255.0
        except Exception:
            array = np.zeros((64, 64, 3), dtype="float32")
    else:
        array = np.zeros((64, 64, 3), dtype="float32")
    return torch.from_numpy(array)[None,]
