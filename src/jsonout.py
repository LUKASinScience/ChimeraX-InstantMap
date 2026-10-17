"""Machine-readable result files (`jsonFile <path>`) for scripts and AI assistants.
Every file is one object: {"schema": "instantmap/1", "version": ..., "command": ..., "ok": true|false, ...data} or, on failure,
{"schema", "version", "command", "ok": false, "error": "..."}. Keys are documented in SKILL.md."""
import json

SCHEMA = "instantmap/1"
VERSION = "1.3.0"


def write(path, command, data=None, error=None):
    if not path:
        return
    body = {"schema": SCHEMA, "version": VERSION, "command": command, "ok": error is None}
    body.update({"error": error} if error is not None else (data or {}))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(body, f, indent=2)
