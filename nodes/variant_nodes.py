from pathlib import Path

from bioflow_harness.runtime.environment import VARIANT_ANALYSIS_REQUIREMENTS
from .execution import require_environment, resolve_runner, load_preview_tensor
from .sample_loading import load_samples
from . import variant_stage_commands
from .ref_nodes import _BaseComfyBIONode

_BaseVariantNode = _BaseComfyBIONode


class VariantInputValidatorNode(_BaseVariantNode):
    CATEGORY = "ComfyBIO/Input"
    RETURN_NAMES = ("sample_metadata_csv",)

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "fastq_dir": cls._string_input("harness/examples/fixtures/variant"),
                "reference_fasta": cls._string_input("harness/examples/fixtures/variant/reference.fasta"),
                "metadata_csv": cls._string_input("harness/examples/fixtures/variant/sample_metadata.csv"),
                "extra_command": cls._extra_command_input(),
            }
        }

    def run(self, fastq_dir, reference_fasta, metadata_csv, extra_command="", probe=None) -> tuple[str]:
        require_environment(probe, requirements=VARIANT_ANALYSIS_REQUIREMENTS)
        fastq_path = Path(fastq_dir)
        if not fastq_path.exists():
            raise FileNotFoundError(f"FASTQ directory not found: {fastq_dir}")
        reference_path = Path(reference_fasta)
        if not reference_path.exists():
            raise FileNotFoundError(f"Reference FASTA not found: {reference_fasta}")
        metadata_path = Path(metadata_csv) if metadata_csv else None
        load_samples(fastq_path, metadata_path)  # raises if no samples resolvable
        return (str(metadata_path) if metadata_path else str(fastq_path),)


class BwaMem2IndexNode(_BaseVariantNode):
    CATEGORY = "ComfyBIO/Alignment"
    RETURN_NAMES = ("reference_fasta_indexed",)
    _INDEX_SUFFIXES = [".0123", ".amb", ".ann", ".bwt.2bit.64", ".pac"]

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "sample_metadata_csv": cls._upstream_input(),
                "reference_fasta": cls._string_input("harness/examples/fixtures/variant/reference.fasta"),
                "extra_command": cls._extra_command_input(),
            }
        }

    def run(self, sample_metadata_csv, reference_fasta, extra_command="", runner=None) -> tuple[str]:
        runner = resolve_runner(runner)
        reference = Path(reference_fasta)
        already_indexed = all((Path(str(reference) + suffix)).exists() for suffix in self._INDEX_SUFFIXES)
        if not already_indexed:
            runner.run(variant_stage_commands.bwa_mem2_index_argv(reference, extra_command), reference.parent)
        return (str(reference),)


class BwaMem2AlignNode(_BaseVariantNode):
    CATEGORY = "ComfyBIO/Alignment"
    RETURN_NAMES = ("sorted_bam_dir",)

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "reference_fasta_indexed": cls._upstream_input(),
                "fastq_dir": cls._string_input("harness/examples/fixtures/variant"),
                "reference_fasta": cls._string_input("harness/examples/fixtures/variant/reference.fasta"),
                "metadata_csv": cls._string_input("harness/examples/fixtures/variant/sample_metadata.csv"),
                "output_dir": cls._string_input("aligned"),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64}),
                "extra_command": cls._extra_command_input(),
            }
        }

    def run(self, reference_fasta_indexed, fastq_dir, reference_fasta, metadata_csv, output_dir, threads=4, extra_command="", runner=None) -> tuple[str]:
        runner = resolve_runner(runner)
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        for sample in load_samples(Path(fastq_dir), Path(metadata_csv) if metadata_csv else None):
            sample_dir = out / sample.sample_id
            sample_dir.mkdir(parents=True, exist_ok=True)
            sam_path = sample_dir / "aligned.sam"
            bam_path = sample_dir / "sorted.bam"
            align_record = runner.run(
                variant_stage_commands.bwa_mem2_align_argv(reference_fasta, sample, threads, extra_command),
                sample_dir,
            )
            sam_path.write_text(align_record.stdout)
            runner.run(variant_stage_commands.samtools_sort_argv(sam_path, bam_path, threads), sample_dir)
            runner.run(variant_stage_commands.samtools_index_argv(bam_path), sample_dir)
        return (str(out),)


class MarkDuplicatesNode(_BaseVariantNode):
    CATEGORY = "ComfyBIO/Alignment"
    RETURN_NAMES = ("dedup_bam_dir",)

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "sorted_bam_dir": cls._upstream_input(),
                "input_dir": cls._string_input("aligned"),
                "output_dir": cls._string_input("dedup"),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64}),
                "extra_command": cls._extra_command_input(),
            }
        }

    def run(self, sorted_bam_dir, input_dir, output_dir, threads=4, extra_command="", runner=None) -> tuple[str]:
        runner = resolve_runner(runner)
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        in_dir = Path(input_dir)
        for sample_dir in sorted(path for path in in_dir.iterdir() if path.is_dir()):
            bam = sample_dir / "sorted.bam"
            sample_out = out / sample_dir.name
            sample_out.mkdir(parents=True, exist_ok=True)
            collated = sample_out / "collated.bam"
            fixmate = sample_out / "fixmate.bam"
            positionsorted = sample_out / "positionsorted.bam"
            dedup = sample_out / "dedup.bam"
            runner.run(variant_stage_commands.samtools_collate_argv(bam, collated, threads), sample_out)
            runner.run(variant_stage_commands.samtools_fixmate_argv(collated, fixmate), sample_out)
            runner.run(variant_stage_commands.samtools_sort_argv(fixmate, positionsorted, threads), sample_out)
            runner.run(variant_stage_commands.samtools_markdup_argv(positionsorted, dedup, extra_command), sample_out)
            runner.run(variant_stage_commands.samtools_index_argv(dedup), sample_out)
        return (str(out),)


