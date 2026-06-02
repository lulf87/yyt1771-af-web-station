from __future__ import annotations

import numpy as np
from yyt1771_af.core.models import (
    CandidateLineDiagnostics,
    DetectionDiagnostics,
    DetectionResult,
    ObjectInterval,
    Point2D,
    RotatedRoi,
)
from yyt1771_af.core.statuses import DetectionStatus, DetectorKind, TargetFamily
from yyt1771_af.report import debug_overlay
from yyt1771_af.report.debug_overlay import render_debug_overlay_png


def test_debug_overlay_renders_png_without_recomputing_points() -> None:
    frame = np.full((40, 60), 220, dtype=np.uint8)
    frame[18:23, 10:50] = 30
    roi = RotatedRoi(center_x=30.0, center_y=20.0, width=44.0, height=16.0, angle_deg=0.0)
    point_a = Point2D(x=10.0, y=20.0)
    point_b = Point2D(x=50.0, y=20.0)

    payload = render_debug_overlay_png(
        frame=frame,
        roi=roi,
        point_a=point_a,
        point_b=point_b,
        frame_index=7,
        status="ok",
        distance_px=40.0,
        quality=0.91,
        reason=None,
    )

    assert payload.startswith(b"\x89PNG\r\n\x1a\n")
    assert b"IEND" in payload[-32:]


def test_detection_debug_overlay_labels_formal_ab_without_rejected_text(monkeypatch) -> None:
    captured_text: list[str] = []

    def capture_text(*args, **kwargs) -> None:
        captured_text.append(str(args[4]))

    monkeypatch.setattr(debug_overlay, "draw_text", capture_text)
    frame = np.full((40, 60), 220, dtype=np.uint8)
    roi = RotatedRoi(center_x=30.0, center_y=20.0, width=44.0, height=16.0, angle_deg=0.0)
    detection = DetectionResult(
        status=DetectionStatus.OK,
        valid=True,
        point_a=Point2D(x=10.0, y=20.0),
        point_b=Point2D(x=50.0, y=20.0),
        distance_px=40.0,
        quality=0.91,
        target_family=TargetFamily.BALLOON_ENVELOPE,
        diagnostics=DetectionDiagnostics(
            detector=DetectorKind.BALLOON_ENVELOPE_DETECTOR,
            pattern_model="blank_object_blank",
            detected_pattern="blank_object_blank",
            measurement_line_y=0.0,
            chord_length_px=40.0,
            parallel_error_px=0.0,
        ),
    )

    payload = debug_overlay.render_detection_debug_overlay_png(
        frame=frame,
        roi=roi,
        detection=detection,
        raw_foreground_mask=None,
        morphology_foreground_mask=None,
        filled_envelope_mask=None,
        selected_component_mask=None,
        selected_contour_mask=None,
    )

    assert payload.startswith(b"\x89PNG\r\n\x1a\n")
    assert any("FORMAL A/B" in text for text in captured_text)
    assert not any("REJECTED DEBUG" in text for text in captured_text)


