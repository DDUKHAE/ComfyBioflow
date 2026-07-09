REQUIRED_WORKFLOW_KEYS = {"metadata", "nodes", "links"}
SUPPORTED_OUTPUT_TYPES = {"STRING", "IMAGE"}
BUILTIN_NODE_TYPES = {"PreviewImage"}


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

    from bioflow_harness.comfy.node_catalog import default_node_catalog

    known_node_types = set(default_node_catalog().keys())
    node_id_set = set(node_ids)
    for node in workflow["nodes"]:
        node_type = node.get("type")
        if node_type not in known_node_types and node_type not in BUILTIN_NODE_TYPES:
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
    link_id_set = set()
    for link in workflow["links"]:
        link_id, origin_id, origin_slot, target_id, target_slot, link_type = _link_parts(link)
        link_ids.append(link_id)
        link_id_set.add(link_id)
        if origin_id not in node_id_set:
            raise WorkflowValidationError(f"Link {link_id} references missing origin_id: {origin_id}")
        if target_id not in node_id_set:
            raise WorkflowValidationError(f"Link {link_id} references missing target_id: {target_id}")
        if link_type not in SUPPORTED_OUTPUT_TYPES:
            raise WorkflowValidationError(f"Unsupported link type on link {link_id}: {link_type}")
        if not isinstance(origin_slot, int) or not isinstance(target_slot, int):
            raise WorkflowValidationError(f"Link {link_id} must use integer origin and target slots.")

    if link_ids != list(range(1, len(link_ids) + 1)):
        raise WorkflowValidationError(f"Workflow link ids must be sequential starting at 1: {link_ids}")

    for node in workflow["nodes"]:
        for input_def in node.get("inputs", []):
            input_link = input_def.get("link")
            if input_link is not None and input_link not in link_id_set:
                raise WorkflowValidationError(f"Node {node.get('id')} input link is missing from workflow links: {input_link}")
        for output_def in node.get("outputs", []):
            for output_link in output_def.get("links") or []:
                if output_link not in link_id_set:
                    raise WorkflowValidationError(
                        f"Node {node.get('id')} output link is missing from workflow links: {output_link}"
                    )

    return workflow


def _link_parts(link: dict | list) -> tuple[int, int, int, int, int, str]:
    if isinstance(link, list):
        if len(link) != 6:
            raise WorkflowValidationError(f"LiteGraph link must have 6 fields: {link}")
        link_id, origin_id, origin_slot, target_id, target_slot, link_type = link
        return link_id, origin_id, origin_slot, target_id, target_slot, link_type
    if isinstance(link, dict):
        return (
            link.get("id"),
            link.get("origin_id"),
            link.get("origin_slot"),
            link.get("target_id"),
            link.get("target_slot"),
            link.get("type"),
        )
    raise WorkflowValidationError(f"Workflow link must be a LiteGraph list or mapping: {link}")
