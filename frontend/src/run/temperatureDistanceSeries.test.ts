import { describe, expect, it } from "vitest";

import type { OfflineRunFrame } from "../api/types";
import {
  appendLiveTemperatureDistanceSample,
  buildDistanceTimeLineSegments,
  buildTemperatureDistanceBins,
  buildTemperatureDistanceScatter,
  buildValidLineSegments,
  sampleFromOfflineRunFrame,
  distanceTimeDomains,
  temperatureDistanceDomains,
} from "./temperatureDistanceSeries";

function frame({
  frameIndex,
  temperatureC,
  distancePx,
  status = "ok",
  valid = true,
  quality = 0.92,
  relativeTimeS = frameIndex / 10,
}: {
  frameIndex: number;
  temperatureC: number | null;
  distancePx: number | null;
  status?: OfflineRunFrame["detection"]["status"];
  valid?: boolean;
  quality?: number;
  relativeTimeS?: number;
}): OfflineRunFrame {
  return {
    session_id: "offline_run_1",
    frame_index: frameIndex,
    frame_name: `frame-${frameIndex}.npy`,
    relative_time_s: relativeTimeS,
    acquisition_width: 320,
    acquisition_height: 220,
    display_width: 320,
    display_height: 220,
    scale_x: 1,
    scale_y: 1,
    coordinate_space: "acquisition",
    preview_url: `/preview/${frameIndex}.png`,
    end_of_stream: false,
    runtime: { temperature_c: temperatureC },
    detection: {
      status,
      valid,
      point_a: null,
      point_b: null,
      distance_px: distancePx,
      quality,
      target_family: "balloon_envelope",
      detector: "balloon_envelope_detector:v1",
      diagnostics: {},
    },
  };
}

