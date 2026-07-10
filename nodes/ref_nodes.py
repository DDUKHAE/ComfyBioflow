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


class WorkflowRequestLoader(_BaseComfyBIONode):
    CATEGORY = "ComfyBIO/Orchestration"
    RETURN_NAMES = ("workflow_request",)

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {"required": {"request_payload": cls._string_input()}}

    def run(self, request_payload: str) -> tuple[str]:
        return (request_payload,)


class SampleMetadataValidatorNode(_BaseComfyBIONode):
    CATEGORY = "ComfyBIO/Input"
    RETURN_NAMES = ("sample_metadata_csv",)

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "workflow_request": cls._upstream_input(),
                "fastq_dir": cls._string_input("fastq"),
                "metadata_csv": cls._string_input("sample_metadata.csv"),
                "extra_command": cls._extra_command_input(),
            }
        }


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


class TenxCountNode(_BaseComfyBIONode):
    CATEGORY = "ComfyBIO/scRNA-seq"
    RETURN_NAMES = ("filtered_feature_bc_matrix",)

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "tenx_fastq_dir": cls._upstream_input(),
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


class WorkflowJSONOutput(_BaseComfyBIONode):
    CATEGORY = "ComfyBIO/Orchestration"
    RETURN_NAMES = ("workflow_json",)

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {"required": {"report_markdown": cls._upstream_input(), "workflow_json_path": cls._string_input("workflow.json")}}
