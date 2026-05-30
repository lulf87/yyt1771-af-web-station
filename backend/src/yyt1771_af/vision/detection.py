from __future__ import annotations

import numpy as np

from yyt1771_af.core.models import (
    BalloonEnvelopeDetectorParams,
    DetectionResult,
    RotatedRoi,
    SegmentationParams,
    WireStripDetectorParams,
)
from yyt1771_af.core.statuses import TargetFamily
from yyt1771_af.vision.balloon_envelope_detector import BalloonEnvelopeDetector
from yyt1771_af.vision.detection_debug import DebugLevel
from yyt1771_af.vision.wire_strip_detector import WireStripDetector


def detect_target(
    *,
    frame: np.ndarray,
    roi: RotatedRoi,
    target_family: TargetFamily,
    segmentation: SegmentationParams,
    params: BalloonEnvelopeDetectorParams | WireStripDetectorParams,
    debug_level: DebugLevel = "full",
) -> DetectionResult:
    if target_family is TargetFamily.BALLOON_ENVELOPE:
        if not isinstance(params, BalloonEnvelopeDetectorParams):
            raise TypeError("balloon_envelope requires BalloonEnvelopeDetectorParams")
        return BalloonEnvelopeDetector().detect(
            frame=frame,
            roi=roi,
            segmentation=segmentation,
            params=params,
            debug_level=debug_level,
        )

    if not isinstance(params, WireStripDetectorParams):
        raise TypeError("wire_strip requires WireStripDetectorParams")
    return WireStripDetector().detect(
        frame=frame,
        roi=roi,
        segmentation=segmentation,
        params=params,
        debug_level=debug_level,
    )
