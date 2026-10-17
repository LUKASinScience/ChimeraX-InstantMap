"""mask_core: properties, an independent exact reference, and -- when the project is on this machine -- real RELION masks."""
import os
import struct
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("scipy")

import mask_core as mc  # noqa: E402  (tests/conftest.py puts src/ on sys.path)

# Real RELION MaskCreate output + its input map. Not shipped (research data); set RELION_MASK_PROJECT to run this test.
REAL = os.environ.get("RELION_MASK_PROJECT") or ""
REAL_JOBS = {   # job: (threshold, extend, soft edge, low-pass in Angstrom) as written in that job's job.star
    "job005": (0.0321, 3, 3, 40),
    "job013": (0.0280, 5, 5, 50),
}


def sphere(n=24, r=5.0, c=11.5):
    z, y, x = np.mgrid[:n, :n, :n]
    return ((z - c) ** 2 + (y - c) ** 2 + (x - c) ** 2) <= r ** 2


def brute_edt(target_true):
    """distance of every voxel to the nearest voxel where `target_true` is True (exact, small grids only)"""
    fg, idx = np.argwhere(target_true), np.argwhere(np.ones(target_true.shape, bool))
    return np.sqrt(((idx[:, None, :] - fg[None, :, :]) ** 2).sum(-1)).min(axis=1).reshape(target_true.shape)


def reference(hard, extend, soft):
    """Independent re-statement of the RELION-verified rules, with a brute-force distance."""
    hard = hard.copy()
    if extend > 0:
        hard = hard | (brute_edt(hard) < extend)
    out = hard.astype(np.float32)
    if soft > 0:
        d = brute_edt(hard)
        e = (~hard) & (d <= soft)
        out[e] = 0.5 + 0.5 * np.cos(np.pi * d[e] / soft)
    return out


@pytest.mark.parametrize("extend,soft", [(0, 0), (2, 0), (0, 3), (2, 4), (3, 3)])
def test_matches_brute_force_reference(extend, soft):
    vol = sphere().astype(float)
    out = mc.make_mask(vol, 0.5, extend=extend, soft_edge=soft)
    assert out.dtype == np.float32 and np.abs(out - reference(sphere(), extend, soft)).max() < 1e-6


def test_extend_is_strictly_below_the_distance():
    """A voxel exactly `extend` away is NOT grown into (this is RELION's rule; '<=' gives one layer more)."""
    vol = np.zeros((15, 15, 15))
    vol[7, 7, 7] = 1.0
    out = mc.make_mask(vol, 0.5, extend=3)
    assert out[7, 7, 10] == 0 and out[7, 7, 9] == 1                      # distance 3 excluded, distance 2 included


def test_soft_edge_profile_and_range():
    vol = np.zeros((21, 21, 21))
    vol[10, 10, 10] = 1.0
    out = mc.make_mask(vol, 0.5, soft_edge=4)
    assert out[10, 10, 10] == 1.0 and out.min() >= 0 and out.max() <= 1
    assert out[10, 10, 12] == pytest.approx(0.5 + 0.5 * np.cos(np.pi * 2 / 4))   # d = 2 of 4 -> 0.5
    assert out[10, 10, 14] == pytest.approx(0.0, abs=1e-6)                       # d = 4 -> 0


def test_erosion_shrinks_and_never_sees_the_box_edge_as_inside():
    full = np.ones((10, 10, 10))
    out = mc.make_mask(full, 0.5, extend=-2)
    assert out[5, 5, 5] == 1 and out[0, 5, 5] == 0                         # the box wall counts as outside
    assert mc.make_mask(sphere().astype(float), 0.5, extend=-2).sum() < sphere().sum()          # strict rule: -1 removes nothing, -2 one layer


def test_lowpass_properties():
    n = 32
    z, y, x = np.mgrid[:n, :n, :n]
    low = np.sin(2 * np.pi * x / n)                                          # 1 cycle per box
    high = np.cos(2 * np.pi * 14 * x / n)                                    # 14 cycles per box
    f = mc.lowpass_filter(5.0 + low + high, angpix=2.0, resolution=10.0)    # cutoff at round(32*2/10) = 6 cycles
    assert f.mean() == pytest.approx(5.0, abs=1e-9)                          # DC preserved
    assert np.abs(f - (5.0 + low)).max() < 1e-9                              # low kept, high removed
    assert np.allclose(mc.lowpass_filter(np.full((8, 8, 8), 3.0), 1.0, 4.0), 3.0)


def test_input_errors():
    v = np.zeros((6, 6, 6))
    for bad in (dict(threshold=np.nan), dict(threshold=0.1, soft_edge=-1), dict(threshold=0.1, lowpass=10)):
        with pytest.raises(ValueError):
            mc.make_mask(v, **bad)
    with pytest.raises(ValueError):
        mc.make_mask(np.zeros((4, 4)), 0.1)
    with pytest.raises(ValueError):
        mc.lowpass_filter(v, 1.0, -5.0)


def _read_mrc(path):
    with open(path, "rb") as f:
        h = f.read(1024)
        nx, ny, nz, mode = struct.unpack("<4i", h[:16])
        mx = struct.unpack("<i", h[28:32])[0]
        cell_x = struct.unpack("<f", h[40:44])[0]
        f.seek(1024 + struct.unpack("<i", h[92:96])[0])
        assert mode == 2
        return np.frombuffer(f.read(nx * ny * nz * 4), dtype=np.float32).reshape(nz, ny, nx).astype(float), cell_x / mx


@pytest.mark.skipif(not REAL or not (Path(REAL) / "default_pipeline.star").exists(), reason="the real RELION project is not on this machine")
@pytest.mark.parametrize("job", sorted(REAL_JOBS))
def test_reproduces_a_real_relion_mask_exactly(job):
    threshold, extend, soft, lowpass = REAL_JOBS[job]
    text = (Path(REAL) / "MaskCreate" / job / "job.star").read_text()
    assert str(extend) in text and str(soft) in text                        # the parameters above are the job's own
    fn_in = next(l.split()[1] for l in text.splitlines() if l.strip().startswith("fn_in"))
    volume, angpix = _read_mrc(Path(REAL) / fn_in)
    relion, _ = _read_mrc(Path(REAL) / "MaskCreate" / job / "mask.mrc")
    ours = mc.make_mask(volume, threshold, extend=extend, soft_edge=soft, lowpass=lowpass, angpix=angpix)
    assert np.abs(ours - relion).max() < 1e-5
