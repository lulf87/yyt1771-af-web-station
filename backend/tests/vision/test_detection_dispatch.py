import numpy as np
from yyt1771_af.core.models import (
    BalloonEnvelopeDetectorParams,
    RotatedRoi,
    SegmentationParams,
    WireStripDetectorParams,
)
from yyt1771_af.core.statuses import DetectorKind, TargetFamily
from yyt1771_af.vision.detection import detect_target


def test_detection_dispatch_uses_balloon_detector_for_balloon_family() -> None:
    frame = np.full((80, 100), 230, dtype=np.uint8)
    frame[30:50, 30:70] = 30

    result = detect_target(
        frame=frame,
        roi=RotatedRoi(center_x=50.0, center_y=40.0, width=60.0, height=40.0, angle_deg=0.0),
        target_family=TargetFamily.BALLOON_ENVELOPE,
        segmentation=SegmentationParams(open_kernel=1),
        params=BalloonEnvelopeDetectorParams(),
    )

    assert result.target_family is TargetFamily.BALLOON_ENVELOPE
    assert result.diagnostics.detector is DetectorKind.BALLOON_ENVELOPE_DETECTOR


def test_detection_dispatch_uses_wire_detector_for_wire_family() -> None:
    frame = np.full((80, 100), 230, dtype=np.uint8)
    frame[35:45, 20:80] = 30

    result = detect_target(
        frame=frame,
        roi=RotatedRoi(center_x=50.0, center_y=40.0, width=30.0, height=70.0, angle_deg=90.0),
        target_family=TargetFamily.WIRE_STRIP,
        segmentation=SegmentationParams(open_kernel=1),
        params=WireStripDetectorParams(),
    )

    assert result.target_family is TargetFamily.WIRE_STRIP
    assert result.diagnostics.detector is DetectorKind.WIRE_STRIP_DETECTOR
