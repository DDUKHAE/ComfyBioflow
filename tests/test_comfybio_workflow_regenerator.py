import shutil
from pathlib import Path

from bioflow_harness.comfy.workflow_regenerator import regenerate_bulk_rna_seq_workflow

QUICKSTART_FIXTURE = Path("harness/examples/fixtures/quickstart")


def _source_workflow():
    return {"version": 0.4, "metadata": {"route_id": "bulk_rna_seq_salmon_ref", "domain": "bulk_rna_seq"}, "nodes": [], "links": []}


def test_regenerated_paths_use_the_actual_fixture_dir_name_not_hardcoded_quickstart(tmp_path):
    # Regression test: regenerate_bulk_rna_seq_workflow used to hardcode the literal string
    # "quickstart" in every generated widget path instead of deriving it from fixture_dir,
    # so running the audit/repair loop against any differently-named fixture directory
    # silently wired the "repaired" workflow to point at .../runs/quickstart/... instead of
    # a path derived from the real fixture. Use a fixture directory with a different name
    # to prove the fix.
    custom_fixture_dir = tmp_path / "fixtures" / "custom_run_fixture"
    shutil.copytree(QUICKSTART_FIXTURE, custom_fixture_dir)

    regenerated = regenerate_bulk_rna_seq_workflow(_source_workflow(), custom_fixture_dir)

    all_paths = " ".join(
        str(value)
        for node in regenerated["nodes"]
        for value in node.get("widgets_values", [])
        if isinstance(value, str)
    )
    assert "custom_run_fixture" in all_paths
    assert "quickstart" not in all_paths
    assert str(custom_fixture_dir.parent.parent / "runs" / "custom_run_fixture") in all_paths
