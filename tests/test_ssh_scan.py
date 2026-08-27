import os
import stat

from ssh_scan import scan_remote_directory, local_cache_path, _join

EXTENSIONS = (".mrc", ".map")


class FakeAttr:
    def __init__(self, filename, is_dir=False, size=2048):
        self.filename = filename
        self.st_mode = (stat.S_IFDIR if is_dir else stat.S_IFREG) | 0o755
        self.st_size = size


class FakeSFTP:
    """Duck-types paramiko's SFTPClient.listdir_attr for a fixed tree."""

    def __init__(self, tree):
        self._tree = tree  # {"/remote": [FakeAttr, ...], ...}

    def listdir_attr(self, path):
        return self._tree[path]


def test_scan_remote_directory_matches_extensions_and_ignores_others():
    sftp = FakeSFTP({
        "/proj": [FakeAttr("volume.mrc"), FakeAttr("notes.txt")],
    })
    result = scan_remote_directory(sftp, "/proj", EXTENSIONS, show_folders=True, opened_files=set())
    assert result["matched_count"] == 1
    assert result["matched"][0]["path"] == "/proj/volume.mrc"
    assert "volume.mrc" in result["matched"][0]["label"]


def test_scan_remote_directory_subfolder_preview_when_show_folders_true():
    sftp = FakeSFTP({
        "/proj": [FakeAttr("job001", is_dir=True)],
        "/proj/job001": [FakeAttr("inner.mrc"), FakeAttr("skip.txt")],
    })
    result = scan_remote_directory(sftp, "/proj", EXTENSIONS, show_folders=True, opened_files=set())
    assert result["subdir_count"] == 1
    entry = result["subdirs"][0]
    assert entry["name"] == "job001"
    assert len(entry["sub_files"]) == 1
    assert entry["sub_files"][0]["path"] == "/proj/job001/inner.mrc"


def test_scan_remote_directory_hides_subdir_preview_when_show_folders_false():
    sftp = FakeSFTP({
        "/proj": [FakeAttr("job001", is_dir=True)],
    })
    result = scan_remote_directory(sftp, "/proj", EXTENSIONS, show_folders=False, opened_files=set())
    assert result["subdirs"] == []
    assert result["subdir_count"] == 1


def test_scan_remote_directory_flags_opened_files():
    sftp = FakeSFTP({
        "/proj": [FakeAttr("volume.mrc")],
    })
    result = scan_remote_directory(
        sftp, "/proj", EXTENSIONS, show_folders=True, opened_files={"/proj/volume.mrc"}
    )
    assert result["matched"][0]["opened"] is True


def test_scan_remote_directory_applies_badge_fn():
    sftp = FakeSFTP({
        "/proj": [FakeAttr("volume.mrc")],
    })

    def badge_fn(path):
        return "[tagged]" if path.endswith(".mrc") else None

    result = scan_remote_directory(
        sftp, "/proj", EXTENSIONS, show_folders=True, opened_files=set(), badge_fn=badge_fn
    )
    assert result["matched"][0]["label"].startswith("[tagged]")


def test_join_handles_trailing_slash():
    assert _join("/proj", "job001") == "/proj/job001"
    assert _join("/proj/", "job001") == "/proj/job001"


def test_local_cache_path_mirrors_remote_structure_under_host():
    path = local_cache_path("/cache", "cluster.edu", "/scratch/user/job001/volume.mrc")
    expected_suffix = os.path.join("cluster.edu", "scratch", "user", "job001", "volume.mrc")
    assert path.endswith(expected_suffix)


def test_local_cache_path_drops_dotdot_segments_to_prevent_traversal():
    # ".." segments are dropped outright (not resolved against preceding
    # segments), so a remote path can never make the local destination
    # escape cache_root/host (path traversal hardening).
    path = local_cache_path("/cache", "cluster.edu", "/scratch/../../etc/passwd")
    assert path == os.path.join("/cache", "cluster.edu", "scratch", "etc", "passwd")
    assert ".." not in path.split(os.sep)
    assert path.startswith(os.path.join("/cache", "cluster.edu"))
