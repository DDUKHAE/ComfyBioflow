import bioflow_harness.comfy.workflow_schema as schema_module


def test_workflow_schema_does_not_import_executable_nodes():
    source = __import__("inspect").getsource(schema_module)
    assert "custom_nodes" not in source
    assert "NODE_CLASS_MAPPINGS" not in source or "node_catalog" in source
