import numpy as np
from yyt1771_af.core.models import BalloonEnvelopeDetectorParams, RotatedRoi, SegmentationParams
from yyt1771_af.core.statuses import CoordinateSpace, DetectionStatus, DetectorKind, TargetFamily
from yyt1771_af.vision.balloon_envelope_detector import BalloonEnvelopeDetector


def _ellipse_frame(
    *,
    width: int = 240,
    height: int = 180,
    center: tuple[float, float] = (120.0, 90.0),
    radii: tuple[float, float] = (60.0, 30.0),
    background: int = 230,
    target: int = 30,
) -> np.ndarray:
    y, x = np.indices((height, width))
    cx, cy = center
    rx, ry = radii
    mask = ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0
    image = np.full((height, width), background, dtype=np.uint8)
    image[mask] = target
    return image


def _add_internal_mesh(image: np.ndarray, center: tuple[float, float]) -> np.ndarray:
    y, x = np.indices(image.shape)
    cx, cy = center
    ellipse_mask = ((x - cx) / 60.0) ** 2 + ((y - cy) / 30.0) ** 2 <= 0.82
    grid = ((x.astype(int) % 12) == 0) | ((y.astype(int) % 12) == 0)
    meshed = image.copy()
    meshed[ellipse_mask & grid] = 230
    return meshed


def _default_roi(width: float = 150.0, height: float = 90.0) -> RotatedRoi:
    return RotatedRoi(
        center_x=120.0,
        center_y=90.0,
        width=width,
        height=height,
        angle_deg=0.0,
    )


def _assert_point_on_external_ellipse(point_x: float, point_y: float) -> None:
    value = ((point_x - 120.0) / 60.0) ** 2 + ((point_y - 90.0) / 30.0) ** 2
    assert 0.90 <= value <= 1.10


def test_solid_balloon_envelope_returns_outer_contour_contacts() -> None:
    detector = BalloonEnvelopeDetector()

    result = detector.detect(
        frame=_ellipse_frame(),
        roi=_default_roi(),
        segmentation=SegmentationParams(close_kernel=7, open_kernel=1),
        params=BalloonEnvelopeDetectorParams(),
    )

    assert result.status is DetectionStatus.OK
    assert result.valid is True
    assert result.target_family is TargetFamily.BALLOON_ENVELOPE
    assert result.diagnostics.detector is DetectorKind.BALLOON_ENVELOPE_DETECTOR
    assert result.point_a is not None
    assert result.point_b is not None
    assert result.point_a.coordinate_space is CoordinateSpace.ACQUISITION
    assert result.point_b.coordinate_space is CoordinateSpace.ACQUISITION
    assert result.point_a.x < 70.0
    assert result.point_b.x > 170.0
    assert result.distance_px is not None
    assert 115.0 <= result.distance_px <= 125.0
    _assert_point_on_external_ellipse(result.point_a.x, result.point_a.y)
    _assert_point_on_external_ellipse(result.point_b.x, result.point_b.y)


def test_balloon_envelope_ignores_internal_mesh_when_selecting_contacts() -> None:
    detector = BalloonEnvelopeDetector()
    frame = _add_internal_mesh(_ellipse_frame(), center=(120.0, 90.0))

    result = detector.detect(
        frame=frame,
        roi=_default_roi(),
        segmentation=SegmentationParams(close_kernel=13, open_kernel=1),
        params=BalloonEnvelopeDetectorParams(),
    )

    assert result.status is DetectionStatus.OK
    assert result.valid is True
    assert result.point_a is not None
    assert result.point_b is not None
    assert result.distance_px is not None
    assert result.distance_px > 110.0
    _assert_point_on_external_ellipse(result.point_a.x, result.point_a.y)
    _assert_point_on_external_ellipse(result.point_b.x, result.point_b.y)


def test_balloon_envelope_fails_when_contact_is_created_by_roi_boundary() -> None:
    detector = BalloonEnvelopeDetector()

    result = detector.detect(
        frame=_ellipse_frame(),
        roi=_default_roi(width=100.0, height=80.0),
        segmentation=SegmentationParams(close_kernel=7, open_kernel=1),
        params=BalloonEnvelopeDetectorParams(boundary_margin_px=4.0),
    )

    assert result.valid is False
    assert result.status is DetectionStatus.CALIPER_CONTACT_ON_ROI_BOUNDARY
    assert result.point_a is None
    assert result.point_b is None
    assert result.distance_px is None
