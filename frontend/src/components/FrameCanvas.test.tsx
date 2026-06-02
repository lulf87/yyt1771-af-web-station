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

  it("does not draw formal A/B if an invalid payload accidentally contains points", () => {
    const invalidDetection: SetupDetectResponse = {
      status: "caliper_contact_on_roi_boundary",
      valid: false,
      point_a: { x: 60, y: 110, coordinate_space: "acquisition" },
      point_b: { x: 160, y: 110, coordinate_space: "acquisition" },
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
        showDiagnosticsOverlay
      />,
    );

    expect(markup).toContain("selected-interval-segment");
    expect(markup).toContain("measurement-line");
    expect(markup).not.toContain("REJECTED DEBUG");
  });

  it("does not synthesize formal A/B from interval diagnostics", () => {
    const wireDetection: SetupDetectResponse = {
      status: "ok",
      valid: true,
      point_a: null,
      point_b: null,
      distance_px: null,
      quality: 0.5,
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
        showDiagnosticsOverlay
      />,
    );

    expect(markup).toContain("selected-interval-segment");
    expect(markup).not.toContain("measurement-line");
    expect(markup).not.toContain("point point-a");
    expect(markup).not.toContain("point point-b");
  });

  it("renders rejected remote wire intervals as rejected diagnostics", () => {
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
        rejected_remote_intervals: [
          { start_local_x: 120, end_local_x: 126, width_px: 6, line_y: 0 },
        ],
      },
    };

    const markup = renderToStaticMarkup(
      <FrameCanvas
        detection={wireDetection}
        frameRef={frameRef}
        previewUrl="/api/camera/frame/1/preview.png?max_width=1200"
        roi={roi}
        showDiagnosticsOverlay
      />,
    );

    expect(markup).toContain("rejected-interval-segment");
    expect(markup).toContain("measurement-line");
    expect(markup).not.toContain("REJECTED DEBUG");
  });

  it("renders top candidate lines only as diagnostics", () => {
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
        measurement_line_y: 0,
        top_candidate_lines: [
          { measurement_line_y: 0, formal_ab_span_px: 80, selected: true },
          { measurement_line_y: 10, formal_ab_span_px: 79, selected: false },
        ],
      },
    };

    const markup = renderToStaticMarkup(
      <FrameCanvas
        detection={wireDetection}
        frameRef={frameRef}
        previewUrl="/api/camera/frame/1/preview.png?max_width=1200"
        roi={roi}
        showDiagnosticsOverlay
      />,
    );

    expect(markup).toContain("candidate-line selected-candidate-line");
    expect(markup).toContain("candidate-line secondary-candidate-line");
    expect(markup).toContain("measurement-line");
  });

  it("does not draw formal A/B for ambiguous invalid detections", () => {
    const ambiguousDetection: SetupDetectResponse = {
      status: "caliper_contact_ambiguous",
      valid: false,
      point_a: null,
      point_b: null,
      distance_px: null,
      quality: 0.4,
      target_family: "wire_strip",
      detector: "wire_strip_detector:v1",
      diagnostics: {
        top_candidate_lines: [
          { measurement_line_y: -8, formal_ab_span_px: 80, selected: false },
          { measurement_line_y: 8, formal_ab_span_px: 80, selected: false },
        ],
      },
    };

    const markup = renderToStaticMarkup(
      <FrameCanvas
        detection={ambiguousDetection}
        frameRef={frameRef}
        previewUrl="/api/camera/frame/1/preview.png?max_width=1200"
        roi={roi}
        showDiagnosticsOverlay
      />,
    );

    expect(markup).toContain("caliper_contact_ambiguous");
    expect(markup).toContain("candidate-line secondary-candidate-line");
    expect(markup).not.toContain("measurement-line");
    expect(markup).not.toContain("point point-a");
    expect(markup).not.toContain("point point-b");
  });

  it("keeps interval diagnostics hidden during playback when diagnostics overlay is disabled", () => {
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
        point_a_source_interval: { start_local_x: -40, end_local_x: -34, width_px: 6, line_y: 0 },
        point_b_source_interval: { start_local_x: 34, end_local_x: 40, width_px: 6, line_y: 0 },
        selected_valid_intervals: [
          { start_local_x: -40, end_local_x: -34, width_px: 6, line_y: 0 },
          { start_local_x: 34, end_local_x: 40, width_px: 6, line_y: 0 },
        ],
        rejected_remote_intervals: [
          { start_local_x: 120, end_local_x: 126, width_px: 6, line_y: 0 },
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

    expect(markup).toContain("measurement-line");
    expect(markup).not.toContain("source-interval-segment");
    expect(markup).not.toContain("selected-interval-segment");
    expect(markup).not.toContain("rejected-interval-segment");
  });

  it("draws formal source intervals when diagnostics overlay is enabled", () => {
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
        point_a_source_interval: { start_local_x: -40, end_local_x: -34, width_px: 6, line_y: 0 },
        point_b_source_interval: { start_local_x: 34, end_local_x: 40, width_px: 6, line_y: 0 },
      },
    };

    const markup = renderToStaticMarkup(
      <FrameCanvas
        detection={wireDetection}
        frameRef={frameRef}
        previewUrl="/api/camera/frame/1/preview.png?max_width=1200"
        roi={roi}
        showDiagnosticsOverlay
      />,
    );

    expect(markup).toContain("source-interval-segment");
    expect(markup).toContain("measurement-line");
    expect(markup).not.toContain("REJECTED DEBUG");
  });

  it("renders a rotation handle for editable ROI", () => {
    const markup = renderToStaticMarkup(
      <FrameCanvas
        detection={null}
        frameRef={frameRef}
        interactive
        onRoiChange={() => undefined}
        previewUrl="/api/camera/frame/1/preview.png?max_width=1200"
        roi={roi}
      />,
    );

    expect(markup).toContain("roi-rotate-handle");
    expect(markup).toContain("roi-rotate-arm");
  });

  it("raw-only mode hides formal and diagnostic overlays while keeping the raw image", () => {
    const markup = renderToStaticMarkup(
      <FrameCanvas
        detection={detection}
        frameRef={frameRef}
        previewUrl="/api/camera/frame/1/preview.png?max_width=1200"
        rawOnly
        roi={roi}
        showDiagnosticsOverlay
      />,
    );

    expect(markup).toContain("frame-image");
    expect(markup).toContain("raw-only");
    expect(markup).not.toContain("roi-overlay");
    expect(markup).not.toContain("measurement-line");
    expect(markup).not.toContain("point point-a");
  });

  it("probe mode exposes an acquisition click layer without computing A/B", () => {
    const markup = renderToStaticMarkup(
      <FrameCanvas
        detection={detection}
        frameRef={frameRef}
        onProbePoint={() => undefined}
        previewUrl="/api/camera/frame/1/preview.png?max_width=1200"
        probeMode
        roi={roi}
      />,
    );

    expect(markup).toContain("probe-point-layer");
    expect(markup).toContain("aria-label=\"Probe point layer\"");
  });
});
