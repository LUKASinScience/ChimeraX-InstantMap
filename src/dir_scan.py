import os


def scan_directory(directory, extensions, show_folders, opened_files, badge_fn=None):
    """Pure filesystem scan of `directory` for files matching `extensions`.

    No Qt/session dependency — safe to run on a background thread. Returns
    plain data for the caller to turn into widgets on the main thread.
    Raises OSError if `directory` itself can't be listed (caller's problem).
    """
    entries = sorted(os.listdir(directory))

    subdirs = [
        f for f in entries
        if os.path.isdir(os.path.join(directory, f))
        and not f.startswith(".")
    ]
    matched = [f for f in entries if _matches(f, extensions)]

    result = {
        "subdirs": [],
        "matched": [],
        "subdir_count": len(subdirs),
        "matched_count": len(matched),
    }

    if show_folders:
        for dname in subdirs:
            subdir_path = os.path.join(directory, dname)
            sub_files = []
            try:
                sub_entries = sorted(os.listdir(subdir_path))
                sub_names = [f for f in sub_entries if _matches(f, extensions)]
                for sfname in sub_names:
                    full_path = os.path.join(subdir_path, sfname)
                    sub_files.append({
                        "label": _label_for(full_path, sfname, badge_fn),
                        "path": full_path,
                        "opened": full_path in opened_files,
                    })
            except OSError:
                pass
            result["subdirs"].append({"name": dname, "sub_files": sub_files})

    for fname in matched:
        full_path = os.path.join(directory, fname)
        result["matched"].append({
            "label": _label_for(full_path, fname, badge_fn),
            "path": full_path,
            "opened": full_path in opened_files,
        })

    return result


def _matches(filename, extensions):
    return filename.lower().endswith(extensions)


def _label_for(full_path, fname, badge_fn):
    try:
        size_mb = os.path.getsize(full_path) / (1024 * 1024)
        label = "%s   (%.1f MB)" % (fname, size_mb)
    except OSError:
        label = fname
    if badge_fn:
        tag = badge_fn(full_path)
        if tag:
            label = "%s  %s" % (tag, label)
    return label
