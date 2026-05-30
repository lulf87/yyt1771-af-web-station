"""Equivalence tests for the SciPy/NumPy morphology backend.

The detector contract must not depend on whether the SciPy acceleration path or
the pure-NumPy fallback is active, so every backend operation must produce
identical results on the same input.
"""

from __future__ import annotations

import numpy as np
import pytest
from yyt1771_af.vision import morphology, segmentation


def _fixtures() -> list[np.ndarray]:
    rng = np.random.default_rng(20260530)
    masks: list[np.ndarray] = []
    for _ in range(12):
        masks.append(rng.random((37, 53)) > 0.55)
    # A solid filled region with internal holes (balloon-like).
    solid = np.zeros((40, 60), dtype=bool)
    solid[6:34, 8:52] = True
    solid[14:20, 20:26] = False
    solid[24:28, 36:44] = False
    masks.append(solid)
    # Several disconnected components of equal area (tie-break sensitivity).
    tied = np.zeros((20, 40), dtype=bool)
    tied[2:5, 2:5] = True
    tied[2:5, 30:33] = True
    tied[15:18, 18:21] = True
    masks.append(tied)
    return masks


def test_label_matches_numpy_fallback() -> None:
    assert morphology.scipy_available() is True
    for mask in _fixtures():
        scipy_labels, scipy_count = morphology.label(mask)
        numpy_labels, numpy_count = morphology.label(mask, force_numpy=True)
        assert scipy_count == numpy_count
        # Label ids may differ; the induced partition must be identical.
        assert _partition(scipy_labels) == _partition(numpy_labels)


def test_connected_components_match_between_backends() -> None:
    for mask in _fixtures():
        scipy_components = segmentation.connected_components(mask, 1)
        numpy_components = segmentation.connected_components(mask, 1, force_numpy=True)
        assert len(scipy_components) == len(numpy_components)
        for scipy_component, numpy_component in zip(
            scipy_components, numpy_components, strict=True
        ):
            assert scipy_component.area_px == numpy_component.area_px
            assert np.array_equal(scipy_component.mask, numpy_component.mask)


def test_fill_holes_matches_numpy_fallback() -> None:
    for mask in _fixtures():
        assert np.array_equal(
            morphology.fill_holes(mask),
            morphology.fill_holes(mask, force_numpy=True),
        )


@pytest.mark.parametrize("kernel_size", [1, 2, 3, 4, 5, 7])
def test_dilate_and_erode_match_numpy_fallback(kernel_size: int) -> None:
    for mask in _fixtures():
        assert np.array_equal(
            morphology.binary_dilate(mask, kernel_size),
            morphology.binary_dilate(mask, kernel_size, force_numpy=True),
        )
        assert np.array_equal(
            morphology.binary_erode(mask, kernel_size),
            morphology.binary_erode(mask, kernel_size, force_numpy=True),
        )


def test_numpy_fallback_used_when_scipy_missing(monkeypatch) -> None:
    monkeypatch.setattr(morphology, "_ndimage", None)
    assert morphology.scipy_available() is False
    mask = _fixtures()[-1]
    labels, count = morphology.label(mask)
    numpy_labels, numpy_count = morphology.label(mask, force_numpy=True)
    assert count == numpy_count
    assert _partition(labels) == _partition(numpy_labels)


def _partition(labels: np.ndarray) -> set[frozenset[int]]:
    groups: dict[int, set[int]] = {}
    height, width = labels.shape
    flat = labels.ravel()
    for index, value in enumerate(flat.tolist()):
        if value == 0:
            continue
        groups.setdefault(value, set()).add(index)
    return {frozenset(members) for members in groups.values()}
