import os
import stat


def connect(host, port, username, key_path=None, passphrase=None, timeout=10):
    """Open an SSH connection + SFTP session to `host`.

    Uses key-based auth only (no password auth). Host keys are checked
    against the user's own `~/.ssh/known_hosts` (`load_system_host_keys`);
    an unknown host is *rejected*, not silently trusted (no `AutoAddPolicy`
    — avoids a MITM footgun). If the host is genuinely new, the user needs
    to `ssh` into it once from a terminal so it gets added to
    `known_hosts`, then retry here.

    Nothing is ever written to disk by this function. Raises on failure —
    callers should catch `Exception` and surface `str(exc)`, since paramiko
    raises several distinct exception types (auth, host-key, socket errors).
    """
    import paramiko

    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    client.connect(
        hostname=host,
        port=port,
        username=username,
        key_filename=key_path or None,
        passphrase=passphrase or None,
        timeout=timeout,
        look_for_keys=True,
        allow_agent=True,
    )
    sftp = client.open_sftp()
    return client, sftp


def scan_remote_directory(sftp, directory, extensions, show_folders, opened_files, badge_fn=None):
    """Pure(ish) SFTP scan of `directory` for files matching `extensions`.

    Mirrors `dir_scan.scan_directory`'s return shape exactly, so callers can
    render both local and remote results with the same tree-building code.
    Only depends on `sftp` via `listdir_attr` (duck-typed: any object with a
    matching method works), so this is unit-testable without real paramiko.
    """
    entries = sorted(sftp.listdir_attr(directory), key=lambda a: a.filename)

    subdirs = [a.filename for a in entries if stat.S_ISDIR(a.st_mode) and not a.filename.startswith(".")]
    matched = [a for a in entries if _matches(a.filename, extensions)]

    result = {
        "subdirs": [],
        "matched": [],
        "subdir_count": len(subdirs),
        "matched_count": len(matched),
    }

    if show_folders:
        for dname in subdirs:
            subdir_path = _join(directory, dname)
            sub_files = []
            try:
                sub_entries = sorted(sftp.listdir_attr(subdir_path), key=lambda a: a.filename)
                for sa in sub_entries:
                    if _matches(sa.filename, extensions):
                        full_path = _join(subdir_path, sa.filename)
                        sub_files.append({
                            "label": _label_for(full_path, sa.filename, sa.st_size, badge_fn),
                            "path": full_path,
                            "opened": full_path in opened_files,
                        })
            except OSError:
                pass
            result["subdirs"].append({"name": dname, "sub_files": sub_files})

    for a in matched:
        full_path = _join(directory, a.filename)
        result["matched"].append({
            "label": _label_for(full_path, a.filename, a.st_size, badge_fn),
            "path": full_path,
            "opened": full_path in opened_files,
        })

    return result


def download_file(sftp, remote_path, local_path):
    """Fetch `remote_path` to `local_path` via SFTP, creating parent dirs."""
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    sftp.get(remote_path, local_path)


def local_cache_path(cache_root, host, remote_path):
    """Mirror a remote path under `<cache_root>/<host>/...` so files from
    different hosts/directories with the same filename don't collide.

    Drops any "." / ".." / empty segments rather than resolving them, so a
    remote path containing ".." (whether typed, or from an oddly-named
    remote entry) can't make the local destination escape `cache_root` —
    the remote fetch itself is unaffected, only the local mirrored path is
    sanitized."""
    parts = [p for p in remote_path.split("/") if p not in ("", ".", "..")]
    return os.path.join(cache_root, host, *parts)


def _join(directory, name):
    # Remote paths are always POSIX-style regardless of the local OS.
    if directory.endswith("/"):
        return directory + name
    return directory + "/" + name


def _matches(filename, extensions):
    return filename.lower().endswith(extensions)


def _label_for(full_path, fname, size_bytes, badge_fn):
    size_mb = size_bytes / (1024 * 1024)
    label = "%s   (%.1f MB)" % (fname, size_mb)
    if badge_fn:
        tag = badge_fn(full_path)
        if tag:
            label = "%s  %s" % (tag, label)
    return label
