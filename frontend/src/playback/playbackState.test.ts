import { describe, expect, it } from "vitest";

import { nextPlaybackIndex, previousPlaybackIndex } from "./playbackState";

describe("offline playback state helpers", () => {
  it("steps through all frames without preloading image data", () => {
    expect(nextPlaybackIndex(1, 4, [])).toBe(2);
    expect(previousPlaybackIndex(1, [])).toBe(0);
  });

  it("steps through failure-only frames", () => {
    expect(nextPlaybackIndex(1, 6, [2, 5])).toBe(2);
    expect(nextPlaybackIndex(5, 6, [2, 5])).toBe(5);
    expect(previousPlaybackIndex(5, [2, 5])).toBe(2);
  });
});
