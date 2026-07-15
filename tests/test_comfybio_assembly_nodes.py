from pathlib import Path

import pytest

from bioflow_harness.runtime.command_runner import DryRunCommandRunner
from nodes.execution import EnvironmentNotReadyError
from nodes.assembly_nodes import AssemblyFastpTrimNode, AssemblyInputValidatorNode, SpadesAssembleNode

ASM_FIXTURES = "harness/examples/fixtures/assembly"
ASM_META = "harness/examples/fixtures/assembly/sample_metadata.csv"


class _ReadyProbe:
    def env_exists(self, name): return True
    def executable_exists(self, name, exe): return True
    def executable_version(self, name, exe): return "1.0"


class _MissingProbe:
    def env_exists(self, name): return False
    def executable_exists(self, name, exe): return False
    def executable_version(self, name, exe): return None


def test_assembly_input_validator_returns_metadata_path_when_env_ready():
    node = AssemblyInputValidatorNode()
    result = node.run(fastq_dir=ASM_FIXTURES, metadata_csv=ASM_META, extra_command="", probe=_ReadyProbe())
    assert result == (ASM_META,)


def test_assembly_input_validator_raises_when_env_not_ready():
    node = AssemblyInputValidatorNode()
    with pytest.raises(EnvironmentNotReadyError):
        node.run(fastq_dir=ASM_FIXTURES, metadata_csv=ASM_META, extra_command="", probe=_MissingProbe())


def test_assembly_input_validator_raises_on_missing_fastq_dir():
    node = AssemblyInputValidatorNode()
    with pytest.raises(FileNotFoundError):
        node.run(fastq_dir="harness/examples/fixtures/assembly_missing", metadata_csv="", extra_command="", probe=_ReadyProbe())


def test_assembly_fastp_trim_creates_per_sample_dir(tmp_path):
    runner = DryRunCommandRunner()
    out = tmp_path / "trimmed"
    node = AssemblyFastpTrimNode()
    result = node.run(
        sample_metadata_csv="upstream", fastq_dir=ASM_FIXTURES, metadata_csv=ASM_META,
        output_dir=str(out), threads=2, extra_command="", runner=runner,
    )
    assert result == (str(out),)
    assert (out / "sample_a").exists()
    assert len(runner.commands) == 1
    assert runner.commands[0].argv[:5] == ["conda", "run", "-n", "genome_assembly", "fastp"]


def _trimmed_fixture(tmp_path):
    trimmed = tmp_path / "trimmed" / "sample_a"
    trimmed.mkdir(parents=True)
    (trimmed / "R1.fastq").write_text("@r1\nACGT\n+\nFFFF\n", encoding="utf-8")
    (trimmed / "R2.fastq").write_text("@r1\nACGT\n+\nFFFF\n", encoding="utf-8")
    return tmp_path / "trimmed"


def test_spades_assemble_runs_one_command_per_sample(tmp_path):
    runner = DryRunCommandRunner()
    trimmed_dir = _trimmed_fixture(tmp_path)
    out = tmp_path / "assembly"
    node = SpadesAssembleNode()
    result = node.run(
        trimmed_fastq_dir="upstream", fastq_dir=ASM_FIXTURES, metadata_csv=ASM_META,
        trimmed_dir=str(trimmed_dir), output_dir=str(out), threads=4, memory_gb=8,
        extra_command="", runner=runner,
    )
    assert result == (str(out),)
    assert len(runner.commands) == 1
    assert runner.commands[0].argv[:5] == ["conda", "run", "-n", "genome_assembly", "spades.py"]
    assert "--pe1-1" in runner.commands[0].argv
    assert (out / "sample_a").exists()


from nodes.assembly_nodes import AssemblyReportNode, AssemblyVisualizationNode, QuastQcNode


def _assembly_fixture(tmp_path):
    assembly = tmp_path / "assembly" / "sample_a"
    assembly.mkdir(parents=True)
    (assembly / "contigs.fasta").write_text(">contig1\nACGT\n", encoding="utf-8")
    return tmp_path / "assembly"


def test_quast_qc_runs_one_command_per_sample(tmp_path):
    runner = DryRunCommandRunner()
    input_dir = _assembly_fixture(tmp_path)
    out = tmp_path / "quast"
    node = QuastQcNode()
    result = node.run(assembly_dir="upstream", input_dir=str(input_dir), output_dir=str(out), extra_command="", runner=runner)
    assert result == (str(out),)
    assert len(runner.commands) == 1
    assert runner.commands[0].argv[:5] == ["conda", "run", "-n", "genome_assembly", "quast.py"]
    assert (out / "sample_a").exists()


def _quast_fixture(tmp_path):
    quast = tmp_path / "quast" / "sample_a"
    quast.mkdir(parents=True)
    return tmp_path / "quast"


def test_assembly_visualization_returns_plot_dir_and_image(tmp_path):
    runner = DryRunCommandRunner()
    input_dir = _quast_fixture(tmp_path)
    plots = tmp_path / "plots"
    node = AssemblyVisualizationNode()
    result = node.run(
        qc_dir="upstream", input_dir=str(input_dir), plot_dir=str(plots),
        extra_command="", runner=runner, preview_loader=lambda path: "IMAGE_STUB",
    )
    assert result == (str(plots), "IMAGE_STUB")
    assert plots.exists()
    assert len(runner.commands) == 1


def test_assembly_report_runs_report_script(tmp_path):
    runner = DryRunCommandRunner()
    report = tmp_path / "report" / "assembly_report.md"
    node = AssemblyReportNode()
    result = node.run(
        plot_dir_path="upstream", qc_dir=str(tmp_path / "quast"),
        plot_dir=str(tmp_path / "plots"), report_path=str(report),
        extra_command="", runner=runner,
    )
    assert result == (str(report),)
    assert report.parent.exists()
    assert len(runner.commands) == 1
    assert "conda" not in runner.commands[0].argv


def test_all_assembly_nodes_registered_in_node_class_mappings():
    import nodes

    expected = {
        "AssemblyInputValidatorNode", "AssemblyFastpTrimNode", "SpadesAssembleNode",
        "QuastQcNode", "AssemblyVisualizationNode", "AssemblyReportNode",
    }
    assert expected.issubset(nodes.NODE_CLASS_MAPPINGS.keys())
