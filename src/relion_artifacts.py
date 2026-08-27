import re

STATE_MARKERS = (
    ("RELION_JOB_EXIT_FAILURE", "failed"),
    ("RELION_JOB_EXIT_ABORTED", "aborted"),
    ("RELION_JOB_ABORT_NOW", "aborted"),
    ("RELION_JOB_EXIT_SUCCESS", "succeeded"),
)


def scan_job_artifacts(job_dir):
    """Classify a RELION job directory's output files. Filename conventions
    and state-sentinel files follow RELION's own output layout; unmatched
    files are simply ignored (best-effort)."""
    try:
        names = [f.name for f in job_dir.iterdir() if f.is_file()]
    except OSError:
        names = []

    state = "unknown"
    for marker, marker_state in STATE_MARKERS:
        if marker in names:
            state = marker_state
            break
    else:
        if any(n.lower() in ("run.out", "run.err") for n in names):
            state = "running"

    artifacts = {
        "state": state,
        "postprocess_map": None,
        "latest_map": None,
        "half_map_1": None,
        "half_map_2": None,
        "mask": None,
    }
    for name in names:
        lowered = name.lower()
        full = job_dir / name
        if lowered == "postprocess.mrc":
            artifacts["postprocess_map"] = full
        elif re.fullmatch(r"run_half1_class\d+_unfil\.mrc", lowered):
            artifacts["half_map_1"] = full
        elif re.fullmatch(r"run_half2_class\d+_unfil\.mrc", lowered):
            artifacts["half_map_2"] = full
        elif re.fullmatch(r"run_(it\d+_)?class\d+\.mrc", lowered) and artifacts["latest_map"] is None:
            artifacts["latest_map"] = full
        elif lowered.endswith(".mrc") and "mask" in lowered and artifacts["mask"] is None:
            artifacts["mask"] = full
    return artifacts


def artifact_badge(artifacts):
    tags = ["[%s]" % artifacts["state"]]
    if artifacts["postprocess_map"]:
        tags.append("[postprocess]")
    elif artifacts["latest_map"]:
        tags.append("[map]")
    if artifacts["half_map_1"] and artifacts["half_map_2"]:
        tags.append("[half-maps]")
    if artifacts["mask"]:
        tags.append("[mask]")
    return " ".join(tags)
