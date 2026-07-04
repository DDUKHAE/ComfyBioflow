from dataclasses import dataclass
from pathlib import Path

from bioflow_harness.runtime.artifact_sidecar import write_artifact_sidecar
from bioflow_harness.runtime.artifacts import RuntimeArtifact
from bioflow_harness.runtime.command_runner import CommandRecord, CondaCommandRunner, DryRunCommandRunner
from bioflow_harness.runtime.environment import EnvironmentProbe, EnvironmentReport, validate_bulk_rna_seq_environment
from bioflow_harness.runtime.fixture_validation import validate_quickstart_fixture
from bioflow_harness.runtime.ref_nodes import (
    ComfyBIOReportNodeRuntime,
    DESeq2AnalysisNodeRuntime,
    DESeq2VisualizationNodeRuntime,
    FastpQCNodeRuntime,
    FastpTrimNodeRuntime,
    SalmonIndexNodeRuntime,
    SalmonQuantNodeRuntime,
    TximportNodeRuntime,
)


@dataclass(frozen=True)
class ReferenceRunResult:
    route_id: str
    output_dir: Path
    commands: list[CommandRecord]
    artifacts: list[RuntimeArtifact]
    sidecar_path: Path


class EnvironmentNotReadyError(RuntimeError):
    def __init__(self, report: EnvironmentReport) -> None:
        super().__init__(
            "bulk_rna_seq managed environment is not ready. "
            "Review the approval-required REF-only install plan before running external tools."
        )
        self.report = report


def run_ref_fixture(
    fixture_dir: Path,
    output_dir: Path,
    dry_run: bool = True,
    environment_probe: EnvironmentProbe | None = None,
) -> ReferenceRunResult:
    fixture = validate_quickstart_fixture(fixture_dir.resolve())
    output_dir = output_dir.resolve()

    output_dir.mkdir(parents=True, exist_ok=True)
    if dry_run:
        runner = DryRunCommandRunner()
    else:
        environment_report = validate_bulk_rna_seq_environment(environment_probe)
        if not environment_report.ready:
            raise EnvironmentNotReadyError(environment_report)
        runner = CondaCommandRunner()
    artifacts: list[RuntimeArtifact] = []

    artifacts.append(FastpQCNodeRuntime().run(fixture, output_dir, runner))
    artifacts.append(FastpTrimNodeRuntime().run(fixture, output_dir, runner))
    artifacts.append(SalmonIndexNodeRuntime().run(fixture, output_dir, runner))
    artifacts.append(SalmonQuantNodeRuntime().run(fixture, output_dir, runner))
    artifacts.append(TximportNodeRuntime().run(output_dir, runner))
    artifacts.append(DESeq2AnalysisNodeRuntime().run(fixture, output_dir, runner))
    artifacts.extend(DESeq2VisualizationNodeRuntime().run(output_dir, runner))
    artifacts.append(ComfyBIOReportNodeRuntime().run(output_dir, runner))

    route_id = "bulk_rna_seq_salmon_ref"
    sidecar_path = write_artifact_sidecar(route_id, output_dir, artifacts)

    return ReferenceRunResult(
        route_id=route_id,
        output_dir=output_dir,
        commands=runner.commands,
        artifacts=artifacts,
        sidecar_path=sidecar_path,
    )
