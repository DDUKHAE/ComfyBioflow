from pathlib import Path

from bioflow_harness.runtime.environment import METAGENOME_REQUIREMENTS
from .execution import require_environment, resolve_runner, load_preview_tensor
from .ref_nodes import _BaseComfyBIONode
from .sample_loading import load_samples
from . import metagenome_stage_commands


class MetagenomeInputValidatorNode(_BaseComfyBIONode):
    CATEGORY = "ComfyBIO/Input"
    RETURN_NAMES = ("sample_metadata_csv",)

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "fastq_dir": cls._string_input("harness/examples/fixtures/metagenome"),
                "kraken2_db_dir": cls._string_input("harness/examples/fixtures/metagenome/kraken2_db"),
                "metadata_csv": cls._string_input("harness/examples/fixtures/metagenome/sample_metadata.csv"),
                "extra_command": cls._extra_command_input(),
            }
        }

    def run(self, fastq_dir, kraken2_db_dir, metadata_csv, extra_command="", probe=None) -> tuple[str]:
        require_environment(probe, requirements=METAGENOME_REQUIREMENTS)
        fastq_path = Path(fastq_dir)
        if not fastq_path.exists():
            raise FileNotFoundError(f"FASTQ directory not found: {fastq_dir}")
        db_path = Path(kraken2_db_dir)
        if not db_path.exists():
            raise FileNotFoundError(f"Kraken2 database directory not found: {kraken2_db_dir}")
        metadata_path = Path(metadata_csv) if metadata_csv else None
        load_samples(fastq_path, metadata_path)  # raises if no samples resolvable
        return (str(metadata_path) if metadata_path else str(fastq_path),)


class MetagenomeFastpTrimNode(_BaseComfyBIONode):
    CATEGORY = "ComfyBIO/QC"
    RETURN_NAMES = ("trimmed_fastq_dir",)

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "sample_metadata_csv": cls._upstream_input(),
                "fastq_dir": cls._string_input("harness/examples/fixtures/metagenome"),
                "metadata_csv": cls._string_input("harness/examples/fixtures/metagenome/sample_metadata.csv"),
                "output_dir": cls._string_input("trimmed"),
                "threads": ("INT", {"default": 2, "min": 1, "max": 64}),
                "extra_command": cls._extra_command_input(),
            }
        }

    def run(self, sample_metadata_csv, fastq_dir, metadata_csv, output_dir, threads=2, extra_command="", runner=None) -> tuple[str]:
        runner = resolve_runner(runner)
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        for sample in load_samples(Path(fastq_dir), Path(metadata_csv) if metadata_csv else None):
            sample_dir = out / sample.sample_id
            sample_dir.mkdir(parents=True, exist_ok=True)
            runner.run(metagenome_stage_commands.fastp_trim_argv(sample, sample_dir, threads, extra_command), out)
        return (str(out),)


class Kraken2ClassifyNode(_BaseComfyBIONode):
    CATEGORY = "ComfyBIO/Taxonomic Classification"
    RETURN_NAMES = ("kraken2_output_dir",)

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "trimmed_fastq_dir": cls._upstream_input(),
                "fastq_dir": cls._string_input("harness/examples/fixtures/metagenome"),
                "metadata_csv": cls._string_input("harness/examples/fixtures/metagenome/sample_metadata.csv"),
                "trimmed_dir": cls._string_input("trimmed"),
                "kraken2_db_dir": cls._string_input("harness/examples/fixtures/metagenome/kraken2_db"),
                "output_dir": cls._string_input("kraken2"),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64}),
                "confidence": ("FLOAT", {"default": 0.1, "min": 0.0, "max": 1.0}),
                "extra_command": cls._extra_command_input(),
            }
        }

    def run(self, trimmed_fastq_dir, fastq_dir, metadata_csv, trimmed_dir, kraken2_db_dir, output_dir, threads=4, confidence=0.1, extra_command="", runner=None) -> tuple[str]:
        runner = resolve_runner(runner)
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        trimmed = Path(trimmed_dir)
        for sample in load_samples(Path(fastq_dir), Path(metadata_csv) if metadata_csv else None):
            sample_out = out / sample.sample_id
            sample_out.mkdir(parents=True, exist_ok=True)
            read1 = trimmed / sample.sample_id / "R1.fastq"
            read2_candidate = trimmed / sample.sample_id / "R2.fastq"
            read2 = read2_candidate if read2_candidate.exists() else None
            report_path = sample_out / "kraken2_report.txt"
            output_path = sample_out / "kraken2_output.txt"
            runner.run(
                metagenome_stage_commands.kraken2_classify_argv(
                    kraken2_db_dir, read1, read2, report_path, output_path, threads, confidence, extra_command
                ),
                sample_out,
            )
        return (str(out),)


