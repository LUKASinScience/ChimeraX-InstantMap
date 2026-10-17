"""`instantmap tree|table|methods` — build a RELION job lineage from the
ChimeraX command line (headless-capable: works with `chimerax --nogui`
too), reusing the same Qt-free core as `relion_cli.py`."""

from chimerax.core.commands import BoolArg, CmdDesc, OpenFolderNameArg, SaveFileNameArg, StringArg, IntArg

from .relion_treebuild import build_tree, ordered_jobs, render_svg
from .relion_export import history_rows, rows_to_csv, rows_to_markdown
from .relion_methods import draft_methods_paragraph

_common_kw = [("job", StringArg), ("max_hops", IntArg), ("save", SaveFileNameArg), ("json_file", SaveFileNameArg)]


def _output(session, text, save):
    if save:
        with open(save, "w", encoding="utf-8") as f:
            f.write(text)
        session.logger.info("Wrote %s" % save)
    else:
        session.logger.info(text, is_html=False)


def instantmap_tree(session, project, job=None, max_hops=None, format="text", save=None, json_file=None):
    tree = build_tree(project, selected=job, max_hops=max_hops)
    jobs = ordered_jobs(tree)
    from . import jsonout
    jsonout.write(json_file, "instantmap tree", {"jobs": [
        {"job": j, "state": tree["artifacts"][j]["state"], "parents": sorted(tree["parents"].get(j, ()))} for j in jobs]})
    if format == "svg":
        _output(session, render_svg(tree), save)
    else:
        _output(session, "\n".join("%s  [%s]" % (j, tree["artifacts"][j]["state"]) for j in jobs), save)


instantmap_tree_desc = CmdDesc(
    required=[("project", OpenFolderNameArg)],
    keyword=_common_kw + [("format", StringArg)],
    synopsis="Build a RELION job lineage tree (text or SVG)",
)


def instantmap_table(session, project, job=None, max_hops=None, format="csv", save=None, json_file=None):
    tree = build_tree(project, selected=job, max_hops=max_hops)
    jobs = ordered_jobs(tree)
    rows = history_rows(jobs, tree["artifacts"], tree["parents"], tree["stats"])
    from . import jsonout
    jsonout.write(json_file, "instantmap table", {"rows": rows})
    text = rows_to_markdown(rows) if format == "md" else rows_to_csv(rows)
    _output(session, text, save)


instantmap_table_desc = CmdDesc(
    required=[("project", OpenFolderNameArg)],
    keyword=_common_kw + [("format", StringArg)],
    synopsis="Build a RELION job lineage table (CSV or Markdown)",
)


def instantmap_methods(session, project, job=None, max_hops=None, save=None, json_file=None):
    tree = build_tree(project, selected=job, max_hops=max_hops)
    jobs = ordered_jobs(tree)
    text = draft_methods_paragraph(jobs, tree["options"], tree["stats"])
    from . import jsonout
    jsonout.write(json_file, "instantmap methods", {"draft": True, "text": text})
    _output(session, text, save)


instantmap_methods_desc = CmdDesc(
    required=[("project", OpenFolderNameArg)],
    keyword=_common_kw,
    synopsis="Draft a methods-section paragraph from a RELION job lineage",
)


def instantmap_listen(session, enable=True):
    from . import listen
    if enable:
        listen.start(session)
        session.logger.info("instantmap listen: on -- reliontree's 3D buttons now open maps in this ChimeraX "
                            "(no network port; `instantmap listen false` to stop)")
    else:
        listen.stop()
        session.logger.info("instantmap listen: off")


instantmap_listen_desc = CmdDesc(
    optional=[("enable", BoolArg)],
    synopsis="Let reliontree open maps in this ChimeraX (private file queue, no network port)",
)


def instantmap_hint(session, show=True):
    from . import hint
    hint.set_shown(session, show)


instantmap_hint_desc = CmdDesc(
    optional=[("show", BoolArg)],
    synopsis="Show (true) or hide (false) the reliontree tip printed at startup",
)


def register_command(logger):
    from chimerax.core.commands import register
    from .mask_command import instantmap_mask, instantmap_mask_desc
    register("instantmap mask", instantmap_mask_desc, instantmap_mask, logger=logger)
    register("instantmap hint", instantmap_hint_desc, instantmap_hint, logger=logger)
    register("instantmap listen", instantmap_listen_desc, instantmap_listen, logger=logger)
    register("instantmap tree", instantmap_tree_desc, instantmap_tree, logger=logger)
    register("instantmap table", instantmap_table_desc, instantmap_table, logger=logger)
    register("instantmap methods", instantmap_methods_desc, instantmap_methods, logger=logger)
