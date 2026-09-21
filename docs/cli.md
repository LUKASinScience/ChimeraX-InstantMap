# Command line

RELION job trees, tables, and methods-paragraph drafts can be built without
opening the InstantMap GUI, two ways.

## From any terminal (no ChimeraX needed)

`relion_cli.py` is a plain, stdlib-only Python 3 script — no ChimeraX, no Qt,
no `pip install` required.

```bash
python3 relion_cli.py tree /path/to/relion/project -o tree.svg
python3 relion_cli.py tree /path/to/relion/project --job Class3D/job012 --format json
python3 relion_cli.py table /path/to/relion/project --format csv -o jobs.csv
python3 relion_cli.py methods /path/to/relion/project
```

`<project>` is a RELION project directory (the one containing
`default_pipeline.star`). Useful flags, shared by all three subcommands:

- `--job Class3D/job012` — restrict to this job's upstream lineage instead
  of the whole project
- `--max-hops N` — with `--job`, limit to N upstream steps ("local view")
- `-o FILE` — write to a file instead of stdout

`tree --format` accepts `text`, `svg`, or `json`; `table --format` accepts
`csv` or `md`.

## From ChimeraX's own command line

The same logic is registered as ChimeraX commands, so it also works
headlessly via `chimerax --nogui --cmd "..."`:

```
instantmap tree /path/to/relion/project format svg save tree.svg
instantmap tree /path/to/relion/project job Class3D/job012 maxHops 3
instantmap table /path/to/relion/project format md save jobs.md
instantmap methods /path/to/relion/project
```

Without `save`, output goes to the ChimeraX Log.
