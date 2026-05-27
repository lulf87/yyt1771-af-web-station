import type { Point2D, RotatedRoi } from "../api/types";

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
