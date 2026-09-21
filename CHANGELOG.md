# Changelog

All notable changes to InstantMap are documented here. Versions follow the
`bundle_info.xml` `version` attribute.

## [1.2.0] - 2026-09-09

### Added
- **Command-line access**: RELION job trees/tables/methods drafts can now be
  built without opening the GUI at all — `instantmap tree|table|methods` on
  ChimeraX's own command line (also works with `chimerax --nogui --cmd`),
  and `relion_cli.py` as a plain stdlib-only Python 3 script runnable from
  any terminal, no ChimeraX or Qt install required. See
  [docs/cli.md](docs/cli.md).
- **Scrolling affordance fixes**: every tab's scrollbar is now forced
  always-visible with a styled track+thumb, instead of the platform
  default — macOS in particular uses an overlay scrollbar that's invisible
  at rest and only flashes in while actively scrolling, giving no
  indication a tab has more content below. On the RELION History tab's two
  sub-tabs specifically, the core action buttons (Open Job Map/Half Maps,
  Export Table…, Show Job Tree, Copy Methods Draft…) and the status label
  are now a fixed footer outside the scrollable area, so they're always
  reachable without having to discover — or even need — scrolling.
- **SSH tab's Remote Files panel no longer forces 220px** regardless of
  content: the file tree used a fixed height (taller than the 180px/260px
  used elsewhere), which stopped the panel from shrinking even when empty.
  It's now a minimum of 120px, so it can compress when the user wants a
  compact panel and still grow to use available space when browsing.
- **Path highlighting** in **Browse Project Tree**: the currently-loaded
  job's ancestry chain is drawn thicker and in an accent color among the
  full project graph, so it's clear at a glance which branch fed into it
  alongside any abandoned/unrelated jobs.
- **Local ("N hops") view** for the Job Tree: a **"Local view — show only
  N hops upstream"** checkbox + spin box on the Job Tree sub-tab limits the
  diagram to jobs within N upstream steps of the selected job, instead of
  always the full lineage — useful once a project's history gets long.
  Unchecked by default (full lineage); the spin box is only enabled once
  the checkbox is on, so there's no ambiguous "0 hops" state. New pure
  `relion_pipeline.limit_hops()`.
- **Session-persistent manual contour levels**: a level set for a
  map in "Adjust map levels manually" mode is remembered (keyed by file
  path) and pre-fills that map's slider the next time the Job Tree is
  shown, instead of resetting to ChimeraX's auto-picked level every time.
- **"Copy Methods Draft…"** (Job Tree sub-tab): assembles a short,
  editable per-job text draft from the lineage's own recorded parameters
  (symmetry, particle diameter, class count, from each job's `job.star`)
  and stats (resolution, particle count) — a starting point for a methods
  section, not a finished paragraph. New pure `relion_methods.py`.
- **"Export Table…"** (History sub-tab): exports the loaded lineage as a
  CSV or Markdown table (job, type, state, parent(s), resolution, particle
  count), independent of the Job Tree diagram. New pure `relion_export.py`.
- **Resolution/particle-count caption** in each Job Tree card's header,
  under the job name ("22.9 Å · 2,150 particles") — read from RELION's own
  files: a PostProcess job's `postprocess.star` (`_rlnFinalResolution`,
  preferred when present) or a Class3D/Refine3D job's own `*_model.star`
  (`_rlnCurrentResolution` as a fallback, `_rlnGroupNrParticles` summed for
  the count). New pure `relion_artifacts.job_stats()`.
- **Masks get an explicit level 0.5** (in addition to the mesh style) —
  RELION masks are normalized 0-1 with a soft edge around 0.5, and the
  auto-picked level otherwise made the mesh nearly invisible or a solid
  blob.
- **Thumbnail caching**: re-opening the Job Tree (e.g. just to try a
  different export format) reuses already-rendered automatic-level
  thumbnails instead of re-rendering every map from scratch, keyed by the
  map file's path and modification time — cache lives on the tool instance
  and persists across dialogs for the session. Skipped when manual levels
  are on, since the level is chosen interactively each time.
- **Cancel button** in the thumbnail-rendering progress dialog — stops
  after the current map and shows the tree with whatever was rendered so
  far, instead of forcing a wait through every remaining class.
- **Job picker redesign** (RELION History tab): the Family/Job dropdown +
  "Load history" button are gone. Instead, a single filterable, newest-first
  job list (RELION numbers jobs globally, so sorting by job number is a
  correct recency order) — clicking a row loads its history immediately,
  and the newest job in the project **auto-loads with zero clicks** when you
  set the directory. A **Browse Project Tree** button opens the same tree
  diagram over the *entire* project graph (no thumbnails, fast) — click any
  job card to select it, CryoSPARC-style. New pure
  `relion_pipeline.sort_by_job_number()`.
