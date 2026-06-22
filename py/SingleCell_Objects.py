from __future__ import annotations

import json
from typing_extensions import override
# pyrefly: ignore [missing-import]
from comfy_api.latest import io


class _Base(io.ComfyNode):
    OUTPUT_NODE = True


class SC_preprocess(_Base):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="SC_preprocess",
            display_name="SC preprocess",
            category="Transcriptomics/SingleCell",
            inputs=[
                io.String.Input("input_path", multiline=False, default=""),
                io.Int.Input("min_genes", default=200),
                io.Int.Input("min_cells", default=3),
                io.Int.Input("n_top_genes", default=2000),
                io.String.Input("output_path", multiline=False, default=""),
            ],
            outputs=[io.String.Output("output_path")],
        )

    @classmethod
    def execute(cls, input_path, min_genes, min_cells, n_top_genes, output_path) -> io.NodeOutput:
        from llm_core.transcriptomics.sc import run_sc_preprocess
        out = run_sc_preprocess(input_path, min_genes, min_cells, n_top_genes, output_path or None)
        return io.NodeOutput(out)


class SC_cluster(_Base):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="SC_cluster",
            display_name="SC cluster",
            category="Transcriptomics/SingleCell",
            inputs=[
                io.String.Input("input_path", multiline=False, default=""),
                io.Float.Input("resolution", default=0.5),
                io.Combo.Input("algorithm", options=["leiden", "louvain"], default="leiden"),
                io.String.Input("output_path", multiline=False, default=""),
            ],
            outputs=[io.String.Output("output_path")],
        )

    @classmethod
    def execute(cls, input_path, resolution, algorithm, output_path) -> io.NodeOutput:
        from llm_core.transcriptomics.sc import run_sc_cluster
        out = run_sc_cluster(input_path, resolution, algorithm, output_path or None)
        return io.NodeOutput(out)


class SC_annotate(_Base):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="SC_annotate",
            display_name="SC annotate",
            category="Transcriptomics/SingleCell",
            inputs=[
                io.String.Input("input_path", multiline=False, default=""),
                io.String.Input("marker_genes_json", multiline=True, default='{"T cell": ["CD3D", "CD3E"]}'),
                io.String.Input("output_path", multiline=False, default=""),
            ],
            outputs=[io.String.Output("output_path")],
        )

    @classmethod
    def execute(cls, input_path, marker_genes_json, output_path) -> io.NodeOutput:
        from llm_core.transcriptomics.sc import run_sc_annotate
        marker_genes = json.loads(marker_genes_json)
        out = run_sc_annotate(input_path, marker_genes, output_path or None)
        return io.NodeOutput(out)
