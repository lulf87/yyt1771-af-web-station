import type { CameraStatus, SetupDetectResponse } from "../api/types";
import { detectionReason, formatNullableNumber, formatPoint } from "./statusDisplay";

interface StatusPanelProps {
  cameraStatus: CameraStatus | null;
  detection: SetupDetectResponse | null;
  error: string | null;
}

export function StatusPanel({ cameraStatus, detection, error }: StatusPanelProps) {
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
        {error ? (
          <div className="metric-error">
            <dt>Error</dt>
            <dd>{error}</dd>
          </div>
        ) : null}
      </dl>
      {detection ? <DebugDiagnostics detection={detection} /> : null}
    </>
  );
}

function DebugDiagnostics({ detection }: { detection: SetupDetectResponse }) {
  const diagnostics = detection.diagnostics;
  const rejectedA = pointLike(diagnostics.rejected_candidate_point_a);
  const rejectedB = pointLike(diagnostics.rejected_candidate_point_b);
  const rows = [
    ["Message", valueText(diagnostics.message)],
    ["Selected polarity", valueText(diagnostics.selected_polarity)],
    ["Selected reason", valueText(diagnostics.selected_reason)],
    ["Threshold", valueText(diagnostics.threshold_value)],
    ["Foreground ratio", valueText(diagnostics.foreground_area_ratio_in_roi)],
    ["Component area", valueText(diagnostics.selected_component_area_px)],
    ["Component bbox", bboxText(diagnostics.selected_component_bbox)],
    ["Component count", valueText(diagnostics.candidate_component_count)],
    ["Min projection", valueText(diagnostics.min_local_projection)],
    ["Max projection", valueText(diagnostics.max_local_projection)],
    ["Left boundary px", valueText(diagnostics.distance_to_left_roi_boundary_px)],
    ["Right boundary px", valueText(diagnostics.distance_to_right_roi_boundary_px)],
    ["Rejected side", valueText(diagnostics.rejected_contact_side)],
    ["Boundary margin", valueText(diagnostics.boundary_margin_px)],
    ["Rejected/debug A", rejectedA],
    ["Rejected/debug B", rejectedB],
  ];

  return (
    <section className="debug-diagnostics" aria-label="Debug Diagnostics">
      <h3>Debug Diagnostics</h3>
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
    </section>
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

function pointLike(value: unknown): string {
  if (typeof value === "object" && value !== null && "x" in value && "y" in value) {
    const point = value as Record<string, unknown>;
    return `${valueText(point.x)}, ${valueText(point.y)} rejected/debug`;
  }
  return "N/A";
}