class BrackenAbundanceNode(_BaseComfyBIONode):
    CATEGORY = "ComfyBIO/Taxonomic Classification"
    RETURN_NAMES = ("bracken_dir",)

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "kraken2_output_dir": cls._upstream_input(),
                "input_dir": cls._string_input("kraken2"),
                "kraken2_db_dir": cls._string_input("harness/examples/fixtures/metagenome/kraken2_db"),
                "output_dir": cls._string_input("bracken"),
                "read_length": ("INT", {"default": 100, "min": 1, "max": 1000}),
                "level": cls._string_input("S"),
                "threshold": ("INT", {"default": 10, "min": 0, "max": 10000}),
                "extra_command": cls._extra_command_input(),
            }
        }

    def run(self, kraken2_output_dir, input_dir, kraken2_db_dir, output_dir, read_length=100, level="S", threshold=10, extra_command="", runner=None) -> tuple[str]:
        runner = resolve_runner(runner)
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        in_dir = Path(input_dir)
        for sample_dir in sorted(path for path in in_dir.iterdir() if path.is_dir()):
            kraken2_report = sample_dir / "kraken2_report.txt"
            sample_out = out / sample_dir.name
            sample_out.mkdir(parents=True, exist_ok=True)
            output_path = sample_out / "bracken_output.txt"
            report_path = sample_out / "bracken_report.txt"
            runner.run(
                metagenome_stage_commands.bracken_abundance_argv(
                    kraken2_db_dir, kraken2_report, output_path, report_path, read_length, level, threshold, extra_command
                ),
                sample_out,
            )
        return (str(out),)


class MetagenomeVisualizationNode(_BaseComfyBIONode):
    CATEGORY = "ComfyBIO/Visualization"
    RETURN_TYPES = ("STRING", "IMAGE")
    RETURN_NAMES = ("plot_dir", "preview_plot")

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "bracken_dir": cls._upstream_input(),
                "input_dir": cls._string_input("bracken"),
                "plot_dir": cls._string_input("plots"),
                "extra_command": cls._extra_command_input(),
            }
        }

    def run(self, bracken_dir, input_dir, plot_dir, extra_command="", runner=None, preview_loader=None) -> tuple[str, object]:
        runner = resolve_runner(runner)
        loader = preview_loader if preview_loader is not None else load_preview_tensor
        plots = Path(plot_dir)
        plots.mkdir(parents=True, exist_ok=True)
        runner.run(metagenome_stage_commands.metagenome_visualization_argv(input_dir, plots, extra_command), plots)
        return (str(plots), loader(plots / "metagenome_summary.png"))


class MetagenomeReportNode(_BaseComfyBIONode):
    CATEGORY = "ComfyBIO/Reporting"
    RETURN_NAMES = ("report_markdown",)

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "plot_dir_path": cls._upstream_input(),
                "bracken_dir": cls._string_input("bracken"),
                "plot_dir": cls._string_input("plots"),
                "report_path": cls._string_input("report/metagenome_report.md"),
                "extra_command": cls._extra_command_input(),
            }
        }

    def run(self, plot_dir_path, bracken_dir, plot_dir, report_path, extra_command="", runner=None) -> tuple[str]:
        runner = resolve_runner(runner)
        report = Path(report_path)
        report.parent.mkdir(parents=True, exist_ok=True)
        runner.run(metagenome_stage_commands.metagenome_report_argv(bracken_dir, plot_dir, report), report.parent)
        return (str(report),)
