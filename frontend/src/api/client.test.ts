import { afterEach, describe, expect, it, vi } from "vitest";

import type { RunStartRequest, SetupDetectRequest } from "./types";
import {
  detectSetupFrame,
  downloadRunExport,
  getTemperatureStatus,
  setTemperatureOutput,
  setTemperaturePower,
  setTemperatureTarget,
  startRun,
} from "./client";

describe("setup API client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("posts the acquisition ROI without adding formal A/B points", async () => {
    const responsePayload = {
      status: "ok",
      valid: true,
      point_a: { x: 1, y: 2, coordinate_space: "acquisition" },
      point_b: { x: 3, y: 4, coordinate_space: "acquisition" },
      distance_px: 5,
      quality: 0.9,
      target_family: "balloon_envelope",
      detector: "balloon_envelope_detector:v1",
      diagnostics: {},
    };
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => responsePayload,
    });
    vi.stubGlobal("fetch", fetchMock);

    const request: SetupDetectRequest = {
      frame_ref: {
        frame_id: 1,
        timestamp_ms: 100,
        width: 320,
        height: 220,
        coordinate_space: "acquisition",
      },
      roi: {
        center_x: 110,
        center_y: 110,
        width: 130,
        height: 80,
        angle_deg: 0,
        coordinate_space: "acquisition",
      },
      target_family: "balloon_envelope",
      recipe_name: "balloon_envelope_default",
    };

    await detectSetupFrame(request);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/setup/detect",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify(request),
      }),
    );
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).not.toHaveProperty("point_a");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).not.toHaveProperty("point_b");
  });

  it("starts a run from a measurement definition id and fixed sample rate", async () => {
    const responsePayload = {
      run_id: "run_1",
      started: true,
      sample_count: 5,
    };
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => responsePayload,
    });
    vi.stubGlobal("fetch", fetchMock);

    const request: RunStartRequest = {
      measurement_definition_id: "md_1",
      sample_hz: 10,
      sample_count: 5,
    };
    await startRun(request);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/runs/start",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify(request),
      }),
    );
  });

  it("reports backend export failures without computing export data", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      text: async () => "export failed",
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(downloadRunExport("run 1", "csv")).rejects.toThrow("export failed");

    expect(fetchMock).toHaveBeenCalledWith("/api/runs/run%201/export.csv");
  });

  it("reads temperature status from the backend API", async () => {
    const responsePayload = {
      controller_type: "mock",
      connected: true,
      status: "ok",
      timestamp_ms: 1000,
      current_temperature_c: 22.5,
      target_temperature_c: 45,
      power_percent: 10,
      output_enabled: false,
      message: null,
    };
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => responsePayload,
    });
    vi.stubGlobal("fetch", fetchMock);

    const status = await getTemperatureStatus();

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/temperature/status",
      expect.objectContaining({
        headers: expect.objectContaining({ "Content-Type": "application/json" }),
      }),
    );
    expect(status.current_temperature_c).toBe(22.5);
  });

  it("sends temperature target power and output commands to the backend", async () => {
    const responsePayload = {
      status: "ok",
      ok: true,
      message: null,
      snapshot: {
        controller_type: "mock",
        connected: true,
        status: "ok",
        timestamp_ms: 1000,
        current_temperature_c: 25,
        target_temperature_c: 45,
        power_percent: 20,
        output_enabled: true,
        message: null,
      },
    };
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => responsePayload,
    });
    vi.stubGlobal("fetch", fetchMock);

    await setTemperatureTarget(45);
    await setTemperaturePower(20);
    await setTemperatureOutput(true);

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/temperature/target",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ target_c: 45 }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/temperature/power",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ power_percent: 20 }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "/api/temperature/output",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ enabled: true }),
      }),
    );
  });
});
