# InstantMap

**Tired of manually refreshing your classification or refinement directories in ChimeraX? InstantMap automatically monitors a directory for new MRC/MAP files and keeps the list up to date — so the latest iteration map is always one click away. Built for Cryo-EM SPA and Cryo-ET STA workflows.**



---

## Overview

InstantMap was built to streamline the everyday file management that comes with single particle analysis (SPA) and subtomogram averaging (STA) workflows. Instead of manually navigating to the output directory every time a new iteration finishes, InstantMap watches the directory and keeps the file list up to date automatically. 

#### Version 1.1.0: Initial Public Release

InstantMap browses Map, Mask, CryoSPARC, and RELION-project directories (local or over SSH/SFTP to a remote cluster), with auto-refresh, RELION job-history/lineage tracking, session save/restore, and a one-click toolbar button. See [CHANGELOG.md](CHANGELOG.md) for the detailed development history that led up to this release.

---

## Features

### RELION Browser Tab

#### Map Browser
- Browse a directory for `.mrc`, `.mrcs`, `.mrc.gz`, `.map`, and `.map.gz` files
- **Auto-refresh** at a configurable interval (default: 60 s) — new maps appear automatically as iterations complete
- Navigate directories with the **↑ button** (go to parent) or double-click a folder to enter it
- **Collapsible folder view** — subdirectories show their contained map files as expandable children
- Toggle between **"Files only"** and **"+ Folders"** display modes
- Double-click any file to open it directly in ChimeraX
- Already-opened files are shown in grey italic so it's always clear what's loaded
- **Close All Maps** button closes all open volumes in one click

#### Mask Browser
- Separate browser panel for mask files, accessed via the **"Open Mask Browser"** button
- Full directory navigation (↑ button + double-click subdirs) for easy browsing through nested project structures
- Same **"Files only" / "+ Folders"** toggle as the map browser
- No auto-refresh on masks by design — masks are stable files that don't change between iterations
- The mask panel can be hidden when not needed to give the map browser more space

