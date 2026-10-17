"""Soft masks the way `relion_mask_create` makes them: low-pass, threshold, extend, soft edge. Pure NumPy/SciPy.

Checked against REAL RELION output (2026-10-17): two MaskCreate jobs of a bin-8 STA project (different threshold,
extend, soft-edge width and low-pass) are reproduced with a maximum voxel difference of 0.0000 by this code
(tests/test_mask_core.py runs that comparison when the project is available). What that pinned down:
  * the map is low-pass filtered first, with a raised-cosine edge of 2 Fourier pixels (RELION's lowPassFilterMap);
  * the binary mask is `filtered > threshold`;
  * `extend` grows it by every voxel whose distance to the mask is STRICTLY below `extend` (distance < extend, not <=);
  * the soft edge is 0.5 + 0.5 cos(pi d / width) at distance d from the grown mask, for d <= width.
Not verified against RELION (no example available): negative `extend` (erosion; implemented as the mirror image of
growing) and boxes that are not cubic (RELION assumes cubic).
"""
import numpy as np


def _distance_transform_edt(array):
    try:
        from scipy.ndimage import distance_transform_edt
    except ImportError as exc:     # an approximate fallback would silently give wrong masks; fail loudly instead
        raise RuntimeError("scipy is required to make masks (it ships with ChimeraX)") from exc
    return distance_transform_edt(array)


def lowpass_filter(volume, angpix, resolution, edge_width=2.0):
    """RELION's low-pass: Fourier components below the cutoff stay, above it go to zero, with a raised-cosine ramp of
    `edge_width` Fourier pixels centred on the cutoff (which is rounded to a whole Fourier pixel, as RELION does)."""
    vol = np.asarray(volume, dtype=float)
    if vol.ndim != 3:
        raise ValueError("volume must be 3-D")
    if resolution <= 0 or angpix <= 0:
        raise ValueError("resolution and pixel size must be positive")
    n = max(vol.shape)
    ires = round(n * angpix / resolution)
    half = edge_width / 2.0
    lo, hi = max(0.0, (ires - half) / n), min(float(n), (ires + half) / n)
    kz, ky, kx = np.meshgrid(*[np.fft.fftfreq(s) * n for s in vol.shape], indexing="ij")   # in units of 1/(n pixels)
    res = np.sqrt(kx ** 2 + ky ** 2 + kz ** 2) / n
    filt = np.where(res < lo, 1.0, np.where(res > hi, 0.0, 0.5 + 0.5 * np.cos(np.pi * (res - lo) / max(hi - lo, 1e-12))))
    return np.real(np.fft.ifftn(np.fft.fftn(vol) * filt))


def make_mask(volume, threshold, extend=0.0, soft_edge=0.0, lowpass=None, angpix=None, edge_width=2.0):
    """float32 mask (values 0..1, same shape as `volume`). `extend` and `soft_edge` are in voxels, `lowpass` in Angstrom
    (needs `angpix`), `threshold` in the units of the (filtered) map."""
    img = np.asarray(volume, dtype=float)
    if img.ndim != 3:
        raise ValueError("volume must be 3-D")
    if not all(np.isfinite(v) for v in (threshold, extend, soft_edge)):
        raise ValueError("threshold, extend and soft edge must be finite numbers")
    if soft_edge < 0:
        raise ValueError("soft edge must not be negative")
    if lowpass:
        if not angpix:
            raise ValueError("a low-pass needs the pixel size")
        img = lowpass_filter(img, angpix, lowpass, edge_width)
    hard = img > threshold
    if extend > 0 and hard.any():
        hard = hard | (_distance_transform_edt(~hard) < extend)
    elif extend < 0 and hard.any():
        padded = np.pad(hard, 1, mode="constant", constant_values=False)    # the box edge counts as outside
        distance = _distance_transform_edt(padded)[1:-1, 1:-1, 1:-1]
        hard = hard & ~(distance < -extend)
    out = hard.astype(np.float32)
    if soft_edge > 0 and hard.any():
        d = _distance_transform_edt(~hard)
        edge = (~hard) & (d <= soft_edge)
        out[edge] = (0.5 + 0.5 * np.cos(np.pi * d[edge] / soft_edge)).astype(np.float32)
    return out
