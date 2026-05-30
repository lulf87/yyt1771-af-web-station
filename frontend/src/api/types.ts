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
  | "pattern_not_found"
  | "object_interval_count_mismatch"
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
  segmentation?: SegmentationParams | null;
  detector?: DetectorParams | null;
}

export interface SetupDetectResponse {
  status: DetectionStatus;
  valid: boolean;
  point_a: Point2D | null;
  point_b: Point2D | null;
  distance_px: number | null;
  quality: number;
  target_family: TargetFamily;
  detector?: string;
  frame_ref?: FrameRef | null;
  diagnostics: Record<string, unknown>;
  debug_overlay_url?: string | null;
}

export interface SegmentationParams {
  polarity: "auto" | "dark_on_light" | "light_on_dark";
  threshold_mode: "otsu" | "adaptive" | "fixed";
  threshold_value: number | null;
  blur_kernel: number;
  close_kernel: number;
  open_kernel: number;
  min_component_area_px: number;
  fill_internal_holes?: boolean | null;
}

export type EnvelopeMode = "solid_balloon" | "open_mesh";
export type ContactSource = "raw_foreground" | "bridged_foreground" | "filled_envelope";

export interface BalloonEnvelopeDetectorParams {
  detector_kind: "balloon_envelope_detector";
  envelope_mode: EnvelopeMode;
  contact_source: ContactSource;
  measurement_model: "blank_object_blank";
  min_quality: number;
  max_point_jump_px: number | null;
  reject_contact_on_roi_boundary: boolean;
  boundary_margin_px: number;
  ignore_internal_texture: boolean;
  fill_internal_holes: boolean;
  bridge_mesh_gaps: boolean;
}

export interface WireStripDetectorParams {
  detector_kind: "wire_strip_detector";
  measurement_model: "blank_wire_bundle_envelope_blank";
  measurement_mode: "wire_bundle_envelope";
  min_quality: number;
  max_point_jump_px: number | null;
  reject_contact_on_roi_boundary: boolean;
  boundary_margin_px: number;
  require_physical_endpoints: false;
  skeleton_endpoint_detection: false;
  preserve_visible_strip_contour: boolean;
}

export type DetectorParams = BalloonEnvelopeDetectorParams | WireStripDetectorParams;

export interface FramePreviewMetadata {
  frame_id: number | null;
  frame_index: number | null;
  frame_name: string | null;
  acquisition_width: number;
  acquisition_height: number;
  display_width: number;
  display_height: number;
  scale_x: number;
  scale_y: number;
  coordinate_space: CoordinateSpace;
  preview_url: string;
}

export interface MeasurementDefinition {
  measurement_definition_id: string;
  name: string;
  target_family: TargetFamily;
  roi: RotatedRoi;
  recipe_name: string;
  segmentation: SegmentationParams;
  detector: DetectorParams;
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
  segmentation?: SegmentationParams | null;
  detector?: DetectorParams | null;
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
  status: "running" | "completed" | "stopped";
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

export interface OfflinePlaybackOpenRequest {
  frames_dir?: string | null;
  evaluation_output_dir?: string | null;
  dataset_label?: string | null;
  target_family: TargetFamily;
  roi: RotatedRoi;
  fps: number;
  recipe_name?: string | null;
  max_preview_width?: number;
}

export interface OfflinePlaybackFrame {
  frame_index: number;
  frame_name: string;
  relative_time_s: number;
  acquisition_width: number;
  acquisition_height: number;
  display_width: number;
  display_height: number;
  scale_x: number;
  scale_y: number;
  coordinate_space: CoordinateSpace;
  preview_url: string;
  detection: SetupDetectResponse;
}

export interface OfflinePlaybackStatus {
  opened: boolean;
  mode: string;
  dataset_label: string | null;
  frame_count: number;
  current_frame_index: number | null;
  top_jump_frames: number[];
  failure_frame_indices: number[];
  current: OfflinePlaybackFrame | null;
}

export interface OfflineRunOpenRequest {
  measurement_definition_id: string;
  frames_dir?: string | null;
  fps: number;
  loop: boolean;
  dataset_label?: string | null;
  start_frame_index?: number;
  max_preview_width?: number;
}

export interface OfflineRunOpenResponse {
  session_id: string;
  opened: boolean;
  dataset_label: string;
  frame_count: number;
  current_frame_index: number;
  fps: number;
  loop: boolean;
  measurement_definition_id: string;
}

export interface OfflineRunStatus {
  session_id: string;
  opened: boolean;
  state: "opened" | "playing" | "paused" | "end_of_stream" | "closed" | "error" | string;
  dataset_label: string;
  frame_count: number;
  current_frame_index: number;
  fps: number;
  loop: boolean;
  measurement_definition_id: string;
  latest: OfflineRunFrame | null;
}

export interface OfflineRunFrame {
  session_id: string;
  frame_index: number;
  frame_name: string;
  relative_time_s: number;
  acquisition_width: number;
  acquisition_height: number;
  display_width: number;
  display_height: number;
  scale_x: number;
  scale_y: number;
  coordinate_space: CoordinateSpace;
  preview_url: string;
  end_of_stream: boolean;
  detection: SetupDetectResponse;
  runtime: Record<string, unknown>;
}

export interface OfflineRunCloseResponse {
  session_id: string;
  closed: boolean;
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
