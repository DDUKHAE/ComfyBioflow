from pathlib import Path

from bioflow_harness.runtime.environment import EPIGENOMICS_REQUIREMENTS
from .execution import require_environment, resolve_runner, load_preview_tensor
from .ref_nodes import _BaseComfyBIONode
from .sample_loading import load_samples
from . import atac_stage_commands


class AtacInputValidatorNode(_BaseComfyBIONode):
    CATEGORY = "ComfyBIO/Input"
    RETURN_NAMES = ("sample_metadata_csv",)

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "fastq_dir": cls._string_input("harness/examples/fixtures/atac"),
                "reference_fasta": cls._string_input("harness/examples/fixtures/atac/reference.fasta"),
                "metadata_csv": cls._string_input("harness/examples/fixtures/atac/sample_metadata.csv"),
                "extra_command": cls._extra_command_input(),
            }
        }

    def run(self, fastq_dir, reference_fasta, metadata_csv, extra_command="", probe=None) -> tuple[str]:
        require_environment(probe, requirements=EPIGENOMICS_REQUIREMENTS)
        fastq_path = Path(fastq_dir)
        if not fastq_path.exists():
            raise FileNotFoundError(f"FASTQ directory not found: {fastq_dir}")
        reference_path = Path(reference_fasta)
        if not reference_path.exists():
            raise FileNotFoundError(f"Reference FASTA not found: {reference_fasta}")
        metadata_path = Path(metadata_csv) if metadata_csv else None
        load_samples(fastq_path, metadata_path)  # raises if no samples resolvable
        return (str(metadata_path) if metadata_path else str(fastq_path),)


class AtacFastpTrimNode(_BaseComfyBIONode):
    CATEGORY = "ComfyBIO/QC"
    RETURN_NAMES = ("trimmed_fastq_dir",)

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "sample_metadata_csv": cls._upstream_input(),
                "fastq_dir": cls._string_input("harness/examples/fixtures/atac"),
                "metadata_csv": cls._string_input("harness/examples/fixtures/atac/sample_metadata.csv"),
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
            runner.run(atac_stage_commands.fastp_trim_argv(sample, sample_dir, threads, extra_command), out)
        return (str(out),)


class AtacBwaMem2IndexNode(_BaseComfyBIONode):
    CATEGORY = "ComfyBIO/Alignment"
    RETURN_NAMES = ("reference_fasta_indexed",)
    _INDEX_SUFFIXES = [".0123", ".amb", ".ann", ".bwt.2bit.64", ".pac"]

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "trimmed_fastq_dir": cls._upstream_input(),
                "reference_fasta": cls._string_input("harness/examples/fixtures/atac/reference.fasta"),
                "extra_command": cls._extra_command_input(),
            }
        }

    def run(self, trimmed_fastq_dir, reference_fasta, extra_command="", runner=None) -> tuple[str]:
        runner = resolve_runner(runner)
        reference = Path(reference_fasta)
        already_indexed = all((Path(str(reference) + suffix)).exists() for suffix in self._INDEX_SUFFIXES)
        if not already_indexed:
            runner.run(atac_stage_commands.bwa_mem2_index_argv(reference, extra_command), reference.parent)
        return (str(reference),)
