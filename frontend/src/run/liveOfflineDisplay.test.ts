import { describe, expect, it } from "vitest";

import { formatPlaybackTime, runtimeNumber } from "./liveOfflineDisplay";

describe("liveOfflineDisplay", () => {
  it("formats playback seconds as mm:ss.s or seconds", () => {
    expect(formatPlaybackTime(12.3)).toBe("12.3s");
    expect(formatPlaybackTime(72.5)).toBe("1:12.5");
    expect(formatPlaybackTime(null)).toBe("N/A");
  });

  it("reads numeric runtime fields", () => {
    expect(runtimeNumber({ temperature_c: 45.2 }, "temperature_c")).toBe(45.2);
    expect(runtimeNumber({}, "temperature_c")).toBeNull();
  });
});
