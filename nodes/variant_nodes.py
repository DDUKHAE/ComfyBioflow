from pathlib import Path

from bioflow_harness.runtime.environment import VARIANT_ANALYSIS_REQUIREMENTS
from .execution import require_environment, resolve_runner, load_preview_tensor
from .sample_loading import load_samples
from . import variant_stage_commands


class _BaseVariantNode:
    CATEGORY = "ComfyBIO"
    FUNCTION = "run"
    RETURN_TYPES = ("STRING",)

    @classmethod
    def _string_input(cls, default: str = "") -> tuple[str, dict[str, str]]:
        return ("STRING", {"default": default})

    @classmethod
    def _upstream_input(cls) -> tuple[str, dict[str, bool]]:
        return ("STRING", {"forceInput": True})

    @classmethod
    def _extra_command_input(cls) -> tuple[str, dict[str, str | bool]]:
        return ("STRING", {"default": "", "multiline": True})


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
