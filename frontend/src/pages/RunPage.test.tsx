import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { MeasurementDefinition } from "../api/types";
import { RunPage } from "./RunPage";

const measurementDefinition: MeasurementDefinition = {
  measurement_definition_id: "md_live",
  name: "live",
  target_family: "balloon_envelope",
  roi: {
    center_x: 110,
    center_y: 110,
    width: 130,
    height: 80,
    angle_deg: 0,
    coordinate_space: "acquisition",
  },
  recipe_name: "balloon_envelope_default",
  segmentation: {
    polarity: "dark_on_light",
    threshold_mode: "fixed",
    threshold_value: 160,
    blur_kernel: 3,
    close_kernel: 1,
    open_kernel: 1,
    min_component_area_px: 20,
    fill_internal_holes: false,
  },
  detector: {
    detector_kind: "balloon_envelope_detector",
    envelope_mode: "open_mesh",
    contact_source: "bridged_foreground",
    measurement_model: "blank_object_blank",
    min_quality: 0.65,
    max_point_jump_px: 25,
    reject_contact_on_roi_boundary: true,
    boundary_margin_px: 4,
    ignore_internal_texture: true,
    fill_internal_holes: false,
    bridge_mesh_gaps: true,
  },
  detector_version: "v1",
  acquisition_frame_size: { width: 320, height: 220 },
  coordinate_space: "acquisition",
  created_at_ms: 1000,
};

describe("RunPage live offline mode", () => {
  it("keeps batch run and exposes live offline controls", () => {
    const markup = renderToStaticMarkup(
      <RunPage
        datasets={[]}
        datasetId=""
        measurementDefinition={measurementDefinition}
        onDatasetChange={() => {}}
      />,
    );

    expect(markup).toContain("Batch Run");
    expect(markup).toContain("Live Offline Run");
    expect(markup).toContain("Open Live Source");
    expect(markup).toContain("间距-时间实时曲线");
    expect(markup).toContain("Temperature vs Distance");
    expect(markup).toContain("Play");
    expect(markup).toContain("Step Next");
    expect(markup).toContain("Inspect current frame");
    expect(markup).toContain("Seek");
    expect(markup).toContain("Loop");
    expect(markup).not.toContain("two_strip_outer_to_outer");
    expect(markup).toContain("FPS");
    expect(markup).toContain("Close");
    expect(markup).toContain("<summary><h2>Diagnostics</h2></summary>");
    expect(markup).toContain("<summary><h2>Live Status</h2></summary>");
    expect(markup).not.toContain("run-summary");
    expect(markup).not.toContain("summary-tile");
    expect(markup).toContain("Last successful frame");
    expect(markup).toContain("Failed frame");
    expect(markup).toContain("Target fps");
    expect(markup).toContain("Segmentation ms");
    expect(markup).toContain("Connected components ms");
    expect(markup).toContain("Wire filtering ms");
    expect(markup).toContain("Line scan ms");
    expect(markup).toContain("Candidate scoring ms");
    expect(markup).toContain("Diagnostics ms");
    expect(markup).toContain("Detector total ms");
    expect(markup).toContain("Frame budget ms");
    expect(markup).toContain("Raw only");
    expect(markup).toContain("Probe point");
    expect(markup).toContain("ROI crop zoom");
  });
});
