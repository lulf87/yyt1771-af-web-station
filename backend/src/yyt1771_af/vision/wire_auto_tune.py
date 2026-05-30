"""Setup-time threshold auto tuning for ``WireStripDetector``.

The auto tuner runs only during setup. It sweeps candidate fixed thresholds,
runs the wire detector for each, scores the outcome, and selects the threshold
sitting on the widest stable platform (see ``docs/17``). It never runs during
the measurement run phase and never depends on the previous measurement line.

Pure NumPy + ``WireStripDetector``: no FastAPI, OpenCV, hardware, or filesystem
side effects.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from yyt1771_af.core.models import RotatedRoi, SegmentationParams, WireStripDetectorParams
from yyt1771_af.vision.roi_ops import rotated_roi_mask
from yyt1771_af.vision.segmentation import otsu_threshold
from yyt1771_af.vision.wire_strip_detector import WireStripDetector

_MIN_CANDIDATE = 60
_MAX_CANDIDATE = 200


@dataclass(frozen=True, slots=True)
class WireAutoTuneCandidate:
    threshold_value: int
    status: str
    valid: bool
    formal_ab_span_px: float | None
    valid_interval_count: int | None
    rejected_interval_count: int
    broad_blob_rejection_count: int | None
    wire_likeness_score: float | None
    distance_px: float | None
    score: float
    on_stable_platform: bool = False


@dataclass(frozen=True, slots=True)
class WireAutoTuneResult:
    candidates: list[WireAutoTuneCandidate]
    recommended_threshold_value: int | None
    recommended_polarity: str
    stable_platform_min: int | None
    stable_platform_max: int | None
    selected_reason: str
    auto_tuned: bool


def candidate_thresholds_for_roi(
    image: np.ndarray,
    roi_mask: np.ndarray,
    *,
    step: int = 8,
) -> list[int]:
    """Build candidate thresholds from a baseline range plus ROI histogram."""
    candidates: set[int] = set(range(80, 161, step))
    roi_values = np.asarray(image)[np.asarray(roi_mask, dtype=bool)]
    if roi_values.size > 0:
        low = int(np.percentile(roi_values, 10))
        high = int(np.percentile(roi_values, 75))
        low = max(_MIN_CANDIDATE, min(low, 150))
        high = max(low + 2 * step, min(high, _MAX_CANDIDATE))
        candidates.update(range(low, high + 1, step))
        candidates.add(int(otsu_threshold(roi_values)))
    bounded = {t for t in candidates if _MIN_CANDIDATE <= t <= _MAX_CANDIDATE}
    return sorted(bounded)


def auto_tune_wire_threshold(
    *,
    frame: np.ndarray,
    roi: RotatedRoi,
    base_segmentation: SegmentationParams | None = None,
    detector_params: WireStripDetectorParams | None = None,
    candidate_thresholds: list[int] | None = None,
) -> WireAutoTuneResult:
    base_segmentation = base_segmentation or SegmentationParams()
    detector_params = detector_params or WireStripDetectorParams()
    detector = WireStripDetector()
    roi_mask = rotated_roi_mask(frame.shape, roi)
    polarity = base_segmentation.polarity
    if candidate_thresholds is None:
        candidate_thresholds = candidate_thresholds_for_roi(frame, roi_mask)

    candidates: list[WireAutoTuneCandidate] = []
    for threshold in candidate_thresholds:
        segmentation = base_segmentation.model_copy(
            update={"threshold_mode": "fixed", "threshold_value": int(threshold)}
        )
        result = detector.detect(
            frame=frame,
            roi=roi,
            segmentation=segmentation,
            params=detector_params,
        )
        diagnostics = result.diagnostics
        rejected = diagnostics.rejected_intervals or []
        candidates.append(
            WireAutoTuneCandidate(
                threshold_value=int(threshold),
                status=result.status.value,
                valid=result.valid,
                formal_ab_span_px=diagnostics.formal_ab_span_px,
                valid_interval_count=diagnostics.object_interval_count,
                rejected_interval_count=len(rejected),
                broad_blob_rejection_count=diagnostics.broad_blob_rejection_count,
                wire_likeness_score=diagnostics.wire_likeness_score,
                distance_px=result.distance_px,
                score=_score_candidate(result.valid, diagnostics, len(rejected)),
            )
        )

    return _select_recommendation(candidates, polarity)


def _score_candidate(valid: bool, diagnostics: object, rejected_count: int) -> float:
    if not valid:
        return -1.0
    wire_likeness = getattr(diagnostics, "wire_likeness_score", None) or 0.0
    broad_blob = getattr(diagnostics, "broad_blob_rejection_count", None) or 0
    neighbor = getattr(diagnostics, "neighbor_line_support", None) or 0
    score = 1.0
    score += float(wire_likeness)
    score += 0.1 * float(neighbor)
    score -= 0.15 * float(broad_blob)
    score -= 0.05 * float(rejected_count)
    return round(score, 4)


def _span_tolerance(span: float | None) -> float:
    if span is None:
        return 3.0
    return max(3.0, 0.05 * span)


def _select_recommendation(
    candidates: list[WireAutoTuneCandidate],
    polarity: str,
) -> WireAutoTuneResult:
    platforms = _stable_platforms(candidates)
    if platforms:
        platform = max(platforms, key=lambda run: (len(run), sum(c.score for c in run)))
        platform_thresholds = {c.threshold_value for c in platform}
        candidates = [
            _with_platform_flag(c, c.threshold_value in platform_thresholds) for c in candidates
        ]
        platform = [c for c in candidates if c.threshold_value in platform_thresholds]
        best = max(platform, key=lambda c: (c.score, -abs(c.threshold_value - _center(platform))))
        if len(platform) >= 2:
            return WireAutoTuneResult(
                candidates=candidates,
                recommended_threshold_value=best.threshold_value,
                recommended_polarity=polarity,
                stable_platform_min=min(platform_thresholds),
                stable_platform_max=max(platform_thresholds),
                selected_reason="stable_platform",
                auto_tuned=True,
            )

    valid_candidates = [c for c in candidates if c.valid]
    if valid_candidates:
        best = max(valid_candidates, key=lambda c: c.score)
        return WireAutoTuneResult(
            candidates=candidates,
            recommended_threshold_value=best.threshold_value,
            recommended_polarity=polarity,
            stable_platform_min=None,
            stable_platform_max=None,
            selected_reason="max_score_no_stable_platform",
            auto_tuned=True,
        )

    return WireAutoTuneResult(
        candidates=candidates,
        recommended_threshold_value=None,
        recommended_polarity=polarity,
        stable_platform_min=None,
        stable_platform_max=None,
        selected_reason="no_valid_candidate",
        auto_tuned=False,
    )


def _stable_platforms(
    candidates: list[WireAutoTuneCandidate],
) -> list[list[WireAutoTuneCandidate]]:
    runs: list[list[WireAutoTuneCandidate]] = []
    current: list[WireAutoTuneCandidate] = []
    for candidate in candidates:
        eligible = (
            candidate.valid
            and (candidate.broad_blob_rejection_count or 0) == 0
            and candidate.formal_ab_span_px is not None
        )
        if not eligible:
            if current:
                runs.append(current)
                current = []
            continue
        if current and (
            abs((candidate.formal_ab_span_px or 0.0) - (current[-1].formal_ab_span_px or 0.0))
            <= _span_tolerance(current[-1].formal_ab_span_px)
        ):
            current.append(candidate)
        else:
            if current:
                runs.append(current)
            current = [candidate]
    if current:
        runs.append(current)
    return runs


def _with_platform_flag(
    candidate: WireAutoTuneCandidate,
    on_platform: bool,
) -> WireAutoTuneCandidate:
    return WireAutoTuneCandidate(
        threshold_value=candidate.threshold_value,
        status=candidate.status,
        valid=candidate.valid,
        formal_ab_span_px=candidate.formal_ab_span_px,
        valid_interval_count=candidate.valid_interval_count,
        rejected_interval_count=candidate.rejected_interval_count,
        broad_blob_rejection_count=candidate.broad_blob_rejection_count,
        wire_likeness_score=candidate.wire_likeness_score,
        distance_px=candidate.distance_px,
        score=candidate.score,
        on_stable_platform=on_platform,
    )


def _center(platform: list[WireAutoTuneCandidate]) -> float:
    thresholds = [c.threshold_value for c in platform]
    return (min(thresholds) + max(thresholds)) / 2.0
