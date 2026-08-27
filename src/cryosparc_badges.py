import os


def cryosparc_badge(full_path):
    """Best-effort classification of a CryoSPARC output file by filename.

    CryoSPARC's exact naming isn't a documented/stable contract, and its
    per-job job.json manifest is an undocumented internal format that isn't
    even guaranteed to be present (see
    https://discuss.cryosparc.com/t/no-job-json-in-exported-job/4336), so
    this deliberately stays filename-heuristic. It is a label only — it
    never filters or blocks anything from showing.
    """
    name = os.path.basename(full_path).lower()
    if name.endswith(".bild"):
        return "[bild]"
    if any(tag in name for tag in ("half_a", "half_b", "half1", "half2")):
        return "[half-map]"
    if "mask" in name:
        return "[mask]"
    if "sharp" in name:
        return "[volume:sharp]"
    if "filtered" in name:
        return "[volume:filtered]"
    if "raw" in name:
        return "[volume:raw]"
    return "[volume]"
