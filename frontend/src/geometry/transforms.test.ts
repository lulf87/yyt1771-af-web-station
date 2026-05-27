import { describe, expect, it } from "vitest";

import type { Point2D, RotatedRoi } from "../api/types";
import { pointToOverlayCircle, roiToOverlayRect } from "./transforms";

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
});
