import subprocess
from dataclasses import dataclass
from shutil import which


CONDA_ENV_NAME = "bulk_rna_seq"
REQUIRED_REF_EXECUTABLES = ["fastp", "salmon", "Rscript"]
REQUIRED_REF_PACKAGES = [
    "python>=3.11",
    "fastp",
    "salmon",
    "bioconductor-deseq2",
    "bioconductor-tximport",
    "r-ggplot2",
    "r-pheatmap",
]
OPTIONAL_ALT_TOOLS = ["STAR", "featureCounts", "MultiQC"]


@dataclass(frozen=True)
class DomainEnvironmentRequirements:
    env_name: str
    required_executables: list[str]
    required_packages: list[str]
    optional_alt_tools: list[str]


BULK_RNA_SEQ_REQUIREMENTS = DomainEnvironmentRequirements(
    env_name=CONDA_ENV_NAME,
    required_executables=REQUIRED_REF_EXECUTABLES,
    required_packages=REQUIRED_REF_PACKAGES,
    optional_alt_tools=OPTIONAL_ALT_TOOLS,
)

VARIANT_ANALYSIS_REQUIREMENTS = DomainEnvironmentRequirements(
    env_name="variant_analysis",
    required_executables=["bwa-mem2", "samtools", "bcftools"],
    required_packages=["python>=3.11", "bwa-mem2", "samtools", "bcftools", "matplotlib"],
    optional_alt_tools=["gatk4"],
)


class EnvironmentProbe:
    def env_exists(self, env_name: str) -> bool:
        raise NotImplementedError

    def executable_exists(self, env_name: str, executable: str) -> bool:
        raise NotImplementedError

    def executable_version(self, env_name: str, executable: str) -> str | None:
        raise NotImplementedError


class CondaEnvironmentProbe(EnvironmentProbe):
    def env_exists(self, env_name: str) -> bool:
        if which("conda") is None:
            return False
        completed = subprocess.run(
            ["conda", "env", "list"],
            check=False,
            capture_output=True,
            text=True,
        )
        return completed.returncode == 0 and any(line.split()[0] == env_name for line in completed.stdout.splitlines() if line and not line.startswith("#"))

    def executable_exists(self, env_name: str, executable: str) -> bool:
        if which("conda") is None:
            return False
        completed = subprocess.run(
            ["conda", "run", "-n", env_name, "which", executable],
            check=False,
            capture_output=True,
            text=True,
        )
        return completed.returncode == 0

    def executable_version(self, env_name: str, executable: str) -> str | None:
        if not self.executable_exists(env_name, executable):
            return None
        version_args = {
            "fastp": ["fastp", "--version"],
            "salmon": ["salmon", "--version"],
            "Rscript": ["Rscript", "--version"],
            "bwa-mem2": ["bwa-mem2", "version"],
        }.get(executable, [executable, "--version"])
        completed = subprocess.run(
            ["conda", "run", "-n", env_name, *version_args],
            check=False,
            capture_output=True,
            text=True,
        )
        output = (completed.stdout or completed.stderr).strip()
        return output.splitlines()[0] if completed.returncode == 0 and output else None


@dataclass(frozen=True)
class InstallPlan:
    env_name: str
    scope: str
    packages: list[str]
    approval_required: bool
    command: list[str]


@dataclass(frozen=True)
class EnvironmentReport:
    conda_env_name: str
    ready: bool
    missing_environment: bool
    missing_ref_tools: list[str]
    detected_versions: dict[str, str]
    optional_alt_tools: list[str]
    install_plan: InstallPlan


def install_plan_for(requirements: DomainEnvironmentRequirements) -> InstallPlan:
    return InstallPlan(
        env_name=requirements.env_name,
        scope="REF-only",
        packages=requirements.required_packages,
        approval_required=True,
        command=["conda", "create", "-n", requirements.env_name, "-c", "conda-forge", "-c", "bioconda", *requirements.required_packages],
    )


def ref_install_plan() -> InstallPlan:
    return install_plan_for(BULK_RNA_SEQ_REQUIREMENTS)


def validate_environment(requirements: DomainEnvironmentRequirements, probe: EnvironmentProbe | None = None) -> EnvironmentReport:
    active_probe = probe or CondaEnvironmentProbe()
    env_exists = active_probe.env_exists(requirements.env_name)
    missing_tools: list[str] = []
    versions: dict[str, str] = {}

    for executable in requirements.required_executables:
        if not env_exists or not active_probe.executable_exists(requirements.env_name, executable):
            missing_tools.append(executable)
            continue
        version = active_probe.executable_version(requirements.env_name, executable)
        if version:
            versions[executable] = version

    return EnvironmentReport(
        conda_env_name=requirements.env_name,
        ready=env_exists and not missing_tools,
        missing_environment=not env_exists,
        missing_ref_tools=missing_tools,
        detected_versions=versions,
        optional_alt_tools=requirements.optional_alt_tools,
        install_plan=install_plan_for(requirements),
    )


def validate_bulk_rna_seq_environment(probe: EnvironmentProbe | None = None) -> EnvironmentReport:
    return validate_environment(BULK_RNA_SEQ_REQUIREMENTS, probe)
