from enum import StrEnum


class CoordinateSpace(StrEnum):
    SENSOR_NATIVE = "sensor_native"
    ACQUISITION = "acquisition"
    ROI_LOCAL = "roi_local"
    DISPLAY = "display"


class TargetFamily(StrEnum):
    BALLOON_ENVELOPE = "balloon_envelope"
    WIRE_STRIP = "wire_strip"


class DetectorKind(StrEnum):
    BALLOON_ENVELOPE_DETECTOR = "balloon_envelope_detector"
    WIRE_STRIP_DETECTOR = "wire_strip_detector"


class DetectionStatus(StrEnum):
    OK = "ok"
    NO_FRESH_FRAME = "no_fresh_frame"
    ROI_INVALID_GEOMETRY = "roi_invalid_geometry"
    ROI_OUTSIDE_FRAME = "roi_outside_frame"
    TARGET_NOT_FOUND = "target_not_found"
    LOW_CONTRAST = "low_contrast"
    SEGMENTATION_FAILED = "segmentation_failed"
    MULTIPLE_TARGETS = "multiple_targets"
    TARGET_TOUCHES_ROI_BOUNDARY = "target_touches_roi_boundary"
    OPPOSING_CONTOUR_EDGES_MISSING = "opposing_contour_edges_missing"
    CALIPER_CONTACT_AMBIGUOUS = "caliper_contact_ambiguous"
    CALIPER_CONTACT_ON_ROI_BOUNDARY = "caliper_contact_on_roi_boundary"
    CONTOUR_FRAGMENTED = "contour_fragmented"
    INTERNAL_TEXTURE_SELECTED = "internal_texture_selected"
    POINTS_NOT_ON_CONTOUR = "points_not_on_contour"
    PATTERN_NOT_FOUND = "pattern_not_found"
    OBJECT_INTERVAL_COUNT_MISMATCH = "object_interval_count_mismatch"
    QUALITY_BELOW_THRESHOLD = "quality_below_threshold"
    JUMP_EXCEEDS_LIMIT = "jump_exceeds_limit"
    COORDINATE_MAPPING_ERROR = "coordinate_mapping_error"
    STALE_FRAME_GEOMETRY_MISMATCH = "stale_frame_geometry_mismatch"
    UNSUPPORTED_TARGET_FAMILY = "unsupported_target_family"


class TemperatureStatus(StrEnum):
    OK = "ok"
    UNAVAILABLE = "unavailable"
    DISCONNECTED = "disconnected"
    NOT_CONNECTED = "not_connected"
    UNSUPPORTED_PROTOCOL = "unsupported_protocol"
    UNSUPPORTED_OPERATION = "unsupported_operation"
    COMMUNICATION_ERROR = "communication_error"
    INVALID_REQUEST = "invalid_request"


class AnalysisMethod(StrEnum):
    AF95_V1 = "af95_v1"
    TANGENT_V1 = "tangent_v1"


class AnalysisStatus(StrEnum):
    OK = "ok"
    INSUFFICIENT_DATA = "insufficient_data"
    NO_VALID_SAMPLES = "no_valid_samples"
    UNSTABLE_CURVE = "unstable_curve"
