import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class CommandRecord:
    argv: list[str]
    cwd: Path
    dry_run: bool
    returncode: int | None = None
    stdout: str = ""
    stderr: str = ""


@dataclass
class DryRunCommandRunner:
    commands: list[CommandRecord] = field(default_factory=list)

    def run(self, argv: list[str], cwd: Path) -> CommandRecord:
        record = CommandRecord(argv=argv, cwd=cwd, dry_run=True)
        self.commands.append(record)
        return record


@dataclass
class CondaCommandRunner:
    commands: list[CommandRecord] = field(default_factory=list)

    def run(self, argv: list[str], cwd: Path) -> CommandRecord:
        completed = subprocess.run(
            argv,
            check=False,
            cwd=cwd,
            capture_output=True,
            text=True,
        )
        record = CommandRecord(
            argv=argv,
            cwd=cwd,
            dry_run=False,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
        self.commands.append(record)
        if completed.returncode != 0:
            raise RuntimeError(f"Command failed with exit code {completed.returncode}: {' '.join(argv)}\n{completed.stderr}")
        return record


def conda_command(env_name: str, executable: str, *args: str) -> list[str]:
    return ["conda", "run", "-n", env_name, executable, *args]