def test_detection_debug_overlay_labels_reference_line_and_debug_envelope(monkeypatch) -> None:
    captured_text: list[str] = []

    def capture_text(*args, **kwargs) -> None:
        captured_text.append(str(args[4]))

    monkeypatch.setattr(debug_overlay, "draw_text", capture_text)
    frame = np.full((50, 90), 220, dtype=np.uint8)
    roi = RotatedRoi(center_x=45.0, center_y=25.0, width=70.0, height=24.0, angle_deg=0.0)
    detection = DetectionResult(
        status=DetectionStatus.OK,
        valid=True,
        point_a=Point2D(x=20.0, y=25.0),
        point_b=Point2D(x=70.0, y=25.0),
        distance_px=50.0,
        quality=0.91,
        target_family=TargetFamily.BALLOON_ENVELOPE,
        diagnostics=DetectionDiagnostics(
            detector=DetectorKind.BALLOON_ENVELOPE_DETECTOR,
            envelope_mode="open_mesh",
            contact_source_used="bridged_foreground",
            pattern_model="blank_object_blank",
            detected_pattern="mesh_outer_span",
            measurement_line_y=0.0,
            chord_length_px=50.0,
            parallel_error_px=0.0,
            raw_intervals=[
                ObjectInterval(start_local_x=-25.0, end_local_x=-15.0, width_px=10.0),
                ObjectInterval(start_local_x=15.0, end_local_x=25.0, width_px=10.0),
            ],
            bridged_intervals=[
                ObjectInterval(start_local_x=-25.0, end_local_x=-15.0, width_px=10.0),
                ObjectInterval(start_local_x=15.0, end_local_x=25.0, width_px=10.0),
            ],
            selected_valid_intervals=[
                ObjectInterval(start_local_x=-25.0, end_local_x=-15.0, width_px=10.0),
                ObjectInterval(start_local_x=15.0, end_local_x=25.0, width_px=10.0),
            ],
            virtual_envelope_span_px=68.0,
            candidate_line_is_debug_only=False,
        ),
    )

    payload = debug_overlay.render_detection_debug_overlay_png(
        frame=frame,
        roi=roi,
        detection=detection,
        raw_foreground_mask=None,
        morphology_foreground_mask=None,
        filled_envelope_mask=np.ones_like(frame, dtype=bool),
        selected_component_mask=None,
        selected_contour_mask=None,
    )

    assert payload.startswith(b"\x89PNG\r\n\x1a\n")
    assert any("MEASUREMENT LINE REF" in text for text in captured_text)
    assert any("FORMAL A/B SEGMENT" in text for text in captured_text)
    assert any("VIRTUAL ENVELOPE DEBUG-ONLY" in text for text in captured_text)
    assert not any("REJECTED DEBUG" in text for text in captured_text)


def test_detection_debug_overlay_labels_top_candidate_lines(monkeypatch) -> None:
    captured_text: list[str] = []

    def capture_text(*args, **kwargs) -> None:
        captured_text.append(str(args[4]))

    monkeypatch.setattr(debug_overlay, "draw_text", capture_text)
    frame = np.full((50, 90), 220, dtype=np.uint8)
    roi = RotatedRoi(center_x=45.0, center_y=25.0, width=70.0, height=24.0, angle_deg=0.0)
    detection = DetectionResult(
        status=DetectionStatus.OK,
        valid=True,
        point_a=Point2D(x=20.0, y=25.0),
        point_b=Point2D(x=70.0, y=25.0),
        distance_px=50.0,
        quality=0.91,
        target_family=TargetFamily.WIRE_STRIP,
        diagnostics=DetectionDiagnostics(
            detector=DetectorKind.WIRE_STRIP_DETECTOR,
            pattern_model="blank_wire_bundle_envelope_blank",
            detected_pattern="wire_bundle_envelope",
            measurement_line_y=0.0,
            chord_length_px=50.0,
            parallel_error_px=0.0,
            top_candidate_lines=[
                CandidateLineDiagnostics(
                    rank=1,
                    selected=True,
                    measurement_line_y=0.0,
                    formal_ab_span_px=50.0,
                    interval_count=3,
                    support_ratio=0.42,
                    max_internal_gap_px=22.0,
                    neighbor_line_support=2,
                    wire_likeness_score=0.81,
                    selected_cluster_id=0,
                ),
                CandidateLineDiagnostics(
                    rank=2,
                    selected=False,
                    measurement_line_y=6.0,
                    formal_ab_span_px=49.0,
                    interval_count=3,
                    support_ratio=0.38,
                    max_internal_gap_px=24.0,
                    neighbor_line_support=2,
                    wire_likeness_score=0.81,
                    selected_cluster_id=0,
                ),
            ],
        ),
    )

    payload = debug_overlay.render_detection_debug_overlay_png(
        frame=frame,
        roi=roi,
        detection=detection,
        raw_foreground_mask=None,
        morphology_foreground_mask=None,
        filled_envelope_mask=None,
        selected_component_mask=None,
        selected_contour_mask=None,
    )

    assert payload.startswith(b"\x89PNG\r\n\x1a\n")
    assert any("SELECTED CANDIDATE" in text for text in captured_text)
    assert any("CANDIDATE 2" in text for text in captured_text)
