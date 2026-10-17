"""listen.poll_once: requests are read, validated and handed to the opener; stale or malformed ones are dropped."""
import json
import os
import time

import listen


def _setup(tmp_path, monkeypatch):
    monkeypatch.setattr(listen, "QUEUE", tmp_path / "q")
    (tmp_path / "q").mkdir()
    m = tmp_path / "a.mrc"
    m.write_bytes(b"x")
    return m


def test_open_tile_and_legacy_requests(tmp_path, monkeypatch):
    m = _setup(tmp_path, monkeypatch)
    q = tmp_path / "q"
    (q / "req-1").write_text(json.dumps({"action": "tile", "paths": [str(m), str(m)]}))
    (q / "req-2").write_text(str(m))                      # legacy: a bare path
    seen = []
    opened = listen.poll_once(None, opener=lambda s, paths, tile: seen.append((len(paths), tile)))
    assert sorted(seen) == [(1, False), (2, True)] and len(opened) == 3
    assert not list(q.glob("req-*"))


def test_stale_malformed_and_wrong_type_are_dropped(tmp_path, monkeypatch):
    m = _setup(tmp_path, monkeypatch)
    q = tmp_path / "q"
    old = q / "req-old"
    old.write_text(json.dumps({"action": "open", "paths": [str(m)]}))
    long_ago = time.time() - listen.MAX_AGE - 5
    os.utime(old, (long_ago, long_ago))
    (q / "req-bad").write_text("{not json")
    (q / "req-type").write_text(json.dumps({"action": "open", "paths": ["/etc/passwd"]}))
    (q / "req-many").write_text(json.dumps({"action": "open", "paths": [str(m)] * 50}))
    seen = []
    assert listen.poll_once(None, opener=lambda *a: seen.append(a)) == [] and not seen
    assert not list(q.glob("req-*"))
