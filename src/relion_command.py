"""`instantmap tree|table|methods` — build a RELION job lineage from the
ChimeraX command line (headless-capable: works with `chimerax --nogui`
too), reusing the same Qt-free core as `relion_cli.py`."""

from chimerax.core.commands import CmdDesc, OpenFolderNameArg, SaveFileNameArg, StringArg, IntArg

from .relion_treebuild import build_tree, ordered_jobs, render_svg
from .relion_export import history_rows, rows_to_csv, rows_to_markdown
from .relion_methods import draft_methods_paragraph

_common_kw = [("job", StringArg), ("max_hops", IntArg), ("save", SaveFileNameArg)]


def _output(session, text, save):
    if save:
        with open(save, "w", encoding="utf-8") as f:
            f.write(text)
        session.logger.info("Wrote %s" % save)
    else:
        session.logger.info(text, is_html=False)


def instantmap_tree(session, project, job=None, max_hops=None, format="text", save=None):
    tree = build_tree(project, selected=job, max_hops=max_hops)
    jobs = ordered_jobs(tree)
    if format == "svg":
        _output(session, render_svg(tree), save)
    else:
        _output(session, "\n".join("%s  [%s]" % (j, tree["artifacts"][j]["state"]) for j in jobs), save)


instantmap_tree_desc = CmdDesc(
    required=[("project", OpenFolderNameArg)],
    keyword=_common_kw + [("format", StringArg)],
    synopsis="Build a RELION job lineage tree (text or SVG)",
)


def instantmap_table(session, project, job=None, max_hops=None, format="csv", save=None):
    tree = build_tree(project, selected=job, max_hops=max_hops)
    jobs = ordered_jobs(tree)
    rows = history_rows(jobs, tree["artifacts"], tree["parents"], tree["stats"])
    text = rows_to_markdown(rows) if format == "md" else rows_to_csv(rows)
    _output(session, text, save)


instantmap_table_desc = CmdDesc(
    required=[("project", OpenFolderNameArg)],
    keyword=_common_kw + [("format", StringArg)],
    synopsis="Build a RELION job lineage table (CSV or Markdown)",
)


def instantmap_methods(session, project, job=None, max_hops=None, save=None):
    tree = build_tree(project, selected=job, max_hops=max_hops)
    jobs = ordered_jobs(tree)
    _output(session, draft_methods_paragraph(jobs, tree["options"], tree["stats"]), save)


instantmap_methods_desc = CmdDesc(
    required=[("project", OpenFolderNameArg)],
    keyword=_common_kw,
    synopsis="Draft a methods-section paragraph from a RELION job lineage",
)


def register_command(logger):
    from chimerax.core.commands import register
    register("instantmap tree", instantmap_tree_desc, instantmap_tree, logger=logger)
    register("instantmap table", instantmap_table_desc, instantmap_table, logger=logger)
    register("instantmap methods", instantmap_methods_desc, instantmap_methods, logger=logger)
