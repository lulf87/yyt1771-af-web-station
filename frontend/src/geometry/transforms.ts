import type { Point2D, RotatedRoi } from "../api/types";

export type RoiHandle = "nw" | "n" | "ne" | "e" | "se" | "s" | "sw" | "w";

const ROTATION_HANDLE_OFFSET_PX = 32;

export interface FrameSize {
  width: number;
  height: number;
}

export interface ClientRectLike {
  left: number;
  top: number;
  width: number;
  height: number;
}

export interface ClientPointLike {
  clientX: number;
  clientY: number;
}

export interface OverlayCircle {
  cx: number;
  cy: number;
}

export interface OverlayRect {
  x: number;
  y: number;
  width: number;
  height: number;
  transform: string;
}

export function pointToOverlayCircle(point: Point2D): OverlayCircle {
  return {
    cx: point.x,
    cy: point.y,
  };
}

export function roiToOverlayRect(roi: RotatedRoi): OverlayRect {
  return {
    x: -roi.width / 2,
    y: -roi.height / 2,
    width: roi.width,
    height: roi.height,
    transform: `translate(${roi.center_x} ${roi.center_y}) rotate(${roi.angle_deg})`,
  };
}

export function clientPointToAcquisition(
  point: ClientPointLike,
  rect: ClientRectLike,
  frame: FrameSize,
): Point2D {
  const x = ((point.clientX - rect.left) / rect.width) * frame.width;
  const y = ((point.clientY - rect.top) / rect.height) * frame.height;
  return {
    x: clamp(x, 0, frame.width),
    y: clamp(y, 0, frame.height),
    coordinate_space: "acquisition",
  };
}

export function createRoiFromDrag(
  start: Point2D,
  end: Point2D,
  frame: FrameSize,
  angleDeg = 0,
): RotatedRoi {
  const x0 = clamp(Math.min(start.x, end.x), 0, frame.width);
  const x1 = clamp(Math.max(start.x, end.x), 0, frame.width);
  const y0 = clamp(Math.min(start.y, end.y), 0, frame.height);
  const y1 = clamp(Math.max(start.y, end.y), 0, frame.height);
  return clampRoiToFrame(
    {
      center_x: (x0 + x1) / 2,
      center_y: (y0 + y1) / 2,
      width: Math.max(1, x1 - x0),
      height: Math.max(1, y1 - y0),
      angle_deg: angleDeg,
      coordinate_space: "acquisition",
    },
    frame,
  );
}

export function moveRoiByDelta(
  roi: RotatedRoi,
  deltaX: number,
  deltaY: number,
  frame: FrameSize,
): RotatedRoi {
  return clampRoiToFrame(
    {
      ...roi,
      center_x: roi.center_x + deltaX,
      center_y: roi.center_y + deltaY,
      coordinate_space: "acquisition",
    },
    frame,
  );
}

export function resizeRoiFromHandle(
  roi: RotatedRoi,
  handle: RoiHandle,
  pointer: Point2D,
  frame: FrameSize,
): RotatedRoi {
  const pointerLocal = toLocalPoint(roi, pointer);
  let left = -roi.width / 2;
  let right = roi.width / 2;
  let top = -roi.height / 2;
  let bottom = roi.height / 2;

  if (handle.includes("w")) {
    left = Math.min(pointerLocal.x, right - 1);
  }
  if (handle.includes("e")) {
    right = Math.max(pointerLocal.x, left + 1);
  }
  if (handle.includes("n")) {
    top = Math.min(pointerLocal.y, bottom - 1);
  }
  if (handle.includes("s")) {
    bottom = Math.max(pointerLocal.y, top + 1);
  }

  const localCenter = {
    x: (left + right) / 2,
    y: (top + bottom) / 2,
  };
  const worldCenter = fromLocalVector(roi.angle_deg, localCenter.x, localCenter.y);
  return clampRoiToFrame(
    {
      ...roi,
      center_x: roi.center_x + worldCenter.x,
      center_y: roi.center_y + worldCenter.y,
      width: Math.max(1, right - left),
      height: Math.max(1, bottom - top),
      coordinate_space: "acquisition",
    },
    frame,
  );
}

