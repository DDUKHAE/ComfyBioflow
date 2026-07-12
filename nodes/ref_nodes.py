from pathlib import Path

from .execution import require_environment, resolve_runner, load_preview_tensor
from .sample_loading import load_samples
from . import stage_commands


class _BaseComfyBIONode:
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


class SampleMetadataValidatorNode(_BaseComfyBIONode):
    CATEGORY = "ComfyBIO/Input"
    RETURN_NAMES = ("sample_metadata_csv",)

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "fastq_dir": cls._string_input("fastq"),
                "metadata_csv": cls._string_input("sample_metadata.csv"),
                "extra_command": cls._extra_command_input(),
            }
        }

    def run(self, fastq_dir, metadata_csv, extra_command="", probe=None) -> tuple[str]:
        require_environment(probe)
        fastq_path = Path(fastq_dir)
        if not fastq_path.exists():
            raise FileNotFoundError(f"FASTQ directory not found: {fastq_dir}")
        metadata_path = Path(metadata_csv) if metadata_csv else None
        load_samples(fastq_path, metadata_path)  # raises if no samples resolvable
        return (str(metadata_path) if metadata_path else str(fastq_path),)


class FastpQCNode(_BaseComfyBIONode):
    CATEGORY = "ComfyBIO/QC"
    RETURN_NAMES = ("fastp_qc_json",)

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "fastq_pair": cls._upstream_input(),
                "fastq_dir": cls._string_input("fastq"),
                "metadata_csv": cls._string_input("sample_metadata.csv"),
                "output_dir": cls._string_input("qc"),
                "threads": ("INT", {"default": 2, "min": 1, "max": 64}),
                "extra_command": cls._extra_command_input(),
            }
        }

    def run(self, fastq_pair, fastq_dir, metadata_csv, output_dir, threads=2, extra_command="", runner=None) -> tuple[str]:
        runner = resolve_runner(runner)
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        for sample in load_samples(Path(fastq_dir), Path(metadata_csv) if metadata_csv else None):
            runner.run(stage_commands.fastp_qc_argv(sample, out, threads, extra_command), out)
        return (str(out),)


class FastpTrimNode(_BaseComfyBIONode):
    CATEGORY = "ComfyBIO/QC"
    RETURN_NAMES = ("trimmed_fastq_dir",)

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "fastp_qc_json": cls._upstream_input(),
                "fastq_dir": cls._string_input("fastq"),
                "metadata_csv": cls._string_input("sample_metadata.csv"),
                "output_dir": cls._string_input("trimmed"),
                "threads": ("INT", {"default": 2, "min": 1, "max": 64}),
                "extra_command": cls._extra_command_input(),
            }
        }

    def run(self, fastp_qc_json, fastq_dir, metadata_csv, output_dir, threads=2, extra_command="", runner=None) -> tuple[str]:
        runner = resolve_runner(runner)
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        for sample in load_samples(Path(fastq_dir), Path(metadata_csv) if metadata_csv else None):
            sample_dir = out / sample.sample_id
            sample_dir.mkdir(parents=True, exist_ok=True)
            runner.run(stage_commands.fastp_trim_argv(sample, sample_dir, threads, extra_command), out)
        return (str(out),)


class SalmonIndexNode(_BaseComfyBIONode):
    CATEGORY = "ComfyBIO/Quantification"
    RETURN_NAMES = ("salmon_index_dir",)

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "transcriptome_fasta_path": cls._upstream_input(),
                "transcriptome_fasta": cls._string_input("toy_transcriptome.fasta"),
                "index_dir": cls._string_input("salmon_index"),
                "threads": ("INT", {"default": 2, "min": 1, "max": 64}),
                "extra_command": cls._extra_command_input(),
            }
        }

    def run(self, transcriptome_fasta_path, transcriptome_fasta, index_dir, threads=2, extra_command="", runner=None) -> tuple[str]:
        runner = resolve_runner(runner)
        idx = Path(index_dir)
        idx.mkdir(parents=True, exist_ok=True)
        runner.run(stage_commands.salmon_index_argv(transcriptome_fasta, idx, threads, extra_command), idx)
        return (str(idx),)


