from pathlib import Path

from bioflow_harness.runtime.environment import GENOME_ASSEMBLY_REQUIREMENTS
from .execution import require_environment, resolve_runner, load_preview_tensor
from .ref_nodes import _BaseComfyBIONode
from .sample_loading import load_samples
from . import assembly_stage_commands


class AssemblyInputValidatorNode(_BaseComfyBIONode):
    CATEGORY = "ComfyBIO/Input"
    RETURN_NAMES = ("sample_metadata_csv",)

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "fastq_dir": cls._string_input("harness/examples/fixtures/assembly"),
                "metadata_csv": cls._string_input("harness/examples/fixtures/assembly/sample_metadata.csv"),
                "extra_command": cls._extra_command_input(),
            }
        }

    def run(self, fastq_dir, metadata_csv, extra_command="", probe=None) -> tuple[str]:
        require_environment(probe, requirements=GENOME_ASSEMBLY_REQUIREMENTS)
        fastq_path = Path(fastq_dir)
        if not fastq_path.exists():
            raise FileNotFoundError(f"FASTQ directory not found: {fastq_dir}")
        metadata_path = Path(metadata_csv) if metadata_csv else None
        load_samples(fastq_path, metadata_path)  # raises if no samples resolvable
        return (str(metadata_path) if metadata_path else str(fastq_path),)


class AssemblyFastpTrimNode(_BaseComfyBIONode):
    CATEGORY = "ComfyBIO/QC"
    RETURN_NAMES = ("trimmed_fastq_dir",)

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "sample_metadata_csv": cls._upstream_input(),
                "fastq_dir": cls._string_input("harness/examples/fixtures/assembly"),
                "metadata_csv": cls._string_input("harness/examples/fixtures/assembly/sample_metadata.csv"),
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
            runner.run(assembly_stage_commands.fastp_trim_argv(sample, sample_dir, threads, extra_command), out)
        return (str(out),)


class SpadesAssembleNode(_BaseComfyBIONode):
    CATEGORY = "ComfyBIO/Assembly"
    RETURN_NAMES = ("assembly_dir",)

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "trimmed_fastq_dir": cls._upstream_input(),
                "fastq_dir": cls._string_input("harness/examples/fixtures/assembly"),
                "metadata_csv": cls._string_input("harness/examples/fixtures/assembly/sample_metadata.csv"),
                "trimmed_dir": cls._string_input("trimmed"),
                "output_dir": cls._string_input("assembly"),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64}),
                "memory_gb": ("INT", {"default": 8, "min": 1, "max": 512}),
                "extra_command": cls._extra_command_input(),
            }
        }

    def run(self, trimmed_fastq_dir, fastq_dir, metadata_csv, trimmed_dir, output_dir, threads=4, memory_gb=8, extra_command="", runner=None) -> tuple[str]:
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
            runner.run(
                assembly_stage_commands.spades_assemble_argv(read1, read2, sample_out, threads, memory_gb, extra_command),
                sample_out,
            )
        return (str(out),)


class QuastQcNode(_BaseComfyBIONode):
    CATEGORY = "ComfyBIO/Assembly"
    RETURN_NAMES = ("qc_dir",)

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "assembly_dir": cls._upstream_input(),
                "input_dir": cls._string_input("assembly"),
                "output_dir": cls._string_input("quast"),
                "extra_command": cls._extra_command_input(),
            }
        }

    def run(self, assembly_dir, input_dir, output_dir, extra_command="", runner=None) -> tuple[str]:
        runner = resolve_runner(runner)
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        in_dir = Path(input_dir)
        for sample_dir in sorted(path for path in in_dir.iterdir() if path.is_dir()):
            contigs = sample_dir / "contigs.fasta"
            sample_out = out / sample_dir.name
            sample_out.mkdir(parents=True, exist_ok=True)
            runner.run(assembly_stage_commands.quast_qc_argv(contigs, sample_out, extra_command), sample_out)
        return (str(out),)


class AssemblyVisualizationNode(_BaseComfyBIONode):
    CATEGORY = "ComfyBIO/Visualization"
    RETURN_TYPES = ("STRING", "IMAGE")
    RETURN_NAMES = ("plot_dir", "preview_plot")

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "qc_dir": cls._upstream_input(),
                "input_dir": cls._string_input("quast"),
                "plot_dir": cls._string_input("plots"),
                "extra_command": cls._extra_command_input(),
            }
        }

    def run(self, qc_dir, input_dir, plot_dir, extra_command="", runner=None, preview_loader=None) -> tuple[str, object]:
        runner = resolve_runner(runner)
        loader = preview_loader if preview_loader is not None else load_preview_tensor
        plots = Path(plot_dir)
        plots.mkdir(parents=True, exist_ok=True)
        runner.run(assembly_stage_commands.assembly_visualization_argv(input_dir, plots, extra_command), plots)
        return (str(plots), loader(plots / "assembly_summary.png"))


class AssemblyReportNode(_BaseComfyBIONode):
    CATEGORY = "ComfyBIO/Reporting"
    RETURN_NAMES = ("report_markdown",)

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "plot_dir_path": cls._upstream_input(),
                "qc_dir": cls._string_input("quast"),
                "plot_dir": cls._string_input("plots"),
                "report_path": cls._string_input("report/assembly_report.md"),
                "extra_command": cls._extra_command_input(),
            }
        }

    def run(self, plot_dir_path, qc_dir, plot_dir, report_path, extra_command="", runner=None) -> tuple[str]:
        runner = resolve_runner(runner)
        report = Path(report_path)
        report.parent.mkdir(parents=True, exist_ok=True)
        runner.run(assembly_stage_commands.assembly_report_argv(qc_dir, plot_dir, report), report.parent)
        return (str(report),)
