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

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {"required": {"request_payload": cls._string_input()}}

    def run(self, request_payload: str) -> tuple[str]:
        return (request_payload,)


class SampleMetadataValidatorNode(_BaseComfyBIONode):
    CATEGORY = "ComfyBIO/Input"

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "upstream": cls._upstream_input(),
                "sample_metadata": cls._string_input("sample_metadata.csv"),
                "extra_command": cls._extra_command_input(),
            }
        }


class FastpQCNode(_BaseComfyBIONode):
    CATEGORY = "ComfyBIO/QC"

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "upstream": cls._upstream_input(),
                "fastq_1": cls._string_input(),
                "fastq_2": cls._string_input(),
                "output_json": cls._string_input("fastp.json"),
                "threads": ("INT", {"default": 2, "min": 1, "max": 64}),
                "extra_command": cls._extra_command_input(),
            }
        }


class FastpTrimNode(_BaseComfyBIONode):
    CATEGORY = "ComfyBIO/QC"

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "upstream": cls._upstream_input(),
                "fastq_1": cls._string_input(),
                "fastq_2": cls._string_input(),
                "output_dir": cls._string_input("trimmed"),
                "threads": ("INT", {"default": 2, "min": 1, "max": 64}),
                "extra_command": cls._extra_command_input(),
            }
        }


class SalmonIndexNode(_BaseComfyBIONode):
    CATEGORY = "ComfyBIO/Quantification"

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "upstream": cls._upstream_input(),
                "transcriptome_fasta": cls._string_input("toy_transcriptome.fasta"),
                "index_dir": cls._string_input("salmon_index"),
                "threads": ("INT", {"default": 2, "min": 1, "max": 64}),
                "extra_command": cls._extra_command_input(),
            }
        }


class SalmonQuantNode(_BaseComfyBIONode):
    CATEGORY = "ComfyBIO/Quantification"

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "upstream": cls._upstream_input(),
                "index_dir": cls._string_input("salmon_index"),
                "fastq_1": cls._string_input(),
                "fastq_2": cls._string_input(),
                "output_dir": cls._string_input("salmon_quant"),
                "read_layout": ("STRING", {"default": "A"}),
                "threads": ("INT", {"default": 2, "min": 1, "max": 64}),
                "extra_command": cls._extra_command_input(),
            }
        }


class TximportNode(_BaseComfyBIONode):
    CATEGORY = "ComfyBIO/Differential Expression"

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "upstream": cls._upstream_input(),
                "salmon_quant_dir": cls._string_input("salmon_quant"),
                "output_count_matrix": cls._string_input("deseq2/count_matrix.csv"),
                "extra_command": cls._extra_command_input(),
            }
        }


class DESeq2AnalysisNode(_BaseComfyBIONode):
    CATEGORY = "ComfyBIO/Differential Expression"

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "upstream": cls._upstream_input(),
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

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "upstream": cls._upstream_input(),
                "count_matrix": cls._string_input("deseq2/count_matrix.csv"),
                "results_csv": cls._string_input("deseq2/results.csv"),
                "plot_dir": cls._string_input("plots"),
                "extra_command": cls._extra_command_input(),
            }
        }


class ComfyBIOReportNode(_BaseComfyBIONode):
    CATEGORY = "ComfyBIO/Reporting"

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "upstream": cls._upstream_input(),
                "results_csv": cls._string_input("deseq2/results.csv"),
                "plot_dir": cls._string_input("plots"),
                "report_path": cls._string_input("report/comfybio_report.md"),
                "extra_command": cls._extra_command_input(),
            }
        }


class WorkflowJSONOutput(_BaseComfyBIONode):
    CATEGORY = "ComfyBIO/Orchestration"

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {"required": {"upstream": cls._upstream_input(), "workflow_json_path": cls._string_input("workflow.json")}}
