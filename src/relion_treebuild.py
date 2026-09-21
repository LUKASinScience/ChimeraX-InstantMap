"""Assemble a RELION job lineage (pipeline graph + per-job artifacts/stats)
into plain data, and render it as SVG — the shared, Qt/ChimeraX-free core
behind both `relion_cli.py` (a plain terminal) and `relion_command.py` (the ChimeraX
command line). Pure stdlib only."""

from pathlib import Path

try:
    from .relion_pipeline import load_pipeline, build_parents, upstream, limit_hops, layers as pipeline_layers
    from .relion_artifacts import scan_job_artifacts, job_stats, parse_job_options
    from .relion_tree_layout import layout_positions
except ImportError:
    from relion_pipeline import load_pipeline, build_parents, upstream, limit_hops, layers as pipeline_layers
    from relion_artifacts import scan_job_artifacts, job_stats, parse_job_options
    from relion_tree_layout import layout_positions

CARD_W, CARD_H = 200, 60
STATE_COLORS = {
    "succeeded": "#2e7d32", "failed": "#c62828", "aborted": "#e65100",
    "running": "#1565c0", "unknown": "#616161",
}


def build_tree(project_dir, selected=None, max_hops=None):
    """Return {"layers": [[job_id,...],...], "parents": {job: {parents}},
    "artifacts": {job: dict}, "stats": {job: dict}, "options": {job: dict}}
    for the job lineage under `project_dir` (a RELION project directory,
    i.e. the one containing `default_pipeline.star`)."""
    project_dir = Path(project_dir)
    procs, node_to_prod, proc_to_in = load_pipeline(project_dir)
    parents = build_parents(procs, node_to_prod, proc_to_in)

    if selected:
        if selected not in parents:
            raise ValueError("job %r not found in pipeline under %s" % (selected, project_dir))
        _, parents = limit_hops(selected, parents, max_hops) if max_hops else upstream(selected, parents)

    lyrs = pipeline_layers(None, parents)  # `selected` arg is unused by layers()

    jobs = [j for layer in lyrs for j in layer]
    artifacts, stats, options = {}, {}, {}
    for job in jobs:
        job_dir = project_dir / job
        artifacts[job] = scan_job_artifacts(job_dir)
        stats[job] = job_stats(job_dir)
        options[job] = parse_job_options(job_dir)

    return {
        "layers": lyrs, "parents": parents,
        "artifacts": artifacts, "stats": stats, "options": options,
    }


def ordered_jobs(tree):
    return [j for layer in tree["layers"] for j in layer]


def _esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def render_svg(tree):
    """A minimal, dependency-free SVG rendering of the job tree: one box per
    job (colored by state), an arrow from each parent to its child. Not a
    pixel-match for the in-app Qt dialog's export — a readable, portable
    equivalent for headless/terminal use."""
    card_sizes = {j: (CARD_W, CARD_H) for j in ordered_jobs(tree)}
    pos = layout_positions(tree["layers"], card_sizes)

    width = max((x + CARD_W for x, y in pos.values()), default=0) + 20
    height = max((y + CARD_H for x, y in pos.values()), default=0) + 20

    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
        'font-family="sans-serif" font-size="11">' % (width, height),
        '<rect width="100%" height="100%" fill="white"/>',
    ]

    for job, ps in tree["parents"].items():
        if job not in pos:
            continue
        cx1, cy1 = pos[job]
        for parent in ps:
            if parent not in pos:
                continue
            px, py = pos[parent]
            x1, y1 = px + CARD_W, py + CARD_H / 2
            x2, y2 = cx1, cy1 + CARD_H / 2
            parts.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" '
                          'stroke="#999" stroke-width="1.5"/>' % (x1, y1, x2, y2))

    for job, (x, y) in pos.items():
        state = tree["artifacts"].get(job, {}).get("state", "unknown")
        color = STATE_COLORS.get(state, STATE_COLORS["unknown"])
        parts.append('<rect x="%.1f" y="%.1f" width="%d" height="%d" rx="6" '
                      'fill="white" stroke="%s" stroke-width="2"/>' % (x, y, CARD_W, CARD_H, color))
        stats = tree["stats"].get(job, {})
        label2 = []
        if stats.get("resolution_angstrom"):
            label2.append("%.1f A" % stats["resolution_angstrom"])
        if stats.get("n_particles"):
            label2.append("%s particles" % format(stats["n_particles"], ","))
        parts.append('<text x="%.1f" y="%.1f" fill="#222" font-weight="bold">%s</text>' %
                      (x + 8, y + 20, _esc(job)))
        parts.append('<text x="%.1f" y="%.1f" fill="%s">[%s]</text>' %
                      (x + 8, y + 36, color, _esc(state)))
        if label2:
            parts.append('<text x="%.1f" y="%.1f" fill="#555">%s</text>' %
                          (x + 8, y + 50, _esc(" / ".join(label2))))

    parts.append("</svg>")
    return "\n".join(parts)
