"""download_file: atomic, size-checked, and skips a cached copy that is still good."""
import os
import types

import pytest

from ssh_scan import download_file


class FakeSftp:
    def __init__(self, data=b"x" * 100, mtime=1_000_000.0, fail_after=None):
        self.data, self.mtime, self.fail_after, self.gets = data, mtime, fail_after, 0

    def stat(self, path):
        return types.SimpleNamespace(st_size=len(self.data), st_mtime=self.mtime)

    def get(self, remote, local):
        self.gets += 1
        with open(local, "wb") as f:
            f.write(self.data if self.fail_after is None else self.data[: self.fail_after])
        if self.fail_after is not None:
            raise IOError("connection lost")


def test_download_then_cache_hit_then_refresh_when_remote_changes(tmp_path):
    local = str(tmp_path / "h" / "a.mrc")
    sftp = FakeSftp()
    assert download_file(sftp, "/r/a.mrc", local) is True and open(local, "rb").read() == sftp.data
    assert download_file(sftp, "/r/a.mrc", local) is False and sftp.gets == 1          # still good: no second transfer
    sftp.mtime += 10                                                                    # remote file was rewritten
    assert download_file(sftp, "/r/a.mrc", local) is True and sftp.gets == 2
    sftp.data = b"y" * 60                                                               # different size, same mtime
    assert download_file(sftp, "/r/a.mrc", local) is True and open(local, "rb").read() == b"y" * 60


def test_interrupted_download_leaves_no_half_file_and_keeps_the_old_copy(tmp_path):
    local = str(tmp_path / "a.mrc")
    good = FakeSftp()
    download_file(good, "/r/a.mrc", local)
    broken = FakeSftp(mtime=good.mtime + 5, fail_after=30)
    with pytest.raises(IOError):
        download_file(broken, "/r/a.mrc", local)
    assert open(local, "rb").read() == good.data                  # the earlier good copy survives
    assert os.listdir(tmp_path) == ["a.mrc"]                       # and no .part file is left behind


def test_short_transfer_is_rejected_even_without_an_exception(tmp_path):
    class Short(FakeSftp):
        def get(self, remote, local):
            open(local, "wb").write(b"z" * 10)                     # claims success but wrote too little
    local = str(tmp_path / "b.mrc")
    with pytest.raises(IOError, match="incomplete"):
        download_file(Short(), "/r/b.mrc", local)
    assert not os.path.exists(local) and os.listdir(tmp_path) == []
