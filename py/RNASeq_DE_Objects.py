from __future__ import annotations

from typing_extensions import override
# pyrefly: ignore [missing-import]
from comfy_api.latest import io


class _Base(io.ComfyNode):
    OUTPUT_NODE = True


class DESeq2_run(_Base):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="DESeq2_run",
            display_name="DESeq2 run",
            category="Transcriptomics/DifferentialExpression",
            inputs=[
                io.String.Input("counts_path", multiline=False, default=""),
                io.String.Input("metadata_path", multiline=False, default=""),
                io.String.Input("condition_col", multiline=False, default="condition"),
                io.String.Input("reference_level", multiline=False, default="control"),
                io.String.Input("output_path", multiline=False, default=""),
            ],
            outputs=[
                io.String.Output("results_path"),
            ],
        )

    @classmethod
    def execute(
        cls, counts_path, metadata_path, condition_col, reference_level, output_path
    ) -> io.NodeOutput:
        from llm_core.transcriptomics.de import run_deseq2
        out = run_deseq2(
            counts_path=counts_path,
            metadata_path=metadata_path,
            condition_col=condition_col,
            reference_level=reference_level,
            output_path=output_path or None,
        )
        return io.NodeOutput(out)
