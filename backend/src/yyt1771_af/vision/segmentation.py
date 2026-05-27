from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np

from yyt1771_af.core.models import SegmentationParams


@dataclass(frozen=True, slots=True)
class BinaryComponent:
    mask: np.ndarray
    coordinates_yx: np.ndarray

    @property
    def area_px(self) -> int:
        return int(self.coordinates_yx.shape[0])


def segment_target_mask(
    frame: np.ndarray,
    roi_mask: np.ndarray,
    params: SegmentationParams,
    *,
    preferred_point_xy: tuple[float, float] | None = None,
) -> tuple[np.ndarray, float]:
    image = _as_grayscale_uint8(frame)
    roi_values = image[roi_mask]
    if roi_values.size == 0:
        return np.zeros_like(roi_mask, dtype=bool), 0.0

    contrast = float(np.percentile(roi_values, 95) - np.percentile(roi_values, 5))
    if contrast <= 4.0:
        return np.zeros_like(roi_mask, dtype=bool), 0.0

    threshold = _threshold_value(roi_values, params)
    dark_mask = (image <= threshold) & roi_mask
    light_mask = (image > threshold) & roi_mask
    foreground = _choose_polarity_mask(
        dark_mask,
        light_mask,
        roi_mask,
        params.polarity,
        preferred_point_xy=preferred_point_xy,
    )

    foreground = binary_close(foreground, params.close_kernel)
    foreground = binary_open(foreground, params.open_kernel)
    foreground &= roi_mask
    return foreground, min(1.0, contrast / 80.0)


def connected_components(mask: np.ndarray, min_area_px: int) -> list[BinaryComponent]:
    source = np.asarray(mask, dtype=bool)
    visited = np.zeros(source.shape, dtype=bool)
    components: list[BinaryComponent] = []
    height, width = source.shape

    for start_y, start_x in np.argwhere(source):
        if visited[start_y, start_x]:
            continue

        stack = [(int(start_y), int(start_x))]
        visited[start_y, start_x] = True
        coordinates: list[tuple[int, int]] = []

        while stack:
            y, x = stack.pop()
            coordinates.append((y, x))
            for neighbor_y, neighbor_x in _neighbors8(y, x):
                if (
                    0 <= neighbor_y < height
                    and 0 <= neighbor_x < width
                    and source[neighbor_y, neighbor_x]
                    and not visited[neighbor_y, neighbor_x]
                ):
                    visited[neighbor_y, neighbor_x] = True
                    stack.append((neighbor_y, neighbor_x))

        if len(coordinates) >= min_area_px:
            coordinates_array = np.asarray(coordinates, dtype=np.int32)
            component_mask = np.zeros(source.shape, dtype=bool)
            component_mask[coordinates_array[:, 0], coordinates_array[:, 1]] = True
            components.append(
                BinaryComponent(mask=component_mask, coordinates_yx=coordinates_array)
            )

    components.sort(key=lambda component: component.area_px, reverse=True)
    return components


def binary_close(mask: np.ndarray, kernel_size: int) -> np.ndarray:
    if kernel_size <= 1:
        return np.asarray(mask, dtype=bool).copy()
    return binary_erode(binary_dilate(mask, kernel_size), kernel_size)


def binary_open(mask: np.ndarray, kernel_size: int) -> np.ndarray:
    if kernel_size <= 1:
        return np.asarray(mask, dtype=bool).copy()
    return binary_dilate(binary_erode(mask, kernel_size), kernel_size)


def binary_dilate(mask: np.ndarray, kernel_size: int) -> np.ndarray:
    radius = kernel_size // 2
    source = np.asarray(mask, dtype=bool)
    padded = np.pad(source, radius, mode="constant", constant_values=False)
    result = np.zeros_like(source, dtype=bool)
    for offset_y in range(kernel_size):
        for offset_x in range(kernel_size):
            result |= padded[
                offset_y : offset_y + source.shape[0],
                offset_x : offset_x + source.shape[1],
            ]
    return result