export function roiHandlePoints(roi: RotatedRoi): Record<RoiHandle, Point2D> {
  const points: Record<RoiHandle, { x: number; y: number }> = {
    nw: { x: -roi.width / 2, y: -roi.height / 2 },
    n: { x: 0, y: -roi.height / 2 },
    ne: { x: roi.width / 2, y: -roi.height / 2 },
    e: { x: roi.width / 2, y: 0 },
    se: { x: roi.width / 2, y: roi.height / 2 },
    s: { x: 0, y: roi.height / 2 },
    sw: { x: -roi.width / 2, y: roi.height / 2 },
    w: { x: -roi.width / 2, y: 0 },
  };
  return Object.fromEntries(
    Object.entries(points).map(([key, value]) => {
      const vector = fromLocalVector(roi.angle_deg, value.x, value.y);
      return [
        key,
        {
          x: roi.center_x + vector.x,
          y: roi.center_y + vector.y,
          coordinate_space: "acquisition",
        },
      ];
    }),
  ) as Record<RoiHandle, Point2D>;
}

export function roiRotationHandlePoint(roi: RotatedRoi): Point2D {
  const vector = fromLocalVector(roi.angle_deg, 0, -roi.height / 2 - ROTATION_HANDLE_OFFSET_PX);
  return {
    x: roi.center_x + vector.x,
    y: roi.center_y + vector.y,
    coordinate_space: "acquisition",
  };
}

export function hitTestRoiHandle(
  roi: RotatedRoi,
  point: Point2D,
  tolerancePx: number,
): RoiHandle | null {
  const handles = roiHandlePoints(roi);
  const candidates = Object.entries(handles) as Array<[RoiHandle, Point2D]>;
  for (const [handle, handlePoint] of candidates) {
    if (distance(point, handlePoint) <= tolerancePx) {
      return handle;
    }
  }
  return null;
}

export function hitTestRoiRotationHandle(
  roi: RotatedRoi,
  point: Point2D,
  tolerancePx: number,
): boolean {
  return distance(point, roiRotationHandlePoint(roi)) <= tolerancePx;
}

export function rotateRoiFromPointer(
  roi: RotatedRoi,
  pointer: Point2D,
  _frame: FrameSize,
): RotatedRoi {
  const pointerAngleDeg =
    (Math.atan2(pointer.y - roi.center_y, pointer.x - roi.center_x) * 180) / Math.PI;
  return {
    ...roi,
    angle_deg: normalizeAngle(pointerAngleDeg + 90),
    coordinate_space: "acquisition",
  };
}

export function pointInsideRoi(roi: RotatedRoi, point: Point2D): boolean {
  const local = toLocalPoint(roi, point);
  return Math.abs(local.x) <= roi.width / 2 && Math.abs(local.y) <= roi.height / 2;
}

export function clampRoiToFrame(roi: RotatedRoi, frame: FrameSize): RotatedRoi {
  const width = Math.min(Math.max(1, roi.width), frame.width);
  const height = Math.min(Math.max(1, roi.height), frame.height);
  const halfWidth = width / 2;
  const halfHeight = height / 2;
  return {
    ...roi,
    center_x: clamp(roi.center_x, halfWidth, Math.max(halfWidth, frame.width - halfWidth)),
    center_y: clamp(roi.center_y, halfHeight, Math.max(halfHeight, frame.height - halfHeight)),
    width,
    height,
    coordinate_space: "acquisition",
  };
}

function toLocalPoint(roi: RotatedRoi, point: Point2D): { x: number; y: number } {
  const dx = point.x - roi.center_x;
  const dy = point.y - roi.center_y;
  const angle = (-roi.angle_deg * Math.PI) / 180;
  return {
    x: dx * Math.cos(angle) - dy * Math.sin(angle),
    y: dx * Math.sin(angle) + dy * Math.cos(angle),
  };
}

function fromLocalVector(angleDeg: number, x: number, y: number): { x: number; y: number } {
  const angle = (angleDeg * Math.PI) / 180;
  return {
    x: x * Math.cos(angle) - y * Math.sin(angle),
    y: x * Math.sin(angle) + y * Math.cos(angle),
  };
}

function distance(a: Point2D, b: Point2D): number {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

function normalizeAngle(angleDeg: number): number {
  const normalized = ((((angleDeg + 180) % 360) + 360) % 360) - 180;
  return Object.is(normalized, -0) ? 0 : Math.round(normalized * 1000) / 1000;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}
