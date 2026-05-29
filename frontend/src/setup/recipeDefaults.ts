import type {
  BalloonEnvelopeDetectorParams,
  DetectorParams,
  EnvelopeMode,
  SegmentationParams,
  TargetFamily,
} from "../api/types";

export interface SetupRecipeDefaults {
  segmentation: SegmentationParams;
  detector: DetectorParams;
}

export function balloonRecipeForEnvelopeMode(envelopeMode: EnvelopeMode): {
  segmentation: SegmentationParams;
  detector: BalloonEnvelopeDetectorParams;
} {
  if (envelopeMode === "open_mesh") {
    return {
      segmentation: {
        polarity: "dark_on_light",
        threshold_mode: "fixed",
        threshold_value: 160,
        blur_kernel: 3,
        close_kernel: 5,
        open_kernel: 3,
        min_component_area_px: 500,
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
    };
  }

  return {
    segmentation: {
      polarity: "auto",
      threshold_mode: "otsu",
      threshold_value: null,
      blur_kernel: 3,
      close_kernel: 11,
      open_kernel: 3,
      min_component_area_px: 500,
      fill_internal_holes: true,
    },
    detector: {
      detector_kind: "balloon_envelope_detector",
      envelope_mode: "solid_balloon",
      contact_source: "filled_envelope",
      measurement_model: "blank_object_blank",
      min_quality: 0.65,
      max_point_jump_px: 25,
      reject_contact_on_roi_boundary: true,
      boundary_margin_px: 4,
      ignore_internal_texture: true,
      fill_internal_holes: true,
      bridge_mesh_gaps: true,
    },
  };
}

export function recipeDefaultsForTarget(targetFamily: TargetFamily): SetupRecipeDefaults {
  if (targetFamily === "balloon_envelope") {
    return balloonRecipeForEnvelopeMode("solid_balloon");
  }
  return {
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
      detector_kind: "wire_strip_detector",
      measurement_model: "blank_object_blank_object_blank",
      measurement_mode: "outer_to_outer",
      min_quality: 0.6,
      max_point_jump_px: 20,
      reject_contact_on_roi_boundary: true,
      boundary_margin_px: 3,
      require_physical_endpoints: false,
      skeleton_endpoint_detection: false,
      preserve_visible_strip_contour: true,
    },
  };
}
