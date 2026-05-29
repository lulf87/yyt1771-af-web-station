from __future__ import annotations

import math

import numpy as np

from yyt1771_af.core.geometry import roi_measurement_direction, rotated_roi_corners
from yyt1771_af.core.models import DetectionResult, Point2D, RotatedRoi
from yyt1771_af.report.simple_png import (
    draw_circle,
    draw_line,
    draw_polyline,
    draw_rect,
    draw_text,
    encode_png,
    grayscale_to_rgb,
)
from yyt1771_af.services.frame_preview_service import preview_size


def render_debug_overlay_png(
    *,
    frame: np.ndarray,
    roi: RotatedRoi,
    point_a: Point2D | None,
    point_b: Point2D | None,
    frame_index: int,
    status: str,
    distance_px: float | None,
    quality: float,
    reason: str | None,
) -> bytes:
    source = np.asarray(frame)
    height, width = source.shape[:2]
    pixels = grayscale_to_rgb(source)
    roi_points = [(int(round(point.x)), int(round(point.y))) for point in rotated_roi_corners(roi)]
    draw_polyline(pixels, width, [*roi_points, roi_points[0]], (24, 144, 255), thickness=2)

    if point_a is not None:
        draw_circle(pixels, width, int(round(point_a.x)), int(round(point_a.y)), 5, (255, 80, 80))
    if point_b is not None:
        draw_circle(pixels, width, int(round(point_b.x)), int(round(point_b.y)), 5, (80, 220, 120))
    if point_a is not None and point_b is not None:
        draw_line(
            pixels,
            width,
            int(round(point_a.x)),
            int(round(point_a.y)),
            int(round(point_b.x)),
            int(round(point_b.y)),
            (255, 214, 80),
            thickness=2,
        )
        draw_text(
            pixels,
            width,
            int(round(point_a.x)) + 8,
            int(round(point_a.y)) - 10,
            "FORMAL A/B",
            (255, 214, 80),
            scale=1,
        )

    label_height = 52
    draw_rect(pixels, width, 0, 0, min(width - 1, 760), label_height, (0, 0, 0))
    distance_text = (
        "-" if distance_px is None or not math.isfinite(distance_px) else f"{distance_px:.2f}"
    )
    reason_text = (reason or "")[:42]
    draw_text(
        pixels,
        width,
        8,
        8,
        f"FRAME:{frame_index} STATUS:{status} DIST:{distance_text} Q:{quality:.2f}",
        (255, 255, 255),
        scale=2,
    )
    if reason_text:
        draw_text(pixels, width, 8, 32, f"REASON:{reason_text}", (255, 220, 120), scale=2)

    return encode_png(width, height, pixels)


