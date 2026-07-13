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


class AtacBwaMem2AlignNode(_BaseComfyBIONode):
    CATEGORY = "ComfyBIO/Alignment"
    RETURN_NAMES = ("sorted_bam_dir",)

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "reference_fasta_indexed": cls._upstream_input(),
                "fastq_dir": cls._string_input("harness/examples/fixtures/atac"),
                "reference_fasta": cls._string_input("harness/examples/fixtures/atac/reference.fasta"),
                "metadata_csv": cls._string_input("harness/examples/fixtures/atac/sample_metadata.csv"),
                "trimmed_dir": cls._string_input("trimmed"),
                "output_dir": cls._string_input("aligned"),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64}),
                "extra_command": cls._extra_command_input(),
            }
        }

    def run(self, reference_fasta_indexed, fastq_dir, reference_fasta, metadata_csv, trimmed_dir, output_dir, threads=4, extra_command="", runner=None) -> tuple[str]:
        runner = resolve_runner(runner)
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        trimmed = Path(trimmed_dir)
        for sample in load_samples(Path(fastq_dir), Path(metadata_csv) if metadata_csv else None):
            sample_dir = out / sample.sample_id
            sample_dir.mkdir(parents=True, exist_ok=True)
            read1 = trimmed / sample.sample_id / "R1.fastq"
            read2_candidate = trimmed / sample.sample_id / "R2.fastq"
            read2 = read2_candidate if read2_candidate.exists() else None
            sam_path = sample_dir / "aligned.sam"
            bam_path = sample_dir / "sorted.bam"
            align_record = runner.run(
                atac_stage_commands.bwa_mem2_align_argv(reference_fasta, read1, read2, threads, extra_command),
                sample_dir,
            )
            sam_path.write_text(align_record.stdout)
            runner.run(atac_stage_commands.samtools_sort_argv(sam_path, bam_path, threads), sample_dir)
            runner.run(atac_stage_commands.samtools_index_argv(bam_path), sample_dir)
        return (str(out),)


class AtacMarkDuplicatesNode(_BaseComfyBIONode):
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
            runner.run(atac_stage_commands.samtools_collate_argv(bam, collated, threads), sample_out)
            runner.run(atac_stage_commands.samtools_fixmate_argv(collated, fixmate), sample_out)
            runner.run(atac_stage_commands.samtools_sort_argv(fixmate, positionsorted, threads), sample_out)
            runner.run(atac_stage_commands.samtools_markdup_argv(positionsorted, dedup, extra_command), sample_out)
            runner.run(atac_stage_commands.samtools_index_argv(dedup), sample_out)
        return (str(out),)


class AtacQualityFilterNode(_BaseComfyBIONode):
    CATEGORY = "ComfyBIO/QC"
    RETURN_NAMES = ("filtered_bam_dir",)

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "dedup_bam_dir": cls._upstream_input(),
                "input_dir": cls._string_input("dedup"),
                "output_dir": cls._string_input("filtered"),
                "min_mapq": ("INT", {"default": 30, "min": 0, "max": 60}),
                "exclude_flags": cls._string_input("1804"),
                "mito_contig": cls._string_input("chrM"),
                "extra_command": cls._extra_command_input(),
            }
        }

    def run(self, dedup_bam_dir, input_dir, output_dir, min_mapq=30, exclude_flags="1804", mito_contig="chrM", extra_command="", runner=None) -> tuple[str]:
        runner = resolve_runner(runner)
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        in_dir = Path(input_dir)
        for sample_dir in sorted(path for path in in_dir.iterdir() if path.is_dir()):
            bam = sample_dir / "dedup.bam"
            sample_out = out / sample_dir.name
            sample_out.mkdir(parents=True, exist_ok=True)
            final_bam = sample_out / "final.bam"
            runner.run(
                atac_stage_commands.samtools_quality_filter_argv(bam, final_bam, min_mapq, exclude_flags, mito_contig, extra_command),
                sample_out,
            )
            runner.run(atac_stage_commands.samtools_index_argv(final_bam), sample_out)
        return (str(out),)
