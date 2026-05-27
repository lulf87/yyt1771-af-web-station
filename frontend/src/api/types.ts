export type CoordinateSpace = "sensor_native" | "acquisition" | "roi_local" | "display";

export type TargetFamily = "balloon_envelope" | "wire_strip";

export type TemperatureStatus =
  | "ok"
  | "unavailable"
  | "disconnected"
  | "not_connected"
  | "unsupported_protocol"
  | "unsupported_operation"
  | "communication_error"
  | "invalid_request";

export type AnalysisMethod = "af95_v1" | "tangent_v1";

export type AnalysisStatus = "ok" | "insufficient_data" | "no_valid_samples" | "unstable_curve";

export type DetectionStatus =
  | "ok"
  | "no_fresh_frame"
  | "roi_invalid_geometry"
  | "roi_outside_frame"
  | "target_not_found"
  | "low_contrast"
  | "segmentation_failed"
  | "multiple_targets"
  | "target_touches_roi_boundary"
  | "opposing_contour_edges_missing"
  | "caliper_contact_ambiguous"
  | "caliper_contact_on_roi_boundary"
  | "contour_fragmented"
  | "internal_texture_selected"
  | "points_not_on_contour"
  | "quality_below_threshold"
  | "jump_exceeds_limit"
  | "coordinate_mapping_error"
  | "stale_frame_geometry_mismatch"
  | "unsupported_target_family";

export interface Point2D {
  x: number;
  y: number;
  coordinate_space: CoordinateSpace;
}

export interface RotatedRoi {
  center_x: number;
  center_y: number;
  width: number;
  height: number;
  angle_deg: number;
  coordinate_space: CoordinateSpace;
}

export interface FrameRef {
  frame_id: number;
  timestamp_ms: number;
  width: number;
  height: number;
  coordinate_space: CoordinateSpace;
}

export interface CameraOpenResponse {
  opened: boolean;
  source_type: string;
}

export interface CameraStatus {
  opened: boolean;
  source_type: string;
  latest_frame_id: number | null;
  frame_width: number | null;
  frame_height: number | null;
  coordinate_space: CoordinateSpace;
}

export interface FreezeResponse {
  frame_ref: FrameRef;
  preview_url: string;
}

export interface SetupDetectRequest {
  frame_ref: FrameRef;
  roi: RotatedRoi;
  target_family: TargetFamily;
  recipe_name: string;
}

export interface SetupDetectResponse {
  status: DetectionStatus;
  valid: boolean;
  point_a: Point2D | null;
  point_b: Point2D | null;
  distance_px: number | null;
  quality: number;
  target_family: TargetFamily;
  detector: string;
  diagnostics: Record<string, unknown>;
}

export interface MeasurementDefinition {
  measurement_definition_id: string;
  name: string;
  target_family: TargetFamily;
  roi: RotatedRoi;
  recipe_name: string;
  detector_version: string;
  acquisition_frame_size: {
    width: number;
    height: number;
  };
  coordinate_space: CoordinateSpace;
  created_at_ms: number;
}

export interface SetupConfirmRequest {
  name: string;
  target_family: TargetFamily;
  roi: RotatedRoi;
  recipe_name: string;
}

export interface SetupConfirmResponse {
  measurement_definition_id: string;
  saved: boolean;
  measurement_definition: MeasurementDefinition;
}

export interface RunStartRequest {
  measurement_definition_id: string;
  sample_hz: number;
  sample_count: number;
}

export interface RunStartResponse {
  run_id: string;
  started: boolean;
  sample_count: number;
}

export interface RunStatusResponse {
  run_id: string;
  status: "running" | "stopped";
  sample_hz: number;
  sample_count: number;
  measurement_definition_id: string;
  temperature_source: Record<string, unknown>;
}

export interface TemperatureReading {
  timestamp_ms: number;
  temperature_c: number | null;
  status: TemperatureStatus;
  source_type: string;
  message: string | null;
}

export interface TemperatureControllerSnapshot {
  controller_type: string;
  connected: boolean;
  status: TemperatureStatus;
  timestamp_ms: number;
  current_temperature_c: number | null;
  target_temperature_c: number | null;
  power_percent: number | null;
  output_enabled: boolean | null;
  message: string | null;
}

export interface TemperatureCommandResponse {
  status: TemperatureStatus;
  ok: boolean;
  message: string | null;
  snapshot: TemperatureControllerSnapshot;
}

export interface RunStopResponse {
  run_id: string;
  stopped: boolean;
}

export interface RunSample {
  run_id: string;
  sample_index: number;
  timestamp_ms: number;
  temperature?: TemperatureReading | null;
  temperature_c: number | null;
  temperature_status: TemperatureStatus;
  detection: SetupDetectResponse;
}

export interface RunSamplesResponse {
  run_id: string;
  samples: RunSample[];
}

export interface RunSummary {
  run_id: string;
  status?: string;
  sample_count?: number;
  measurement_definition_id?: string;
  [key: string]: unknown;
}

export interface RunListResponse {
  runs: RunSummary[];
}

export interface AnalysisCurvePoint {
  sample_index: number;
  timestamp_ms: number;
  temperature_c: number;
  distance_px: number;
  recovered_fraction: number;
}

export interface AnalysisResult {
  min_distance_px: number;
  max_distance_px: number;
  initial_distance_px: number;
  final_distance_px: number;
  recovered_fraction: number;
  valid_sample_count: number;
  invalid_sample_count: number;
  temperature_range: [number, number];
  af95_temperature_c: number | null;
}

export interface AnalysisResponse {
  method: AnalysisMethod;
  status: AnalysisStatus;
  curve: AnalysisCurvePoint[];
  result: AnalysisResult | null;
  diagnostics: Record<string, unknown>;
}

export type ExportFormat = "csv" | "json" | "png" | "xlsx";
