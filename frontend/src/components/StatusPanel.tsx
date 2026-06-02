import type {
  CameraStatus,
  FrameIdentity,
  PointProbeResponse,
  SetupDetectResponse,
} from "../api/types";
import { detectionReason, formatNullableNumber, formatPoint } from "./statusDisplay";

interface StatusPanelProps {
  cameraStatus: CameraStatus | null;
  detection: SetupDetectResponse | null;
  error: string | null;
  showDebugDiagnostics?: boolean;
  probeResult?: PointProbeResponse | null;
  frameIdentity?: FrameIdentity | null;
}

export function StatusPanel({
  cameraStatus,
  detection,
  error,
  showDebugDiagnostics = true,
  probeResult = null,
  frameIdentity = null,
}: StatusPanelProps) {
  const identity = detection?.frame_identity ?? frameIdentity;
  return (
    <>
      <dl className="metric-list">
        <div>
          <dt>Source</dt>
          <dd>{cameraStatus?.opened ? cameraStatus.source_type : "closed"}</dd>
        </div>
        <div>
          <dt>Status</dt>
          <dd>{detection?.status ?? "waiting"}</dd>
        </div>
        <div>
          <dt>Quality</dt>
          <dd>{detection ? detection.quality.toFixed(2) : "N/A"}</dd>
        </div>
        <div>
          <dt>Distance px</dt>
          <dd>{detection ? formatNullableNumber(detection.distance_px) : "N/A"}</dd>
        </div>
        <div>
          <dt>A x,y</dt>
          <dd>{detection ? formatPoint(detection.point_a) : "N/A"}</dd>
        </div>
        <div>
          <dt>B x,y</dt>
          <dd>{detection ? formatPoint(detection.point_b) : "N/A"}</dd>
        </div>
        <div>
          <dt>Detector</dt>
          <dd>{detection?.detector ?? "N/A"}</dd>
        </div>
        <div>
          <dt>Coordinates</dt>
          <dd>
            {detection?.point_a?.coordinate_space ??
              detection?.point_b?.coordinate_space ??
              "acquisition"}
          </dd>
        </div>
        <div>
          <dt>Reason</dt>
          <dd>{detectionReason(detection)}</dd>
        </div>
        {identity ? (
          <>
            <div>
              <dt>Frame identity</dt>
              <dd>{identity.frame_name ?? valueText(identity.frame_index ?? identity.frame_id)}</dd>
            </div>
            <div>
              <dt>Frame index</dt>
              <dd>{valueText(identity.frame_index)}</dd>
            </div>
            <div>
              <dt>Frame source</dt>
              <dd>{identity.source_type}</dd>
            </div>
            <div>
              <dt>Frame size</dt>
              <dd>
                {identity.acquisition_width} x {identity.acquisition_height}
              </dd>
            </div>
            <div>
              <dt>Debug level</dt>
              <dd>{identity.debug_level ?? "N/A"}</dd>
            </div>
            <div>
              <dt>Recipe summary</dt>
              <dd>{recipeSummaryText(identity.recipe_summary)}</dd>
            </div>
          </>
        ) : null}
        {error ? (
          <div className="metric-error">
            <dt>Error</dt>
            <dd>{error}</dd>
          </div>
        ) : null}
      </dl>
      {probeResult ? <PointProbeReadout probe={probeResult} /> : null}
      {detection && showDebugDiagnostics ? <DebugDiagnostics detection={detection} /> : null}
    </>
  );
}

