from pathlib import Path
import sys

from bioflow_harness.runtime.artifacts import RuntimeArtifact, ensure_dir_artifact, write_text_artifact
from bioflow_harness.runtime.command_runner import DryRunCommandRunner, conda_command
from bioflow_harness.runtime.fixture_validation import QuickstartFixture


ENV_NAME = "bulk_rna_seq"
SCRIPT_DIR = Path(__file__).resolve().parents[3] / "scripts"
REPORT_SCRIPT = Path(__file__).resolve().parent / "report.py"


def _is_dry_run(record) -> bool:
    return bool(getattr(record, "dry_run", False))


class FastpQCNodeRuntime:
    stage_id = "read_qc"

    def run(self, fixture: QuickstartFixture, output_dir: Path, runner: DryRunCommandRunner) -> RuntimeArtifact:
        for sample in fixture.samples:
            argv = conda_command(
                ENV_NAME,
                "fastp",
                "-i",
                str(sample.fastq_1),
                "-I",
                str(sample.fastq_2),
                "--json",
                str(output_dir / "qc" / f"{sample.sample_id}.fastp.json"),
            )
            runner.run(argv, output_dir)
        if isinstance(runner, DryRunCommandRunner):
            path = write_text_artifact(output_dir / "qc" / "fastp.json", '{"summary": "dry-run fastp QC"}\n')
        else:
            path = write_text_artifact(
                output_dir / "qc" / "fastp.json",
                '{"summary": "fastp QC complete", "sample_reports": "qc/*.fastp.json"}\n',
            )
        return RuntimeArtifact("qc_report", "json", path, self.stage_id)


class FastpTrimNodeRuntime:
    stage_id = "trimming"

    def run(self, fixture: QuickstartFixture, output_dir: Path, runner: DryRunCommandRunner) -> RuntimeArtifact:
        trimmed_dir = ensure_dir_artifact(output_dir / "trimmed")
        for sample in fixture.samples:
            sample_dir = ensure_dir_artifact(trimmed_dir / sample.sample_id)
            record = runner.run(
                conda_command(
                    ENV_NAME,
                    "fastp",
                    "-i",
                    str(sample.fastq_1),
                    "-I",
                    str(sample.fastq_2),
                    "--out1",
                    str(sample_dir / "R1.fastq"),
                    "--out2",
                    str(sample_dir / "R2.fastq"),
                    "--length_required",
                    "1",
                ),
                output_dir,
            )
            if _is_dry_run(record):
                write_text_artifact(sample_dir / "R1.fastq", f"dry-run trimmed read 1 for {sample.sample_id}\n")
                write_text_artifact(sample_dir / "R2.fastq", f"dry-run trimmed read 2 for {sample.sample_id}\n")
        return RuntimeArtifact("trimmed_fastq_dir", "directory", trimmed_dir, self.stage_id)


class SalmonIndexNodeRuntime:
    stage_id = "salmon_index"

    def run(self, fixture: QuickstartFixture, output_dir: Path, runner: DryRunCommandRunner) -> RuntimeArtifact:
        index_dir = ensure_dir_artifact(output_dir / "salmon_index")
        record = runner.run(
            conda_command(
                ENV_NAME,
                "salmon",
                "index",
                "-t",
                str(fixture.transcriptome_fasta),
                "-i",
                str(index_dir),
                "-k",
                "7",
            ),
            output_dir,
        )
        if _is_dry_run(record):
            write_text_artifact(index_dir / "versionInfo.json", '{"salmon": "dry-run"}\n')
        return RuntimeArtifact("salmon_index_dir", "directory", index_dir, self.stage_id)


class SalmonQuantNodeRuntime:
    stage_id = "salmon_quant"

    def run(self, fixture: QuickstartFixture, output_dir: Path, runner: DryRunCommandRunner) -> RuntimeArtifact:
        quant_dir = ensure_dir_artifact(output_dir / "salmon_quant")
        for index, sample in enumerate(fixture.samples):
            sample_quant_dir = ensure_dir_artifact(quant_dir / sample.sample_id)
            record = runner.run(
                conda_command(
                    ENV_NAME,
                    "salmon",
                    "quant",
                    "-i",
                    str(output_dir / "salmon_index"),
                    "-l",
                    "A",
                    "-1",
                    str(output_dir / "trimmed" / sample.sample_id / "R1.fastq"),
                    "-2",
                    str(output_dir / "trimmed" / sample.sample_id / "R2.fastq"),
                    "-o",
                    str(sample_quant_dir),
                ),
                output_dir,
            )
            if _is_dry_run(record):
                write_text_artifact(
                    sample_quant_dir / "quant.sf",
                    "Name\tLength\tEffectiveLength\tTPM\tNumReads\n"
                    f"tx1\t20\t20\t12.5\t{50 + index * 10}\n"
                    f"tx2\t20\t20\t7.5\t{30 + index * 5}\n",
                )
        return RuntimeArtifact("salmon_quant_dir", "directory", quant_dir, self.stage_id)


