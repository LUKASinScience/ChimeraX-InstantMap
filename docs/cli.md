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

Add `jsonFile <path>` to `tree`, `table` or `methods` to also write the result as a JSON file
(`{"schema": "instantmap/1", "version", "command", "ok", ...}` with `jobs`, `rows` or `text`) for scripts and AI assistants.

## Make a RELION-style mask from a map

```
instantmap mask #1 threshold 0.02 extend 3 softEdge 3 lowpass 40 output mask.mrc
```

Low-pass filter (Angstrom), threshold, grow by `extend` pixels and add a cosine soft edge of `softEdge` pixels, on the same
grid as the map. The result is a new map model; `output` also saves it as `.mrc`. The rules were checked against real
`relion_mask_create` output (identical voxel values). The same is available in the tool as **Create Mask from Map...**.

## Open maps from reliontree

```
instantmap listen          # let reliontree's 3D buttons open maps in this window
instantmap listen false    # stop listening
instantmap hint false      # hide the one-line reliontree tip shown at startup (true shows it again)
```

[reliontree](https://lukasinscience.github.io/reliontree/) is the browser view of a RELION project. `listen` polls a private
folder (`~/.reliontree/chimerax`, owner-only), opens only existing `.mrc`/`.map`/`.bild` files that you own and runs nothing
else; no network port is opened. reliontree can also start ChimeraX with its own listener, so InstantMap is optional for that.
