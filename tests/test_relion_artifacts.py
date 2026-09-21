from relion_artifacts import (
    artifact_badge, scan_job_artifacts, list_class_maps, referenced_class_maps, job_stats, parse_job_options,
)


def _touch(path):
    path.write_text("")


def test_succeeded_job_with_postprocess_and_half_maps(tmp_path):
    job_dir = tmp_path / "Refine3D" / "job003"
    job_dir.mkdir(parents=True)
    _touch(job_dir / "RELION_JOB_EXIT_SUCCESS")
    _touch(job_dir / "postprocess.mrc")
    _touch(job_dir / "run_half1_class001_unfil.mrc")
    _touch(job_dir / "run_half2_class001_unfil.mrc")

    artifacts = scan_job_artifacts(job_dir)
    assert artifacts["state"] == "succeeded"
    assert artifacts["postprocess_map"] == job_dir / "postprocess.mrc"
    assert artifacts["half_map_1"] == job_dir / "run_half1_class001_unfil.mrc"
    assert artifacts["half_map_2"] == job_dir / "run_half2_class001_unfil.mrc"

    badge = artifact_badge(artifacts)
    assert "[succeeded]" in badge
    assert "[postprocess]" in badge
    assert "[half-maps]" in badge
    assert "[map]" not in badge  # postprocess present, so no separate "map" tag


def test_failed_job_state_marker(tmp_path):
    job_dir = tmp_path / "Class3D" / "job002"
    job_dir.mkdir(parents=True)
    _touch(job_dir / "RELION_JOB_EXIT_FAILURE")

    artifacts = scan_job_artifacts(job_dir)
    assert artifacts["state"] == "failed"
    assert artifact_badge(artifacts) == "[failed]"


def test_running_job_inferred_from_run_out(tmp_path):
    job_dir = tmp_path / "Class2D" / "job001"
    job_dir.mkdir(parents=True)
    _touch(job_dir / "run.out")

    artifacts = scan_job_artifacts(job_dir)
    assert artifacts["state"] == "running"


def test_unknown_state_and_mask_detection(tmp_path):
    job_dir = tmp_path / "MaskCreate" / "job004"
    job_dir.mkdir(parents=True)
    _touch(job_dir / "mask_tight.mrc")

    artifacts = scan_job_artifacts(job_dir)
    assert artifacts["state"] == "unknown"
    assert artifacts["mask"] == job_dir / "mask_tight.mrc"
    assert "[mask]" in artifact_badge(artifacts)


def test_latest_map_fallback_when_no_postprocess(tmp_path):
    job_dir = tmp_path / "Class3D" / "job002"
    job_dir.mkdir(parents=True)
    _touch(job_dir / "run_it025_class001.mrc")

    artifacts = scan_job_artifacts(job_dir)
    assert artifacts["latest_map"] == job_dir / "run_it025_class001.mrc"
    assert artifacts["postprocess_map"] is None
    badge = artifact_badge(artifacts)
    assert "[map]" in badge
    assert "[postprocess]" not in badge


def test_missing_directory_returns_unknown_empty(tmp_path):
    artifacts = scan_job_artifacts(tmp_path / "does_not_exist")
    assert artifacts["state"] == "unknown"
    assert artifacts["postprocess_map"] is None


def test_list_class_maps_keeps_latest_iteration_per_class(tmp_path):
    job_dir = tmp_path / "Class3D" / "job003"
    job_dir.mkdir(parents=True)
    for it in (10, 25):
        for cls in (1, 2, 3):
            _touch(job_dir / ("run_it%03d_class%03d.mrc" % (it, cls)))

    maps = list_class_maps(job_dir)
    assert len(maps) == 3
    assert all("it025" in str(p) for p in maps)
    assert [p.name for p in maps] == [
        "run_it025_class001.mrc", "run_it025_class002.mrc", "run_it025_class003.mrc",
    ]


def test_list_class_maps_no_iteration_prefix(tmp_path):
    job_dir = tmp_path / "Class3D" / "job002"
    job_dir.mkdir(parents=True)
    _touch(job_dir / "run_class001.mrc")
    _touch(job_dir / "run_class002.mrc")

    maps = list_class_maps(job_dir)
    assert [p.name for p in maps] == ["run_class001.mrc", "run_class002.mrc"]


def test_list_class_maps_empty_when_no_match(tmp_path):
    job_dir = tmp_path / "Import" / "job001"
    job_dir.mkdir(parents=True)
    _touch(job_dir / "note.txt")
    assert list_class_maps(job_dir) == []
    assert list_class_maps(tmp_path / "does_not_exist") == []


def test_referenced_class_maps_finds_the_one_named_in_job_star(tmp_path):
    class_dir = tmp_path / "Class3D" / "job003"
    class_dir.mkdir(parents=True)
    candidates = [class_dir / ("run_it025_class%03d.mrc" % c) for c in (1, 2, 3)]
    for p in candidates:
        _touch(p)

    child_dir = tmp_path / "Refine3D" / "job004"
    child_dir.mkdir(parents=True)
    (child_dir / "job.star").write_text(
        "data_job\n\nloop_\n_rlnJobOptionVariable\n_rlnJobOptionValue\n"
        "fn_ref Class3D/job003/run_it025_class002.mrc\n"
    )

    referenced = referenced_class_maps(child_dir, candidates)
    assert referenced == {str(candidates[1])}