class SalmonQuantNode(_BaseComfyBIONode):
    CATEGORY = "ComfyBIO/Quantification"
    RETURN_NAMES = ("salmon_quant_dir",)

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "salmon_index_dir": cls._upstream_input(),
                "index_dir": cls._string_input("salmon_index"),
                "fastq_dir": cls._string_input("fastq"),
                "metadata_csv": cls._string_input("sample_metadata.csv"),
                "output_dir": cls._string_input("salmon_quant"),
                "read_layout": ("STRING", {"default": "A"}),
                "threads": ("INT", {"default": 2, "min": 1, "max": 64}),
                "extra_command": cls._extra_command_input(),
            }
        }

    def run(self, salmon_index_dir, index_dir, fastq_dir, metadata_csv, output_dir, read_layout="A", threads=2, extra_command="", runner=None) -> tuple[str]:
        runner = resolve_runner(runner)
        quant = Path(output_dir)
        quant.mkdir(parents=True, exist_ok=True)
        trimmed = quant.parent / "trimmed"
        for sample in load_samples(Path(fastq_dir), Path(metadata_csv) if metadata_csv else None):
            sample_out = quant / sample.sample_id
            sample_out.mkdir(parents=True, exist_ok=True)
            read1 = trimmed / sample.sample_id / "R1.fastq"
            read2 = trimmed / sample.sample_id / "R2.fastq" if sample.fastq_2 is not None else None
            runner.run(
                stage_commands.salmon_quant_argv(index_dir, read1, read2, sample_out, read_layout, threads, extra_command),
                quant,
            )
        return (str(quant),)


class TximportNode(_BaseComfyBIONode):
    CATEGORY = "ComfyBIO/Differential Expression"
    RETURN_NAMES = ("deseq2_count_matrix",)

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "salmon_quant_dir_path": cls._upstream_input(),
                "salmon_quant_dir": cls._string_input("salmon_quant"),
                "metadata_csv": cls._string_input("sample_metadata.csv"),
                "output_count_matrix": cls._string_input("deseq2/count_matrix.csv"),
                "extra_command": cls._extra_command_input(),
            }
        }

    def run(self, salmon_quant_dir_path, salmon_quant_dir, metadata_csv, output_count_matrix, extra_command="", runner=None) -> tuple[str]:
        runner = resolve_runner(runner)
        matrix = Path(output_count_matrix)
        matrix.parent.mkdir(parents=True, exist_ok=True)
        runner.run(stage_commands.tximport_argv(salmon_quant_dir, matrix, extra_command), matrix.parent)
        return (str(matrix),)


class DESeq2AnalysisNode(_BaseComfyBIONode):
    CATEGORY = "ComfyBIO/Differential Expression"
    RETURN_NAMES = ("deseq2_results_table",)

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "deseq2_count_matrix": cls._upstream_input(),
                "count_matrix": cls._string_input("deseq2/count_matrix.csv"),
                "sample_metadata": cls._string_input("sample_metadata.csv"),
                "results_csv": cls._string_input("deseq2/results.csv"),
                "design_formula": ("STRING", {"default": "~ condition"}),
                "extra_command": cls._extra_command_input(),
            }
        }

    def run(self, deseq2_count_matrix, count_matrix, sample_metadata, results_csv, design_formula="~ condition", extra_command="", runner=None) -> tuple[str]:
        runner = resolve_runner(runner)
        results = Path(results_csv)
        results.parent.mkdir(parents=True, exist_ok=True)
        runner.run(stage_commands.deseq2_argv(count_matrix, sample_metadata, results, extra_command), results.parent)
        return (str(results),)


class DESeq2VisualizationNode(_BaseComfyBIONode):
    CATEGORY = "ComfyBIO/Visualization"
    RETURN_TYPES = ("STRING", "IMAGE")
    RETURN_NAMES = ("plot_dir", "preview_plot")

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "deseq2_results_table": cls._upstream_input(),
                "count_matrix": cls._string_input("deseq2/count_matrix.csv"),
                "results_csv": cls._string_input("deseq2/results.csv"),
                "plot_dir": cls._string_input("plots"),
                "extra_command": cls._extra_command_input(),
            }
        }

    def run(self, deseq2_results_table, count_matrix, results_csv, plot_dir, extra_command="", runner=None, preview_loader=None) -> tuple[str, object]:
        runner = resolve_runner(runner)
        loader = preview_loader if preview_loader is not None else load_preview_tensor
        plots = Path(plot_dir)
        plots.mkdir(parents=True, exist_ok=True)
        runner.run(stage_commands.deseq2_viz_argv(count_matrix, results_csv, plots, extra_command), plots)
        return (str(plots), loader(plots / "pca.png"))


class TenxCountNode(_BaseComfyBIONode):
    CATEGORY = "ComfyBIO/scRNA-seq"
    RETURN_NAMES = ("filtered_feature_bc_matrix",)

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "fastq_dir": cls._string_input("fastqs"),
                "sample_id": cls._string_input("sample"),
                "reference_dir": cls._string_input("cellranger_reference"),
                "output_matrix_dir": cls._string_input("cellranger_count/filtered_feature_bc_matrix"),
                "threads": ("INT", {"default": 8, "min": 1, "max": 128}),
                "extra_command": cls._extra_command_input(),
            }
        }