- **Manual contour levels, with a live preview**: an **"Adjust map levels
  manually"** checkbox — when on, each map is shown with a slider + spin box
  (synced, range from the volume's own min/max surface level) *and a live
  preview rendered right inside the same small dialog* (debounced, updates
  as you drag) — no need to go find ChimeraX's own graphics window to see
  the effect. **Skip this map** excludes it entirely. Fixes masks and other
  volumes that render solid black at ChimeraX's automatic level.
- **RELION History tab split into sub-tabs** ("History" / "Job Tree") — the
  day-to-day browsing controls (project dir, job picker, lineage list, Open
  Job Map/Half Maps) no longer share space with the figure-export-focused
  Job Tree controls (Select All/None, manual levels, Show Job Tree).
- **"Adjust map levels manually" is now on by default** (still a checkbox,
  so it can be turned off for the fast/automatic path).
- **Selected-class indicator**: within a job's thumbnail grid (a Class3D
  job with several classes), the specific class a *downstream* job actually
  used as its input gets a **dashed border** around just that one
  thumbnail — so it's clear which single class was carried forward rather
  than the whole card. Two RELION mechanisms detected, confirmed against a
  real project: a "Select classes" (Subset selection) job's
  `backup_selection.star` — which records **no filenames at all**, only a
  positional list of `_rlnSelected` 0/1 flags matched up here against the
  upstream classes by class-number order — and a job that names one class
  directly as its own reference (e.g. a Refine3D job's `job.star` "fn_ref"),
  via a text search across the job's own small option files. Excludes large
  per-particle tables (`particles.star`) and pipeline-snapshot files
  (`job_pipeline.star`/`default_pipeline.star`, which list *every* upstream
  class as a node regardless of selection and would otherwise mark all of
  them). RELION doesn't record per-class selection in `default_pipeline.star`
  itself (edges there are per-job, not per-file-within-a-job). New pure
  `relion_artifacts.referenced_class_maps()`.
- **Masks rendered as a mesh**: a job's thumbnail is shown with `volume
  ... style mesh` instead of a solid surface when its filename matches
  RELION's mask naming convention (the same heuristic already used for the
  mask badge) — a solid binary mask is otherwise just a flat blob with no
  visible internal shape.
- **Job Tree card styling**: rounded card corners (matching the header strip
  to the card body), orthogonal (horizontal/vertical only, single-elbow)
  connector lines instead of diagonals, and maps rendered with a
  transparent background (`save ... transparentBackground true`) so a
  card's white body shows through instead of ChimeraX's default black —
  both the thumbnail grid and the manual-level preview.
- **Job Tree layout redesign**: left-aligned, content-aware positioning —
  a simple chain of jobs now forms a straight left-hand column (only actual
  branch points indent rightward, git-log-graph style) and row spacing is
  based on each generation's *actual* tallest card instead of a fixed gap,
  closing up the large empty space text-only rows used to leave.
  `relion_tree_layout.layout_positions()` now takes real card sizes and
  does this positioning itself (previously a fixed, content-blind grid).
- **Job Tree diagram** (RELION History tab): click **Show Job Tree** to open
  a popup with a **top-to-bottom** card diagram of the full upstream
  lineage, styled after CryoSPARC's own tree/card views — every job is a
  card with a family-colored header (job number/type + a state dot:
  succeeded/failed/running/aborted/unknown), and jobs with a map show it as
  a thumbnail (or a **grid of thumbnails** for a Class3D job with multiple
  classes — each class rendered separately, latest iteration only).
  Thumbnails are rendered **one map at a time** (open → snapshot → close
  before the next), so peak memory never exceeds a single map regardless of
  how many jobs/classes are included. Every job with a map is **included by
  default** (checkboxes let you opt individual ones out; **Select All** /
  **Select None** for bulk toggling; jobs without a map are shown disabled).
  Exportable as **PNG**, **PDF**, or **SVG** — the vector formats keep
  cards/lines/text as separate, editable objects in Illustrator (or
  Inkscape), with thumbnails embedded as raster images inside.
- New pure module `src/relion_tree_layout.py` (`layout_positions`) —
  generation-based 2D layout (top-to-bottom), unit tested like the rest of
  the RELION pipeline logic.
- New `relion_artifacts.list_class_maps()` — enumerates every class volume
  in a Class3D-style job directory, keeping only the latest RELION
  iteration per class.

### Notes
- SVG export needed one workaround: this project's Qt compatibility shim
  doesn't expose `QtSvg`, so `JobTreeDialog` detects the active Qt binding
  (PyQt6 here) via `QObject.__module__` and imports `QtSvg` from it
  directly — confirmed to work the same way PyQt5/PySide2/PySide6 all ship
  a `QtSvg` module.
- Design informed directly by reading CryoSPARC's own docs (Job Views:
  Cards/Tree/Table, Job Relationships) and several of their forum threads
  on tree-view usability — local/sub-tree views, filter-by-connectivity, and
  click-to-highlight-lineage are real ideas from there but out of scope for
  this pass; noted in the README Roadmap as future items.

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
