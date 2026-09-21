## External tooling notes
- davidhenty/benchio (MPI I/O benchmark): only pull in if SSH/SFTP directory watching or map transfer from remote clusters becomes a measured bottleneck — not a default dependency.

## Analysis findings (2026-09-19)
Good test coverage for RELION/CryoSPARC logic (`tests/test_relion_*.py`, `test_cryosparc_badges.py`, `test_ssh_scan.py`, `test_dir_scan.py`) — but the GUI-glue files have zero tests: `src/tool.py` (1106 lines, main ToolInstance), `src/cmd.py`, `src/browser_panel.py` (330 lines), `src/ssh_browser_panel.py`, `src/relion_treebuild.py`. `browser_panel.py`/`relion_treebuild.py` likely have extractable pure logic (dir-diffing, tree assembly) worth pulling out and testing.
1. `src/relion_tree_dialog.py` has 5 separate `except Exception:` blocks (lines 162, 169, 230, 238, 464) — a bug there fails silently rather than surfacing.
2. `src/ssh_browser_panel.py:281,286` use bare `except Exception:` with no visible `session.logger` call — confirm errors actually surface.
3. `src/relion_pipeline.py:50` — one `except Exception:`, worth checking it logs since it drives RELION lineage/job detection correctness.
No TODO/FIXME markers found otherwise — scope looks complete.