def render_detection_debug_overlay_png(
    *,
    frame: np.ndarray,
    roi: RotatedRoi,
    detection: DetectionResult,
    raw_foreground_mask: np.ndarray | None,
    morphology_foreground_mask: np.ndarray | None,
    filled_envelope_mask: np.ndarray | None,
    selected_component_mask: np.ndarray | None,
    selected_contour_mask: np.ndarray | None,
    max_width: int = 1200,
    max_height: int | None = None,
    show_raw_foreground: bool = True,
    show_morphology_foreground: bool = True,
    show_filled_envelope: bool = True,
    show_selected_contour: bool = True,
    show_rejected_candidates: bool = True,
) -> bytes:
    source = np.asarray(frame)
    if source.ndim != 2:
        raise ValueError("debug overlay requires a 2D grayscale frame")
    acquisition_height, acquisition_width = source.shape
    display_width, display_height = preview_size(
        acquisition_width=acquisition_width,
        acquisition_height=acquisition_height,
        max_width=max_width,
        max_height=max_height,
    )
    y_indices = np.linspace(0, acquisition_height - 1, display_height).astype(np.int64)
    x_indices = np.linspace(0, acquisition_width - 1, display_width).astype(np.int64)
    preview = np.clip(source[np.ix_(y_indices, x_indices)], 0, 255).astype(np.uint8)
    rgb = np.repeat(preview[:, :, None], 3, axis=2)

    if show_raw_foreground:
        _blend_mask(
            rgb,
            _downsample_mask(raw_foreground_mask, y_indices, x_indices),
            (60, 180, 255),
            0.26,
        )
    _blend_mask(
        rgb,
        _downsample_mask(morphology_foreground_mask, y_indices, x_indices)
        if show_morphology_foreground
        else None,
        (255, 230, 80),
        0.28,
    )
    _blend_mask(
        rgb,
        _downsample_mask(filled_envelope_mask, y_indices, x_indices)
        if show_filled_envelope
        else None,
        (255, 174, 66),
        0.34,
    )
    if selected_component_mask is not None:
        _blend_mask(
            rgb,
            _downsample_mask(selected_component_mask, y_indices, x_indices),
            (255, 110, 60),
            0.18,
        )
    if show_selected_contour:
        _blend_mask(
            rgb,
            _downsample_mask(selected_contour_mask, y_indices, x_indices),
            (255, 64, 64),
            0.85,
        )

    pixels = bytearray(rgb.astype(np.uint8).tobytes())
    scale_x = display_width / acquisition_width
    scale_y = display_height / acquisition_height
    scaled_roi = RotatedRoi(
        center_x=roi.center_x * scale_x,
        center_y=roi.center_y * scale_y,
        width=roi.width * scale_x,
        height=roi.height * scale_y,
        angle_deg=roi.angle_deg,
    )
    roi_points = [
        (int(round(point.x)), int(round(point.y))) for point in rotated_roi_corners(scaled_roi)
    ]
    draw_polyline(
        pixels,
        display_width,
        [*roi_points, roi_points[0]],
        (24, 144, 255),
        thickness=2,
    )
    _draw_boundary_margin_lines(
        pixels,
        display_width,
        scaled_roi,
        float(detection.diagnostics.boundary_margin_px or 0.0) * scale_x,
    )
    _draw_measurement_line(
        pixels,
        display_width,
        scaled_roi,
        None
        if detection.diagnostics.measurement_line_y is None
        else float(detection.diagnostics.measurement_line_y) * scale_y,
    )

    if show_rejected_candidates and not detection.valid:
        _draw_point(
            pixels,
            display_width,
            detection.diagnostics.rejected_candidate_point_a,
            scale_x,
            scale_y,
            (190, 120, 255),
        )
        _draw_point(
            pixels,
            display_width,
            detection.diagnostics.rejected_candidate_point_b,
            scale_x,
            scale_y,
            (80, 255, 180),
        )
    _draw_point(pixels, display_width, detection.point_a, scale_x, scale_y, (255, 80, 80))
    _draw_point(pixels, display_width, detection.point_b, scale_x, scale_y, (80, 220, 120))
    if detection.point_a is not None and detection.point_b is not None:
        draw_line(
            pixels,
            display_width,
            int(round(detection.point_a.x * scale_x)),
            int(round(detection.point_a.y * scale_y)),
            int(round(detection.point_b.x * scale_x)),
            int(round(detection.point_b.y * scale_y)),
            (255, 214, 80),
            thickness=2,
        )

    draw_rect(pixels, display_width, 0, 0, min(display_width - 1, 900), 70, (0, 0, 0))
    status_text = detection.status.value
    polarity_text = detection.diagnostics.selected_polarity or "-"
    pattern_text = detection.diagnostics.detected_pattern or "-"
    source_text = detection.diagnostics.contact_source_used or "-"
    model_text = detection.diagnostics.pattern_model or "-"
    chord = detection.diagnostics.chord_length_px
    chord_text = "-" if chord is None else f"{chord:.2f}"
    parallel_error = detection.diagnostics.parallel_error_px
    parallel_text = "-" if parallel_error is None else f"{parallel_error:.2f}"
    side_text = detection.diagnostics.rejected_contact_side or "-"
    right_distance = detection.diagnostics.distance_to_right_roi_boundary_px
    right_text = "-" if right_distance is None else f"{right_distance:.2f}"
    draw_text(
        pixels,
        display_width,
        8,
        8,
        f"STATUS:{status_text} POL:{polarity_text} SRC:{source_text}",
        (255, 255, 255),
        scale=2,
    )
    detail_text = (
        f"FORMAL A/B MODEL:{model_text} PATTERN:{pattern_text} "
        f"CHORD:{chord_text} PAR_ERR:{parallel_text}"
        if detection.valid
        else f"SIDE:{side_text} RIGHT_MARGIN:{right_text} REJECTED DEBUG CANDIDATES"
    )
    draw_text(
        pixels,
        display_width,
        8,
        34,
        detail_text,
        (255, 220, 120),
        scale=2,
    )
    return encode_png(display_width, display_height, pixels)