class ScanpyQCNode(_BaseComfyBIONode):
    CATEGORY = "ComfyBIO/scRNA-seq"
    RETURN_NAMES = ("qc_h5ad",)

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "filtered_feature_bc_matrix": cls._upstream_input(),
                "matrix_dir": cls._string_input("filtered_feature_bc_matrix"),
                "output_h5ad": cls._string_input("scanpy/qc.h5ad"),
                "min_genes": ("INT", {"default": 200, "min": 0, "max": 10000}),
                "max_mito_pct": ("FLOAT", {"default": 20.0, "min": 0.0, "max": 100.0}),
                "extra_command": cls._extra_command_input(),
            }
        }


class ScanpyNormalizeNode(_BaseComfyBIONode):
    CATEGORY = "ComfyBIO/scRNA-seq"
    RETURN_NAMES = ("normalized_h5ad",)

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "qc_h5ad": cls._upstream_input(),
                "input_h5ad": cls._string_input("scanpy/qc.h5ad"),
                "output_h5ad": cls._string_input("scanpy/normalized.h5ad"),
                "target_sum": ("INT", {"default": 10000, "min": 1, "max": 1000000}),
                "extra_command": cls._extra_command_input(),
            }
        }


class ScanpyClusterNode(_BaseComfyBIONode):
    CATEGORY = "ComfyBIO/scRNA-seq"
    RETURN_NAMES = ("clustered_h5ad",)

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "normalized_h5ad": cls._upstream_input(),
                "input_h5ad": cls._string_input("scanpy/normalized.h5ad"),
                "output_h5ad": cls._string_input("scanpy/clustered.h5ad"),
                "n_pcs": ("INT", {"default": 30, "min": 1, "max": 200}),
                "resolution": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 10.0}),
                "extra_command": cls._extra_command_input(),
            }
        }


class ScanpyMarkerGenesNode(_BaseComfyBIONode):
    CATEGORY = "ComfyBIO/scRNA-seq"
    RETURN_NAMES = ("marker_genes_csv",)

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "clustered_h5ad": cls._upstream_input(),
                "input_h5ad": cls._string_input("scanpy/clustered.h5ad"),
                "markers_csv": cls._string_input("scanpy/markers.csv"),
                "groupby": cls._string_input("leiden"),
                "method": cls._string_input("wilcoxon"),
                "extra_command": cls._extra_command_input(),
            }
        }


class ScRNAVisualizationNode(_BaseComfyBIONode):
    CATEGORY = "ComfyBIO/scRNA-seq"
    RETURN_TYPES = ("STRING", "IMAGE")
    RETURN_NAMES = ("plot_dir", "preview_plot")

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "marker_genes_csv": cls._upstream_input(),
                "input_h5ad": cls._string_input("scanpy/clustered.h5ad"),
                "markers_csv": cls._string_input("scanpy/markers.csv"),
                "plot_dir": cls._string_input("scanpy/plots"),
                "extra_command": cls._extra_command_input(),
            }
        }


class ScRNAReportNode(_BaseComfyBIONode):
    CATEGORY = "ComfyBIO/scRNA-seq"
    RETURN_NAMES = ("report_markdown",)

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "plot_dir_path": cls._upstream_input(),
                "input_h5ad": cls._string_input("scanpy/clustered.h5ad"),
                "markers_csv": cls._string_input("scanpy/markers.csv"),
                "plot_dir": cls._string_input("scanpy/plots"),
                "report_path": cls._string_input("report/scrna_report.md"),
                "extra_command": cls._extra_command_input(),
            }
        }


class ComfyBIOReportNode(_BaseComfyBIONode):
    CATEGORY = "ComfyBIO/Reporting"
    RETURN_NAMES = ("report_markdown",)

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "plot_dir_path": cls._upstream_input(),
                "results_csv": cls._string_input("deseq2/results.csv"),
                "plot_dir": cls._string_input("plots"),
                "report_path": cls._string_input("report/comfybio_report.md"),
                "extra_command": cls._extra_command_input(),
            }
        }

    def run(self, plot_dir_path, results_csv, plot_dir, report_path, extra_command="", runner=None) -> tuple[str]:
        runner = resolve_runner(runner)
        report = Path(report_path)
        report.parent.mkdir(parents=True, exist_ok=True)
        runner.run(stage_commands.report_argv(results_csv, plot_dir, report), report.parent)
        return (str(report),)
