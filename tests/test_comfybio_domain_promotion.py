import importlib.util
import sys

import nodes
from bioflow_harness.comfy.node_catalog import default_node_catalog
from bioflow_harness.planner.tool_selector import load_registry

_MODULE_PATH = "harness/skills/domain-bootstrap/scripts/validate_domain_promotion.py"
_spec = importlib.util.spec_from_file_location("validate_domain_promotion", _MODULE_PATH)
validate_domain_promotion = importlib.util.module_from_spec(_spec)
sys.modules["validate_domain_promotion"] = validate_domain_promotion
_spec.loader.exec_module(validate_domain_promotion)
check_domain_promotion = validate_domain_promotion.check_domain_promotion

REGISTRY_PATH = "harness/registry/tool_selection_registry.yaml"


def test_variant_analysis_route_passes_promotion_gate():
    registry = load_registry(REGISTRY_PATH)
    report = check_domain_promotion(registry, "variant_analysis_bwa_ref", default_node_catalog(), nodes.NODE_CLASS_MAPPINGS)
    assert report.ready is True
    assert report.stub_node_types == []
    assert report.error is None


def test_scrna_route_fails_promotion_gate_because_nodes_are_stubs():
    registry = load_registry(REGISTRY_PATH)
    report = check_domain_promotion(registry, "scrna_seq_scanpy_ref", default_node_catalog(), nodes.NODE_CLASS_MAPPINGS)
    assert report.ready is False
    assert "TenxCountNode" in report.stub_node_types


def test_check_domain_promotion_surfaces_registry_validation_errors():
    registry = load_registry(REGISTRY_PATH)
    report = check_domain_promotion(registry, "does_not_exist", default_node_catalog(), nodes.NODE_CLASS_MAPPINGS)
    assert report.ready is False
    assert report.error is not None


def test_atac_seq_route_passes_promotion_gate():
    registry = load_registry(REGISTRY_PATH)
    report = check_domain_promotion(registry, "atac_seq_macs3_ref", default_node_catalog(), nodes.NODE_CLASS_MAPPINGS)
    assert report.ready is True
    assert report.stub_node_types == []
    assert report.error is None


def test_metagenome_route_passes_promotion_gate():
    registry = load_registry(REGISTRY_PATH)
    report = check_domain_promotion(registry, "metagenome_kraken2_ref", default_node_catalog(), nodes.NODE_CLASS_MAPPINGS)
    assert report.ready is True
    assert report.stub_node_types == []
    assert report.error is None


def test_genome_assembly_route_passes_promotion_gate():
    registry = load_registry(REGISTRY_PATH)
    report = check_domain_promotion(registry, "genome_assembly_spades_ref", default_node_catalog(), nodes.NODE_CLASS_MAPPINGS)
    assert report.ready is True
    assert report.stub_node_types == []
    assert report.error is None
