import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { SegmentationParams } from "../api/types";
import { SegmentationControls } from "./SegmentationControls";

const segmentation: SegmentationParams = {
  polarity: "auto",
  threshold_mode: "otsu",
  threshold_value: null,
  blur_kernel: 3,
  close_kernel: 11,
  open_kernel: 3,
  min_component_area_px: 500,
  fill_internal_holes: true,
};

const detector = {
  detector_kind: "balloon_envelope_detector" as const,
  envelope_mode: "solid_balloon" as const,
  contact_source: "filled_envelope" as const,
  measurement_model: "blank_object_blank" as const,
  min_quality: 0.65,
  max_point_jump_px: 25,
  reject_contact_on_roi_boundary: true,
  boundary_margin_px: 4,
  ignore_internal_texture: true,
  fill_internal_holes: true,
  bridge_mesh_gaps: true,
};

describe("SegmentationControls", () => {
  it("renders fill holes and morphology controls", () => {
    const markup = renderToStaticMarkup(
      <SegmentationControls
        detector={detector}
        onChange={() => undefined}
        onDetectorChange={() => undefined}
        value={segmentation}
      />,
    );

    expect(markup).toContain("Fill holes");
    expect(markup).toContain("Polarity");
    expect(markup).toContain("Close kernel");
    expect(markup).toContain("Open kernel");
    expect(markup).toContain("Min area");
  });

  it("renders envelope mode and contact source controls", () => {
    const markup = renderToStaticMarkup(
      <SegmentationControls
        detector={{
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
        }}
        onChange={() => undefined}
        onDetectorChange={() => undefined}
        value={segmentation}
      />,
    );

    expect(markup).toContain("Envelope mode");
    expect(markup).toContain("open_mesh");
    expect(markup).toContain("Contact source");
    expect(markup).toContain("bridged_foreground");
  });
});