class TximportNodeRuntime:
    stage_id = "tximport_import"

    def run(self, output_dir: Path, runner: DryRunCommandRunner) -> RuntimeArtifact:
        matrix_path = output_dir / "deseq2" / "count_matrix.csv"
        record = runner.run(
            conda_command(
                ENV_NAME,
                "Rscript",
                str(SCRIPT_DIR / "tximport_import.R"),
                str(output_dir / "salmon_quant"),
                str(matrix_path),
            ),
            output_dir,
        )
        if _is_dry_run(record):
            sample_dirs = sorted(path for path in (output_dir / "salmon_quant").iterdir() if path.is_dir())
            sample_ids = [path.name for path in sample_dirs]
            rows = ["gene_id," + ",".join(sample_ids)]
            for transcript in ["tx1", "tx2"]:
                values = []
                for sample_dir in sample_dirs:
                    quant_lines = (sample_dir / "quant.sf").read_text(encoding="utf-8").splitlines()
                    quant_record = next(line.split("\t") for line in quant_lines[1:] if line.startswith(transcript + "\t"))
                    values.append(quant_record[4])
                rows.append(transcript + "," + ",".join(values))
            write_text_artifact(matrix_path, "\n".join(rows) + "\n")
        return RuntimeArtifact("deseq2_count_matrix", "csv", matrix_path, self.stage_id)


class DESeq2AnalysisNodeRuntime:
    stage_id = "deseq2_analysis"

    def run(self, fixture: QuickstartFixture, output_dir: Path, runner: DryRunCommandRunner) -> RuntimeArtifact:
        results_path = output_dir / "deseq2" / "results.csv"
        record = runner.run(
            conda_command(
                ENV_NAME,
                "Rscript",
                str(SCRIPT_DIR / "deseq2_analysis.R"),
                str(output_dir / "deseq2" / "count_matrix.csv"),
                str(fixture.sample_metadata),
                str(results_path),
            ),
            output_dir,
        )
        if _is_dry_run(record):
            write_text_artifact(results_path, "gene_id,log2FoldChange,padj\ntx1,1.3,0.01\ntx2,-0.4,0.2\n")
        return RuntimeArtifact("deseq2_results_table", "csv", results_path, self.stage_id)


class DESeq2VisualizationNodeRuntime:
    stage_id = "deseq2_visualization"

    def run(self, output_dir: Path, runner: DryRunCommandRunner) -> list[RuntimeArtifact]:
        plot_dir = ensure_dir_artifact(output_dir / "plots")
        record = runner.run(
            conda_command(
                ENV_NAME,
                "Rscript",
                str(SCRIPT_DIR / "deseq2_visualization.R"),
                str(output_dir / "deseq2" / "count_matrix.csv"),
                str(output_dir / "deseq2" / "results.csv"),
                str(plot_dir),
            ),
            output_dir,
        )
        artifacts = []
        for artifact_id, filename in [
            ("pca_plot", "pca.png"),
            ("ma_plot", "ma.png"),
            ("volcano_plot", "volcano.png"),
            ("heatmap_plot", "heatmap.png"),
        ]:
            path = plot_dir / filename
            if _is_dry_run(record):
                path = write_text_artifact(path, f"dry-run image placeholder: {filename}\n")
            artifacts.append(RuntimeArtifact(artifact_id, "image", path, self.stage_id))
        return artifacts


class ComfyBIOReportNodeRuntime:
    stage_id = "reporting"

    def run(self, output_dir: Path, runner: DryRunCommandRunner) -> RuntimeArtifact:
        report_path = output_dir / "report" / "comfybio_report.md"
        record = runner.run(
            [
                sys.executable,
                str(REPORT_SCRIPT),
                "--results",
                str(output_dir / "deseq2" / "results.csv"),
                "--plot-dir",
                str(output_dir / "plots"),
                "--output",
                str(report_path),
            ],
            output_dir,
        )
        if _is_dry_run(record):
            write_text_artifact(
                report_path,
                "# ComfyBIO Report\n\n"
                "## DESeq2 Results\n\n"
                "- Results table: `../deseq2/results.csv`\n"
                "- PCA: `../plots/pca.png`\n"
                "- MA plot: `../plots/ma.png`\n"
                "- Volcano: `../plots/volcano.png`\n"
                "- Heatmap: `../plots/heatmap.png`\n",
            )
        return RuntimeArtifact("report", "markdown", report_path, self.stage_id)
