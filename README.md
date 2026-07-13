# ChimeraX-InstantMap

**Tired of manually refreshing your classification or refinement directories in ChimeraX? inSTAnt Map automatically monitors a directory for new MRC/MAP files and keeps the list up to date — so the latest iteration map is always one click away. Built for Cryo-EM SPA and Cryo-ET STA workflows.**


---

## Overview

inSTAnt Map was built to streamline the everyday file management that comes with single particle analysis (SPA) and subtomogram averaging (STA) workflows. Instead of manually navigating to the output directory every time a new iteration finishes, inSTAnt Map watches the directory and keeps the file list up to date automatically. 

####Update Version 1.0.1: RELION Job History Tab

To know, in case you are using RELION, which jobs have been running bevor your job you are running/analyzing, this new tab allows you to get the job history of a selected job in your RELION processing dir.

---

## Features

### Browser Tab

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

### RELION Job History Tab
- Select a RELION project directory — reads `default_pipeline.star` automatically
- Choose a job family (e.g. `Refine3D`) and a specific job from dropdowns
- Displays the complete **upstream job lineage** in chronological order: job number, job type (color-coded), parent job(s)
- Useful for tracing which classification or selection led to a given refinement

### General
- Compact scrollable UI — fits neatly in the ChimeraX side panel
- Works seamlessly alongside other ChimeraX tools

---

## Installation

### Via ChimeraX Toolshed
1. Open ChimeraX
2. Go to **Tools → More Tools...** (opens the Toolshed)
3. Search for **inSTAnt Map**
4. Click **Install**

### Manual installation
```
toolshed install /path/to/ChimeraX_InstantMap-1.0.1-py3-none-any.whl
```

---

## Usage

### Getting started
1. Open the tool via **Tools → Volume Data → inSTAnt Map**
2. In the **Browser** tab, click **Browse** or paste a path into the Map Directory field to select the output directory (e.g. a RELION or cryoSPARC job folder)
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

### RELION Job History
1. Switch to the **RELION Job History** tab
2. Browse to or paste the RELION project root (the folder containing `default_pipeline.star`)
3. Select a job family and job from the dropdowns
4. Click **Load history** — the upstream lineage appears in chronological order

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

Set the active refinement job as the **Map Directory** — new `*_class*.mrc` or `*_half*.mrc` files will appear automatically as iterations complete. Set the masks folder as the **Mask Directory** and browse to the right mask when needed. Use the **RELION Job History** tab to trace which upstream jobs led to the current refinement.

---

## Requirements

- ChimeraX 1.0 or later
- ChimeraX-Core ≥ 1.0
- ChimeraX-UI ≥ 1.0
- ChimeraX-Map ≥ 1.0

---

## Credits

**Author:** Lukas W. Bauer (AI-assisted development by Claude, Anthropic)

This tool was developed by Lukas W. Bauer. The code was written collaboratively with **Claude** (Anthropic) acting as AI copilot — contributing to Python/Qt implementation, UI design decisions, and iterative improvements based on real-world usage feedback.

The plugin icon was generated with **Gemini** (Google).
