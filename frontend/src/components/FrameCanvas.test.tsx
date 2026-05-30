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

  it("draws debug measurement line when diagnostics overlay is enabled", () => {
    const markup = renderToStaticMarkup(
      <FrameCanvas
        detection={{
          ...detection,
          diagnostics: { measurement_line_y: 0 },
        }}
        frameRef={frameRef}
        previewUrl="/api/camera/frame/1/preview.png?max_width=1200"
        roi={roi}
        showDiagnosticsOverlay
      />,
    );

    expect(markup).toContain("debug-measurement-line");
    expect(markup).toContain("measurement-line");
  });

  it("makes invalid detection visible without drawing fake A/B points", () => {
    const invalidDetection: SetupDetectResponse = {
      status: "caliper_contact_on_roi_boundary",
      valid: false,
      point_a: null,
      point_b: null,
      distance_px: null,
      quality: 1,
      target_family: "balloon_envelope",
      detector: "balloon_envelope_detector:v1",
      diagnostics: {},
    };

    const markup = renderToStaticMarkup(
      <FrameCanvas
        detection={invalidDetection}
        frameRef={frameRef}
        previewUrl="/api/camera/frame/1/preview.png?max_width=1200"
        roi={roi}
      />,
    );

    expect(markup).toContain("detection-invalid-banner");
    expect(markup).toContain("caliper_contact_on_roi_boundary");
    expect(markup).toContain("roi-overlay invalid");
    expect(markup).not.toContain("measurement-line");
    expect(markup).not.toContain("point point-a");
    expect(markup).not.toContain("point point-b");
  });

  it("marks rejected candidates as debug-only for invalid detections", () => {
    const invalidDetection: SetupDetectResponse = {
      status: "caliper_contact_on_roi_boundary",
      valid: false,
      point_a: null,
      point_b: null,
      distance_px: null,
      quality: 1,
      target_family: "balloon_envelope",
      detector: "balloon_envelope_detector:v1",
      diagnostics: {
        rejected_candidate_point_a: { x: 60, y: 110, coordinate_space: "acquisition" },
        rejected_candidate_point_b: { x: 160, y: 110, coordinate_space: "acquisition" },
      },
    };

    const markup = renderToStaticMarkup(
      <FrameCanvas
        detection={invalidDetection}
        frameRef={frameRef}
        previewUrl="/api/camera/frame/1/preview.png?max_width=1200"
        roi={roi}
      />,
    );

    expect(markup).toContain("rejected-debug-point");
    expect(markup).toContain("REJECTED DEBUG");
    expect(markup).not.toContain("measurement-line");
    expect(markup).not.toContain("point point-a");
    expect(markup).not.toContain("point point-b");
  });

  it("renders selected wire intervals as overlay diagnostics without computing A/B", () => {
    const wireDetection: SetupDetectResponse = {
      status: "ok",
      valid: true,
      point_a: { x: 70, y: 110, coordinate_space: "acquisition" },
      point_b: { x: 150, y: 110, coordinate_space: "acquisition" },
      distance_px: 80,
      quality: 0.9,
      target_family: "wire_strip",
      detector: "wire_strip_detector:v1",
      diagnostics: {
        selected_valid_intervals: [
          { start_local_x: -40, end_local_x: -34, width_px: 6, line_y: 0 },
          { start_local_x: 34, end_local_x: 40, width_px: 6, line_y: 0 },
        ],
      },
    };

    const markup = renderToStaticMarkup(
      <FrameCanvas
        detection={wireDetection}
        frameRef={frameRef}
        previewUrl="/api/camera/frame/1/preview.png?max_width=1200"
        roi={roi}
      />,
    );

    expect(markup).toContain("selected-interval-segment");
    expect(markup).toContain("measurement-line");
    expect(markup).not.toContain("REJECTED DEBUG");
  });
});
