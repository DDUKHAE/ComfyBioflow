import bioflow_harness.comfy.workflow_schema as schema_module


def test_workflow_schema_does_not_import_executable_nodes():
    source = __import__("inspect").getsource(schema_module)
    assert "custom_nodes" not in source
    assert "NODE_CLASS_MAPPINGS" not in source or "node_catalog" in source


def test_nodes_package_registers_classes():
    import nodes

    assert nodes.NODE_CLASS_MAPPINGS
    assert "SalmonQuantNode" in nodes.NODE_CLASS_MAPPINGS


def _widget_input_count(input_types: dict) -> int:
    required = input_types.get("required", {})
    count = 0
    for _name, spec in required.items():
        options = spec[1] if isinstance(spec, tuple) and len(spec) > 1 else {}
        if not (isinstance(options, dict) and options.get("forceInput")):
            count += 1
    return count


def test_catalog_widgets_match_node_input_arity():
    import nodes
    from bioflow_harness.comfy.node_catalog import default_node_catalog

    catalog = default_node_catalog()
    for node_type, node_class in nodes.NODE_CLASS_MAPPINGS.items():
        if node_type not in catalog:
            continue
        widget_count = _widget_input_count(node_class.INPUT_TYPES())
        assert widget_count == len(catalog[node_type].widgets), (
            f"{node_type}: INPUT_TYPES widgets={widget_count} vs catalog widgets={len(catalog[node_type].widgets)}"
        )


def test_salmon_quant_uses_fastq_dir_and_metadata():
    import nodes

    required = nodes.NODE_CLASS_MAPPINGS["SalmonQuantNode"].INPUT_TYPES()["required"]
    assert "fastq_dir" in required
    assert "metadata_csv" in required
    assert "fastq_1" not in required
