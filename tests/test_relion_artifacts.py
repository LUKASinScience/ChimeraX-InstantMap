from relion_artifacts import artifact_badge, scan_job_artifacts


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
