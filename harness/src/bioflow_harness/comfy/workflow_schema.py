REQUIRED_WORKFLOW_KEYS = {"metadata", "nodes", "links"}
SUPPORTED_OUTPUT_TYPES = {"STRING", "IMAGE"}


class WorkflowValidationError(ValueError):
    pass


def validate_workflow_export(workflow: dict) -> dict:
    missing = REQUIRED_WORKFLOW_KEYS - workflow.keys()
    if missing:
        raise WorkflowValidationError(f"Workflow export is missing keys: {sorted(missing)}")
    if not workflow["nodes"]:
        raise WorkflowValidationError("Workflow export must contain at least one node.")

    node_ids = [node.get("id") for node in workflow["nodes"]]
    expected_ids = list(range(1, len(node_ids) + 1))
    if node_ids != expected_ids:
        raise WorkflowValidationError(f"Workflow node ids must be sequential starting at 1: {node_ids}")

    try:
        from bioflow_harness.custom_nodes.registry import NODE_CLASS_MAPPINGS
    except ImportError as error:
        raise WorkflowValidationError("Could not import ComfyBIO custom node registry.") from error

    node_id_set = set(node_ids)
    for node in workflow["nodes"]:
        node_type = node.get("type")
        if node_type not in NODE_CLASS_MAPPINGS:
            raise WorkflowValidationError(f"Workflow references unregistered node type: {node_type}")
        if not node.get("title"):
            raise WorkflowValidationError(f"Node {node.get('id')} is missing a title.")
        if "metadata" not in node or "stage_id" not in node["metadata"]:
            raise WorkflowValidationError(f"Node {node.get('id')} is missing stage metadata.")
        for output in node.get("outputs", []):
            output_type = output.get("type")
            if output_type not in SUPPORTED_OUTPUT_TYPES:
                raise WorkflowValidationError(f"Unsupported output type on node {node.get('id')}: {output_type}")

    link_ids = []
    for link in workflow["links"]:
        link_ids.append(link.get("id"))
        origin_id = link.get("origin_id")
        target_id = link.get("target_id")
        if origin_id not in node_id_set:
            raise WorkflowValidationError(f"Link {link.get('id')} references missing origin_id: {origin_id}")
        if target_id not in node_id_set:
            raise WorkflowValidationError(f"Link {link.get('id')} references missing target_id: {target_id}")
        if link.get("type") not in SUPPORTED_OUTPUT_TYPES:
            raise WorkflowValidationError(f"Unsupported link type on link {link.get('id')}: {link.get('type')}")

    if link_ids != list(range(1, len(link_ids) + 1)):
        raise WorkflowValidationError(f"Workflow link ids must be sequential starting at 1: {link_ids}")

    return workflow
