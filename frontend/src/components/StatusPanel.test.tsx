import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { SetupDetectResponse } from "../api/types";
import { StatusPanel } from "./StatusPanel";

describe("StatusPanel debug diagnostics", () => {
  it("shows same-line local A/B as formal coordinates for valid detections", () => {
    const detection: SetupDetectResponse = {
      status: "ok",
      valid: true,
      point_a: { x: 61, y: 110, coordinate_space: "acquisition" },
      point_b: { x: 159, y: 110, coordinate_space: "acquisition" },
      distance_px: 98,
      quality: 0.95,
      target_family: "balloon_envelope",
      detector: "balloon_envelope_detector:v1",
      diagnostics: {
        pattern_model: "blank_object_blank",
        detected_pattern: "blank_object_blank",
        measurement_line_y: 0,
        point_a_local: { x: -49, y: 0, coordinate_space: "roi_local" },
        point_b_local: { x: 49, y: 0, coordinate_space: "roi_local" },
        local_y_delta_px: 0,
        parallel_error_px: 0,
        chord_length_px: 98,
        object_interval_count: 1,
      },
    };

    const markup = renderToStaticMarkup(
      <StatusPanel cameraStatus={null} detection={detection} error={null} />,
    );

    expect(markup).toContain("A local x,y");
    expect(markup).toContain("-49, 0");
    expect(markup).toContain("B local x,y");
    expect(markup).toContain("49, 0");
    expect(markup).not.toContain("rejected/debug");
  });

  it("shows boundary debug diagnostics without promoting rejected candidates to formal A/B", () => {
    const detection: SetupDetectResponse = {
      status: "caliper_contact_on_roi_boundary",
      valid: false,
      point_a: null,
      point_b: null,
      distance_px: null,
      quality: 1,
      target_family: "balloon_envelope",
      detector: "balloon_envelope_detector:v1",
      diagnostics: {
        message: "Selected contour is too close to the ROI boundary.",
        selected_polarity: "auto_dark_selected",
        selected_reason: "preferred_point_dark",
        threshold_value: 196,
        pattern_model: "blank_object_blank",
        detected_pattern: "blank_object_blank",
        measurement_line_y: 0,
        point_a_local: { x: -508.4, y: 0, coordinate_space: "roi_local" },
        point_b_local: { x: 613.6, y: 0, coordinate_space: "roi_local" },
        local_y_delta_px: 0,
        parallel_error_px: 0,
        chord_length_px: 1122,
        envelope_mode: "open_mesh",
        configured_contact_source: "bridged_foreground",
        actual_contact_source_area_ratio: 0.48,
        raw_foreground_ratio: 0.36,
        bridged_foreground_ratio: 0.48,
        morphology_foreground_ratio: 0.48,
        filled_envelope_ratio: 0.62,
        foreground_area_ratio_in_roi: 0.48,
        object_interval_count: 1,
        selected_intervals: [{ start_local_x: -508.4, end_local_x: 613.6, width_px: 1122 }],
        selected_component_area_px: 676613,
        selected_component_bbox: { min_x: 643, min_y: 324, max_x: 1765, max_y: 1125 },
        candidate_component_count: 2,
        min_local_projection: -508.4,
        max_local_projection: 613.6,
        left_margin_px: 105.7,
        right_margin_px: 0.54,
        top_margin_px: 12.3,
        bottom_margin_px: 1.2,
        distance_to_left_roi_boundary_px: 105.7,
        distance_to_right_roi_boundary_px: 0.54,
        rejected_contact_side: "right",
        boundary_margin_px: 4,
        contact_source_used: "filled_envelope",
        fill_internal_holes_used: true,
        rejected_candidate_point_a: { x: 643, y: 700, coordinate_space: "acquisition" },
        rejected_candidate_point_b: { x: 1765, y: 700, coordinate_space: "acquisition" },
      },
    };

    const markup = renderToStaticMarkup(
      <StatusPanel cameraStatus={null} detection={detection} error={null} />,
    );

    expect(markup).toContain("A x,y");
    expect(markup).toContain("N/A");
    expect(markup).toContain("Debug Diagnostics");
    expect(markup).toContain("auto_dark_selected");
    expect(markup).toContain("preferred_point_dark");
    expect(markup).toContain("196");
    expect(markup).toContain("Envelope mode");
    expect(markup).toContain("Pattern model");
    expect(markup).toContain("Measurement line y");
    expect(markup).toContain("Parallel error");
    expect(markup).toContain("Chord length");
    expect(markup).toContain("Configured source");
    expect(markup).toContain("Actual source ratio");
    expect(markup).toContain("open_mesh");
    expect(markup).toContain("Raw ratio");
    expect(markup).toContain("Bridged ratio");
    expect(markup).toContain("Filled ratio");
    expect(markup).toContain("Top margin");
    expect(markup).toContain("Bottom margin");
    expect(markup).toContain("filled_envelope");
    expect(markup).toContain("0.54");
    expect(markup).toContain("right");
    expect(markup).toContain("rejected/debug");
    expect(markup).toContain("不要直接放宽边界保护");
  });
});