function PointProbeReadout({ probe }: { probe: PointProbeResponse }) {
  const rows: Array<[string, string]> = [
    ["Frame", probe.frame_identity.frame_name ?? valueText(probe.frame_identity.frame_index)],
    ["Probe x,y", `${valueText(probe.x)}, ${valueText(probe.y)}`],
    ["Pixel value", valueText(probe.pixel_value)],
    ["Inside ROI", valueText(probe.inside_roi)],
    ["Raw foreground", valueText(probe.raw_foreground)],
    ["Morphology foreground", valueText(probe.morphology_foreground)],
    ["Wire foreground", valueText(probe.wire_foreground)],
    ["Component id", valueText(probe.component_id)],
    ["Component accepted", valueText(probe.component_accepted)],
    ["Component reject reason", valueText(probe.component_reject_reason)],
    ["Interval id", valueText(probe.interval_id)],
    ["Selected valid interval", valueText(probe.selected_valid_interval)],
    ["Rejected interval", valueText(probe.rejected_interval)],
    ["Rejected remote interval", valueText(probe.rejected_remote_interval)],
    ["Reject reason", valueText(probe.reject_reason)],
    ["A/B source interval", valueText(probe.source_interval_id)],
    ["Would be A/B source", valueText(probe.would_be_ab_source)],
  ];
  return (
    <details className="debug-diagnostics collapsible-section" open>
      <summary>
        <h3>Point Probe</h3>
      </summary>
      <dl className="metric-list debug-list">
        {rows.map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
    </details>
  );
}

function DebugDiagnostics({ detection }: { detection: SetupDetectResponse }) {
  const diagnostics = detection.diagnostics;
  const diagnosticPointSuffix = detection.valid ? undefined : "rejected/debug";
  const rejectedA = pointLike(diagnostics.rejected_candidate_point_a, "rejected/debug");
  const rejectedB = pointLike(diagnostics.rejected_candidate_point_b, "rejected/debug");
  const pointASourceInterval =
    diagnostics.point_a_source_interval ?? diagnostics.formal_point_a_source_interval;
  const pointBSourceInterval =
    diagnostics.point_b_source_interval ?? diagnostics.formal_point_b_source_interval;
  const rows = [
    ["Message", valueText(diagnostics.message)],
    ["Pattern model", valueText(diagnostics.pattern_model)],
    ["Detected pattern", valueText(diagnostics.detected_pattern)],
    ["Measurement mode", valueText(diagnostics.measurement_mode)],
    ["Measurement line y", valueText(diagnostics.measurement_line_y)],
    ["A local x,y", pointLike(diagnostics.point_a_local, diagnosticPointSuffix)],
    ["B local x,y", pointLike(diagnostics.point_b_local, diagnosticPointSuffix)],
    ["Local y delta", valueText(diagnostics.local_y_delta_px)],
    ["Parallel error", valueText(diagnostics.parallel_error_px)],
    ["Chord length", valueText(diagnostics.chord_length_px)],
    ["Envelope mode", valueText(diagnostics.envelope_mode)],
    ["Configured source", valueText(diagnostics.configured_contact_source)],
    ["Contact source", valueText(diagnostics.contact_source_used)],
    ["Actual source ratio", valueText(diagnostics.actual_contact_source_area_ratio)],
    ["Selected polarity", valueText(diagnostics.selected_polarity)],
    ["Selected reason", valueText(diagnostics.selected_reason)],
    ["Threshold", valueText(diagnostics.threshold_value)],
    ["Raw ratio", valueText(diagnostics.raw_foreground_ratio)],
    ["Bridged ratio", valueText(diagnostics.morphology_foreground_ratio)],
    ["Filled ratio", valueText(diagnostics.filled_envelope_ratio)],
    ["Foreground ratio", valueText(diagnostics.foreground_area_ratio_in_roi)],
    ["Object intervals", valueText(diagnostics.object_interval_count)],
    ["Selected intervals", intervalSummary(diagnostics.selected_intervals)],
    ["Raw intervals", intervalSummary(diagnostics.raw_intervals)],
    ["Bridged intervals", intervalSummary(diagnostics.bridged_intervals)],
    ["Selected valid intervals", intervalSummary(diagnostics.selected_valid_intervals)],
    ["Rejected intervals", intervalSummary(diagnostics.rejected_intervals)],
    ["Rejected interval reasons", reasonSummary(diagnostics.rejected_interval_reasons)],
    ["Interval gaps", numberListSummary(diagnostics.interval_gaps)],
    ["Bundle clusters", valueText(diagnostics.bundle_cluster_count)],
    ["Selected bundle cluster", valueText(diagnostics.selected_bundle_cluster_id)],
    ["Selected bundle intervals", valueText(diagnostics.selected_bundle_interval_count)],
    ["Selected bundle span", valueText(diagnostics.selected_bundle_outer_span_px)],
    ["Bundle support ratio", valueText(diagnostics.selected_bundle_support_ratio)],
    ["Max internal gap", valueText(diagnostics.selected_bundle_max_internal_gap_px)],
    ["Max bundle gap threshold", valueText(diagnostics.max_bundle_internal_gap_px)],
    ["Max bundle gap ratio", valueText(diagnostics.max_bundle_internal_gap_ratio)],
    ["Rejected remote intervals", intervalSummary(diagnostics.rejected_remote_intervals)],
    [
      "Rejected remote reasons",
      reasonSummary(diagnostics.rejected_remote_interval_reasons),
    ],
    [
      "Remote interval rejection count",
      valueText(diagnostics.remote_interval_rejection_count),
    ],
    ["Local contrast", valueText(diagnostics.local_contrast_score)],
    ["Wire likeness", valueText(diagnostics.wire_likeness_score)],
    ["Component area", valueText(diagnostics.component_area_px ?? diagnostics.selected_component_area_px)],
    ["Component bbox", bboxText(diagnostics.component_bbox ?? diagnostics.selected_component_bbox)],
    ["Component aspect ratio", valueText(diagnostics.component_aspect_ratio)],
    ["Component orientation", valueText(diagnostics.component_orientation)],
    ["Component orientation deg", valueText(diagnostics.component_orientation_deg)],
    ["Orientation deviation", valueText(diagnostics.orientation_deviation_deg)],
    ["Neighbor line support", valueText(diagnostics.neighbor_line_support)],
    ["Broad blob rejections", valueText(diagnostics.broad_blob_rejection_count)],
    ["Broad blob area ratio", valueText(diagnostics.broad_blob_area_ratio)],
    ["Threshold mode", valueText(diagnostics.threshold_mode)],
    ["Configured polarity", valueText(diagnostics.configured_polarity)],
    ["Close kernel", valueText(diagnostics.close_kernel)],
    ["Open kernel", valueText(diagnostics.open_kernel)],
    ["Min component area", valueText(diagnostics.min_component_area_px)],
    ["Leftmost valid interval", intervalSummary(singleInterval(diagnostics.leftmost_valid_interval))],
    ["Rightmost valid interval", intervalSummary(singleInterval(diagnostics.rightmost_valid_interval))],
    [
      "A source interval",
      intervalSummary(singleInterval(pointASourceInterval)),
    ],
    [
      "B source interval",
      intervalSummary(singleInterval(pointBSourceInterval)),
    ],
    ["A on foreground boundary", valueText(diagnostics.point_a_on_foreground_boundary)],
    ["B on foreground boundary", valueText(diagnostics.point_b_on_foreground_boundary)],
    ["A source layer", valueText(diagnostics.point_a_source_layer)],
    ["B source layer", valueText(diagnostics.point_b_source_layer)],
    ["Internal gaps", valueText(diagnostics.internal_gap_count)],
    ["Line max internal gap", valueText(diagnostics.max_internal_gap_px)],
    ["Bundle outer span", valueText(diagnostics.bundle_outer_span_px ?? diagnostics.mesh_outer_span_px)],
    ["Formal A/B span", valueText(diagnostics.formal_ab_span_px)],
    ["Selected line rank", valueText(diagnostics.selected_line_rank)],
    ["Selected line span", valueText(diagnostics.selected_line_span_px)],
    ["Second best span", valueText(diagnostics.second_best_span_px)],
    ["Span margin to second", valueText(diagnostics.span_margin_to_second_best_px)],
    ["Selected line support", valueText(diagnostics.selected_line_support_ratio)],
    ["Selected line max gap", valueText(diagnostics.selected_line_max_internal_gap_px)],
    ["Selected line intervals", valueText(diagnostics.selected_line_interval_count)],
    ["Candidate count", valueText(diagnostics.candidate_count)],
    ["Ambiguous candidates", valueText(diagnostics.ambiguous_candidate_count)],
    ["Top candidate lines", candidateLineSummary(diagnostics.top_candidate_lines)],
    ["Virtual envelope span", valueText(diagnostics.virtual_envelope_span_px)],
    ["Candidate line debug-only", valueText(diagnostics.candidate_line_is_debug_only)],
    ["Selected line reason", valueText(diagnostics.selected_line_reason)],
    ["Previous line y", valueText(diagnostics.previous_measurement_line_y)],
    ["Line y jump", valueText(diagnostics.line_y_delta_from_previous)],
    ["Distance jump", valueText(diagnostics.distance_jump_from_previous)],
    ["Point A jump", valueText(diagnostics.point_a_jump_from_previous)],
    ["Point B jump", valueText(diagnostics.point_b_jump_from_previous)],
    ["Selected component area", valueText(diagnostics.selected_component_area_px)],
    ["Selected component bbox", bboxText(diagnostics.selected_component_bbox)],
    ["Component count", valueText(diagnostics.candidate_component_count)],
    ["Min projection", valueText(diagnostics.min_local_projection)],
    ["Max projection", valueText(diagnostics.max_local_projection)],
    ["Left margin", valueText(diagnostics.left_margin_px)],
    ["Right margin", valueText(diagnostics.right_margin_px)],
    ["Top margin", valueText(diagnostics.top_margin_px)],
    ["Bottom margin", valueText(diagnostics.bottom_margin_px)],
    ["Left boundary px", valueText(diagnostics.distance_to_left_roi_boundary_px)],
    ["Right boundary px", valueText(diagnostics.distance_to_right_roi_boundary_px)],
    ["Rejected side", valueText(diagnostics.rejected_contact_side)],
    ["Boundary margin", valueText(diagnostics.boundary_margin_px)],
    ["Fill holes used", valueText(diagnostics.fill_internal_holes_used)],
    ["Rejected/debug A", rejectedA],
    ["Rejected/debug B", rejectedB],
  ];

  return (
    <details className="debug-diagnostics collapsible-section" aria-label="Debug Diagnostics">
      <summary>
        <h3>Debug Diagnostics</h3>
      </summary>
      {detection.status === "caliper_contact_on_roi_boundary" ? (
        <p className="debug-warning">
          检测到的候选轮廓接触点距离 ROI 边界太近，可能是 ROI 裁剪边界而不是真实目标轮廓。请查看
          debug mask，确认是否选中了背景或 ROI 边缘；不要直接放宽边界保护。
        </p>
      ) : null}
      <dl className="metric-list debug-list">
        {rows.map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
    </details>
  );
}

function valueText(value: unknown): string {
  if (typeof value === "number") {
    return Number.isInteger(value) ? value.toString() : value.toFixed(2);
  }
  if (typeof value === "string" && value.length > 0) {
    return value;
  }
  if (typeof value === "boolean") {
    return value ? "true" : "false";
  }
  return "N/A";
}

function recipeSummaryText(value: unknown): string {
  if (typeof value !== "object" || value === null) {
    return "N/A";
  }
  const summary = value as Record<string, unknown>;
  const target = valueText(summary.target_family);
  const recipe = valueText(summary.recipe_name);
  const thresholdMode = valueText(summary.threshold_mode);
  const threshold = valueText(summary.threshold_value);
  const detector = valueText(summary.detector_kind);
  return `${target} / ${recipe} / ${detector} / ${thresholdMode}:${threshold}`;
}

function bboxText(value: unknown): string {
  if (
    typeof value === "object" &&
    value !== null &&
    "min_x" in value &&
    "min_y" in value &&
    "max_x" in value &&
    "max_y" in value
  ) {
    const bbox = value as Record<string, unknown>;
    return `${valueText(bbox.min_x)}, ${valueText(bbox.min_y)} - ${valueText(
      bbox.max_x,
    )}, ${valueText(bbox.max_y)}`;
  }
  return "N/A";
}

function pointLike(value: unknown, suffix?: string): string {
  if (typeof value === "object" && value !== null && "x" in value && "y" in value) {
    const point = value as Record<string, unknown>;
    const coordinate = `${valueText(point.x)}, ${valueText(point.y)}`;
    return suffix ? `${coordinate} ${suffix}` : coordinate;
  }
  return "N/A";
}

function singleInterval(value: unknown): unknown[] | null {
  return value ? [value] : null;
}

function reasonSummary(value: unknown): string {
  if (!Array.isArray(value) || value.length === 0) {
    return "N/A";
  }
  return value.map((item) => (typeof item === "string" ? item : "N/A")).join(", ");
}

function numberListSummary(value: unknown): string {
  if (!Array.isArray(value) || value.length === 0) {
    return "N/A";
  }
  return value.map((item) => valueText(item)).join(", ");
}

function intervalSummary(value: unknown): string {
  if (!Array.isArray(value) || value.length === 0) {
    return "N/A";
  }
  return value
    .map((item) => {
      if (
        typeof item === "object" &&
        item !== null &&
        "start_local_x" in item &&
        "end_local_x" in item
      ) {
        const interval = item as Record<string, unknown>;
        return `${valueText(interval.start_local_x)}..${valueText(interval.end_local_x)}`;
      }
      return "N/A";
    })
    .join(", ");
}

function candidateLineSummary(value: unknown): string {
  if (!Array.isArray(value) || value.length === 0) {
    return "N/A";
  }
  return value
    .map((item) => {
      if (typeof item !== "object" || item === null) {
        return "N/A";
      }
      const candidate = item as Record<string, unknown>;
      const selected = candidate.selected === true ? " selected" : "";
      const rejected =
        typeof candidate.rejected_reason === "string" ? ` rejected=${candidate.rejected_reason}` : "";
      return `y=${valueText(candidate.measurement_line_y)} span=${valueText(
        candidate.formal_ab_span_px,
      )} support=${valueText(candidate.support_ratio)} gap=${valueText(
        candidate.max_internal_gap_px,
      )}${selected}${rejected}`;
    })
    .join("; ");
}