def test_referenced_class_maps_empty_when_no_job_star(tmp_path):
    class_dir = tmp_path / "Class3D" / "job003"
    class_dir.mkdir(parents=True)
    candidates = [class_dir / "run_it025_class001.mrc"]

    child_dir = tmp_path / "Refine3D" / "job004"
    child_dir.mkdir(parents=True)

    assert referenced_class_maps(child_dir, candidates) == set()


def test_referenced_class_maps_backup_selection_positional_flags(tmp_path):
    # Real RELION "Select classes" job format: backup_selection.star has no
    # filenames at all, just a bare _rlnSelected 0/1 list in class order.
    class_dir = tmp_path / "Class3D" / "job001"
    class_dir.mkdir(parents=True)
    candidates = [class_dir / ("run_it025_class%03d.mrc" % c) for c in (1, 2, 3, 4)]
    for p in candidates:
        _touch(p)

    select_dir = tmp_path / "Select" / "job002"
    select_dir.mkdir(parents=True)
    (select_dir / "backup_selection.star").write_text(
        "\n# version 30001\n\ndata_\n\nloop_ \n_rlnSelected #1 \n"
        "           0 \n           0 \n           1 \n           1 \n \n"
    )

    referenced = referenced_class_maps(select_dir, candidates)
    assert referenced == {str(candidates[2]), str(candidates[3])}


def test_referenced_class_maps_ignores_particles_star_and_size_cutoff(tmp_path, monkeypatch):
    class_dir = tmp_path / "Class3D" / "job001"
    class_dir.mkdir(parents=True)
    candidates = [class_dir / "run_it025_class001.mrc"]
    _touch(candidates[0])

    select_dir = tmp_path / "Select" / "job002"
    select_dir.mkdir(parents=True)
    # a huge/irrelevant particles.star that happens to mention the filename
    # must never be scanned (both by name and by the size cutoff)
    (select_dir / "particles.star").write_text("run_it025_class001.mrc\n")
    monkeypatch.setattr("relion_artifacts._MAX_SCAN_BYTES", 10)
    (select_dir / "note.txt").write_text("run_it025_class001.mrc — way over the size cutoff\n")

    assert referenced_class_maps(select_dir, candidates) == set()


_MODEL_STAR_TEXT = """
data_model_general

_rlnReferenceDimensionality                        3
_rlnCurrentResolution                      22.996479
_rlnCurrentImageSize                              52


data_model_groups

loop_
_rlnGroupNumber #1
_rlnGroupName #2
_rlnGroupNrParticles #3
           1 group_1  1200
           2 group_2   950
"""


def test_job_stats_reads_resolution_and_sums_particles_from_model_star(tmp_path):
    job_dir = tmp_path / "Refine3D" / "job006"
    job_dir.mkdir(parents=True)
    (job_dir / "run_model.star").write_text(_MODEL_STAR_TEXT)

    stats = job_stats(job_dir)
    assert stats["resolution_angstrom"] == 22.996479
    assert stats["n_particles"] == 2150


def test_job_stats_prefers_latest_iteration_model_star_when_not_finished(tmp_path):
    job_dir = tmp_path / "Class3D" / "job001"
    job_dir.mkdir(parents=True)
    (job_dir / "run_it010_model.star").write_text(
        "data_model_general\n\n_rlnCurrentResolution        30.0\n"
    )
    (job_dir / "run_it025_model.star").write_text(_MODEL_STAR_TEXT)

    stats = job_stats(job_dir)
    assert stats["resolution_angstrom"] == 22.996479


def test_job_stats_prefers_postprocess_resolution_when_present(tmp_path):
    job_dir = tmp_path / "PostProcess" / "job010"
    job_dir.mkdir(parents=True)
    (job_dir / "postprocess.star").write_text(
        "data_general\n\n_rlnFinalResolution        3.142\n"
    )
    (job_dir / "run_model.star").write_text(_MODEL_STAR_TEXT)

    stats = job_stats(job_dir)
    assert stats["resolution_angstrom"] == 3.142
    assert stats["n_particles"] == 2150


def test_job_stats_empty_when_no_files(tmp_path):
    job_dir = tmp_path / "Import" / "job001"
    job_dir.mkdir(parents=True)
    assert job_stats(job_dir) == {"resolution_angstrom": None, "n_particles": None}


def test_parse_job_options_reads_variable_value_loop(tmp_path):
    job_dir = tmp_path / "Refine3D" / "job006"
    job_dir.mkdir(parents=True)
    (job_dir / "job.star").write_text(
        "\ndata_job\n\n_rlnJobTypeLabel   relion.refine3d.tomo\n\n"
        "data_joboptions_values\n\nloop_ \n"
        "_rlnJobOptionVariable #1 \n_rlnJobOptionValue #2 \n"
        "particle_diameter        350 \n"
        "sym_name         C6 \n"
        '   fn_ref         "" \n'
    )

    options = parse_job_options(job_dir)
    assert options["particle_diameter"] == "350"
    assert options["sym_name"] == "C6"
    assert options["fn_ref"] == ""


def test_parse_job_options_empty_when_no_job_star(tmp_path):
    job_dir = tmp_path / "Import" / "job001"
    job_dir.mkdir(parents=True)
    assert parse_job_options(job_dir) == {}
