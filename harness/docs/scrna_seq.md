# scRNA-seq Domain Expansion

This document records the first non-bulk domain expansion used to prove that ComfyBIO can move beyond documentation into route selection, node implementation, workflow JSON generation, and validation.

## Scope

Supported domain: `scrna_seq`

Official route: `scrna_seq_scanpy_ref`

The route targets a 10x-style single-cell RNA-seq analysis path from FASTQ or count matrix inputs through QC, normalization, clustering, marker-gene discovery, visualization, report generation, and workflow export.

## Canonical Inputs

- 10x FASTQ directory
- sample ID
- Cell Ranger-compatible reference directory
- optional existing filtered feature-barcode matrix directory
- optional `extra_command` text for site-specific runtime flags

## Workflow Stages

1. `request_loading`: capture the normalized user request.
2. `tenx_count`: produce a filtered feature-barcode matrix from 10x FASTQ inputs.
3. `scrna_qc`: load the matrix and apply cell/gene QC thresholds.
4. `scrna_normalization`: normalize counts and create a normalized `.h5ad` artifact.
5. `scrna_clustering`: compute PCA/neighbors/UMAP and cluster labels.
6. `scrna_marker_genes`: identify marker genes per cluster.
7. `scrna_visualization`: create UMAP, cluster, and marker-gene plots.
8. `scrna_reporting`: summarize QC, clustering, markers, plots, software assumptions, and artifact paths.
9. `workflow_export`: write the route-specific ComfyUI workflow JSON path.

## Artifact Contract

- `filtered_feature_bc_matrix`: output from `TenxCountNode`; input to `ScanpyQCNode`
- `qc.h5ad`: output from `ScanpyQCNode`; input to `ScanpyNormalizeNode`
- `normalized.h5ad`: output from `ScanpyNormalizeNode`; input to `ScanpyClusterNode`
- `clustered.h5ad`: output from `ScanpyClusterNode`; input to marker detection, visualization, and report nodes
- `markers.csv`: output from `ScanpyMarkerGenesNode`; input to visualization and report nodes
- `plots/`: output from `ScRNAVisualizationNode`; input to report generation and preview image display
- `scrna_report.md`: output from `ScRNAReportNode`

## Node Implementation

The ComfyUI custom-node classes are implemented under `bioflow_harness.custom_nodes.ref_nodes` and registered through `bioflow_harness.custom_nodes.registry`.

Implemented node types:

- `TenxCountNode`
- `ScanpyQCNode`
- `ScanpyNormalizeNode`
- `ScanpyClusterNode`
- `ScanpyMarkerGenesNode`
- `ScRNAVisualizationNode`
- `ScRNAReportNode`

The route uses the shared `WorkflowRequestLoader`, `WorkflowJSONOutput`, and built-in `PreviewImage` nodes. `ScRNAVisualizationNode` exposes an `IMAGE` output so the generated workflow includes a visible preview connection.

## Validation Status

The implemented success gate is workflow generation and ComfyUI-loadable graph structure:

- prompts mentioning single-cell RNA-seq, 10x, UMAP, or marker genes route to `scrna_seq`
- the planner selects `scrna_seq_scanpy_ref`
- every route stage maps to a registered REF node type
- generated workflow JSON has LiteGraph-visible links between nodes
- route-specific widgets show scRNA paths instead of bulk RNA-seq defaults
- visualization connects to `PreviewImage`

Real execution against a full 10x fixture remains a later runtime-readiness gate. Until that is added, this route should be treated as a workflow-construction implementation rather than a proven production analysis runner.