### CryoSPARC Browser Tab
- Point it at a CryoSPARC project (`P#`) or job (`J#`) directory on disk — same directory navigation (↑ button, double-click, "Files only" / "+ Folders") as the Map/Mask browsers
- Reads whatever is already on disk, so the project directory needs to be mounted/reachable locally (filesystem-only — no CryoSPARC login or network access involved)
- Recognizes volumes (including sharpened/filtered/raw variants), half-maps, masks, and `.bild` files, and tags each with a best-effort label (`[volume]`/`[volume:sharp]`/`[volume:filtered]`/`[volume:raw]`, `[half-map]`, `[mask]`, `[bild]`) based on filename — see the [CryoSPARC BILD tutorial](https://guide.cryosparc.com/processing-data/tutorials-and-case-studies/tutorial-bild-files) for what `.bild` viewing-direction files are
- Double-click or **Open Selected** to load a file directly in ChimeraX (`.bild` files use ChimeraX's native BILD reader)
- **Copy Path** copies the selected file path(s) to the clipboard
- Optional **auto-refresh** (off by default — enable with a configurable interval, same as the Map browser) alongside the manual **Refresh** button

### SSH Tab
- Browse a RELION or CryoSPARC project on a remote cluster over SFTP — for when the project isn't reachable through a local mount or VPN path
- **Key-based auth only**: reads `~/.ssh` keys (auto-detects `id_ed25519`/`id_rsa`), a running `ssh-agent`, or a key you point at explicitly, with an optional passphrase kept only in memory — no passwords, nothing ever written to disk
- An unknown host's key is **rejected**, not silently trusted — connect to the host once from a terminal (`ssh user@host`) so it's added to your normal `~/.ssh/known_hosts`, then Connect here
- Same navigation as the other browsers (↑ button, double-click, "Files only" / "+ Folders"), with the same volume/half-map/mask/bild badges
- Choose per session: **Auto-download && open** (fetches the file via SFTP into a local cache directory — mirrored per-host under the configurable cache path — then opens it in ChimeraX) or uncheck it for **browse-only** (double-click just selects; use **Copy Remote Path** instead)
- Session save/restore remembers the non-secret connection fields (host, port, username, key path, last directory, download-mode toggle) — **never** the passphrase, and reloading a session **never** auto-connects; you always click Connect yourself

### RELION History Tab
- Select a RELION project directory — reads `default_pipeline.star` automatically
- Choose a job family (e.g. `Refine3D`) and a specific job from dropdowns
- Displays the complete **upstream job lineage** in chronological order: job number, job type (color-coded), parent job(s)
- Each job is tagged with its **state** (`succeeded`/`running`/`failed`/`aborted`/`unknown`, detected from RELION's own `RELION_JOB_EXIT_*` sentinel files) and its **output artifacts** (`[postprocess]`/`[map]`, `[half-maps]`, `[mask]`), detected from RELION's standard output filename conventions
- Select a job in the list and click **Open Job Map** (postprocess map if present, else the latest refine/class map) or **Open Half Maps** to load its outputs directly in ChimeraX
- Useful for tracing which classification or selection led to a given refinement

### General
- Opens at a comfortable size (≥800px tall) and each tab scrolls independently if its content doesn't fit — the panel can still be resized smaller at any time
- Works seamlessly alongside other ChimeraX tools
- Directory scanning runs on a background thread, so browsing large or slow/network-mounted directories doesn't freeze the interface
- Browsed directories, auto-refresh settings, and RELION selection are remembered when you save and reload a ChimeraX session
- One-click access from a **InstantMap** button in a new **EM** section of ChimeraX's built-in **Map** toolbar tab, in addition to **Tools → Volume Data → InstantMap**

---

## Installation

### Via ChimeraX Toolshed
1. Open ChimeraX
2. Go to **Tools → More Tools...** (opens the Toolshed)
3. Search for **InstantMap**
4. Click **Install**

### Manual installation
```
toolshed install /path/to/ChimeraX_InstantMap-<version>-py3-none-any.whl
```

---

## Usage

### Getting started
1. Open the tool via **Tools → Volume Data → InstantMap**
2. In the **RELION Browser** tab, click **Browse** or paste a path into the Map Directory field to select the output directory (e.g. a RELION or cryoSPARC job folder)
3. The file list populates automatically. Files are refreshed every 60 seconds by default.
4. **Double-click** a file to open it, or select multiple files and click **Open Selected**

### Navigating directories
- Use the **↑ button** to go up to the parent directory
- With **"Files only"** mode active, subdirectories appear at the top of the list — click the **▶** arrow to expand them and see their map files, or double-click to navigate into them
- Switch to **"+ Folders"** mode to hide subdirectories and see only map files in the current directory

### Working with masks
- Click **Open Mask Browser** to reveal the mask panel
- Navigate to the mask directory (e.g. `Masks/` or a classification output subfolder)
- Use the same navigation controls as the map browser
- Click **Open Selected Mask** or double-click to load a mask into ChimeraX

### Auto-refresh
- The map list refreshes automatically every 60 seconds while the tool is open
- Change the interval with the spin box (5–600 s)
- Uncheck **Auto-refresh every** to disable automatic refreshing
- Click **Refresh Now** at any time to force an immediate update

### Working with CryoSPARC output
1. Switch to the **CryoSPARC Browser** tab
2. Browse to or paste a CryoSPARC project (`P#`) or job (`J#`) directory
3. Double-click or select files and click **Open Selected** to load them in ChimeraX — `.bild` viewing-direction files open the same way as volumes
4. Use **Copy Path** to grab a file's full path, or **Refresh** to rescan (no auto-refresh here)

### RELION History
1. Switch to the **RELION History** tab
2. Browse to or paste the RELION project root (the folder containing `default_pipeline.star`)
3. Select a job family and job from the dropdowns
4. Click **Load history** — the upstream lineage appears in chronological order, each entry tagged with its state and available output artifacts
5. Click a job in the list, then **Open Job Map** or **Open Half Maps** to load its outputs directly

### Connecting to a cluster over SSH
1. Switch to the **SSH** tab
2. Enter the host, port, and username; the key field auto-detects `~/.ssh/id_ed25519`/`id_rsa` if present — change it or enter a passphrase if needed
3. Click **Connect** — an unknown host is rejected; if that happens, `ssh user@host` once from a terminal to trust it, then retry
4. Enter the remote project directory and browse it like the other tabs
5. Leave **Auto-download && open** checked to fetch-and-open files directly, or uncheck it and use **Copy Remote Path** to just grab the path

---

## Typical Cryo-EM / Cryo-ET Workflow

    Project/
        Class3D/
            job001/    navigate here for classification maps
            job002/
        Refine3D/
            job003/    set as Map Directory for refinement iterations
            job004/
        Masks/         set as Mask Directory
            mask_tight.mrc
            mask_loose.mrc

    cryosparc_projects/
        P1/                     set as CryoSPARC Project / Job Directory
            J42/
                cryosparc_P1_J42_volume_map.mrc
                cryosparc_P1_J42_volume_map_half_A.mrc
                cryosparc_P1_J42_volume_map_half_B.mrc
                cryosparc_P1_J42_mask.mrc
                cryosparc_P1_J42_class_00_view_dist.bild

Set the active refinement job as the **Map Directory** — new `*_class*.mrc` or `*_half*.mrc` files will appear automatically as iterations complete. Set the masks folder as the **Mask Directory** and browse to the right mask when needed. Use the **RELION Job History** tab to trace which upstream jobs led to the current refinement.

---

## Requirements

- ChimeraX 1.0 or later
- ChimeraX-Core ≥ 1.0
- ChimeraX-UI ≥ 1.0
- ChimeraX-Map ≥ 1.0
- `paramiko` (SFTP client for the SSH tab — installed automatically as a bundle dependency)

---

## Credits

**Author:** Lukas W. Bauer (AI-assisted development by Claude, Anthropic)

This tool was developed by Lukas W. Bauer. The code was written collaboratively with **Claude** (Anthropic) acting as AI copilot — contributing to Python/Qt implementation, UI design decisions, and iterative improvements based on real-world usage feedback.

The plugin icon was generated with **Gemini** (Google).

---

## Acknowledgments

Looking at [`m2selfA/CryoRemote`](https://github.com/m2selfA/CryoRemote)'s approach to RELION STAR-table parsing and per-job artifact/state detection inspired the shlex-based STAR parser fix and the job state/artifact badges (see CHANGELOG's "Internal iteration 3"). No code was copied — InstantMap's implementation is independently written — but the idea traces back to their `src/relion.py`.

---

## License

InstantMap is released under the [MIT License](LICENSE).

See [CHANGELOG.md](CHANGELOG.md) for the version history.

---

## Roadmap / Backlog

- **Done (1.1.0, initial release):** RELION/Mask/CryoSPARC browsers with auto-refresh; RELION job-history/lineage with state+artifact badges; SSH/SFTP browsing of a remote RELION/CryoSPARC project (key-based auth, download-and-open or browse-only); session save/restore; background-threaded directory scanning so slow/network mounts don't freeze the UI; a `pytest` test suite; one-click InstantMap button with a transparent-background icon in a new EM section of ChimeraX's Map toolbar tab — see [CHANGELOG.md](CHANGELOG.md) for the full breakdown
- **Considered, not planned:** `csparc2star`/pyem-style particle-metadata conversion (a different tool category — full `.cs` particle-metadata parsing and coordinate-convention conversion — and pyem is GPL-3.0, which would require InstantMap itself to go GPL to embed it; a future thin "shell out to a separately-installed `csparc2star.py`" convenience button would sidestep the licensing issue but isn't currently planned)
- **Possible future items:**
  - A RELION pipeline flowchart view as an alternative to the flat lineage list.
  - CryoSPARC job status/badges backed by `job.json` once its schema can be confirmed against real project output (still undocumented and not always present as of this writing — [CryoSPARC Guide](https://guide.cryosparc.com/) has no spec for it — so intentionally left as a filename heuristic).
  - Optionally backing the CryoSPARC tab with [`cryosparc-tools`](https://github.com/cryoem-uoft/cryosparc-tools) — Structura Biotechnology's own official Python API for CryoSPARC (PyPI, source-available) — instead of/alongside filesystem reads. Would give real job type/status/parameters instead of filename guessing, but needs a live connection (host/port/API credentials) to the CryoSPARC master, which not every cluster setup exposes to the client machine — a bigger, separate feature, not started.
  - SSH tab hardening: an in-app "trust this new host" prompt (showing the key fingerprint) as an alternative to requiring a manual `ssh` once from a terminal — common UX pattern in other SSH-capable tools, would need its own care to avoid weakening the current TOFU-via-`known_hosts` model.

## Before Publishing to the Toolshed

Not done yet — noting this for when this bundle is ready to publish:
- Toolshed submission requires signing in with a Google account, then using the "Submit a Bundle" link; **the first submission needs approval from ChimeraX staff**, later updates from the same account publish immediately. ([Building and Distributing Bundles](https://www.cgl.ucsf.edu/chimerax/docs/devel/writing_bundles.html))
- The bundle is a standard wheel (already builds cleanly via `devel install .`); nothing else in `bundle_info.xml` needs to change for submission.

---

## Development

Run the test suite (no ChimeraX installation required — the STAR/artifact/badge/directory-scan logic lives in standalone modules under `src/`):

```
pip install pytest
pytest tests/
```

To install into a local ChimeraX for manual testing:

```
ChimeraX --nogui --exit --cmd "devel install . ; exit"
```
