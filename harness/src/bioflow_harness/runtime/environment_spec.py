from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CondaEnvironmentSpec:
    name: str
    channels: list[str]
    dependencies: list[str]


def load_conda_environment_spec(path: Path) -> CondaEnvironmentSpec:
    name = ""
    channels: list[str] = []
    dependencies: list[str] = []
    current_list: str | None = None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("name:"):
            name = line.split(":", 1)[1].strip()
            current_list = None
            continue
        if line == "channels:":
            current_list = "channels"
            continue
        if line == "dependencies:":
            current_list = "dependencies"
            continue
        if line.startswith("- ") and current_list:
            value = line[2:].strip()
            if current_list == "channels":
                channels.append(value)
            elif current_list == "dependencies":
                dependencies.append(value)

    if not name:
        raise ValueError(f"Conda environment spec missing name: {path}")
    if not channels:
        raise ValueError(f"Conda environment spec missing channels: {path}")
    if not dependencies:
        raise ValueError(f"Conda environment spec missing dependencies: {path}")

    return CondaEnvironmentSpec(name=name, channels=channels, dependencies=dependencies)
