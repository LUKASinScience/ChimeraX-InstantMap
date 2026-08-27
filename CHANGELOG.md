# Changelog

All notable changes to InstantMap are documented here. Versions follow the
`bundle_info.xml` `version` attribute.

## [1.1.0] - 2026-08-27 — Initial public release

The full feature set as of the first public release (everything below was
built and tested across several local development iterations first — see
"Internal development history" further down for the detailed, dated
breakdown of how it got here).

### Features
- **RELION Browser tab**: auto-refreshing `.mrc`/`.mrcs`/`.mrc.gz`/`.map`/
  `.map.gz` directory browser (configurable interval, default 60s), with
  directory navigation (↑ button, double-click), a collapsible folder view,
  a "Files only" / "+ Folders" toggle, and a separate Mask Browser panel
  (no auto-refresh — masks don't change between iterations). Already-opened
  files are greyed out; **Close All Maps** closes every open volume at once.
- **CryoSPARC Browser tab**: same navigation, pointed at a CryoSPARC project
  (`P#`) or job (`J#`) directory on disk (filesystem-only, no CryoSPARC
  login/network access). Volumes (incl. sharpened/filtered/raw variants),
  half-maps, masks, and `.bild` viewing-direction files are recognized and
  tagged by filename heuristic. Optional auto-refresh (off by default).
  **Copy Path** for the selected file(s).
- **RELION History tab**: point it at a RELION project root
  (`default_pipeline.star`) and a job family/job; shows the full upstream
  job lineage in chronological order, each job tagged with its state
  (`succeeded`/`running`/`failed`/`aborted`/`unknown`, from RELION's own
  `RELION_JOB_EXIT_*` sentinel files) and output artifacts (postprocess map,
  half-maps, mask). **Open Job Map** / **Open Half Maps** open a selected
  job's outputs directly.
- **SSH tab**: browse a RELION/CryoSPARC project on a remote cluster over
  SFTP. Key-based auth only (`~/.ssh` keys, `ssh-agent`, or an explicit key
  path — no passwords); an unknown host's key is rejected rather than
  silently trusted (backed by the user's own `known_hosts`). Toggle between
  **auto-download & open** (fetches into a local per-host cache, then opens
  in ChimeraX) and **browse-only** (Copy Remote Path instead).
- **Session save/restore**: browsed directories, auto-refresh settings, and
  RELION/SSH selections (non-secret fields only — never a passphrase)
  survive a saved-and-reloaded ChimeraX session. Restoring never
  auto-connects the SSH tab.
- **Responsive UI**: directory scanning (local and SFTP) runs on background
  thread pools, so slow/network-mounted directories never freeze the
  interface. All four tabs scroll independently; the tool opens at a
  comfortable size (≥800px) but can still be resized smaller.
- One-click **InstantMap** button (transparent-background icon) in a new
  **EM** section of ChimeraX's built-in **Map** toolbar tab, alongside the
  regular Tools → Volume Data menu entry.
- MIT license; `pytest` test suite (33 tests) covering the STAR pipeline
  parser, RELION job artifact/state detection, CryoSPARC/SSH badge and
  directory-scan logic — runs standalone, no ChimeraX/Qt required.

### Security
- SSH host keys are verified against the user's own `known_hosts`
  (`paramiko.RejectPolicy` — unknown hosts are rejected, never silently
  trusted).
- SSH cache paths sanitize `.`/`..`/empty segments so a remote path can't
  make a downloaded file's local destination escape the configured cache
  directory.
- No credentials (SSH passphrase) are ever persisted to a session file.

### Researched, not implemented
- CryoSPARC's `job.json` — confirmed undocumented/not always present even in
  exported jobs, so CryoSPARC badges stay filename-heuristic rather than
  parsing it.
- `csparc2star`/pyem-style particle-metadata conversion — different tool
  category, and pyem is GPL-3.0 (would force InstantMap itself to go GPL to
  embed it) — see README Roadmap.
- `cryosparc-tools` (Structura Biotechnology's official CryoSPARC API) as a
  richer alternative to filename heuristics — needs a live API connection
  to the CryoSPARC master, bigger scope, not started.

---

## Internal development history (pre-1.1.0, local iterations)

These were local build/test iterations before the first public release —
kept here for the detailed record, renumbered so they don't collide with
the public version numbers above.

### Internal iteration 5 (was locally "1.4.0") - 2026-08-26

**Added**
- SSH tab (see Features above for the full description).
- CryoSPARC Browser auto-refresh checkbox/interval.
- Tabs renamed/reordered: RELION Browser, RELION History, CryoSPARC
  Browser, SSH.
- CryoSPARC/SSH tabs' explanatory text moved behind a **Help** button popup.
- All tabs made scrollable; tool opens at ≥800px via a `sizeHint()`
  override (not a hard `setMinimumHeight`, so the panel stays resizable).

**Fixed**
- SSH cache path traversal: `local_cache_path()` now drops `.`/`..`/empty
  segments instead of passing them through to `os.path.join`. Found during
  a self-review pass; the actual remote fetch was never affected (it always
  used the real, unsanitized remote path) — only the local file-naming was
  vulnerable. Covered by a regression test.

**Changed**
- `DirectoryBrowserPanel`'s tree-rendering extracted into a shared
  `populate_tree()` function so the local and SSH browsers render
  identically from the same plain-data scan-result shape.

### Internal iteration 4 (was locally "1.3.0") - 2026-08-26

**Added**
- Session save/restore of browsed directories, auto-refresh settings, and
  RELION family/job selection (`take_snapshot`/`set_state_from_snapshot`).
- Background-threaded directory scanning (thread pool + polling timer) so
  slow/network-mounted directories no longer freeze the UI.
- `pytest` test suite (25 tests) for the STAR pipeline parser, RELION job
  artifact/state detection, CryoSPARC badge classification, and directory
  scanning.
- CryoSPARC volume badges distinguishing sharpened/filtered/raw variants.
- MIT license (`LICENSE`, `<License>`/`PythonClassifier` in
  `bundle_info.xml`).
- One-click InstantMap button with a transparent-background icon in a new
  EM section of ChimeraX's Map toolbar tab.

**Changed**
- STAR parsing, RELION job-artifact detection, CryoSPARC badge
  classification, and directory scanning extracted from
  `InstantMapTool`/`DirectoryBrowserPanel` into standalone, dependency-free
  modules — unit testable and reusable.

**Researched, not changed**
- `job.json` for CryoSPARC badges — undocumented, not always present, kept
  the filename heuristic.
- `csparc2star`/pyem-style conversion — out of scope, pyem is GPL-3.0.

### Internal iteration 3 (was locally "1.2.0") - 2026-08-25

**Added**
- RELION Job History tab job state (`succeeded`/`running`/`failed`/
  `aborted`/`unknown`, from `RELION_JOB_EXIT_*` sentinel files) and output
  artifacts (postprocess map, half-maps, mask).
- **Open Job Map** / **Open Half Maps** buttons.

**Fixed**
- STAR-table row parsing switched to `shlex.split()` instead of naive
  whitespace splitting, so quoted fields containing spaces no longer
  misalign subsequent columns.

### Internal iteration 2 (was locally "1.1.0") - 2026-08-25

**Added**
- CryoSPARC Browser tab: browse a CryoSPARC project (`P#`) or job (`J#`)
  directory, with volumes, half-maps, masks, and `.bild` files.
- Shared `DirectoryBrowserPanel` component, replacing duplicated Map/Mask
  browser code.

### Internal iteration 1 (was locally "1.0.1") - 2026-08-25

**Added**
- RELION Job History tab: select a RELION project, family, and job to see
  the complete upstream job lineage in chronological order.

### Internal iteration 0 (was locally "1.0.0") — initial local build

**Added**
- Map Browser (auto-refreshing `.mrc`/`.map` directory listing) and Mask
  Browser, with directory navigation, folder/file toggle, and one-click
  opening in ChimeraX.
