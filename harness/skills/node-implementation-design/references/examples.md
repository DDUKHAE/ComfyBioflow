# Node Implementation Design Examples

## Contract (operation → node)

`SalmonIndexNode` maps to the `salmon_index` operation and outputs a `STRING` path to a salmon index directory.

`DESeq2VisualizationNode` maps to `deseq2_visualization` and outputs a `STRING` plot directory plus an optional `IMAGE` preview.

## Socket naming (do not infer)

A test agent, given only the skill docs, correctly reconstructed the `bulk_rna_seq_salmon_ref` stage/tool/node sequence with zero errors, but guessed two input socket names wrong by inferring a `<upstream_output_name>` pattern instead of looking them up:

- `TximportNode`'s input is `salmon_quant_dir_path` (not `salmon_quant_dir`, the name of `SalmonQuantNode`'s output it connects from).
- `ComfyBIOReportNode`'s input is `plot_dir_path` (not `plot_dir`, the name of `DESeq2VisualizationNode`'s output it connects from).

Both wrong guesses were plausible — the input usually echoes the upstream output's name — but this isn't a rule the codebase actually follows consistently, so it isn't safe to infer. Always confirm with `emit_node_spec.py` or `ARCHITECTURE.md`.

## Widget design

`BiopythonSequenceInfoNode` is a lightweight runnable utility node that accepts a FASTA path, returns a summary output path, and does not require external command-line tools.

`SalmonQuantNode` should expose index path, FASTQ paths, output directory, thread count, read layout, and strandness as core UI parameters.
