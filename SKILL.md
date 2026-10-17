---
name: instantmap
description: Work with RELION cryo-EM projects in ChimeraX via InstantMap - build the job lineage tree, a job table (CSV/Markdown) or a draft methods paragraph from a RELION project, and make a RELION-style soft mask from a map. Use when someone asks "which jobs led to this map", "write the methods section for my RELION project", "make a mask like RELION MaskCreate", or wants to open RELION maps in one ChimeraX.
---

# InstantMap for AI assistants

Headless-capable ChimeraX commands (run them through `reliontree/contrib/chx_run.py` or `ChimeraX --nogui --cmd`):

- `instantmap tree <projectFolder> [job Refine3D/job012] [maxHops 3] [format text|svg] [save file]`
- `instantmap table <projectFolder> [format csv|md] [save file]`
- `instantmap methods <projectFolder> [job ...] [save file]` - a DRAFT paragraph; check it before publishing.
- `instantmap mask ...` - RELION-convention mask (low-pass, threshold, extend, cosine soft edge); reproduced bit-exact on a real MaskCreate output.
- `instantmap listen` / `hint` - GUI helpers for reliontree's 3D buttons; not for scripted use (the runner refuses `listen`).

JSON: `tree`, `table`, `methods` accept `jsonFile <path>` -> {"schema": "instantmap/1", "version", "command", "ok", "jobs"|"rows"|"text"}.
Output goes to the ChimeraX log unless `save` is given; use `save` to get a file you can read back.
For reading a RELION project WITHOUT ChimeraX (JSON, read-only) use `reliontree mcp <project>` instead.

Limits: the mask needs SciPy and fails loudly without it; negative `extend` and non-cubic boxes are untested.
