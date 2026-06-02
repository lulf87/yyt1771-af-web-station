import { describe, expect, it } from "vitest";

import type { Point2D, RotatedRoi } from "../api/types";
import {
  clientPointToAcquisition,
  createRoiFromDrag,
  moveRoiByDelta,
  pointToOverlayCircle,
  resizeRoiFromHandle,
  rotateRoiFromPointer,
  roiHandlePoints,
  roiToOverlayRect,
} from "./transforms";

describe("setup overlay transforms", () => {
  it("keeps backend A/B points in acquisition coordinates for the SVG viewBox", () => {
    const point: Point2D = { x: 42.5, y: 18.25, coordinate_space: "acquisition" };

    expect(pointToOverlayCircle(point)).toEqual({ cx: 42.5, cy: 18.25 });
  });

  it("renders a rotated ROI from its acquisition center and angle", () => {
    const roi: RotatedRoi = {
      center_x: 100,
      center_y: 80,
      width: 40,
      height: 20,
      angle_deg: 12,
      coordinate_space: "acquisition",
    };

    expect(roiToOverlayRect(roi)).toEqual({
      x: -20,
      y: -10,
      width: 40,
      height: 20,
      transform: "translate(100 80) rotate(12)",
    });
  });

  it("maps browser client coordinates into acquisition coordinates", () => {
    const point = clientPointToAcquisition(
      { clientX: 350, clientY: 180 },
      { left: 50, top: 30, width: 600, height: 300 },
      { width: 1200, height: 600 },
    );

    expect(point).toEqual({ x: 600, y: 300, coordinate_space: "acquisition" });
  });

  it("creates an acquisition ROI from a drag gesture", () => {
    const roi = createRoiFromDrag(
      { x: 100, y: 80, coordinate_space: "acquisition" },
      { x: 240, y: 160, coordinate_space: "acquisition" },
      { width: 320, height: 220 },
      12,
    );

    expect(roi).toEqual({
      center_x: 170,
      center_y: 120,
      width: 140,
      height: 80,
      angle_deg: 12,
      coordinate_space: "acquisition",
    });
  });

  it("moves and clamps ROI coordinates in acquisition space", () => {
    const roi: RotatedRoi = {
      center_x: 300,
      center_y: 200,
      width: 80,
      height: 40,
      angle_deg: 0,
      coordinate_space: "acquisition",
    };

    expect(moveRoiByDelta(roi, 80, -40, { width: 320, height: 220 })).toEqual({
      ...roi,
      center_x: 280,
      center_y: 160,
    });
  });

  it("resizes a rotated ROI from backend acquisition handles", () => {
    const roi: RotatedRoi = {
      center_x: 100,
      center_y: 100,
      width: 80,
      height: 40,
      angle_deg: 0,
      coordinate_space: "acquisition",
    };
    const handles = roiHandlePoints(roi);

    expect(handles.e.x).toBe(140);
    const resized = resizeRoiFromHandle(
      roi,
      "e",
      { x: 170, y: 100, coordinate_space: "acquisition" },
      { width: 320, height: 220 },
    );

    expect(resized.center_x).toBe(115);
    expect(resized.width).toBe(110);
    expect(resized.height).toBe(40);
    expect(resized.coordinate_space).toBe("acquisition");
  });

  it("rotates ROI from a pointer around its acquisition center", () => {
    const roi: RotatedRoi = {
      center_x: 100,
      center_y: 100,
      width: 80,
      height: 40,
      angle_deg: 0,
      coordinate_space: "acquisition",
    };

    const rotated = rotateRoiFromPointer(
      roi,
      { x: 160, y: 100, coordinate_space: "acquisition" },
      { width: 320, height: 220 },
    );

    expect(rotated).toEqual({
      ...roi,
      angle_deg: 90,
      coordinate_space: "acquisition",
    });
  });
});
