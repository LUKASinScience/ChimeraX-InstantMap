from dir_scan import scan_directory

EXTENSIONS = (".mrc", ".map")


def _touch(path):
    path.write_text("x" * 2048)  # non-zero size so the MB label is stable-ish


def test_scan_directory_matches_extensions_and_ignores_others(tmp_path):
    _touch(tmp_path / "volume.mrc")
    _touch(tmp_path / "notes.txt")

    result = scan_directory(str(tmp_path), EXTENSIONS, show_folders=True, opened_files=set())
    assert result["matched_count"] == 1
    assert result["matched"][0]["path"] == str(tmp_path / "volume.mrc")
    assert "volume.mrc" in result["matched"][0]["label"]


def test_scan_directory_subfolder_preview_when_show_folders_true(tmp_path):
    sub = tmp_path / "job001"
    sub.mkdir()
    _touch(sub / "inner.mrc")
    _touch(sub / "skip.txt")

    result = scan_directory(str(tmp_path), EXTENSIONS, show_folders=True, opened_files=set())
    assert result["subdir_count"] == 1
    entry = result["subdirs"][0]
    assert entry["name"] == "job001"
    assert len(entry["sub_files"]) == 1
    assert entry["sub_files"][0]["path"] == str(sub / "inner.mrc")


def test_scan_directory_hides_subdir_preview_when_show_folders_false(tmp_path):
    sub = tmp_path / "job001"
    sub.mkdir()
    _touch(sub / "inner.mrc")

    result = scan_directory(str(tmp_path), EXTENSIONS, show_folders=False, opened_files=set())
    assert result["subdirs"] == []
    # subdir_count still reflects the real count even though the preview is hidden
    assert result["subdir_count"] == 1


def test_scan_directory_flags_opened_files(tmp_path):
    target = tmp_path / "volume.mrc"
    _touch(target)

    result = scan_directory(
        str(tmp_path), EXTENSIONS, show_folders=True, opened_files={str(target)}
    )
    assert result["matched"][0]["opened"] is True


def test_scan_directory_applies_badge_fn(tmp_path):
    _touch(tmp_path / "volume.mrc")

    def badge_fn(path):
        return "[tagged]" if path.endswith(".mrc") else None

    result = scan_directory(
        str(tmp_path), EXTENSIONS, show_folders=True, opened_files=set(), badge_fn=badge_fn
    )
    assert result["matched"][0]["label"].startswith("[tagged]")


def test_scan_directory_raises_for_missing_directory(tmp_path):
    import pytest

    with pytest.raises(OSError):
        scan_directory(str(tmp_path / "nope"), EXTENSIONS, True, set())
