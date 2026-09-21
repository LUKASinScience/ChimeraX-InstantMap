#!/usr/bin/env python3
"""Build RELION job trees/tables/methods drafts from any terminal — no
ChimeraX, no Qt, no third-party packages required (pure stdlib).

    python3 relion_cli.py tree /path/to/relion/project -o tree.svg
    python3 relion_cli.py tree /path/to/relion/project --job Class3D/job012 --format json
    python3 relion_cli.py table /path/to/relion/project --format csv -o jobs.csv
    python3 relion_cli.py methods /path/to/relion/project

Also runnable inside ChimeraX's own bundle as `chimerax.instant_map.relion_cli`
(same code, imported rather than executed) — the ChimeraX command line uses
`relion_treebuild` directly instead, see relion_command.py.
"""

import argparse
import json
import sys

try:
    from .relion_treebuild import build_tree, ordered_jobs, render_svg
    from .relion_export import history_rows, rows_to_csv, rows_to_markdown
    from .relion_methods import draft_methods_paragraph
except ImportError:
    from relion_treebuild import build_tree, ordered_jobs, render_svg
    from relion_export import history_rows, rows_to_csv, rows_to_markdown
    from relion_methods import draft_methods_paragraph


def _write(text, out_path):
    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text)
    else:
        sys.stdout.write(text if text.endswith("\n") else text + "\n")


def cmd_tree(args):
    tree = build_tree(args.project, selected=args.job, max_hops=args.max_hops)
    jobs = ordered_jobs(tree)
    if args.format == "svg":
        _write(render_svg(tree), args.out)
    elif args.format == "json":
        _write(json.dumps({
            "jobs": jobs,
            "parents": {j: sorted(p) for j, p in tree["parents"].items()},
            "artifacts": {j: {k: (str(v) if v else v) for k, v in a.items()}
                          for j, a in tree["artifacts"].items()},
            "stats": tree["stats"],
        }, indent=2), args.out)
    else:
        lines = ["%s%s  [%s]" % ("  " * 0, j, tree["artifacts"][j]["state"]) for j in jobs]
        _write("\n".join(lines), args.out)


def cmd_table(args):
    tree = build_tree(args.project, selected=args.job, max_hops=args.max_hops)
    jobs = ordered_jobs(tree)
    rows = history_rows(jobs, tree["artifacts"], tree["parents"], tree["stats"])
    text = rows_to_markdown(rows) if args.format == "md" else rows_to_csv(rows)
    _write(text, args.out)


def cmd_methods(args):
    tree = build_tree(args.project, selected=args.job, max_hops=args.max_hops)
    jobs = ordered_jobs(tree)
    _write(draft_methods_paragraph(jobs, tree["options"], tree["stats"]), args.out)


def main(argv=None):
    p = argparse.ArgumentParser(prog="relion_cli", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("project", help="RELION project directory (contains default_pipeline.star)")
        sp.add_argument("--job", help="restrict to this job's upstream lineage, e.g. Class3D/job012")
        sp.add_argument("--max-hops", type=int, default=None, help="limit upstream depth from --job")
        sp.add_argument("-o", "--out", help="output file (default: stdout)")

    sp = sub.add_parser("tree", help="job lineage as text/svg/json")
    common(sp)
    sp.add_argument("--format", choices=["text", "svg", "json"], default="text")
    sp.set_defaults(func=cmd_tree)

    sp = sub.add_parser("table", help="job lineage as a CSV/Markdown table")
    common(sp)
    sp.add_argument("--format", choices=["csv", "md"], default="csv")
    sp.set_defaults(func=cmd_table)

    sp = sub.add_parser("methods", help="draft methods-section paragraph")
    common(sp)
    sp.set_defaults(func=cmd_methods)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
