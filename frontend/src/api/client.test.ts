import { afterEach, describe, expect, it, vi } from "vitest";

import type { RunStartRequest, SetupConfirmRequest, SetupDetectRequest } from "./types";
import {
  confirmSetup,
  detectSetupFrame,
  downloadRunExport,
  closeOfflineRun,
  getTemperatureStatus,
  nextOfflineRun,
  openCamera,
  openOfflineRun,
  seekOfflineRun,
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

  it("posts the dev_lab profile when opening the lab camera source", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ opened: true, source_type: "hik_mvs" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await openCamera("dev_lab");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/camera/open",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ profile: "dev_lab" }),
      }),
    );
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

  it("uses session-scoped live offline run endpoints", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({}),
    });
    vi.stubGlobal("fetch", fetchMock);

    await openOfflineRun({
      measurement_definition_id: "md_1",
      frames_dir: null,
      fps: 10,
      loop: true,
      dataset_label: null,
      start_frame_index: 0,
      max_preview_width: 1200,
    });
    await nextOfflineRun("offline_run_1");
    await seekOfflineRun("offline_run_1", 12);
    await closeOfflineRun("offline_run_1");

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/offline-run/open",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          measurement_definition_id: "md_1",
          frames_dir: null,
          fps: 10,
          loop: true,
          dataset_label: null,
          start_frame_index: 0,
          max_preview_width: 1200,
        }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/offline-run/offline_run_1/next",
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "/api/offline-run/offline_run_1/seek",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ frame_index: 12 }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      "/api/offline-run/offline_run_1/close",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("posts complete detector recipe snapshot when confirming setup", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        measurement_definition_id: "md_1",
        saved: true,
        measurement_definition: {},
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const request: SetupConfirmRequest = {
      name: "open-mesh",
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
        close_kernel: 7,
        open_kernel: 1,
        min_component_area_px: 50,
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

    await confirmSetup(request);

    const posted = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(posted.detector.envelope_mode).toBe("open_mesh");
    expect(posted.detector.contact_source).toBe("bridged_foreground");
    expect(posted.segmentation.threshold_value).toBe(160);
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
