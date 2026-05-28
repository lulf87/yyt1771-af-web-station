import { describe, expect, it } from "vitest";

import type { SetupDetectResponse } from "../api/types";
import { detectionReason, formatNullableNumber, formatPoint } from "./statusDisplay";

describe("status display formatting", () => {
  it("formats backend A/B coordinates with fixed precision", () => {
    expect(formatPoint({ x: 12.345, y: 67.891, coordinate_space: "acquisition" })).toBe(
      "12.3, 67.9",
    );
  });

  it("shows N/A for invalid detection points instead of fake coordinates", () => {
    expect(formatPoint(null)).toBe("N/A");
    expect(formatNullableNumber(null)).toBe("N/A");
  });

  it("uses diagnostics message as the result reason when present", () => {
    const detection: SetupDetectResponse = {
      status: "target_not_found",
      valid: false,
      point_a: null,
      point_b: null,
      distance_px: null,
      quality: 0.1,
      target_family: "balloon_envelope",
      detector: "balloon_envelope_detector:v1",
      diagnostics: { message: "target missing in ROI" },
    };

    expect(detectionReason(detection)).toBe("target missing in ROI");
  });
});
