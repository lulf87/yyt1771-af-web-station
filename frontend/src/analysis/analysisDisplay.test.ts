import { describe, expect, it } from "vitest";

import type { AnalysisResponse } from "../api/types";
import { af95Label, analysisSummaryRows } from "./analysisDisplay";

const okAnalysis: AnalysisResponse = {
  method: "af95_v1",
  status: "ok",
  curve: [
    {
      sample_index: 0,
      timestamp_ms: 0,
      temperature_c: 0,
      distance_px: 100,
      recovered_fraction: 0,
    },
  ],
  result: {
    min_distance_px: 0,
    max_distance_px: 100,
    initial_distance_px: 100,
    final_distance_px: 0,
    recovered_fraction: 1,
    valid_sample_count: 5,
    invalid_sample_count: 1,
    temperature_range: [0, 40],
    af95_temperature_c: 35,
  },
  diagnostics: {},
};

describe("analysis display", () => {
  it("formats backend Af-95 result without recalculating it", () => {
    expect(af95Label(okAnalysis)).toBe("35.0 C");
    expect(analysisSummaryRows(okAnalysis)).toContainEqual({
      label: "Invalid samples",
      value: "1",
    });
  });

  it("keeps failure status visible when analysis has no result", () => {
    const failed: AnalysisResponse = {
      method: "af95_v1",
      status: "insufficient_data",
      curve: [],
      result: null,
      diagnostics: { reason: "Need at least 3 valid temperature-distance samples." },
    };

    expect(af95Label(failed)).toBe("-");
    expect(analysisSummaryRows(failed)).toContainEqual({
      label: "Status",
      value: "insufficient_data",
    });
  });
});
