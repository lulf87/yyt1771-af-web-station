import { describe, expect, it } from "vitest";

import type { RunSample } from "../api/types";
import { latestSample, sampleRows } from "./sampleDisplay";

const samples: RunSample[] = [
  {
    run_id: "run_1",
    sample_index: 0,
    timestamp_ms: 100,
    temperature_c: 12.345,
    temperature_status: "ok",
    detection: {
      status: "ok",
      valid: true,
      point_a: { x: 1, y: 2, coordinate_space: "acquisition" },
      point_b: { x: 4, y: 6, coordinate_space: "acquisition" },
      distance_px: 5,
      quality: 0.9,
      target_family: "balloon_envelope",
      detector: "balloon_envelope_detector:v1",
      diagnostics: {},
    },
  },
  {
    run_id: "run_1",
    sample_index: 1,
    timestamp_ms: 200,
    temperature_c: null,
    temperature_status: "unavailable",
    detection: {
      status: "opposing_contour_edges_missing",
      valid: false,
      point_a: null,
      point_b: null,
      distance_px: null,
      quality: 0.2,
      target_family: "wire_strip",
      detector: "wire_strip_detector:v1",
      diagnostics: { message: "Only one contour side was visible." },
    },
  },
];

describe("run sample display", () => {
  it("keeps invalid samples visible with status and null distance", () => {
    expect(sampleRows(samples)).toEqual([
      {
        index: 0,
        status: "ok",
        distance: "5.00",
        temperature: "12.3",
        temperatureStatus: "ok",
        quality: "0.90",
      },
      {
        index: 1,
        status: "opposing_contour_edges_missing",
        distance: "-",
        temperature: "-",
        temperatureStatus: "unavailable",
        quality: "0.20",
      },
    ]);
  });

  it("returns the latest sample even when it is invalid", () => {
    expect(latestSample(samples)).toBe(samples[1]);
  });
});
