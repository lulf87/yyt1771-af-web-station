import type { Point2D, SetupDetectResponse } from "../api/types";

export function formatPoint(point: Point2D | null): string {
  if (point === null) {
    return "N/A";
  }
  return `${point.x.toFixed(1)}, ${point.y.toFixed(1)}`;
}

export function formatNullableNumber(value: number | null, digits = 2): string {
  if (value === null || !Number.isFinite(value)) {
    return "N/A";
  }
  return value.toFixed(digits);
}

export function detectionReason(detection: SetupDetectResponse | null): string {
  if (detection === null) {
    return "N/A";
  }
  const message = detection.diagnostics.message;
  if (typeof message === "string" && message.length > 0) {
    return message;
  }
  return detection.valid ? "N/A" : detection.status;
}
