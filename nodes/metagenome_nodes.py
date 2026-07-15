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