class BcftoolsCallNode(_BaseVariantNode):
    CATEGORY = "ComfyBIO/Variant Calling"
    RETURN_NAMES = ("raw_vcf_dir",)

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "dedup_bam_dir": cls._upstream_input(),
                "input_dir": cls._string_input("dedup"),
                "reference_fasta": cls._string_input("harness/examples/fixtures/variant/reference.fasta"),
                "output_dir": cls._string_input("calls"),
                "extra_command": cls._extra_command_input(),
            }
        }

    def run(self, dedup_bam_dir, input_dir, reference_fasta, output_dir, extra_command="", runner=None) -> tuple[str]:
        runner = resolve_runner(runner)
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        in_dir = Path(input_dir)
        for sample_dir in sorted(path for path in in_dir.iterdir() if path.is_dir()):
            bam = sample_dir / "dedup.bam"
            sample_out = out / sample_dir.name
            sample_out.mkdir(parents=True, exist_ok=True)
            raw_bcf = sample_out / "raw.bcf"
            raw_vcf = sample_out / "raw.vcf"
            runner.run(variant_stage_commands.bcftools_mpileup_argv(reference_fasta, bam, raw_bcf, extra_command), sample_out)
            runner.run(variant_stage_commands.bcftools_call_argv(raw_bcf, raw_vcf), sample_out)
        return (str(out),)


class BcftoolsFilterNode(_BaseVariantNode):
    CATEGORY = "ComfyBIO/Variant Calling"
    RETURN_NAMES = ("filtered_vcf_dir",)

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "raw_vcf_dir": cls._upstream_input(),
                "input_dir": cls._string_input("calls"),
                "output_dir": cls._string_input("filtered"),
                "exclude_expression": cls._string_input("QUAL<20 || DP<10"),
                "extra_command": cls._extra_command_input(),
            }
        }

    def run(self, raw_vcf_dir, input_dir, output_dir, exclude_expression="QUAL<20 || DP<10", extra_command="", runner=None) -> tuple[str]:
        runner = resolve_runner(runner)
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        in_dir = Path(input_dir)
        for sample_dir in sorted(path for path in in_dir.iterdir() if path.is_dir()):
            raw_vcf = sample_dir / "raw.vcf"
            sample_out = out / sample_dir.name
            sample_out.mkdir(parents=True, exist_ok=True)
            filtered_vcf = sample_out / "filtered.vcf"
            runner.run(
                variant_stage_commands.bcftools_filter_argv(raw_vcf, filtered_vcf, exclude_expression, extra_command),
                sample_out,
            )
        return (str(out),)


class VariantVisualizationNode(_BaseVariantNode):
    CATEGORY = "ComfyBIO/Visualization"
    RETURN_TYPES = ("STRING", "IMAGE")
    RETURN_NAMES = ("plot_dir", "preview_plot")

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "filtered_vcf_dir": cls._upstream_input(),
                "input_dir": cls._string_input("filtered"),
                "plot_dir": cls._string_input("plots"),
                "extra_command": cls._extra_command_input(),
            }
        }

    def run(self, filtered_vcf_dir, input_dir, plot_dir, extra_command="", runner=None, preview_loader=None) -> tuple[str, object]:
        runner = resolve_runner(runner)
        loader = preview_loader if preview_loader is not None else load_preview_tensor
        plots = Path(plot_dir)
        plots.mkdir(parents=True, exist_ok=True)
        in_dir = Path(input_dir)
        for sample_dir in sorted(path for path in in_dir.iterdir() if path.is_dir()):
            vcf = sample_dir / "filtered.vcf"
            stats_out = plots / f"{sample_dir.name}.stats.txt"
            stats_record = runner.run(variant_stage_commands.bcftools_stats_argv(vcf), plots)
            stats_out.write_text(stats_record.stdout)
        runner.run(variant_stage_commands.variant_visualization_argv(plots, plots, extra_command), plots)
        return (str(plots), loader(plots / "variant_summary.png"))


class VariantReportNode(_BaseVariantNode):
    CATEGORY = "ComfyBIO/Reporting"
    RETURN_NAMES = ("report_markdown",)

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "plot_dir_path": cls._upstream_input(),
                "vcf_dir": cls._string_input("filtered"),
                "plot_dir": cls._string_input("plots"),
                "report_path": cls._string_input("report/variant_report.md"),
                "extra_command": cls._extra_command_input(),
            }
        }

    def run(self, plot_dir_path, vcf_dir, plot_dir, report_path, extra_command="", runner=None) -> tuple[str]:
        runner = resolve_runner(runner)
        report = Path(report_path)
        report.parent.mkdir(parents=True, exist_ok=True)
        runner.run(variant_stage_commands.variant_report_argv(vcf_dir, plot_dir, report), report.parent)
        return (str(report),)
