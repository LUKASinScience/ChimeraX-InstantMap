"""`instantmap listen`: let reliontree (or anything else of yours) open maps in
THIS ChimeraX without a network port.

Polls ~/.reliontree/chimerax for `req-*` files (a bare path, or JSON
{"action": "open"|"tile", "paths": [...]}) and runs `open <path>` per file, plus
`tile` for the opened models when asked -- nothing else is ever executed.
Requests must be owned by the current user and name existing .mrc/.map/.bild files.
"""
import json
import os
import threading
import time
from pathlib import Path

QUEUE = Path.home() / ".reliontree" / "chimerax"
MAP_SUFFIXES = (".mrc", ".map", ".bild")
MAX_FILES = 40
MAX_AGE = 300.0   # seconds: a request older than this is leftover from an earlier session and is dropped, not opened
_stop = None  # threading.Event of the running listener


def _mine(path):
    return not hasattr(os, "getuid") or path.stat().st_uid == os.getuid()


def _open(session, paths, tile=False):
    from chimerax.core.commands import run, quote_path_if_necessary
    models = []
    for path in paths:
        models += run(session, "open %s" % quote_path_if_necessary(str(path))) or []
    ids = [m.id_string for m in models if getattr(m, "id_string", "")]
    if tile and len(ids) > 1:
        run(session, "tile #%s" % ",".join(ids))


def _parse(text):
    """-> (paths, tile) from a request file's text; raises ValueError on junk."""
    if text.startswith("{"):
        data = json.loads(text)
        paths, tile = data["paths"], data.get("action") == "tile"
    else:
        paths, tile = [text], False
    if not isinstance(paths, list) or not 1 <= len(paths) <= MAX_FILES:
        raise ValueError("bad path list")
    return [Path(p).resolve() for p in paths], tile


def poll_once(session, opener=_open):
    """Handle pending requests once; returns the paths opened."""
    opened = []
    for f in sorted(QUEUE.glob("req-*")):
        try:
            if time.time() - f.stat().st_mtime > MAX_AGE:
                f.unlink()
                continue
            text = f.read_text().strip() if _mine(f) else None
            f.unlink()
            paths, tile = _parse(text) if text else ([], False)
        except (OSError, ValueError, KeyError, TypeError):
            continue
        if paths and all(p.suffix.lower() in MAP_SUFFIXES and p.is_file() for p in paths):
            opener(session, paths, tile)
            opened += paths
    return opened


def start(session):
    global _stop
    stop()
    QUEUE.mkdir(parents=True, exist_ok=True)
    QUEUE.chmod(0o700)
    if not _mine(QUEUE):
        raise OSError("%s is not owned by you" % QUEUE)
    ev = _stop = threading.Event()

    def loop():
        while not ev.wait(0.5):
            try:
                (QUEUE / "alive").touch()
                for p in poll_once(session, opener=lambda s, ps, t: s.ui.thread_safe(_open, s, ps, t)):
                    pass
            except Exception as e:  # keep listening; surface in the log
                session.ui.thread_safe(session.logger.warning, "instantmap listen: %s" % e)

    threading.Thread(target=loop, daemon=True, name="instantmap-listen").start()


def stop():
    global _stop
    if _stop:
        _stop.set()
        _stop = None
        try:
            (QUEUE / "alive").unlink()
        except OSError:
            pass
