from pathlib import Path

from relion_treebuild import build_tree, ordered_jobs, render_svg


def _make_project(tmp_path):
    (tmp_path / "Import" / "job001").mkdir(parents=True)
    (tmp_path / "Class3D" / "job002").mkdir(parents=True)
    (tmp_path / "Import" / "job001" / "RELION_JOB_EXIT_SUCCESS").touch()
    (tmp_path / "Class3D" / "job002" / "RELION_JOB_EXIT_SUCCESS").touch()
    (tmp_path / "default_pipeline.star").write_text(
        "data_pipeline_processes\n"
        "loop_\n"
        "_rlnPipeLineProcessName\n"
        "_rlnPipeLineProcessTypeLabel\n"
        "_rlnPipeLineProcessStatusLabel\n"
        "Import/job001/ relion.import Succeeded\n"
        "Class3D/job002/ relion.class3d Succeeded\n"
        "\n"
        "data_pipeline_nodes\n"
        "loop_\n"
        "_rlnPipeLineNodeName\n"
        "_rlnPipeLineNodeTypeLabel\n"
        "n1 particles\n"
        "\n"
        "data_pipeline_input_edges\n"
        "loop_\n"
        "_rlnPipeLineEdgeFromNode\n"
        "_rlnPipeLineEdgeProcess\n"
        "n1 Class3D/job002/\n"
        "\n"
        "data_pipeline_output_edges\n"
        "loop_\n"
        "_rlnPipeLineEdgeProcess\n"
        "_rlnPipeLineEdgeToNode\n"
        "Import/job001/ n1\n"
    )
    return tmp_path


def test_build_tree_orders_root_before_child(tmp_path):
    project = _make_project(tmp_path)
    tree = build_tree(project)
    jobs = ordered_jobs(tree)
    assert jobs == ["Import/job001", "Class3D/job002"]
    assert tree["parents"]["Class3D/job002"] == {"Import/job001"}
    assert tree["artifacts"]["Class3D/job002"]["state"] == "succeeded"


def test_build_tree_selected_job_restricts_to_upstream(tmp_path):
    project = _make_project(tmp_path)
    tree = build_tree(project, selected="Import/job001")
    assert ordered_jobs(tree) == ["Import/job001"]


def test_render_svg_contains_both_jobs(tmp_path):
    project = _make_project(tmp_path)
    tree = build_tree(project)
    svg = render_svg(tree)
    assert svg.startswith("<svg")
    assert "Import/job001" in svg
    assert "Class3D/job002" in svg
