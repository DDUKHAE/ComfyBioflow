from pathlib import Path

from .ref_nodes import (
    ComfyBIOReportNode,
    DESeq2AnalysisNode,
    DESeq2VisualizationNode,
    FastpQCNode,
    FastpTrimNode,
    ScRNAReportNode,
    ScRNAVisualizationNode,
    SalmonIndexNode,
    SalmonQuantNode,
    SampleMetadataValidatorNode,
    ScanpyClusterNode,
    ScanpyMarkerGenesNode,
    ScanpyNormalizeNode,
    ScanpyQCNode,
    TenxCountNode,
    TximportNode,
)
from .variant_nodes import (
    BcftoolsCallNode,
    BcftoolsFilterNode,
    BwaMem2AlignNode,
    BwaMem2IndexNode,
    MarkDuplicatesNode,
    VariantInputValidatorNode,
    VariantReportNode,
    VariantVisualizationNode,
)
from .atac_nodes import (
    AtacBwaMem2AlignNode,
    AtacBwaMem2IndexNode,
    AtacFastpTrimNode,
    AtacInputValidatorNode,
    AtacMarkDuplicatesNode,
    AtacPeakVisualizationNode,
    AtacQualityFilterNode,
    AtacReportNode,
    Macs3PeakCallingNode,
)
from .metagenome_nodes import (
    BrackenAbundanceNode,
    Kraken2ClassifyNode,
    MetagenomeFastpTrimNode,
    MetagenomeInputValidatorNode,
    MetagenomeReportNode,
    MetagenomeVisualizationNode,
)
from .assembly_nodes import (
    AssemblyFastpTrimNode,
    AssemblyInputValidatorNode,
    AssemblyReportNode,
    AssemblyVisualizationNode,
    QuastQcNode,
    SpadesAssembleNode,
)


NODE_CLASS_MAPPINGS = {
    "SampleMetadataValidatorNode": SampleMetadataValidatorNode,
    "FastpQCNode": FastpQCNode,
    "FastpTrimNode": FastpTrimNode,
    "TenxCountNode": TenxCountNode,
    "ScanpyQCNode": ScanpyQCNode,
    "ScanpyNormalizeNode": ScanpyNormalizeNode,
    "ScanpyClusterNode": ScanpyClusterNode,
    "ScanpyMarkerGenesNode": ScanpyMarkerGenesNode,
    "ScRNAVisualizationNode": ScRNAVisualizationNode,
    "ScRNAReportNode": ScRNAReportNode,
    "SalmonIndexNode": SalmonIndexNode,
    "SalmonQuantNode": SalmonQuantNode,
    "TximportNode": TximportNode,
    "DESeq2AnalysisNode": DESeq2AnalysisNode,
    "DESeq2VisualizationNode": DESeq2VisualizationNode,
    "ComfyBIOReportNode": ComfyBIOReportNode,
    "VariantInputValidatorNode": VariantInputValidatorNode,
    "BwaMem2IndexNode": BwaMem2IndexNode,
    "BwaMem2AlignNode": BwaMem2AlignNode,
    "MarkDuplicatesNode": MarkDuplicatesNode,
    "BcftoolsCallNode": BcftoolsCallNode,
    "BcftoolsFilterNode": BcftoolsFilterNode,
    "VariantVisualizationNode": VariantVisualizationNode,
    "VariantReportNode": VariantReportNode,
    "AtacInputValidatorNode": AtacInputValidatorNode,
    "AtacFastpTrimNode": AtacFastpTrimNode,
    "AtacBwaMem2IndexNode": AtacBwaMem2IndexNode,
    "AtacBwaMem2AlignNode": AtacBwaMem2AlignNode,
    "AtacMarkDuplicatesNode": AtacMarkDuplicatesNode,
    "AtacQualityFilterNode": AtacQualityFilterNode,
    "Macs3PeakCallingNode": Macs3PeakCallingNode,
    "AtacPeakVisualizationNode": AtacPeakVisualizationNode,
    "AtacReportNode": AtacReportNode,
    "MetagenomeInputValidatorNode": MetagenomeInputValidatorNode,
    "MetagenomeFastpTrimNode": MetagenomeFastpTrimNode,
    "Kraken2ClassifyNode": Kraken2ClassifyNode,
    "BrackenAbundanceNode": BrackenAbundanceNode,
    "MetagenomeVisualizationNode": MetagenomeVisualizationNode,
    "MetagenomeReportNode": MetagenomeReportNode,
    "AssemblyInputValidatorNode": AssemblyInputValidatorNode,
    "AssemblyFastpTrimNode": AssemblyFastpTrimNode,
    "SpadesAssembleNode": SpadesAssembleNode,
    "QuastQcNode": QuastQcNode,
    "AssemblyVisualizationNode": AssemblyVisualizationNode,
    "AssemblyReportNode": AssemblyReportNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    node_type: node_type.replace("Node", "").replace("Workflow", "Workflow ")
    for node_type in NODE_CLASS_MAPPINGS
}


def resolve_node_class(node_type: str):
    try:
        return NODE_CLASS_MAPPINGS[node_type]
    except KeyError as error:
        raise KeyError(f"No ComfyBIO custom node class registered for {node_type}") from error


def _load_autogen_nodes() -> None:
    """Scan nodes/autogen/*.py (written by bioflow_harness.autogen.node_synthesizer for
    self-extended domains) and merge their AUTOGEN_NODE_CLASSES into the mappings above.
    New autogen modules are picked up automatically — this function does not need editing
    when a new self-extended domain/tool is added."""
    import importlib
    import pkgutil

    autogen_dir = Path(__file__).parent / "autogen"
    if not autogen_dir.exists():
        return
    for module_info in pkgutil.iter_modules([str(autogen_dir)]):
        module = importlib.import_module(f"nodes.autogen.{module_info.name}")
        for class_name in getattr(module, "AUTOGEN_NODE_CLASSES", []):
            node_cls = getattr(module, class_name)
            NODE_CLASS_MAPPINGS[class_name] = node_cls
            NODE_DISPLAY_NAME_MAPPINGS[class_name] = class_name.replace("Node", "")


_load_autogen_nodes()
