from pathlib import Path

import pytest

import nodes
from nodes.execution import EnvironmentNotReadyError

QS = "harness/examples/fixtures/quickstart"
QS_META = "harness/examples/fixtures/quickstart/sample_metadata.csv"


class _ReadyProbe:
    def env_exists(self, name): return True
    def executable_exists(self, name, exe): return True
    def executable_version(self, name, exe): return "1.0"


class _MissingProbe:
    def env_exists(self, name): return False
    def executable_exists(self, name, exe): return False
    def executable_version(self, name, exe): return None


def test_metadata_validator_returns_metadata_path_when_env_ready():
    node = nodes.NODE_CLASS_MAPPINGS["SampleMetadataValidatorNode"]()
    result = node.run(fastq_dir=QS, metadata_csv=QS_META, extra_command="", probe=_ReadyProbe())
    assert result == (QS_META,)


def test_metadata_validator_raises_when_env_not_ready():
    node = nodes.NODE_CLASS_MAPPINGS["SampleMetadataValidatorNode"]()
    with pytest.raises(EnvironmentNotReadyError):
        node.run(fastq_dir=QS, metadata_csv=QS_META, extra_command="", probe=_MissingProbe())


def test_metadata_validator_raises_on_missing_fastq_dir():
    node = nodes.NODE_CLASS_MAPPINGS["SampleMetadataValidatorNode"]()
    with pytest.raises(FileNotFoundError):
        node.run(fastq_dir="harness/examples/fixtures/missing", metadata_csv="", extra_command="", probe=_ReadyProbe())


from bioflow_harness.runtime.command_runner import DryRunCommandRunner


def test_fastp_qc_runs_one_command_per_sample_and_creates_output(tmp_path):
    runner = DryRunCommandRunner()
    out = tmp_path / "qc"
    node = nodes.NODE_CLASS_MAPPINGS["FastpQCNode"]()
    result = node.run(
        fastq_pair="upstream", fastq_dir=QS, metadata_csv=QS_META,
        output_dir=str(out), threads=2, extra_command="", runner=runner,
    )
    assert result == (str(out),)
    assert out.exists()
    assert len(runner.commands) == 4
    assert runner.commands[0].argv[:5] == ["conda", "run", "-n", "bulk_rna_seq", "fastp"]


def test_fastp_trim_creates_per_sample_dirs(tmp_path):
    runner = DryRunCommandRunner()
    out = tmp_path / "trimmed"
    node = nodes.NODE_CLASS_MAPPINGS["FastpTrimNode"]()
    result = node.run(
        fastp_qc_json="upstream", fastq_dir=QS, metadata_csv=QS_META,
        output_dir=str(out), threads=2, extra_command="", runner=runner,
    )
    assert result == (str(out),)
    assert (out / "sample_a").exists()
    assert len(runner.commands) == 4


def test_salmon_index_runs_once_and_creates_dir(tmp_path):
    runner = DryRunCommandRunner()
    idx = tmp_path / "salmon_index"
    node = nodes.NODE_CLASS_MAPPINGS["SalmonIndexNode"]()
    result = node.run(
        transcriptome_fasta_path="upstream",
        transcriptome_fasta="harness/examples/fixtures/quickstart/toy_transcriptome.fasta",
        index_dir=str(idx), threads=2, extra_command="", runner=runner,
    )
    assert result == (str(idx),)
    assert idx.exists()
    assert len(runner.commands) == 1
    assert runner.commands[0].argv[:6] == ["conda", "run", "-n", "bulk_rna_seq", "salmon", "index"]


def test_salmon_quant_uses_trimmed_reads_sibling_of_output(tmp_path):
    runner = DryRunCommandRunner()
    base = tmp_path / "run"
    quant = base / "salmon_quant"
    node = nodes.NODE_CLASS_MAPPINGS["SalmonQuantNode"]()
    result = node.run(
        salmon_index_dir="upstream", index_dir=str(base / "salmon_index"),
        fastq_dir=QS, metadata_csv=QS_META, output_dir=str(quant),
        read_layout="A", threads=2, extra_command="", runner=runner,
    )
    assert result == (str(quant),)
    assert len(runner.commands) == 4
    joined = " ".join(runner.commands[0].argv)
    assert str(base / "trimmed" / "sample_a" / "R1.fastq") in joined
    assert (quant / "sample_a").exists()


def test_tximport_runs_once_and_creates_matrix_parent(tmp_path):
    runner = DryRunCommandRunner()
    matrix = tmp_path / "deseq2" / "count_matrix.csv"
    node = nodes.NODE_CLASS_MAPPINGS["TximportNode"]()
    result = node.run(
        salmon_quant_dir_path="upstream", salmon_quant_dir=str(tmp_path / "salmon_quant"),
        metadata_csv=QS_META, output_count_matrix=str(matrix), extra_command="", runner=runner,
    )
    assert result == (str(matrix),)
    assert matrix.parent.exists()
    assert len(runner.commands) == 1
    assert "Rscript" in runner.commands[0].argv


def test_deseq2_analysis_runs_once_and_returns_results(tmp_path):
    runner = DryRunCommandRunner()
    results = tmp_path / "deseq2" / "results.csv"
    node = nodes.NODE_CLASS_MAPPINGS["DESeq2AnalysisNode"]()
    result = node.run(
        deseq2_count_matrix="upstream", count_matrix=str(tmp_path / "count_matrix.csv"),
        sample_metadata=QS_META, results_csv=str(results),
        design_formula="~ condition", extra_command="", runner=runner,
    )
    assert result == (str(results),)
    assert results.parent.exists()
    assert len(runner.commands) == 1


def test_deseq2_visualization_returns_plot_dir_and_image(tmp_path):
    runner = DryRunCommandRunner()
    plots = tmp_path / "plots"
    node = nodes.NODE_CLASS_MAPPINGS["DESeq2VisualizationNode"]()
    result = node.run(
        deseq2_results_table="upstream", count_matrix=str(tmp_path / "count_matrix.csv"),
        results_csv=str(tmp_path / "results.csv"), plot_dir=str(plots),
        extra_command="", runner=runner, preview_loader=lambda path: "IMAGE_STUB",
    )
    assert result == (str(plots), "IMAGE_STUB")
    assert plots.exists()
    assert len(runner.commands) == 1


def test_comfybio_report_runs_report_script(tmp_path):
    runner = DryRunCommandRunner()
    report = tmp_path / "report" / "comfybio_report.md"
    node = nodes.NODE_CLASS_MAPPINGS["ComfyBIOReportNode"]()
    result = node.run(
        plot_dir_path="upstream", results_csv=str(tmp_path / "results.csv"),
        plot_dir=str(tmp_path / "plots"), report_path=str(report),
        extra_command="", runner=runner,
    )
    assert result == (str(report),)
    assert report.parent.exists()
    assert len(runner.commands) == 1
    assert "conda" not in runner.commands[0].argv