describe("temperature distance live series", () => {
  it("builds samples only from backend live frame result fields", () => {
    const sample = sampleFromOfflineRunFrame(
      frame({ frameIndex: 7, temperatureC: 42.5, distancePx: 98.4, quality: 0.71 }),
    );

    expect(sample).toEqual({
      frameIndex: 7,
      relativeTimeS: 0.7,
      temperatureC: 42.5,
      distancePx: 98.4,
      status: "ok",
      quality: 0.71,
      valid: true,
    });
  });

  it("appends while playback is running and ignores paused/manual frames", () => {
    const first = frame({ frameIndex: 1, temperatureC: 40, distancePx: 100 });
    const paused = frame({ frameIndex: 2, temperatureC: 41, distancePx: 101 });

    const afterPlaying = appendLiveTemperatureDistanceSample([], first, {
      fromPlaybackLoop: true,
    });
    const afterPaused = appendLiveTemperatureDistanceSample(afterPlaying, paused, {
      fromPlaybackLoop: false,
    });

    expect(afterPlaying).toHaveLength(1);
    expect(afterPaused).toHaveLength(1);
    expect(afterPaused[0]?.frameIndex).toBe(1);
  });

  it("records invalid frames but breaks valid line segments around them", () => {
    const samples = [
      sampleFromOfflineRunFrame(frame({ frameIndex: 1, temperatureC: 40, distancePx: 100 })),
      sampleFromOfflineRunFrame(
        frame({
          frameIndex: 2,
          temperatureC: 41,
          distancePx: null,
          status: "target_not_found",
          valid: false,
        }),
      ),
      sampleFromOfflineRunFrame(frame({ frameIndex: 3, temperatureC: 42, distancePx: 102 })),
    ];

    const segments = buildValidLineSegments(samples);

    expect(samples[1]?.valid).toBe(false);
    expect(segments).toHaveLength(2);
    expect(segments[0].map((sample) => sample.frameIndex)).toEqual([1]);
    expect(segments[1].map((sample) => sample.frameIndex)).toEqual([3]);
  });

  it("keeps a stable minimum domain when temperature wobbles slightly", () => {
    const samples = [
      sampleFromOfflineRunFrame(frame({ frameIndex: 1, temperatureC: 40.0, distancePx: 100.0 })),
      sampleFromOfflineRunFrame(frame({ frameIndex: 2, temperatureC: 39.9, distancePx: 100.2 })),
      sampleFromOfflineRunFrame(frame({ frameIndex: 3, temperatureC: 40.1, distancePx: 99.8 })),
    ];

    const domains = temperatureDistanceDomains(samples);

    expect(domains.x.max - domains.x.min).toBeGreaterThanOrEqual(1);
    expect(domains.y.max - domains.y.min).toBeGreaterThanOrEqual(1);
    expect(domains.x.min).toBeLessThan(39.9);
    expect(domains.x.max).toBeGreaterThan(40.1);
  });

  it("builds distance-time line segments in playback order and breaks on invalid frames", () => {
    const samples = [
      sampleFromOfflineRunFrame(frame({ frameIndex: 1, temperatureC: 40, distancePx: 100 })),
      sampleFromOfflineRunFrame(frame({ frameIndex: 2, temperatureC: 40.1, distancePx: 101 })),
      sampleFromOfflineRunFrame(
        frame({
          frameIndex: 3,
          temperatureC: 40.2,
          distancePx: null,
          status: "target_not_found",
          valid: false,
        }),
      ),
      sampleFromOfflineRunFrame(frame({ frameIndex: 4, temperatureC: 40.3, distancePx: 103 })),
    ];

    const segments = buildDistanceTimeLineSegments(samples);

    expect(segments).toHaveLength(2);
    expect(segments[0].map((point) => point.xValue)).toEqual([0.1, 0.2]);
    expect(segments[0].map((point) => point.distancePx)).toEqual([100, 101]);
    expect(segments[1].map((point) => point.sample.frameIndex)).toEqual([4]);
  });

  it("builds temperature-distance bins from raw numeric temperatures and sorts them", () => {
    const samples = [
      sampleFromOfflineRunFrame(frame({ frameIndex: 1, temperatureC: 40.01, distancePx: 100 })),
      sampleFromOfflineRunFrame(frame({ frameIndex: 2, temperatureC: 40.04, distancePx: 104 })),
      sampleFromOfflineRunFrame(frame({ frameIndex: 3, temperatureC: 40.17, distancePx: 120 })),
      sampleFromOfflineRunFrame(
        frame({
          frameIndex: 4,
          temperatureC: 40.03,
          distancePx: null,
          status: "target_not_found",
          valid: false,
        }),
      ),
    ];

    const bins = buildTemperatureDistanceBins(samples, { binSizeC: 0.1 });

    expect(bins).toHaveLength(2);
    expect(bins.map((bin) => bin.temperatureCenter)).toEqual([40.05, 40.15]);
    expect(bins[0]).toMatchObject({
      count: 2,
      meanDistancePx: 102,
      medianDistancePx: 102,
      minDistancePx: 100,
      maxDistancePx: 104,
    });
    expect(bins[1]).toMatchObject({
      count: 1,
      meanDistancePx: 120,
      medianDistancePx: 120,
    });
  });

  it("separates raw temperature-distance scatter from invalid samples", () => {
    const samples = [
      sampleFromOfflineRunFrame(frame({ frameIndex: 1, temperatureC: 40.01, distancePx: 100 })),
      sampleFromOfflineRunFrame(
        frame({
          frameIndex: 2,
          temperatureC: 40.02,
          distancePx: null,
          status: "target_not_found",
          valid: false,
        }),
      ),
      sampleFromOfflineRunFrame(frame({ frameIndex: 3, temperatureC: null, distancePx: 103 })),
    ];

    const scatter = buildTemperatureDistanceScatter(samples);

    expect(scatter.valid).toHaveLength(1);
    expect(scatter.valid[0]?.temperatureC).toBe(40.01);
    expect(scatter.invalid.map((sample) => sample.frameIndex)).toEqual([2, 3]);
  });

  it("computes separate domains for distance-time and temperature-distance views", () => {
    const samples = [
      sampleFromOfflineRunFrame(frame({ frameIndex: 1, temperatureC: 40.01, distancePx: 100 })),
      sampleFromOfflineRunFrame(frame({ frameIndex: 2, temperatureC: 40.17, distancePx: 120 })),
    ];
    const bins = buildTemperatureDistanceBins(samples, { binSizeC: 0.1 });

    const timeDomains = distanceTimeDomains(samples);
    const temperatureDomains = temperatureDistanceDomains(samples, bins);

    expect(timeDomains.x.min).toBeLessThan(0.1);
    expect(timeDomains.x.max).toBeGreaterThan(0.2);
    expect(temperatureDomains.x.min).toBeLessThan(40.01);
    expect(temperatureDomains.x.max).toBeGreaterThan(40.17);
  });

  it("keeps a wider distance-time y domain so tiny distance wobble is not magnified", () => {
    const samples = [
      sampleFromOfflineRunFrame(frame({ frameIndex: 1, temperatureC: 40.01, distancePx: 140.1 })),
      sampleFromOfflineRunFrame(frame({ frameIndex: 2, temperatureC: 40.02, distancePx: 140.3 })),
    ];

    const timeDomains = distanceTimeDomains(samples);

    expect(timeDomains.y.max - timeDomains.y.min).toBeGreaterThanOrEqual(10);
  });
});
