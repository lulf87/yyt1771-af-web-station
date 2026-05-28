import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { FrameRef, RotatedRoi, SetupDetectResponse } from "../api/types";
import { FrameCanvas } from "./FrameCanvas";

const frameRef: FrameRef = {
  frame_id: 1,
  timestamp_ms: 1000,
  width: 320,
  height: 220,
  coordinate_space: "acquisition",
};

const roi: RotatedRoi = {
  center_x: 110,
  center_y: 110,
  width: 130,
  height: 80,
  angle_deg: 0,
  coordinate_space: "acquisition",
};

const detection: SetupDetectResponse = {
  status: "ok",
  valid: true,
  point_a: { x: 60, y: 110, coordinate_space: "acquisition" },
  point_b: { x: 160, y: 110, coordinate_space: "acquisition" },
  distance_px: 100,
  quality: 0.9,
  target_family: "balloon_envelope",
  detector: "balloon_envelope_detector:v1",
  diagnostics: {},
};

describe("FrameCanvas", () => {
  it("renders backend sample overlay points without computing A/B in the frontend", () => {
    const markup = renderToStaticMarkup(
      <FrameCanvas
        detection={detection}
        frameRef={frameRef}
        previewUrl="/api/camera/frame/1/preview.png?max_width=1200"
        roi={roi}
      />,
    );

    expect(markup).toContain('viewBox="0 0 320 220"');
    expect(markup).toContain('x1="60"');
    expect(markup).toContain('x2="160"');
    expect(markup).toContain('cy="110"');
  });
});
