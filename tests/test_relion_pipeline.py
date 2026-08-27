from relion_pipeline import (
    build_parents,
    layers,
    load_pipeline,
    parse_pipeline_star,
    upstream,
)


def test_parse_pipeline_star_handles_quoted_alias_with_space():
    # Regression for the shlex fix: a naive whitespace split would misalign
    # every column after the quoted field.
    text = (
        "data_pipeline_processes\n"
        "\n"
        "loop_\n"
        "_rlnPipeLineProcessName #1\n"
        "_rlnPipeLineProcessAlias #2\n"
        "_rlnPipeLineProcessTypeLabel #3\n"
        "_rlnPipeLineProcessStatusLabel #4\n"
        'Refine3D/job003/ "My Refine Run" relion.refine3d Succeeded\n'
    )
    parsed = parse_pipeline_star(text)
    assert len(parsed["processes"]) == 1
    row = parsed["processes"][0]
    assert row["_rlnPipeLineProcessName"] == "Refine3D/job003/"
    assert row["_rlnPipeLineProcessAlias"] == "My Refine Run"
    assert row["_rlnPipeLineProcessTypeLabel"] == "relion.refine3d"
    assert row["_rlnPipeLineProcessStatusLabel"] == "Succeeded"


def _write_chain_pipeline(project):
    (project / "default_pipeline.star").write_text(
        "data_pipeline_processes\n"
        "\n"
        "loop_\n"
        "_rlnPipeLineProcessName #1\n"
        "_rlnPipeLineProcessTypeLabel #2\n"
        "_rlnPipeLineProcessStatusLabel #3\n"
        "Import/job001/ relion.import.movies Succeeded\n"
        "CtfFind/job002/ relion.ctffind.ctffind4 Succeeded\n"
        "Class2D/job003/ relion.class2d Succeeded\n"
        "Class3D/job004/ relion.class3d Succeeded\n"
        "Refine3D/job005/ relion.refine3d Succeeded\n"
        "PostProcess/job006/ relion.postprocess Succeeded\n"
        "\n"
        "data_pipeline_output_edges\n"
        "\n"
        "loop_\n"
        "_rlnPipeLineEdgeProcess #1\n"
        "_rlnPipeLineEdgeToNode #2\n"
        "Import/job001/ Import/job001/particles.star\n"
        "CtfFind/job002/ CtfFind/job002/micrographs_ctf.star\n"
        "Class2D/job003/ Class2D/job003/particles.star\n"
        "Class3D/job004/ Class3D/job004/particles.star\n"
        "Refine3D/job005/ Refine3D/job005/run_class001.mrc\n"
        "\n"
        "data_pipeline_input_edges\n"
        "\n"
        "loop_\n"
        "_rlnPipeLineEdgeFromNode #1\n"
        "_rlnPipeLineEdgeProcess #2\n"
        "Import/job001/particles.star CtfFind/job002/\n"
        "CtfFind/job002/micrographs_ctf.star Class2D/job003/\n"
        "Class2D/job003/particles.star Class3D/job004/\n"
        "Class3D/job004/particles.star Refine3D/job005/\n"
        "Refine3D/job005/run_class001.mrc PostProcess/job006/\n"
    )


def test_upstream_and_layers_give_chronological_lineage(tmp_path):
    _write_chain_pipeline(tmp_path)

    procs, node_to_prod, proc_to_in = load_pipeline(tmp_path)
    parents = build_parents(procs, node_to_prod, proc_to_in)

    selected = "Refine3D/job005"
    keep, sub = upstream(selected, parents)

    # PostProcess is downstream of the selected job, must not be included
    assert keep == {
        "Import/job001",
        "CtfFind/job002",
        "Class2D/job003",
        "Class3D/job004",
        "Refine3D/job005",
    }

    ordered_layers = layers(selected, sub)
    ordered = [j for layer in ordered_layers for j in layer]
    assert ordered == [
        "Import/job001",
        "CtfFind/job002",
        "Class2D/job003",
        "Class3D/job004",
        "Refine3D/job005",
    ]