def _downsample_mask(
    mask: np.ndarray | None,
    y_indices: np.ndarray,
    x_indices: np.ndarray,
) -> np.ndarray | None:
    if mask is None:
        return None
    return np.asarray(mask, dtype=bool)[np.ix_(y_indices, x_indices)]


def _blend_mask(
    rgb: np.ndarray,
    mask: np.ndarray | None,
    color: tuple[int, int, int],
    alpha: float,
) -> None:
    if mask is None or not np.any(mask):
        return
    color_array = np.asarray(color, dtype=np.float32)
    rgb[mask] = np.round(rgb[mask].astype(np.float32) * (1.0 - alpha) + color_array * alpha)


def _draw_point(
    pixels: bytearray,
    width: int,
    point: Point2D | None,
    scale_x: float,
    scale_y: float,
    color: tuple[int, int, int],
) -> None:
    if point is None:
        return
    draw_circle(
        pixels,
        width,
        int(round(point.x * scale_x)),
        int(round(point.y * scale_y)),
        5,
        color,
    )


def _draw_boundary_margin_lines(
    pixels: bytearray,
    width: int,
    roi: RotatedRoi,
    margin_px: float,
) -> None:
    if margin_px <= 0:
        return
    unit_x, unit_y = roi_measurement_direction(roi.angle_deg)
    perp_x, perp_y = -unit_y, unit_x
    for local_x in (-roi.width / 2.0 + margin_px, roi.width / 2.0 - margin_px):
        x0 = roi.center_x + local_x * unit_x - roi.height / 2.0 * perp_x
        y0 = roi.center_y + local_x * unit_y - roi.height / 2.0 * perp_y
        x1 = roi.center_x + local_x * unit_x + roi.height / 2.0 * perp_x
        y1 = roi.center_y + local_x * unit_y + roi.height / 2.0 * perp_y
        draw_line(
            pixels,
            width,
            int(round(x0)),
            int(round(y0)),
            int(round(x1)),
            int(round(y1)),
            (255, 230, 80),
            thickness=1,
        )
    for local_y in (-roi.height / 2.0 + margin_px, roi.height / 2.0 - margin_px):
        x0 = roi.center_x - roi.width / 2.0 * unit_x + local_y * perp_x
        y0 = roi.center_y - roi.width / 2.0 * unit_y + local_y * perp_y
        x1 = roi.center_x + roi.width / 2.0 * unit_x + local_y * perp_x
        y1 = roi.center_y + roi.width / 2.0 * unit_y + local_y * perp_y
        draw_line(
            pixels,
            width,
            int(round(x0)),
            int(round(y0)),
            int(round(x1)),
            int(round(y1)),
            (255, 230, 80),
            thickness=1,
        )


def _draw_measurement_line(
    pixels: bytearray,
    width: int,
    roi: RotatedRoi,
    measurement_line_y: float | None,
) -> None:
    if measurement_line_y is None:
        return
    unit_x, unit_y = roi_measurement_direction(roi.angle_deg)
    perp_x, perp_y = -unit_y, unit_x
    x0 = roi.center_x - roi.width / 2.0 * unit_x + measurement_line_y * perp_x
    y0 = roi.center_y - roi.width / 2.0 * unit_y + measurement_line_y * perp_y
    x1 = roi.center_x + roi.width / 2.0 * unit_x + measurement_line_y * perp_x
    y1 = roi.center_y + roi.width / 2.0 * unit_y + measurement_line_y * perp_y
    draw_line(
        pixels,
        width,
        int(round(x0)),
        int(round(y0)),
        int(round(x1)),
        int(round(y1)),
        (120, 255, 255),
        thickness=1,
    )
