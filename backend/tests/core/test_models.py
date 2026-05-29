import pytest
from pydantic import ValidationError
from yyt1771_af.core.models import (
    AcquisitionFrameSize,
    BalloonEnvelopeDetectorParams,
    DetectionDiagnostics,
    DetectionResult,
    FrameRef,
    MeasurementDefinition,
    Point2D,
    RotatedRoi,
    SegmentationParams,
)
from yyt1771_af.core.statuses import (
    CoordinateSpace,
    DetectionStatus,
    DetectorKind,
    TargetFamily,
)


def test_detection_status_matches_contract_without_wire_endpoint_missing() -> None:
    expected = {
        "ok",
        "no_fresh_frame",
        "roi_invalid_geometry",
        "roi_outside_frame",
        "target_not_found",
        "low_contrast",
        "segmentation_failed",
        "multiple_targets",
        "target_touches_roi_boundary",
        "opposing_contour_edges_missing",
        "caliper_contact_ambiguous",
        "caliper_contact_on_roi_boundary",
        "contour_fragmented",
        "internal_texture_selected",
        "points_not_on_contour",
        "pattern_not_found",
        "object_interval_count_mismatch",
        "quality_below_threshold",
        "jump_exceeds_limit",
        "coordinate_mapping_error",
        "stale_frame_geometry_mismatch",
        "unsupported_target_family",
    }

    assert {status.value for status in DetectionStatus} == expected
    assert "wire_endpoint_missing" not in {status.value for status in DetectionStatus}


def test_rotated_roi_rejects_non_positive_dimensions() -> None:
    with pytest.raises(ValidationError):
        RotatedRoi(center_x=10.0, center_y=20.0, width=0.0, height=5.0, angle_deg=0.0)

    with pytest.raises(ValidationError):
        RotatedRoi(center_x=10.0, center_y=20.0, width=5.0, height=-1.0, angle_deg=0.0)


def test_formal_roi_and_frame_ref_require_acquisition_coordinates() -> None:
    with pytest.raises(ValidationError):
        RotatedRoi(
            center_x=10.0,
            center_y=20.0,
            width=5.0,
            height=4.0,
            angle_deg=0.0,
            coordinate_space=CoordinateSpace.DISPLAY,
        )

    with pytest.raises(ValidationError):
        FrameRef(
            frame_id=1,
            timestamp_ms=100,
            width=640,
            height=480,
            coordinate_space=CoordinateSpace.SENSOR_NATIVE,
        )


def test_valid_detection_result_requires_ok_status_points_and_distance() -> None:
    result = DetectionResult(
        status=DetectionStatus.OK,
        valid=True,
        point_a=Point2D(x=1.0, y=2.0),
        point_b=Point2D(x=4.0, y=6.0),
        distance_px=5.0,
        quality=0.95,
        target_family=TargetFamily.BALLOON_ENVELOPE,
        diagnostics=DetectionDiagnostics(detector=DetectorKind.BALLOON_ENVELOPE_DETECTOR),
    )

    assert result.valid is True
    assert result.distance_px == 5.0


def test_valid_detection_result_rejects_missing_points_or_non_ok_status() -> None:
    with pytest.raises(ValidationError):
        DetectionResult(
            status=DetectionStatus.TARGET_NOT_FOUND,
            valid=True,
            point_a=Point2D(x=1.0, y=2.0),
            point_b=Point2D(x=4.0, y=6.0),
            distance_px=5.0,
            quality=0.95,
            target_family=TargetFamily.BALLOON_ENVELOPE,
            diagnostics=DetectionDiagnostics(detector=DetectorKind.BALLOON_ENVELOPE_DETECTOR),
        )

    with pytest.raises(ValidationError):
        DetectionResult(
            status=DetectionStatus.OK,
            valid=True,
            point_a=None,
            point_b=Point2D(x=4.0, y=6.0),
            distance_px=5.0,
            quality=0.95,
            target_family=TargetFamily.BALLOON_ENVELOPE,
            diagnostics=DetectionDiagnostics(detector=DetectorKind.BALLOON_ENVELOPE_DETECTOR),
        )


def test_invalid_detection_result_rejects_distance() -> None:
    with pytest.raises(ValidationError):
        DetectionResult(
            status=DetectionStatus.TARGET_NOT_FOUND,
            valid=False,
            point_a=None,
            point_b=None,
            distance_px=5.0,
            quality=0.2,
            target_family=TargetFamily.WIRE_STRIP,
            diagnostics=DetectionDiagnostics(detector=DetectorKind.WIRE_STRIP_DETECTOR),
        )


def test_invalid_detection_result_rejects_ok_status() -> None:
    with pytest.raises(ValidationError):
        DetectionResult(
            status=DetectionStatus.OK,
            valid=False,
            point_a=None,
            point_b=None,
            distance_px=None,
            quality=0.2,
            target_family=TargetFamily.WIRE_STRIP,
            diagnostics=DetectionDiagnostics(detector=DetectorKind.WIRE_STRIP_DETECTOR),
        )


def test_detection_result_rejects_target_family_detector_mismatch() -> None:
    with pytest.raises(ValidationError):
        DetectionResult(
            status=DetectionStatus.OK,
            valid=True,
            point_a=Point2D(x=1.0, y=2.0),
            point_b=Point2D(x=4.0, y=6.0),
            distance_px=5.0,
            quality=0.95,
            target_family=TargetFamily.BALLOON_ENVELOPE,
            diagnostics=DetectionDiagnostics(detector=DetectorKind.WIRE_STRIP_DETECTOR),
        )


def test_balloon_detector_params_persist_envelope_mode_and_contact_source() -> None:
    solid = BalloonEnvelopeDetectorParams()
    assert solid.envelope_mode == "solid_balloon"
    assert solid.contact_source == "filled_envelope"
    assert solid.fill_internal_holes is True

    open_mesh = BalloonEnvelopeDetectorParams(envelope_mode="open_mesh")
    assert open_mesh.envelope_mode == "open_mesh"
    assert open_mesh.contact_source == "bridged_foreground"
    assert open_mesh.fill_internal_holes is False


def test_measurement_definition_persists_complete_balloon_recipe_snapshot() -> None:
    measurement_definition = MeasurementDefinition(
        measurement_definition_id="md_recipe_snapshot",
        name="open-mesh-setup",
        target_family=TargetFamily.BALLOON_ENVELOPE,
        roi=RotatedRoi(center_x=80.0, center_y=60.0, width=100.0, height=50.0, angle_deg=0.0),
        recipe_name="open_mesh_local",
        segmentation=SegmentationParams(
            polarity="dark_on_light",
            threshold_mode="fixed",
            threshold_value=160,
            close_kernel=7,
            open_kernel=1,
            min_component_area_px=120,
            fill_internal_holes=False,
        ),
        detector=BalloonEnvelopeDetectorParams(envelope_mode="open_mesh"),
        detector_version="v1",
        acquisition_frame_size=AcquisitionFrameSize(width=160, height=120),
        created_at_ms=1000,
    )

    assert measurement_definition.detector.envelope_mode == "open_mesh"
    assert measurement_definition.detector.contact_source == "bridged_foreground"
    assert measurement_definition.segmentation.threshold_mode == "fixed"
    assert measurement_definition.segmentation.threshold_value == 160
