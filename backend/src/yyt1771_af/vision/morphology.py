"""Binary morphology backend with an optional SciPy acceleration path.

The vision detectors need connected-component labelling, internal-hole filling,
and small binary dilation/erosion. These operations dominate per-frame cost for
solid balloon envelopes, where the foreground is a large filled region.

This module prefers ``scipy.ndimage`` when it is installed (vectorised C
routines, ~10-100x faster on large masks) and transparently falls back to the
pure-NumPy/Python implementations otherwise. The pure-NumPy implementations are
kept as both the offline fallback and the regression baseline: tests assert the
two backends produce identical masks/labels so the detector semantics and the
formal A/B contract never depend on which backend is active.

No OpenCV. No FastAPI/hardware/filesystem dependencies.
"""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np

try:  # Optional acceleration backend.
    from scipy import ndimage as _ndimage
except Exception:  # pragma: no cover - exercised only when scipy is absent
    _ndimage = None

_EIGHT_CONNECTED = np.ones((3, 3), dtype=bool)


def scipy_available() -> bool:
    """Return True when the SciPy acceleration backend is importable."""
    return _ndimage is not None


def label(mask: np.ndarray, *, force_numpy: bool = False) -> tuple[np.ndarray, int]:
    """8-connectivity component labelling.

    Returns ``(labels, count)`` where ``labels`` is an int array with ``0`` for
    background and ``1..count`` for components in row-major discovery order.
    """
    source = np.asarray(mask, dtype=bool)
    if not force_numpy and _ndimage is not None:
        labels, count = _ndimage.label(source, structure=_EIGHT_CONNECTED)
        return np.asarray(labels, dtype=np.int32), int(count)
    return _label_numpy(source)


def fill_holes(mask: np.ndarray, *, force_numpy: bool = False) -> np.ndarray:
    """Fill background regions that are fully enclosed by the foreground."""
    source = np.asarray(mask, dtype=bool)
    if not force_numpy and _ndimage is not None:
        return np.asarray(_ndimage.binary_fill_holes(source), dtype=bool)
    return _fill_holes_numpy(source)


def binary_dilate(mask: np.ndarray, kernel_size: int, *, force_numpy: bool = False) -> np.ndarray:
    source = np.asarray(mask, dtype=bool)
    if kernel_size <= 1:
        return source.copy()
    # SciPy centres an odd square structuring element exactly like the NumPy
    # fallback (radius = kernel // 2 on every side, background border = False).
    # Even kernels are asymmetric in the NumPy path, so keep them on NumPy to
    # guarantee identical output.
    if not force_numpy and _ndimage is not None and kernel_size % 2 == 1:
        structure = np.ones((kernel_size, kernel_size), dtype=bool)
        return np.asarray(_ndimage.binary_dilation(source, structure=structure), dtype=bool)
    return _binary_dilate_numpy(source, kernel_size)


def binary_erode(mask: np.ndarray, kernel_size: int, *, force_numpy: bool = False) -> np.ndarray:
    source = np.asarray(mask, dtype=bool)
    if kernel_size <= 1:
        return source.copy()
    if not force_numpy and _ndimage is not None and kernel_size % 2 == 1:
        structure = np.ones((kernel_size, kernel_size), dtype=bool)
        return np.asarray(
            _ndimage.binary_erosion(source, structure=structure, border_value=0),
            dtype=bool,
        )
    return _binary_erode_numpy(source, kernel_size)


def _label_numpy(source: np.ndarray) -> tuple[np.ndarray, int]:
    height, width = source.shape
    labels = np.zeros((height, width), dtype=np.int32)
    current = 0
    for start_y, start_x in np.argwhere(source):
        if labels[start_y, start_x]:
            continue
        current += 1
        stack = [(int(start_y), int(start_x))]
        labels[start_y, start_x] = current
        while stack:
            y, x = stack.pop()
            for neighbor_y, neighbor_x in _neighbors8(y, x):
                if (
                    0 <= neighbor_y < height
                    and 0 <= neighbor_x < width
                    and source[neighbor_y, neighbor_x]
                    and not labels[neighbor_y, neighbor_x]
                ):
                    labels[neighbor_y, neighbor_x] = current
                    stack.append((neighbor_y, neighbor_x))
    return labels, current


def _fill_holes_numpy(source: np.ndarray) -> np.ndarray:
    inverse = ~source
    reachable_background = np.zeros(source.shape, dtype=bool)
    height, width = source.shape
    stack: list[tuple[int, int]] = []

    for x in range(width):
        stack.extend([(0, x), (height - 1, x)])
    for y in range(height):
        stack.extend([(y, 0), (y, width - 1)])

    while stack:
        y, x = stack.pop()
        if not (0 <= y < height and 0 <= x < width):
            continue
        if reachable_background[y, x] or not inverse[y, x]:
            continue
        reachable_background[y, x] = True
        stack.extend(_neighbors4(y, x))

    holes = inverse & ~reachable_background
    return source | holes


def _binary_dilate_numpy(source: np.ndarray, kernel_size: int) -> np.ndarray:
    radius = kernel_size // 2
    padded = np.pad(source, radius, mode="constant", constant_values=False)
    result = np.zeros_like(source, dtype=bool)
    for offset_y in range(kernel_size):
        for offset_x in range(kernel_size):
            result |= padded[
                offset_y : offset_y + source.shape[0],
                offset_x : offset_x + source.shape[1],
            ]
    return result


def _binary_erode_numpy(source: np.ndarray, kernel_size: int) -> np.ndarray:
    radius = kernel_size // 2
    padded = np.pad(source, radius, mode="constant", constant_values=False)
    result = np.ones_like(source, dtype=bool)
    for offset_y in range(kernel_size):
        for offset_x in range(kernel_size):
            result &= padded[
                offset_y : offset_y + source.shape[0],
                offset_x : offset_x + source.shape[1],
            ]
    return result


def _neighbors8(y: int, x: int) -> Iterable[tuple[int, int]]:
    for offset_y in (-1, 0, 1):
        for offset_x in (-1, 0, 1):
            if offset_y != 0 or offset_x != 0:
                yield y + offset_y, x + offset_x


def _neighbors4(y: int, x: int) -> Iterable[tuple[int, int]]:
    yield y - 1, x
    yield y + 1, x
    yield y, x - 1
    yield y, x + 1
