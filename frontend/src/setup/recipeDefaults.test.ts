import { describe, expect, it } from "vitest";

import { balloonRecipeForEnvelopeMode, recipeDefaultsForTarget } from "./recipeDefaults";

describe("setup recipe defaults", () => {
  it("recommends open mesh segmentation and contact source without making a new detector", () => {
    const recipe = balloonRecipeForEnvelopeMode("open_mesh");

    expect(recipe.detector.detector_kind).toBe("balloon_envelope_detector");
    expect(recipe.detector.measurement_model).toBe("blank_object_blank");
    expect(recipe.detector.envelope_mode).toBe("open_mesh");
    expect(recipe.detector.contact_source).toBe("bridged_foreground");
    expect(recipe.detector.fill_internal_holes).toBe(false);
    expect(recipe.detector.reject_contact_on_roi_boundary).toBe(true);
    expect(recipe.segmentation.polarity).toBe("dark_on_light");
    expect(recipe.segmentation.threshold_mode).toBe("fixed");
    expect(recipe.segmentation.threshold_value).toBe(160);
    expect(recipe.segmentation.fill_internal_holes).toBe(false);
  });

  it("keeps wire strip in wire bundle envelope same-line chord mode", () => {
    const recipe = recipeDefaultsForTarget("wire_strip");

    expect(recipe.detector.detector_kind).toBe("wire_strip_detector");
    if (recipe.detector.detector_kind !== "wire_strip_detector") {
      throw new Error("expected wire detector");
    }
    expect(recipe.detector.measurement_model).toBe("blank_wire_bundle_envelope_blank");
    expect(recipe.detector.measurement_mode).toBe("wire_bundle_envelope");
    expect(recipe.detector.require_physical_endpoints).toBe(false);
    expect(recipe.detector.skeleton_endpoint_detection).toBe(false);
    expect(recipe.detector.min_interval_width_px).toBe(3);
    expect(recipe.detector.min_valid_interval_count).toBe(2);
    expect(recipe.detector.min_local_contrast_score).toBe(8);
    expect(recipe.detector.max_bundle_internal_gap_px).toBe(60);
    expect(recipe.detector.max_bundle_internal_gap_ratio).toBe(1);
    expect(recipe.detector.enable_remote_interval_rejection).toBe(true);
    expect(recipe.detector.enable_local_contrast_filter).toBe(true);
    expect(recipe.detector.enable_orientation_scoring).toBe(true);
    expect(recipe.segmentation.threshold_mode).toBe("fixed");
    expect(recipe.segmentation.threshold_value).toBe(100);
  });
});