def binary_erode(mask: np.ndarray, kernel_size: int) -> np.ndarray:
    radius = kernel_size // 2
    source = np.asarray(mask, dtype=bool)
    padded = np.pad(source, radius, mode="constant", constant_values=False)
    result = np.ones_like(source, dtype=bool)
    for offset_y in range(kernel_size):
        for offset_x in range(kernel_size):
            result &= padded[
                offset_y : offset_y + source.shape[0],
                offset_x : offset_x + source.shape[1],
            ]
    return result


def fill_internal_holes(mask: np.ndarray) -> np.ndarray:
    source = np.asarray(mask, dtype=bool)
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


def contour_mask(mask: np.ndarray) -> np.ndarray:
    source = np.asarray(mask, dtype=bool)
    return source & ~binary_erode(source, 3)


def _as_grayscale_uint8(frame: np.ndarray) -> np.ndarray:
    image = np.asarray(frame)
    if image.ndim != 2:
        raise ValueError("vision detectors require a 2D grayscale frame")
    if image.dtype == np.uint8:
        return image
    return np.clip(image, 0, 255).astype(np.uint8)


def _threshold_value(values: np.ndarray, params: SegmentationParams) -> int:
    if params.threshold_mode == "fixed":
        if params.threshold_value is None:
            raise ValueError("fixed threshold mode requires threshold_value")
        return int(params.threshold_value)
    return _otsu_threshold(values)


def _otsu_threshold(values: np.ndarray) -> int:
    hist = np.bincount(values.astype(np.uint8), minlength=256).astype(np.float64)
    total = hist.sum()
    if total <= 0:
        return 0

    levels = np.arange(256, dtype=np.float64)
    sum_total = float(np.dot(levels, hist))
    weight_background = 0.0
    sum_background = 0.0
    best_variance = -1.0
    best_threshold = 0

    for threshold in range(256):
        weight_background += hist[threshold]
        if weight_background == 0:
            continue
        weight_foreground = total - weight_background
        if weight_foreground == 0:
            break
        sum_background += threshold * hist[threshold]
        mean_background = sum_background / weight_background
        mean_foreground = (sum_total - sum_background) / weight_foreground
        variance = weight_background * weight_foreground * (mean_background - mean_foreground) ** 2
        if variance > best_variance:
            best_variance = variance
            best_threshold = threshold

    return best_threshold


def _choose_polarity_mask(
    dark_mask: np.ndarray,
    light_mask: np.ndarray,
    roi_mask: np.ndarray,
    polarity: str,
    *,
    preferred_point_xy: tuple[float, float] | None,
) -> np.ndarray:
    if polarity == "dark_on_light":
        return dark_mask.copy()
    if polarity == "light_on_dark":
        return light_mask.copy()

    roi_area = max(1, int(np.count_nonzero(roi_mask)))
    candidates = [dark_mask, light_mask]
    preferred_candidate = _candidate_containing_point(candidates, preferred_point_xy)
    if preferred_candidate is not None:
        return preferred_candidate.copy()

    plausible = [
        candidate
        for candidate in candidates
        if 0.01 <= (np.count_nonzero(candidate) / roi_area) <= 0.80
    ]
    if not plausible:
        return min(candidates, key=np.count_nonzero).copy()
    return min(plausible, key=np.count_nonzero).copy()


def _candidate_containing_point(
    candidates: list[np.ndarray],
    preferred_point_xy: tuple[float, float] | None,
) -> np.ndarray | None:
    if preferred_point_xy is None:
        return None

    x, y = preferred_point_xy
    point_x = int(round(x))
    point_y = int(round(y))
    radius = 3
    scores: list[int] = []
    for candidate in candidates:
        y_min = max(0, point_y - radius)
        y_max = min(candidate.shape[0], point_y + radius + 1)
        x_min = max(0, point_x - radius)
        x_max = min(candidate.shape[1], point_x + radius + 1)
        scores.append(int(np.count_nonzero(candidate[y_min:y_max, x_min:x_max])))
    best_index = int(np.argmax(scores))
    if scores[best_index] > 0 and scores.count(scores[best_index]) == 1:
        return candidates[best_index]
    return None


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
