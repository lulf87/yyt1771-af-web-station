from __future__ import annotations

import numpy as np

from yyt1771_af.core.models import (
    BalloonEnvelopeDetectorParams,
    DetectionResult,
    RotatedRoi,
    SegmentationParams,
)
from yyt1771_af.core.statuses import DetectionStatus, DetectorKind, TargetFamily
from yyt1771_af.vision.roi_ops import (
    failure_result,
    roi_is_inside_frame,
    rotated_roi_mask,
    select_contact_points,
    valid_result,
)
from yyt1771_af.vision.segmentation import (
    connected_components,
    fill_internal_holes,
    segment_target_mask,
)


class BalloonEnvelopeDetector:
    detector_kind = DetectorKind.BALLOON_ENVELOPE_DETECTOR
    target_family = TargetFamily.BALLOON_ENVELOPE

    def detect(
        self,
        *,
        frame: np.ndarray,
        roi: RotatedRoi,
        segmentation: SegmentationParams | None = None,
        params: BalloonEnvelopeDetectorParams | None = None,
    ) -> DetectionResult:
        segmentation = segmentation or SegmentationParams()
        params = params or BalloonEnvelopeDetectorParams()

        if frame.ndim != 2:
            return self._failure(
                DetectionStatus.SEGMENTATION_FAILED,
                message="Frame is not grayscale.",
            )
        if not roi_is_inside_frame(frame, roi):
            return self._failure(
                DetectionStatus.ROI_OUTSIDE_FRAME,
                message="ROI is outside frame.",
            )

        roi_mask = rotated_roi_mask(frame.shape, roi)
        foreground, contrast_quality = segment_target_mask(
            frame,
            roi_mask,
            segmentation,
            preferred_point_xy=(roi.center_x, roi.center_y),
        )
        if not np.any(foreground):
            return self._failure(DetectionStatus.LOW_CONTRAST, quality=contrast_quality)

        if params.fill_internal_holes:
            foreground = fill_internal_holes(foreground)
            foreground &= roi_mask

        components = connected_components(foreground, segmentation.min_component_area_px)
        if not components:
            return self._failure(DetectionStatus.TARGET_NOT_FOUND, quality=contrast_quality)
        if len(components) > 1 and components[1].area_px > components[0].area_px * 0.35:
            return self._failure(
                DetectionStatus.MULTIPLE_TARGETS,
                quality=contrast_quality,
                candidate_components=len(components),
            )

        component = components[0]
        selection = select_contact_points(
            component,
            roi,
            boundary_margin_px=params.boundary_margin_px,
            reject_contact_on_roi_boundary=params.reject_contact_on_roi_boundary,
        )
        if isinstance(selection, DetectionStatus):
            return self._failure(
                selection,
                quality=contrast_quality,
                contour_area_px=float(component.area_px),
                candidate_components=len(components),
            )

        quality = max(params.min_quality, min(0.98, 0.65 + 0.3 * contrast_quality))
        return valid_result(
            target_family=self.target_family,
            detector=self.detector_kind,
            selection=selection,
            contour_area_px=float(component.area_px),
            candidate_components=len(components),
            quality=quality,
        )

    def _failure(
        self,
        status: DetectionStatus,
        *,
        quality: float = 0.0,
        contour_area_px: float | None = None,
        candidate_components: int | None = None,
        message: str | None = None,
    ) -> DetectionResult:
        return failure_result(
            target_family=self.target_family,
            detector=self.detector_kind,
            status=status,
            quality=quality,
            contour_area_px=contour_area_px,
            candidate_components=candidate_components,
            message=message,
        )
